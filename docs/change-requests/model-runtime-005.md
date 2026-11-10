# 변경 요청 model-runtime-005: 레지스트리로 나가는 호출을 Exposure.egress 에 선언할 방법이 없다

처리됨(deploy 0648092, 영역 55b6689): 레지스트리 egress 는 deploy 가 설치 설정에서 읽어 노출 선언에 더한다(deploy install_egress_targets).

- 영역: model-runtime
- 대상: `Exposure.egress`, `EgressTarget`(계약 `components.yaml`), deploy 의 영역 게이트웨이 구성 생성
- 상태: 헤드 결정 대기. `exposure.json` 의 `egress` 는 `["platform"]`(토큰 발급자)만 선언했다(ADR services/model-runtime 0009).

## 문제
model-runtime 은 `OPENIT_REGISTRY_URL` 의 레지스트리에서 모델 패키지를 받는다. 나가는 호출은 영역 게이트웨이의 CONNECT 터널을 지나고 `Exposure.egress` 에 선언한 상대에게만 간다(D128). 그런데
- 서비스 이름(`ServiceName`)에는 레지스트리가 없다. `platform` 은 계약상 토큰 발급자로 나가는 터널을 뜻한다(`EgressTarget` 설명).
- `ExternalEgressTarget`(호스트·포트)는 설치처 값인데 `Exposure` 는 이미지 라벨(`io.openit.exposure`)이라 빌드 때 못 박힌다. 레지스트리의 호스트는 설치처마다 다르고 다른 서버에 있을 수도 있다(`OPENIT_HOSTS_TABLE_FILE`).

그래서 레지스트리 터널이 열리지 않아 `egress_proxy` 를 쓰는 배치에서 패키지를 받지 못할 수 있다.

## 요청 (제안)
deploy 가 게이트웨이 구성을 만들 때 model-runtime 의 `OPENIT_REGISTRY_URL` 에서 호스트와 포트를 읽어 그 영역의 `egress` 에 `ExternalEgressTarget` 으로 더한다. 또는 `EgressTarget` 에 '모델 패키지 레지스트리'를 뜻하는 서비스 이름을 계약에 더한다. 어느 쪽이든 이름 표(`HostsTable`)에 있는 이름을 게이트웨이가 풀 수 있어야 한다.
