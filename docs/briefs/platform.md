# platform 브리프

공통 규칙은 [README](README.md). 맡는 일과 컴포넌트는 [design.md 2절 platform](../design.md). 기성품 구성 영역이다(코드보다 설정).

## 이미 있는 것
`deploy/compose.yaml` 의 Envoy, Keycloak, oauth2-proxy, step-ca, Prometheus·blackbox_exporter, 레지스트리(ADR 0008, 0013~0016), `./deploy bootstrap`·`ca` 명령.

## 할 일
- 설정 폴더를 `deploy/` 에서 `platform/` 으로 옮긴다(envoy, keycloak, caddy, monitoring, step-ca 설정과 pki.py). `./deploy` 는 새 경로를 읽게 고친다(design.md 5절).
- gateway(Envoy):
  - 공개 입구 TLS: 인증서 방식(IngressCertificateMode: acme-public, organization, private, ADR 0015)대로 장착.
  - 키오스크 기기 인증서 검증(mTLS, 기기 CA 신뢰 목록, DeviceAllowlist)과 `X-Forwarded-Client-Cert` 전달. 외부에서 온 같은 헤더는 지운다.
  - 경로 라우팅: 각 영역 이미지의 노출 선언(Exposure, 라벨 `io.openit.exposure`)에서 Envoy 설정을 생성한다. ExposureAudience 별로 인증 요구를 건다.
  - 나가는 호출(CONNECT 터널): Exposure.egress 에 선언한 상대만.
- identity(Keycloak): realm 설정을 파일로(가져오기). 사람 역할은 계약의 OIDC 역할 이름, 기계 클라이언트는 MachineRole(result-reader, risk-detector, inference-caller, case-reader). 접근 토큰은 RFC 9068 프로파일(계약 README 의 프로파일 표).
- identity_proxy(oauth2-proxy): admin-console 앞단 로그인.
- monitoring: 각 영역 /metrics 수집, 인증서 만료 경보(이미 있음), 서버 전체 중단 경보 수신처는 설정.
- 기기 인증서·기관 CA 종단 시험, 루트 CA 교체 명령(지금은 문서 절차만).

## 끝 조건(공통에 더해)
- 컨테이너로: 기기 인증서 있는 요청만 키오스크 경로 통과, 없는 요청 거부, XFCC 위조 헤더 제거, OIDC 토큰 없는 직원 경로 거부, 기계 토큰 역할별 허용·거부 시나리오 시험 rc=0(샌드박스, 제품 compose 에 시험용 문을 두지 않는다, D123).
