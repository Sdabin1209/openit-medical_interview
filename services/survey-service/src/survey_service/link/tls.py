"""link 의 클라이언트 TLS: 루트 인증서로 서버를 검증하고 클라이언트 인증서로 mTLS 를 한다(계약 area_mtls).

클라이언트 인증서와 개인키는 영역 게이트웨이의 인증서 에이전트(ACME, RFC 8555)가 발급·갱신해 영역 안 공유 폴더에
둔다. 그래서 파일이 바뀌면 다시 읽어야 한다(ADR 0015).
"""

import logging
import os
import ssl

log = logging.getLogger(__name__)


class ClientTls:
    """SSLContext 하나를 들고, 인증서 파일이 바뀌었으면 요청 전에 그 컨텍스트에 다시 올린다.

    왜 같은 컨텍스트에 다시 올리나: `SSLContext.load_cert_chain` 은 다시 불러도 되고(표준 라이브러리 문서) 새 연결부터
    새 인증서를 쓴다. 이미 열린 연결은 낡은 인증서로 남지만 서버는 핸드셰이크에서만 검사하므로 문제가 없다. 컨텍스트를
    바꿔 끼우면 httpx 클라이언트를 새로 만들고 열린 요청이 있는 낡은 클라이언트를 안전하게 닫는 일이 따라온다.
    왜 수정 시각으로 보나: 인증서 에이전트가 파일을 덮어쓰면 수정 시각이 바뀐다. 요청마다 stat 두 번이라 비용이 작다.
    (인증서 갱신 주기에 비해 요청이 잦으므로 따로 타이머를 두지 않는다. 측정하지 않은 선택이다.)
    """

    def __init__(self, root_certificate: str, certificate: str, private_key: str) -> None:
        self._certificate = certificate
        self._private_key = private_key
        self._seen: tuple[int, int] | None = None
        self.context = ssl.create_default_context(cafile=root_certificate)

    def _stamp(self) -> tuple[int, int]:
        return os.stat(self._certificate).st_mtime_ns, os.stat(self._private_key).st_mtime_ns

    def refresh(self) -> None:
        """파일이 바뀌었거나 처음이면 클라이언트 인증서를 올린다. 못 읽으면 앞의 것을 두고 다음 요청에서 다시 본다."""
        try:
            stamp = self._stamp()
            if stamp == self._seen:
                return
            self.context.load_cert_chain(self._certificate, self._private_key)
        except (OSError, ssl.SSLError):
            # 왜 삼키나: 에이전트가 인증서와 키를 차례로 쓰는 사이에는 짝이 맞지 않는다. 다음 요청이 다시 읽는다
            log.warning("클라이언트 인증서를 올리지 못했다. 앞의 인증서를 쓰고 다시 시도한다")
            return
        self._seen = stamp
