# 0028. 잡 스케줄러: 관리 노드의 systemd 타이머를 deploy 가 만들고, 잡 결과는 Pushgateway 로 감시에 올린다

## 상태
승인(2026-11-11, 배포 담당). D39(영역 사이 자동 연결은 저장소를 보고 일하는 멱등 잡이고 언제 돌릴지는 deploy 의 스케줄러가 정한다)를 이행한다. D111(사용자 확정 2026-10-29: 자체 스케줄러는 systemd timer 로)이 고른 방식을 따르고, ADR 0027 이 '아직 스케줄러가 없다'고 적은 것을 닫는다.

## 맥락
계약이 잡 이름(`JobName`), 영역의 선언(`JobsDeclaration` = 이미지 라벨 `io.openit.jobs`), 한 번의 결과(`JobRunResult`, 종료 코드 0·75·1)를 정했지만 잡을 언제 돌리는 것은 아무것도 하지 않았다. 매일 백업(BACKUP), 서버 밖 동기(OFFSITE_SYNC), 복구 시험(RESTORE_TEST), 실패 사례 탐지(DETECT_FAILURES), 만료 정리(PURGE_EXPIRED)가 자동으로 돌지 않았다. 필요한 것은 다섯이다: 일정, 겹치지 않음, 시간 상한, 결과 기록, 실패가 경보로 이어짐. 여러 서버 배치(ADR 0026)에서는 잡이 그 영역이 있는 서버에서 돌아야 한다.

## 결정
- **스케줄러는 관리 노드의 systemd 타이머이고 `./deploy` 가 유닛 파일을 만든다.** 잡마다 서비스(`<프로젝트>-job-<잡>.service`, `Type=oneshot`)와 타이머(`.timer`) 하나씩. `./deploy schedule render` 가 만들고(`deploy/generated/schedule/`) `./deploy schedule install` 이 systemd 폴더에 두고 타이머를 켠다(root 권한, 다시 실행해도 같다, 지금 스케줄에 없는 이 설치의 유닛만 지운다). `schedule uninstall`, `schedule list`(주기·다음 실행), `schedule status`(마지막 결과)가 있다. 프로젝트 이름이 유닛 이름에 들어가 한 서버에 설치를 둘 이상 둘 수 있다.
- **서비스는 `./deploy schedule run <잡>` 을 부른다.** 이 명령이 잡 한 번을 실행하고 결과를 기록하고 감시에 올린다(아래). 타이머가 부르든 사람이 부르든 같다.
- **어떤 잡이 있는가:** ① 상시 서비스 이미지의 라벨 `io.openit.jobs`(영역이 선언한 잡, 지금은 survey-service 의 DETECT_FAILURES·PURGE_EXPIRED) ② deploy 가 도는 잡 BACKUP·OFFSITE_SYNC·RESTORE_TEST. RESTORE 는 덮어쓰는 복구라 스케줄에 넣지 않는다(사람이 `--yes` 로 한다). 잡 이미지(`jobs/`, model-lab 의 가져오기·학습·평가·게시)는 순서가 있는 파이프라인이라 스케줄에 넣지 않는다(`./deploy job`, 설계서 6절). 영역이 deploy 의 잡 이름을 선언하거나 두 영역이 같은 잡을 선언하면 스케줄을 만들지 않는다(주인이 하나여야 한다).
- **영역의 잡은 이미지의 선언대로 실행한다.** 이미지 라벨 `io.openit.inputs`(ContainerInputs)의 `processes` 에서 그 잡의 절대 경로 argv 를 읽고(D134), 그 영역이 있는 서버의 compose 로 `docker compose run --rm --no-deps -T --entrypoint <argv[0]> <영역> <argv[1:]> --requested-at <RFC 3339>` 한다(ADR 0022). 시각은 스케줄러가 주입한다(계약 `JobRunInput.requested_at`: 잡이 시계를 스스로 읽지 않는다). `--requested-at` 이라는 인자 이름은 survey-service 가 정한 호출 모양이다(survey-service ADR 0010). 계약은 잡이 입력을 인자로 받는다고만 말하고 인자 이름은 정하지 않았다(아래 '감수하는 것'). deploy 의 잡은 같은 `./deploy` 의 명령(`backup`, `offsite-sync`, `restore-test`)을 부르고 그 명령이 서버마다 엔진을 고른다.
- **주기(근거):**

  | 잡 | 주인 | 일정 | 시간 상한 | 근거 |
  |---|---|---|---|---|
  | DETECT_FAILURES | survey-service | 900초마다 | 600초(영역 선언) | D131: 선언한 상한보다 큰 가장 작은 300초 배수. 측정하지 않았다 |
  | PURGE_EXPIRED | survey-service | 900초마다 | 600초(영역 선언) | 같음. 영역의 상한 600초는 jobs 틀 예시와 같은 값이고 측정이 아니다(survey-service ADR 0010) |
  | BACKUP | deploy | 매일 02:00(관리 노드의 지역 시각) | 86400초 | 매일은 정본(D85(5), OPEN_GAPS U31 사용자 결정 2026-11-03). 02시는 정본에 없고 환자가 쓰는 시간을 피한 선택이며 측정하지 않았다 |
  | OFFSITE_SYNC | deploy | 매일 03:00 | 86400초 | 서버 밖 사본은 일일 백업을 따른다(D88 U6). 백업이 끝난 뒤여야 해서 한 시간 뒤. 백업 시간은 측정하지 않았다. 백업이 한 시간을 넘기면 그날은 앞의 스냅샷을 옮기고 새 것은 다음 날 옮긴다(사본이 하루 늦는다) |
  | RESTORE_TEST | deploy | 매주 일요일 04:00 | 604800초 | 정본(D88 U6)은 '정기 복원 시험'이고 주기가 없다. 매주는 관행으로 고른 값이다(측정하지 않았다). 일일이 아닌 이유: 일회용 PostgreSQL 로 모든 DB 를 복구해 무겁다(측정하지 않았다) |

  D131 의 주기는 '기본 주기보다 짧지 않게'이고 D85(5) 의 옛 표준값(후보 수집 10분, 운영 피드백 1시간)은 그 잡들이 없어졌으므로 쓰지 않는다. deploy 의 잡은 선언 상한이 없어 시간 상한을 자기 주기로 둔다(다음 실행 전에 끝나야 한다. 측정하지 않았다).
- **겹치지 않는다:** (1) systemd 는 이미 활성인 `oneshot` 서비스를 다시 시작하지 않는다(타이머가 늦게 오면 건너뛴다). (2) `schedule run` 은 잡마다 `deploy/job-runs/<잡>.lock` 을 `flock` 으로 잡는다. 이미 잡혀 있으면(타이머와 사람의 실행이 겹침) 시작하지 않고 종료 코드 75 와 결과 줄(75)을 내며 기록하지 않는다. 서로 다른 잡은 겹칠 수 있다(백업 저장소는 restic 의 잠금이 맞는다. 못 얻으면 restic 종료 코드 11 → 75, ADR 0027).
- **시간 상한:** 영역의 선언 `timeout_seconds`(deploy 의 잡은 자기 주기)를 `TimeoutStartSec` 과 `schedule run` 이 모두 건다. 넘으면 프로세스 그룹에 SIGTERM, 30초 뒤 SIGKILL(compose 와 그 자식까지), 남은 일회용 컨테이너를 지우고 실패(1)로 기록한다.
- **결과:** 잡의 표준 출력 마지막 줄이 계약 `JobRunResult` 다. `schedule run` 이 그 줄을 읽어(계약 칸 밖의 키, 다른 잡 이름, 종료 코드와 다른 exit_code 는 실패로 본다) ① 표준 출력에 낸다(journald 로 가고 보관은 저널의 표준 정책) ② `deploy/job-runs/<잡>.json`(마지막 결과)과 성공이면 `<잡>.success.json`(마지막 성공)에 쓴다 ③ 감시에 올린다. 종료 코드는 잡의 것(0·75·1)이고 `SuccessExitStatus=75` 로 75 를 서비스의 실패로 세지 않는다(다음 실행에서 다시 하는 정상 경로, D130). 결과 줄이 없으면(잡이 계약을 안 지켰다) 실패(1)로 기록한다.
- **감시로의 연결:** Pushgateway(compose 의 `pushgateway`, platform 서버, backend 네트워크, 호스트 포트 없음)에 잡마다 한 그룹(`/metrics/job/openit-jobs/job_name/<잡>`)으로 지표를 올린다: `openit_job_last_exit_code`, `openit_job_last_run_timestamp_seconds`, `openit_job_last_duration_seconds`, `openit_job_period_seconds`, `openit_job_last_processed_count`, 성공일 때만 `openit_job_last_success_timestamp_seconds`. 올리는 방법은 `POST` 라 같은 이름의 지표만 바뀌어 실패해도 마지막 성공 시각이 남는다. 올리는 쪽은 `./deploy schedule run` 이 platform 서버의 엔진에서 돌리는 일회용 컨테이너(`pushgateway-client`, 같은 이미지의 busybox `wget`)이고 backend 네트워크로 닿는다. 올리지 못하면 경고만 하고 잡 결과는 바꾸지 않는다. Prometheus(`platform/monitoring/prometheus.yml` 의 `openit-jobs`, `honor_labels: true`)가 긁고 규칙이 경보를 만든다(Alertmanager 가 수신처로 보낸다, platform ADR 0005):
  - `OpenitJobFailed`: 마지막 종료 코드가 1. 서버 밖 대상이 없거나 틀려 백업이 시작하지 못한 것도 1 이라 이것이 D88 U6 의 CRIT 이다. 75(일시적)는 울리지 않는다.
  - `OpenitJobStale`: 마지막 성공이 두 주기보다 오래됨(일시적 실패가 이어지거나 스케줄러가 멈춤). 주기는 지표(`openit_job_period_seconds`)로 올려 D131 의 '주기에서' 규칙이 한 곳(deploy 의 스케줄)에서 나온다.
  - `OpenitJobNeverSucceeded`: 성공 지표가 두 주기 동안 없음(한 번도 못 성공함, 스케줄러가 설치되지 않음). 어떤 잡이 있는지는 설치에 달려 있어 deploy 가 스케줄에서 규칙을 만든다(`generated/monitoring/job-rules.yml`, Prometheus 에 읽기 전용으로 마운트, 바뀌면 Prometheus 를 다시 만든다).
  - `OpenitJobGatewayDown`: Pushgateway 를 읽지 못함.
  두 주기(2배)는 한 번 늦거나 못 도는 것을 넘기려는 선택값이고 근거가 되는 표준이 없다(측정하지 않았다).
- **여러 서버:** 영역의 잡은 `layout.server_of(영역)` 의 compose 프로젝트(`<프로젝트>-<서버>`)에서 일회용 컨테이너로 돈다. DB 와 영역 네트워크가 그 서버에 있기 때문이다. deploy 의 잡은 관리 노드가 돌고 서버마다 엔진을 부른다(ADR 0027). 타이머는 관리 노드 한 곳에만 둔다.
- **doctor** 가 스케줄이 만들어지는지, 영역 잡의 시작 명령줄이 선언에 있는지, 생성한 규칙 파일이 `promtool check rules` 를 지나는지, 이 노드에 타이머가 설치됐는지(안내만)를 본다.

## 왜
- **systemd 타이머**: D111 이 사용자 확정으로 정했다. 표준 기능이 이 요구를 그대로 갖는다: 오래된 일정은 `Persistent=true` 로 켜질 때 보충하고, 활성인 oneshot 은 겹쳐 시작하지 않고, `TimeoutStartSec`·`SuccessExitStatus` 가 있고, 출력은 저널로 간다. systemd 는 리눅스 서버의 표준 서비스 관리자이고 새 의존이 아니다(라이선스 LGPL-2.1+ 이지만 배포물에 들어가지 않는다. 우리는 유닛 파일 텍스트를 만들 뿐 링크하거나 배포하지 않는다. 실행하는 호스트 도구라 라이선스 원칙 ADR 0017 에 걸리지 않는다).
- **Pushgateway(Apache-2.0)**: Prometheus 문서가 '서비스 수준 배치 작업의 결과를 올리는 길'로 안내한다. 잡은 짧게 살다 사라져 긁을 수 없고 관리 노드는 Prometheus 의 긁기 대상이 아니다. Prometheus·Alertmanager 는 이미 구성에 있어 경보 경로를 새로 만들지 않는다. 영속(`--persistence.file`)은 쓰지 않는다: 다시 시작하면 지표가 사라지지만 다음 실행이 다시 올리고 그 사이는 `OpenitJobNeverSucceeded` 가 두 주기를 기다리므로 거짓 경보가 없다(볼륨과 root 권한을 피한다).
- **flock**: 사람이 부르는 실행과 타이머가 겹치는 것은 systemd 가 막지 못하는 유일한 경우다. `flock(2)` 는 POSIX 계열의 표준 잠금이고 프로세스가 죽으면 풀린다(잠금 파일이 남아 막지 않는다).
- **시각을 인자로 준다**: 계약 `JobRunInput` 이 정했다(같은 입력은 같은 결과, D39).

## 검토한 대안과 버리는 이유
- **cron(cronie 등):** 일정은 되지만 놓친 실행의 보충(`Persistent`), 겹침 방지, 시간 상한, 종료 코드별 처리가 모두 따로 필요하고 출력은 메일로 간다. 정본(D111)도 systemd timer 다.
- **docker 잡 스케줄러 컨테이너(ofelia(MIT), supercronic(MIT) 등):** 상시 컨테이너가 `docker.sock` 을 마운트하면 호스트 root 와 같은 권한이다(서버마다 하나씩 필요하고 읽기 전용 루트·권한 최소 원칙에 어긋난다). 여러 서버 배치에서는 관리 노드가 서버마다 엔진을 부르는 것이 이미 구조(ADR 0026)다.
- **영역 안의 백그라운드 스케줄러:** 영역이 스스로 일정을 가진다(D39·D131 위반, survey-service ADR 0010 이 이미 버렸다).
- **Airflow·Cronicle·Kubernetes CronJob 같은 오케스트레이터:** 다섯 잡에 비해 무겁다. 오케스트레이터는 ADR 0004 가 나중으로 미뤘다.
- **node_exporter 의 textfile 수집기:** 파일을 쓰는 곳이 Prometheus 가 긁는 호스트여야 한다. 관리 노드는 구성 밖이다.
- **잡 결과를 Alertmanager API 로 직접 보내기:** 실패는 알리지만 '스케줄러가 멈춰서 아무것도 안 돈다'(Stale·NeverSucceeded)를 알 수 없다. 지표는 둘 다 한다.
- **OFFSITE_SYNC 를 BACKUP 서비스의 `OnSuccess=` 로 잇기:** 시각 어림이 필요 없지만 systemd 249 이상이 필요하다(Debian 11 은 247). 고정 시각은 어느 판에서나 된다. 사본이 하루 늦을 수 있는 것을 감수했다.

## 결과
- **얻는 것:** 다섯 잡이 자동으로 돌고 같은 잡이 겹치지 않고 시간 상한이 있고 결과(JobRunResult)가 저널·파일·지표에 남고 실패와 멈춤이 Prometheus·Alertmanager 로 알려진다. 영역은 일정을 모른다(구조 규칙 4). 새 영역이 잡을 선언하면 스케줄에 자동으로 들어온다(deploy 코드를 고치지 않는다).
- **감수하는 것:**
  - 스케줄러는 관리 노드 한 곳이다. 노드가 꺼져 있으면 잡이 돌지 않는다. 일일·주간 잡은 켜질 때 한 번 보충하고(`Persistent=true`) 15분 잡은 보충하지 않는다. 멈춤은 `OpenitJobStale` 이 알린다(지표는 Pushgateway 에 남아 있어 노드가 죽어도 경보가 평가된다). 감시가 사는 platform 서버가 같이 죽으면 Watchdog 의 하트비트 끊김이 알린다(platform ADR 0005).
  - 일정의 시각은 관리 노드의 지역 시각이다(서머타임이 있으면 그 규칙을 따른다).
  - Pushgateway 의 지표는 스케줄에서 뺀 잡의 것도 남는다(`OpenitJobStale` 이 계속 울린다). 그때는 `docker compose up -d --force-recreate pushgateway` 로 비운다.
  - 잡 결과를 올리는 호출은 영역 사이 호출이 아니라 deploy 도구와 platform 의 기성품 사이이고 같은 엔진의 안쪽(internal) 네트워크로 평문 HTTP 다. 영역 사이 모든 HTTP 는 TLS(C14)이지만 이 호출이 그 예외 목록(CONVENTIONS 13절 '유일한 예외')에 드는지는 이 작업 트리에서 읽지 못해 확인하지 못했다. 헤드가 확인할 일이다.
  - `--requested-at` 은 survey-service 의 선택이고 계약이 인자 이름을 정하지 않았다. 다른 영역이 다른 이름을 쓰면 deploy 가 그것을 모른다(계약에 호출 인자 모양을 정하는 변경 요청이 필요하다).
  - 타이머의 실제 주기(15분마다 정말 도는가)와 `systemctl enable` 은 이 PC 의 systemd 에 설치하지 않아 시험하지 못했다. 생성한 유닛은 `systemd-analyze verify` 와 가짜 systemctl 로, 실행 경로는 샌드박스에서 잡을 한 번씩 트리거해 확인했다. 실제 원격(SSH) 엔진은 확인하지 못했다.
  - `tools/schedule-sandbox` 의 경보 확인은 Prometheus 의 긁기·평가 주기(각 1분)를 조건이 될 때까지 기다린다(상한 420초, 측정하지 않았다). `OpenitJobStale`·`OpenitJobNeverSucceeded` 는 두 주기를 기다릴 수 없어 `promtool test rules`(시험 시계)로만 확인했다.
- 값: 두 주기(2배), 새벽 02·03·04시, 일요일, 상한 30초(SIGTERM 뒤 SIGKILL까지), 모두 측정하지 않았다.

## 되돌리는 조건
관리 노드가 단일 실패점이어서는 안 되면(서버마다 타이머) 서버마다 `schedule render` 를 설치하고 지표 경로를 서버별로 나눈다. 계약이 호출 인자 모양을 정하면 `--requested-at` 을 그것으로 바꾼다. 오케스트레이터로 옮기면(ADR 0004) 그 도구의 표준 잡 기능으로 바꾼다. Pushgateway 의 지표가 남는 문제가 실제로 일어나면 스케줄에서 빠진 잡의 그룹을 지우는 단계를 `schedule install` 에 더한다.
