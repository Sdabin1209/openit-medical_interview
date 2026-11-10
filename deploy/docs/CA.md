# 사설 CA 운영

결정과 근거는 [ADR 0013](../../docs/adr/0013-관리-노드와-부트스트랩-순서.md), [0014](../../docs/adr/0014-인증서-수명과-자동-갱신.md), [0015](../../docs/adr/0015-신뢰-구성.md)에 있다. 이 문서는 명령과 절차만 적는다. 모든 명령은 관리 노드(`deploy` 명령이 도는 곳)에서 실행한다.

## 설정 값

`deploy/env.example`이 기본값과 뜻이다. 설치처 값은 `deploy/.env`에 키만 덮어쓴다(예시에 없는 키는 오류).

| 키 | 뜻 |
|---|---|
| `OPENIT_CA_MODE` | `self`(루트를 만든다) 또는 `institution`(기관 CA가 서명한 중간 CA) |
| `OPENIT_CA_ALLOWED_DNS`, `OPENIT_CA_ALLOWED_IPS` | 사설 CA가 발급해도 되는 이름·IP |
| `OPENIT_LEAF_LIFETIME`, `OPENIT_CA_INTERMEDIATE_LIFETIME`, `OPENIT_CA_ROOT_LIFETIME` | 수명(`168h`, `5m` 형식) |
| `OPENIT_CA_WARN_*` | `./deploy ca status`가 실패(rc=1)로 보는 남은 기간 |
| `OPENIT_INTERNAL_ACME_DIRECTORY_URL` | 서비스 사이 리프를 받는 ACME 주소 |
| `OPENIT_TRUST_BUNDLE_PATH`, `OPENIT_TRUST_EXTRA_DIR` | 신뢰 목록 파일과 추가 루트 폴더 |
| `OPENIT_PUBLIC_CERT_MODE`, `OPENIT_PUBLIC_NAMES`, `OPENIT_PUBLIC_ACME_DIRECTORY_URL`, `OPENIT_KIOSK_CLIENT_CA_FILE` | 공개 입구와 키오스크 클라이언트 인증서 |
| `OPENIT_REGISTRY_MODE`, `OPENIT_REGISTRY_ADDRESS`, `OPENIT_REGISTRY_NAMES` | 레지스트리(local 또는 external) |

## 처음 설치

- `self`: `./deploy bootstrap` 한 번이면 루트와 중간 CA를 만든다. 루트 개인 키는 `deploy/pki/root_ca.key`(암호로 잠김, 암호는 `deploy/secrets/step_ca_root_password`)에 있다. 이 두 파일을 백업하고(관리 노드 밖, 안전한 곳) 서버에 두지 않는다.
- `institution`: 
  1. `./deploy bootstrap`이 중간 CA 키와 서명 요청 `deploy/pki/pending/intermediate.csr`을 만들고 멈춘다(rc=1, 안내를 출력한다).
  2. 기관 CA에 요청을 서명받는다. 요구: CA 인증서(`basicConstraints` CA 참, `keyUsage` keyCertSign), 유효 기간이 리프 수명보다 길 것.
  3. `./deploy ca install --cert <서명된 인증서(사슬이면 이어 붙인 파일)> --root <기관 루트 인증서>`: 사슬, 키 짝, 유효 기간을 검증하고 설치한다.
  4. `./deploy bootstrap`을 다시 실행한다.

## 상태 확인

```
./deploy ca status      # 루트·중간·리프·추가 루트의 남은 기간. 기준 미만이면 rc=1
```

정기 실행 시각은 deploy의 스케줄러가 정한다. Prometheus 경보(`OpenitCertificateExpiresSoon`, `OpenitTlsProbeFailed`)는 서비스가 내놓는 인증서(리프)를 본다. 루트·중간 CA는 이 명령만 본다.

## 중간 CA 교체

사유: 만료 임박(`ca status`가 실패), 중간 CA 키 침해 의심, 정기 교체.

- `self`: `./deploy ca rotate`. 새 중간 CA를 루트 키로 만들고 검증한 뒤 이전 파일을 `deploy/pki/archive/<시각>/`에 보관하고 설치하며 step-ca를 다시 만든다. 이어서 `ca status`를 돌린다. 이미 나간 리프는 만료(기본 7일)까지 유효하고 이후 갱신되는 리프는 새 중간 CA로 서명된다. 키 침해 때는 보관본의 이전 중간 CA 키를 삭제한다.
- `institution`: `./deploy ca rotate`가 새 키와 요청을 만든다. 기관 CA에 서명받은 뒤 `./deploy ca install --cert ... --root ...`.

## 루트 교체(절차 문서, 명령 없음)

루트는 신뢰 목록을 가진 모든 기기가 새 루트를 믿어야 바꿀 수 있다. 루트 만료 `OPENIT_CA_WARN_ROOT`(기본 180일) 전에 시작한다.

1. 새 루트를 만든다. `self`: `deploy/pki/`의 `root_ca.crt`·`root_ca.key`를 보관(예: `deploy/pki/archive/old-root/`)으로 옮기고 이전 루트 인증서를 `OPENIT_TRUST_EXTRA_DIR`(`deploy/pki/trust.d/`)에 `old-root.crt`로 복사한다. `institution`은 기관이 새 루트를 정한다.
2. `./deploy bootstrap`을 실행하면 새 루트와 새 중간 CA가 만들어진다(`self`). `./deploy ca bundle`이 신뢰 목록을 새 루트와 이전 루트 둘 다 담도록 다시 만든다. 신뢰 목록의 루트는 여럿 허용된다.
3. 새 신뢰 목록(또는 새 루트)을 키오스크와 직원 PC에 배포한다(아래).
4. 이전 루트가 서명한 리프가 모두 만료될 때까지(리프 수명) 기다린 뒤 `trust.d/old-root.crt`를 지우고 `./deploy ca bundle`을 다시 실행한다.

## 루트를 키오스크와 직원 PC에 배포(도메인이 없는 설치처)

배포할 파일은 이 설치의 루트 인증서 `deploy/pki/root_ca.crt`(공개 정보다. 개인 키가 아니다)다. 신뢰 목록 전체는 `deploy/pki/trust-bundle.pem`이다.

- Windows: 루트 인증서를 "신뢰할 수 있는 루트 인증 기관"에 가져온다(그룹 정책 또는 `certutil -addstore -f Root root_ca.crt`).
- Linux: `/usr/local/share/ca-certificates/`에 `.crt`로 두고 `update-ca-certificates`.
- 키오스크의 브라우저(Chromium 계열): 운영체제 신뢰 저장소를 쓴다.
- Docker 데몬(레지스트리를 다른 서버에서 받을 때): `/etc/docker/certs.d/<레지스트리 주소>/ca.crt`에 루트를 둔다(Docker 표준 위치).

기기에 루트를 넣는 방법은 설치처의 기기 관리 체계를 따른다.

## 시험(갱신 확인)

수명을 짧게(`5m`) 두면 갱신을 눈으로 볼 수 있다. `deploy/.env`에 `OPENIT_LEAF_LIFETIME=5m`과 `OPENIT_CA_WARN_LEAF=1m`을 함께 두고 `./deploy bootstrap` 뒤 `./deploy ca status`를 반복하면 리프의 `serial`·발급 시각이 약 1분마다 바뀐다(Caddy가 ACME로 새로 받는다). 끝나면 값을 지운다.
