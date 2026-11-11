# 설치 안내서

운영자가 처음부터 따라 하는 순서다. 명령은 리포 루트에서 실행한다. 구성의 이유는 ADR 에 있고 이 문서는 절차만 적는다(서버 나누기는 [ADR 0026](../../docs/adr/0026-여러-서버-배치.md), 부트스트랩 순서는 [ADR 0013](../../docs/adr/0013-관리-노드와-부트스트랩-순서.md), 인증서는 [CA.md](CA.md)). 이 문서의 `./deploy` 명령은 `tools/checks` 시험이 실제 명령 목록과 대조한다.

## 목차

1. 준비물
2. 관리 노드 준비와 리포 가져오기
3. 설치 값 채우기
4. 기기 CA와 기관 CA
5. 배치 설정: 서버 한 대, 여러 대
6. doctor → bootstrap → status
7. 모델 패키지 게시와 활성화
8. 업데이트
9. 롤백
10. 백업과 복구(잡 스케줄러 포함)
11. 장애 확인
12. 지우기

## 1. 준비물

### 서버
| 항목 | 요건 | 근거 |
|---|---|---|
| 운영체제·권한 | 도커 엔진을 돌릴 수 있는 리눅스, 배포 계정이 `docker` 를 부를 수 있음 | Docker 문서 |
| Docker Engine | 이 리포는 28.5.1 에서 확인했다. 컨테이너의 `sysctls`, 게시 포트, 읽기 전용 루트를 쓴다 | 확인한 판만 적는다(더 낮은 판은 확인하지 않았다) |
| Docker Compose | v2.24 이상(관리 노드에서 실행되는 클라이언트). 여러 서버 배치가 `!override` 태그를 쓴다. 확인한 판은 v2.40.3 | Compose 명세의 `!override`, `!reset` |
| Docker Buildx | 관리 노드에서 이미지를 빌드한다(`docker buildx bake`). 확인한 판은 v0.29.1 | ADR 0004 |
| 서비스 서버 | GPU 필요 없음 | 설계서 6절 |
| 서빙 GPU 서버 | NVIDIA 드라이버, NVIDIA 컨테이너 툴킷, 도커에 `nvidia` 런타임 등록(`docker info` 의 Runtimes 에 `nvidia`). 기반 모델이 올라갈 VRAM(`rtx4090-24g` 는 24GB급, `gpu-12g` 는 12GB급) | 추론 엔진(vLLM) 컨테이너가 GPU 를 예약한다(compose.yaml) |
| 네트워크 | 서버가 공개 레지스트리(Docker Hub 등, 기반 이미지)에 닿거나 내부 미러를 준비. 서버 사이 포트는 `./deploy doctor` 가 계산해 알려 준다(5절) | 기반 서비스 이미지는 공식 이미지다 |

### 디스크 용량(추정이다. 측정하지 않았다)
- 서비스 서버: 영역 이미지 4개는 합쳐 190MB 안팎(이 환경 측정: survey-service 72MB, model-runtime 63MB, 화면 둘 28MB씩), 기반 이미지(Keycloak 246MB 등)를 더해 1GB 안팎을 이미지로 잡는다. 여기에 PostgreSQL·레지스트리·감시 데이터가 쌓인다. **여유 20GB 이상**을 권한다. 20GB 는 이미지 약 1GB 에 데이터 증가를 넉넉히 잡은 값이고 데이터 증가량은 측정하지 않았다.
- 서빙 GPU 서버: vLLM 이미지(수 GB, 이 환경에서 크기를 재지 못했다)와 기반 모델 가중치(Qwen3-8B 는 약 16GB, `deploy/e2e/README.md`), 모델 패키지 캐시. **여유 60GB 이상**을 권한다(위 항목들의 합에 이미지·캐시 여유를 더한 추정).
- 관리 노드: 이미지를 빌드하므로 빌드 캐시와 이미지가 쌓인다. **여유 20GB 이상**(측정하지 않았다).

### 관리 노드
`./deploy` 를 실행하는 곳이다. 서버 한 대면 그 서버다. 서버가 여럿이면 관리 노드 한 곳에서 docker context(SSH)로 다른 서버의 엔진을 다룬다. 루트 CA 개인 키, 비밀 파일(`deploy/secrets/`), `deploy/pki/` 는 관리 노드에만 있다(모두 git 제외이니 이 노드를 백업 대상으로 둔다).
필요한 것: `git`, `uv`(파이썬과 `./deploy` 의 의존을 받는다), `docker`(+ compose, buildx), SSH 클라이언트(여러 서버일 때).

## 2. 관리 노드 준비와 리포 가져오기

```
git --version
uv --version
docker version
docker compose version
docker buildx version
```

리포가 비공개이고 관리 노드가 원격 저장소에 닿지 못하면 **git bundle** 로 옮긴다(Git 표준).

```
# 리포에 닿는 PC 에서
git bundle create openit-v7.bundle --all
# 관리 노드로 파일을 옮긴 뒤(USB, scp 등) 관리 노드에서
git clone openit-v7.bundle openit-v7
cd openit-v7
```

닿으면 `git clone <리포 주소> openit-v7` 이다. 이미지는 관리 노드의 엔진에서 빌드한다.

```
./deploy build
```

## 3. 설치 값 채우기

`deploy/env.example` 이 기본값이다. 바꿀 키만 `deploy/.env`(git 제외)에 적는다(`deploy/.env` 에 `env.example` 에 없는 키가 있으면 시작하지 않는다). 비밀 값은 적지 않는다(`./deploy secrets init` 이 `deploy/secrets/` 에 만든다).

```
cp deploy/env.example deploy/.env      # 그리고 아래 키 중 바꿀 것만 남긴다
./deploy secrets init
```

| 키 | 뜻과 정하는 법 |
|---|---|
| `OPENIT_PROJECT_NAME` | compose 프로젝트 이름(컨테이너·볼륨 이름의 접두어). 한 서버에 설치를 둘 이상 두면 서로 다르게. 여러 서버면 `<이름>-<서버 이름>` 이 된다 |
| `OPENIT_LAYOUT_FILE` | 배치 설정 파일(5절). 기본 `./layout.json`, 파일이 없으면 서버 한 대 |
| `OPENIT_STAGE_ROOT` | 여러 서버일 때 서버의 엔진 호스트에 설정·비밀 파일을 올려 둘 폴더. 기본 `/var/lib/openit/stage` |
| `OPENIT_BIND_ADDRESS` | 서버 한 대일 때 입구·레지스트리가 호스트에서 듣는 주소(포트는 도커가 배정). 여러 서버면 서버 주소에 고정 게시한다 |
| `OPENIT_OIDC_ISSUER_URL` | 사람 인증 발급자 주소. `https://<입구 이름>:<OPENIT_LISTEN_PORT>/realms/openit`. 호스트는 `OPENIT_PUBLIC_NAMES` 안에 있어야 한다 |
| `OPENIT_PUBLIC_NAMES`, `OPENIT_INGRESS_CERTIFICATE_MODE` | 입구가 서비스하는 이름과 입구 인증서를 누가 서명하는가(`private` 사설 CA, `organization` 조직 발급 파일, `acme-public` 공인 CA) |
| `OPENIT_INGRESS_CERTIFICATE_FILE`, `OPENIT_INGRESS_PRIVATE_KEY_FILE` | `organization` 일 때만 |
| `OPENIT_LISTEN_PORT`, `OPENIT_SERVICE_PORT` | 입구와 영역 게이트웨이가 컨테이너 안에서 듣는 포트(1024 이상). **여러 서버에서 플랫폼 서버가 영역도 두면 둘이 달라야 한다**(doctor 가 막는다) |
| `OPENIT_CA_MODE`, `OPENIT_CA_NAME`, `OPENIT_CA_ALLOWED_DNS`, `OPENIT_CA_ALLOWED_IPS`, 수명·경보 값 | 신뢰의 뿌리(4절, [CA.md](CA.md)). 값마다 근거는 ADR 0014 |
| `OPENIT_TRUST_LIST_FILE`, `OPENIT_TRUST_EXTRA_DIR` | 신뢰 목록과 추가 루트 폴더 |
| `OPENIT_DEVICE_CA_CERTIFICATE_FILE`, `OPENIT_DEVICE_ALLOWLIST_FILE` | 키오스크 기기 인증서를 검증할 조직 PKI 루트와 기기 허용 목록(4절). 루트가 없으면 입구가 기기 경로를 열 수 없어 시작하지 않는다 |
| `OPENIT_MACHINE_TOKENS_FILE` | 기계 호출자 표(`deploy/machine-callers.json`). 병원 시스템 같은 호출자는 항목을 더한다 |
| `OPENIT_ALERT_RECEIVER_URL`, `OPENIT_ALERT_SMTP_SMARTHOST`, `OPENIT_ALERT_HEARTBEAT_INTERVAL` | 경보 수신처(https 웹훅 또는 mailto). 비우면 경보를 어디로도 보내지 않는다(doctor 가 알린다) |
| `OPENIT_REGISTRY_MODE`, `OPENIT_REGISTRY_ADDRESS`, `OPENIT_REGISTRY_NAMES` | `local` 이면 이 설치가 레지스트리를 띄운다(플랫폼 서버). `external` 이면 설치처 레지스트리 주소를 쓴다 |
| `OPENIT_MODEL_REGISTRY_REPOSITORY`, `OPENIT_MODEL_PROFILE` | 모델 패키지 저장소 이름과 GPU 크기 프로파일(`rtx4090-24g`, `gpu-12g`) |
| `OPENIT_INFERENCE_ENGINE_LOCAL`, `OPENIT_BASE_MODEL` | 이 설치가 추론 엔진(vLLM)을 띄우는가와 기반 모델. 프로파일의 기반 모델과 같아야 한다. GPU 가 없는 서버면 `false` |
| `OPENIT_VAPID_SUBJECT`, `OPENIT_PUSH_SERVICE_HOSTS`, `SURVEY_FHIR_CANONICAL_BASE_URL` | 웹 푸시 연락처·푸시 서비스 호스트, FHIR 결과의 기준 주소 |

## 4. 기기 CA와 기관 CA

- **기기 CA(키오스크):** 조직 PKI 가 키오스크 기기에 클라이언트 인증서를 발급하고, 그 루트 인증서(PEM)를 `OPENIT_DEVICE_CA_CERTIFICATE_FILE` 로 가리킨다. 기기 허용 목록(`OPENIT_DEVICE_ALLOWLIST_FILE`, 계약 DeviceAllowlist 모양의 JSON)에 기기 ID 와 일련번호를 올리고 바꾼 뒤 `./deploy up` 을 다시 한다.
- **서비스 사이 인증서(사설 CA):** `OPENIT_CA_MODE=self` 이면 `./deploy bootstrap` 이 루트 CA 를 만든다(루트 개인 키는 `deploy/pki/root_ca.key`, 관리 노드에만 둔다). 직원 PC·키오스크가 입구를 신뢰하려면 `deploy/pki/root_ca.crt` 를 배포한다.
- **기관 CA(조직이 서명한 중간 CA):** `OPENIT_CA_MODE=organization` 으로 두고

```
./deploy ca csr
./deploy ca install --cert <서명된 인증서> --root <기관 루트 인증서>
./deploy bootstrap
```

CA 상태·교체는 [CA.md](CA.md) 를 따른다(`./deploy ca status`, `./deploy ca rotate`).

## 5. 배치 설정: 서버 한 대, 여러 대

### 서버 한 대(기본)
배치 설정 파일을 두지 않는다. 관리 노드의 엔진에 전부 뜬다. 엔진은 `DOCKER_CONTEXT`/`DOCKER_HOST` 또는 현재 docker context 가 정한다(ADR 0009). **이 경우 백업 설정(`backup`)과 기기별 문진표 배치(`device_placements`)가 없다**: 백업 저장소가 뜨지 않고 `./deploy backup` 은 시작하지 않으며(서버 밖 백업 대상이 없으면 백업을 시작하지 않는다), 키오스크는 활성 문진표가 둘 이상이면 환자에게 고르게 한다. 운영 설치는 서버가 하나여도 아래 '여러 대'의 배치 설정 파일을 두고 서버 하나에 서비스 다섯을 적는다(서버 이름은 docker context 이름이 아니라 설정의 이름일 뿐이고 서버가 하나면 context 를 만들지 않는다).

### 여러 대
1. `deploy/layout.example.json` 을 `deploy/layout.json` 으로 복사해 고친다(계약 DeploymentLayout). 서비스 다섯(`platform`, `survey-service`, `model-runtime`, `admin-console`, `kiosk-frontend`)이 정확히 한 서버에 들어가야 한다. 서버 이름은 소문자·숫자·`-` 이고 그 서버의 docker context 이름이다. `backup`, `device_placements` 는 계약상 필수라 채운다(아래 '백업 칸', '기기별 기본 문진표 칸').

```
{
  "servers": [
    { "name": "service-01", "address": "192.0.2.10", "services": ["platform", "survey-service", "admin-console", "kiosk-frontend"] },
    { "name": "serving-01", "address": "192.0.2.20", "services": ["model-runtime"] }
  ],
  "device_placements": [{ "device_id": "kiosk-01", "questionnaire_id": "national-health" }],
  "backup": { "...": "layout.example.json 참고" }
}
```

#### 기기별 기본 문진표 칸(`device_placements`)
키오스크 기기(기기 인증서 주체의 CN, 예 `kiosk-01`)마다 기본 문진표 식별자를 적는다. `./deploy` 가 이것을 `deploy/generated/survey-service/device-placements.json`(계약 DevicePlacementTable)으로 쓰고 survey-service 가 `SURVEY_DEVICE_PLACEMENTS_FILE` 로 읽는다. 세션을 시작할 때 시작 코드에 문진표가 묶여 있지 않고 키오스크가 문진표를 보내지 않으면 survey-service 가 이 기기의 기본 문진표를 쓴다. 그래서 배치된 기기는 활성 문진표가 여럿이어도 환자에게 문진표를 묻지 않고, 배치가 없는 기기는 활성 문진표가 둘 이상일 때만 묻는다. 배치한 문진표에 활성 문항 세트가 없으면 세션 시작이 400 으로 막힌다(문항 세트를 먼저 올리고 활성화한다). 한 기기에 문진표를 둘 적으면 설정을 받아들이지 않는다. 값은 survey-service 가 시작할 때 읽으므로 바꾼 뒤 `./deploy up` 이 survey-service 를 다시 만든다.

#### 백업 칸(`backup`)
계약 DeployBackupConfig 의 여섯 칸이다. 파일 경로는 **관리 노드의 절대 경로**이고 권한은 0600 이어야 한다(다른 사용자가 읽으면 doctor 가 거절한다).

| 칸 | 뜻 |
|---|---|
| `repository_url` | 백업 저장소 주소 `rest:https://<이름>[:<포트>]/<저장소>`. 이름은 DNS 이름이고 사설 CA 가 발급하는 이름(`OPENIT_CA_ALLOWED_DNS`, 기본에 `backup` 이 있다)이어야 한다. 저장소 이름은 아래 자격의 사용자와 같아야 한다. 저장소는 플랫폼 서버에 뜬다 |
| `password_file` | 백업 저장소의 restic 암호 파일. **잃으면 백업을 읽을 수 없다** |
| `http_credentials_file` | 저장소 서버의 HTTP 기본 인증 자격, 한 줄 `사용자:비밀번호` |
| `encryption_key_file` | 서버 밖 저장소의 restic 암호 파일(로컬 암호와 다르다) |
| `offsite_url` | 서버 밖 저장소 주소(`https://…`, restic REST 저장소). 이 주소의 서버는 직접 준비한다 |
| `offsite_credentials_file` | 서버 밖 저장소의 HTTP 기본 인증 자격, 한 줄 `사용자:비밀번호`(서버 밖 쪽이 주는 것) |

`./deploy secrets init` 이 위 파일 중 `password_file`, `http_credentials_file`, `encryption_key_file` 이 없으면 만든다(무작위 값, 이미 있으면 건드리지 않는다). `offsite_credentials_file` 은 서버 밖 대상이 주는 것이라 직접 둔다. 서버 밖 저장소의 인증서가 공인 CA 가 아니면 그 루트를 `deploy/pki/trust.d/` 에 둔다(신뢰 목록에 들어간다). 이 칸이 틀리면 `up` 이 서비스를 띄우지 않는다.

2. 서버마다 docker context 를 만든다. 프로젝트의 격리 설정 폴더(`.docker-config`)에 만든다(`~/.docker` 를 쓰지 않는다). 배포 계정이 서버에 SSH 키로 접속되어 있어야 한다.

```
export DOCKER_CONFIG="$PWD/.docker-config"
docker context create service-01 --docker host=ssh://deploy@192.0.2.10
docker context create serving-01 --docker host=ssh://deploy@192.0.2.20
```

3. 입구와 영역의 포트를 다르게 둔다(`deploy/.env`): 예) `OPENIT_LISTEN_PORT=9443` 이고 `OPENIT_OIDC_ISSUER_URL` 의 포트도 9443 으로.
4. **서버의 엔진 호스트마다** 한 번(root 권한. 이미지를 레지스트리에서 받는 데몬이 읽는 설정이다. 플랫폼 서버가 아닌 서버에서만):

```
echo "192.0.2.10 registry" | sudo tee -a /etc/hosts
sudo install -D deploy/pki/trust-bundle.pem /etc/docker/certs.d/registry:443/ca.crt
```

(`deploy/pki/trust-bundle.pem` 은 `./deploy bootstrap` 이 만든다. 먼저 6절의 doctor 까지 하고 bootstrap 중 이미지 받기에서 막히면 이 단계를 하고 `./deploy bootstrap` 을 다시 실행한다. 멱등이다.)
5. `./deploy doctor` 가 서버 사이에 열어야 하는 포트를 '출발 -> 도착:포트' 로 알려 준다. 방화벽에서 그 방향만 연다. 플랫폼 서버가 아닌 서버의 9100(상태·지표)은 플랫폼 서버에만 열어야 한다.

## 6. doctor → bootstrap → status

```
./deploy doctor
./deploy bootstrap
./deploy status
```

- `doctor` 는 도구, 엔진(서버마다), 비밀 파일, 설정 검증, 배치(context 와 주소, 포트)를 본다. 실패 항목이 없어야 다음으로 간다(rc=0).
- `bootstrap` 은 신뢰의 뿌리 → 레지스트리(플랫폼 서버) → 이미지 올리기 → 서비스 기동(서버마다, 플랫폼 서버 먼저)이다. 이미 된 단계는 건너뛰므로 실패하면 같은 명령을 다시 실행한다. 끝에 인증서 상태가 나온다.
- `status` 는 모든 서버의 컨테이너와 health 를 본다. 정상이 아니면 rc=1.

처음 로그인할 사람 계정은 Keycloak(`realm openit`)에 만든다. 관리자 비밀번호는 관리 노드의 `deploy/secrets/keycloak_admin_password` 파일에 있다(화면에 출력하지 않는다). 역할은 `staff`, `clinician`, `author`, `release-approver` 등이다(계약 UserRole). realm 설정을 바꿨다면 `./deploy identity sync` 로 반영한다.

## 7. 모델 패키지 게시와 활성화

1. 게시: 학습한 어댑터를 평가해 보고서와 함께 레지스트리에 올린다(`package-publish`, 인자의 뜻은 [model-runtime README](../../services/model-runtime/README.md) 의 '모델 패키지 게시'). 성공하면 마지막 줄이 패키지 digest 다.

```
uv run --project services/model-runtime package-publish publish --adapter-a <LoRA-A 폴더> --adapter-b <LoRA-B 폴더> ... --report-out report.json
```

레지스트리 주소는 `https://registry`(플랫폼 서버 주소로 풀리는 이름), 루트 인증서는 `deploy/pki/trust-bundle.pem`, 자격은 `deploy/secrets/registry_credentials` 다. 평가는 엔진이 어댑터 폴더를 같은 경로로 읽을 수 있어야 하고 GPU 에서 돈다.

2. 활성화: 직원 화면(관리 콘솔, 입구의 `/console/`)의 모델 배포 화면에서 게시된 패키지의 평가 보고서를 확인하고 활성화를 승인한다(역할 `release-approver`). 승인자·시각·사유가 기록된다. model-runtime 의 적재 상태가 READY 가 되고 `/readyz` 가 200 이 되어야 문진이 간다.

## 8. 업데이트

```
git pull          # 또는 새 git bundle 을 받아 fetch
./deploy build
./deploy bootstrap
./deploy status
```

`build` 가 이미지를 다시 만들고 `deploy/images.lock` 에 digest 를 쓴다. `bootstrap` 이 새 이미지를 레지스트리에 올리고(이미 있는 digest 는 건너뜀) 서비스를 다시 띄운다(`up` 과 같다). 바뀐 설정 파일을 쓰는 서비스는 다시 만든다. 여러 서버면 서버마다 같다. 설정만 바꿨다면 `./deploy up` 이면 된다.

## 9. 롤백

- **모델 롤백:** 관리 콘솔의 모델 배포 화면에서 이전 패키지로 롤백한다(사유와 근거 사례를 남긴다). 이미지는 그대로다.
- **이미지 롤백:** 이전 커밋의 `images.lock` 으로 되돌려 그 digest 를 받아 띄운다.

```
git log --oneline -- deploy/images.lock
git checkout <이전 커밋> -- deploy/images.lock
./deploy pull
./deploy up
./deploy status
```

## 10. 백업과 복구(잡 스케줄러 포함)

백업 설정은 5절의 `backup` 칸이다(배치 설정 파일이 없으면 백업을 시작하지 않는다). 결정과 근거는 [ADR 0027](../../docs/adr/0027-백업과-복구.md) 이다.

```
./deploy backup                       # 모든 영역 데이터베이스와 상태 파일 -> 백업 저장소(스냅샷 하나), 14일 지난 스냅샷 정리
./deploy offsite-sync                 # 백업 저장소의 스냅샷 -> 서버 밖 저장소
./deploy restore-test                 # 일회용 PostgreSQL 에 복구하고 상태 파일 tar 의 SHA-256 을 대조해 되는지 시험(운영 DB·볼륨은 건드리지 않는다)
./deploy restore-test --offsite       # 서버 밖 사본으로 같은 시험
./deploy restore latest --yes         # 가장 최근 스냅샷으로 운영 DB 를 덮어쓴다
./deploy restore <스냅샷 ID> --yes
./deploy restore latest --yes --offsite   # 백업 저장소를 잃었을 때 서버 밖 사본에서(ID 는 서버 밖 저장소의 것)
```

- **무엇을 백업하나:** compose 서비스 라벨 `io.openit.backup: postgres` 인 PostgreSQL 모두와 `io.openit.backup: files` 인 서비스의 상태 파일, 각각 그것이 있는 서버에서. 지금은 platform 의 `postgres`(Keycloak 의 사용자·realm), survey-service 의 `survey-db`(문진 결과), model-runtime 의 활성화·롤백 기록(승인자·시각·사유, 활성 패키지는 이 기록에서 구한다)이다. 서버가 달라도 한 번의 `backup` 이 한 스냅샷에 담는다. 백업하는 동안 관리 노드의 `deploy/backups/` 에 덤프 크기만큼의 임시 디스크가 필요하다(끝나면 지운다).
- **무엇을 백업하지 않나:** step-ca·레지스트리·감시의 볼륨(다시 받거나 다시 올린다), model-runtime 이 받은 패키지와 기반 모델 가중치(`model-runtime-data` 의 활성화 기록 밖: 레지스트리에서 다시 받는다. 레지스트리 볼륨도 백업하지 않으므로 서버를 통째로 잃으면 모델 패키지는 학습 쪽에서 다시 게시한다), 그리고 관리 노드의 `deploy/secrets/`, `deploy/pki/`, `deploy/.env`, `deploy/layout.json`, 백업 비밀 파일 네 개. 이것들은 직접 안전한 곳에 보관한다(루트 CA 키를 잃으면 신뢰의 뿌리를 다시 만들어야 하고 백업 암호를 잃으면 백업을 읽을 수 없다).
- **일정:** 각 명령은 잡 한 번이다(끝에 표준 출력으로 한 줄 JSON, 종료 코드 0 성공·75 일시적 실패(다음 실행에서 다시)·1 실패). 자동으로 도는 일정은 deploy 의 스케줄러가 정한다(아래 '잡 스케줄러', D39): 백업 매일 02:00, 서버 밖 동기 매일 03:00, 복구 시험 매주 일요일 04:00(서버 밖 사본은 `./deploy restore-test --offsite` 로 사람이 따로 시험한다).
- **보관:** 14일(`forget --keep-within 14d`, 운영 데이터의 가장 짧은 보존 30일 이하). 서버 밖 저장소에도 같은 정리를 한다.
- **복구 절차:** `restore` 는 스냅샷에 있는 데이터베이스를 지우고 다시 만들고(상태 파일은 백업한 경로를 비우고 되돌리고), 그것을 쓰는 서비스는 멈췄다가 다시 띄운다. model-runtime 은 복구한 기록의 마지막 활성 패키지를 레지스트리에서 받아 다시 적재한다. 서버를 처음부터 다시 세웠다면 먼저 `./deploy bootstrap` 으로 빈 상태를 세운 뒤(저장소가 비어 있으면 `--offsite` 로) `restore` 한다. 이전 형식(`deploy/backups/postgres-<시각>/` 폴더)의 백업은 새 `restore` 가 읽지 않는다.
- `./deploy down --volumes` 는 백업 저장소의 볼륨도 지운다(서버 밖 사본은 남는다).

### 잡 스케줄러

잡(백업, 서버 밖 동기, 복구 시험, 영역이 선언한 DETECT_FAILURES·PURGE_EXPIRED)은 관리 노드의 systemd 타이머가 돌린다. 일정·근거·값은 [ADR 0028](../../docs/adr/0028-잡-스케줄러는-systemd-타이머.md) 이다. 설치하지 않으면 잡이 자동으로 돌지 않는다(`./deploy doctor` 가 설치 여부를 알린다).

```
./deploy schedule list                  # 잡마다 주인, 도는 서버, 주기와 근거, 시간 상한, 다음 실행
./deploy schedule render                # 유닛 파일을 deploy/generated/schedule/ 에 만든다(설치하지 않는다)
./deploy schedule status                # 잡마다 마지막 결과. 실패(1)이거나 두 주기 넘게 성공이 없으면 rc=1
./deploy schedule run BACKUP            # 잡 하나를 타이머가 부르는 것과 같게 한 번 실행한다(결과 기록·감시 포함)
./deploy schedule install               # 유닛을 /etc/systemd/system 에 두고 타이머를 켠다(root 권한 필요)
./deploy schedule uninstall             # 이 설치의 잡 타이머를 끄고 지운다
```

- **설치(root):** `sudo env "PATH=$PATH" ./deploy schedule install --user "$USER"`. `--user` 는 잡을 실행할 사용자이고 docker 를 쓸 수 있어야 한다(8절의 배포 계정). 다시 실행해도 같고, 지금 스케줄에 없는 이 설치의 잡 유닛만 지운다. 새 영역 이미지를 만들어 잡 선언이 바뀌면 `./deploy build` 뒤에 다시 설치한다.
- **어디서 도나:** 타이머는 관리 노드 한 곳에만 둔다. 영역의 잡은 그 영역이 있는 서버의 엔진에서 일회용 컨테이너로 돌고(배치 설정이 정한다) deploy 의 잡은 서버마다 엔진을 부른다. 관리 노드가 꺼져 있으면 잡이 돌지 않는다(일일·주간 잡은 켜질 때 한 번 보충한다).
- **결과:** 잡의 표준 출력(JobRunResult 한 줄)은 저널에 남는다: `journalctl -u <프로젝트>-job-backup.service`. 마지막 결과는 `deploy/job-runs/<잡>.json`. 같은 잡이 이미 돌고 있으면 새로 시작하지 않는다(종료 코드 75).
- **경보:** 잡의 마지막 실행이 실패(1)면 `OpenitJobFailed`, 마지막 성공이 두 주기보다 오래되면 `OpenitJobStale`, 한 번도 성공하지 못하면 `OpenitJobNeverSucceeded`, 결과를 받는 Pushgateway 를 읽지 못하면 `OpenitJobGatewayDown` 이 `OPENIT_ALERT_RECEIVER_URL` 의 수신처로 간다. 서버 밖 백업 설정이 틀려 백업이 시작하지 못하면 `OpenitJobFailed(BACKUP)` 다(D88 U6).
- 스케줄에서 뺀 잡의 지표는 Pushgateway 에 남아 `OpenitJobStale` 이 울린다. `docker compose up -d --force-recreate pushgateway`(서버 프로젝트 안) 로 비운다.

## 11. 장애 확인

```
./deploy status                  # 서버마다 컨테이너·health, 배정됐는데 없는 서비스, 서버에 닿지 못함
./deploy ca status               # 인증서 남은 기간(기준 미만이면 rc=1)
./deploy doctor                  # 설정·도구·포트
```

컨테이너 로그는 서버의 context 로 본다(여러 서버일 때는 서버 이름이 context 이름이고 프로젝트 이름은 `<OPENIT_PROJECT_NAME>-<서버 이름>`).

```
export DOCKER_CONFIG="$PWD/.docker-config"
docker --context serving-01 ps --filter label=com.docker.compose.project=openit-serving-01
docker --context serving-01 logs --tail 100 openit-serving-01-model-runtime-gateway-1
```

흔한 경우: 영역 게이트웨이가 unhealthy 면 사설 CA(`step-ca:9000`)에 닿는지(서버 사이 포트. 이름 풀이는 deploy 가 compose 의 `extra_hosts` 로 만든다) 본다. model-runtime 의 `/readyz` 503 은 추론 엔진이 준비되지 않았거나 활성 패키지가 없을 때다. 여러 서버에서 이미지를 받지 못하면 5절 4번(레지스트리 이름과 신뢰)을 확인한다.

## 12. 지우기

```
./deploy down                          # 컨테이너만(볼륨·데이터 유지)
./deploy down --volumes --yes          # 데이터베이스·인증서 저장소 볼륨과 서버에 올린 파일까지(되돌릴 수 없다)
```

관리 노드에 남은 상태는 직접 지운다: `deploy/secrets/`, `deploy/pki/`, `deploy/generated/`, `deploy/.env`, `deploy/layout.json`, `deploy/backups/`, `.docker-config/`(docker context 포함). 이미지는 `docker --context <서버> image prune` 등 도커 표준 명령으로 지운다.
