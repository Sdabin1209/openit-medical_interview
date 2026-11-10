"""인사말 컴포넌트(템플릿 예시). 자기 입력(GreetingRequest)과 출력(Greeting)과 할 일만 안다."""

from __PKG__.types import Greeting, GreetingRequest


def greet(request: GreetingRequest) -> Greeting:
    """요청한 이름으로 인사말을 만든다."""
    return Greeting(message=f"안녕하세요, {request.name}님")
