# 화면이 응답마다 붙이는 보안 헤더. location 마다 add_header 가 있으면 서버 수준 헤더가 사라지므로 각 location 이 이 파일을 include 한다.
# CSP(W3C Content Security Policy 3): 연결(connect-src)을 같은 출처로 막아 환자 발화와 답이 이 화면을 연 서버 밖으로 나가지 못하게 한다(UD-12).
# style-src 의 'unsafe-inline': Radix UI(react-remove-scroll)가 스타일 요소를 넣는다. script-src 는 같은 출처만 허용한다.
# 한계: 브라우저 내장 음성 인식이 소리를 보내는지는 CSP 가 막지 못한다. 그래서 processLocally 확인을 따로 한다(src/components/speech).
add_header Content-Security-Policy "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; media-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
