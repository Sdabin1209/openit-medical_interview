# platform-001: PlatformEnv 에 없는 설치 값

처리됨(계약 9.0.0(5f3c616, 848dbcb), platform a56d244): PlatformEnv 에 선택 입력 6개를 더했다.

상태: 요청(헤드 검토 전). 대상 계약: `contracts/components.yaml` 의 `PlatformEnv`(태그 `contracts-v7.0.0`).

## 문제

platform 이 입구·인증서·감시를 구성하는 데 필요한 값 중 `PlatformEnv` 에 없는 것이 있다. 지금은 `deploy/env.example` 의 설치 값으로 두었다(계약 이름을 쓰는 값은 그 이름 그대로 둠).

| 설치 값(deploy/env.example) | 쓰는 컴포넌트 | 왜 필요한가 | 계약에 없어서 생기는 일 |
|---|---|---|---|
| `OPENIT_PUBLIC_NAMES` | gateway, ca | 입구 인증서의 이름(SAN)과 입구가 서비스하는 이름. `OidcIssuerUrl` 의 호스트가 그 안에 있어야 한다 | 이름이 계약 밖이라 deploy 가 영역 이미지에 줄 수 없다(영역은 이 값이 필요 없다. platform 안의 값) |
| `OPENIT_INGRESS_CERTIFICATE_FILE`, `OPENIT_INGRESS_PRIVATE_KEY_FILE` | gateway | `IngressCertificateMode.organization` 은 "조직이 발급한 인증서를 쓴다"인데 그 인증서와 키의 위치를 받을 입력이 없다 | 방식 이름만 있고 값을 줄 길이 없다 |
| `OPENIT_SERVICE_PORT` | gateway, monitoring | 입구가 영역 서비스(`https://<서비스 이름>`)에 접속하는 포트. 계약의 `OPENIT_LISTEN_PORT` 는 서비스마다 deploy 가 주는 값이라 입구가 모른다 | 포트를 platform 이 알 길이 없다. 지금은 모든 서비스가 같은 포트를 쓴다고 가정한다 |
| `OPENIT_ALERT_SMTP_SMARTHOST` | monitoring | `AlertReceiverUrl` 이 `mailto:` 이면 메일을 내보낼 SMTP 서버가 필요하다 | mailto 수신처를 설정해도 보낼 수 없다 |
| `OPENIT_ALERT_HEARTBEAT_INTERVAL` | monitoring | 서버 전체가 멈췄음을 수신처가 알아차리려면 생존 신호(Watchdog 경보)를 일정 간격으로 받아야 한다(D10) | 간격이 platform 안의 선택값이다 |

## 제안

1. `PlatformEnv` 에 위 값을 더한다(`OPENIT_PUBLIC_NAMES` 는 `HostName` 배열, 인증서·키 파일은 `ConfigFilePath`·`SecretFilePath`, 포트는 `ListenPort`, SMTP 는 `HostAddress:포트`).
2. 또는 이 값들이 platform 영역 안의 값이므로(영역 사이 값이 아님) 계약에 두지 않고 platform 의 환경 입력 스키마를 영역이 소유한다고 정한다. 이 경우 `PlatformEnv` 의 소유(`x-owner: platform`)와 deploy 가 넘기는 입력의 정의 위치(D133)를 헤드가 정리해 달라.

## platform 쪽 임시 처리

값은 `deploy/env.example` 에 두고 `platform/src/openit_platform/settings.py` 가 검증한다(값마다 근거 주석). 계약 변경이 정해지면 이름을 맞춘다.
