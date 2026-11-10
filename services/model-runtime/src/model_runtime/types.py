"""영역 안 컴포넌트 사이를 오가는 값과 포트(ADR 0003). 칸마다 description 과 제약을 둔다.

포트(Protocol)는 컴포넌트가 영역 밖(레지스트리, 추론 엔진)이나 저장소를 쓰는 길이다. 컴포넌트는 포트만 알고
구현은 `link/`(통신)와 `store/`(저장)가 맡는다. 그래서 컴포넌트는 통신 라이브러리를 import 하지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from model_runtime.contract.models import (
    ModelIoVersion,
    ModelLoadState,
    ModelPackageManifest,
    ProblemReason,
    ServingConfig,
)


class ServiceFault(Exception):
    """작업이 계약의 오류 응답으로 끝나는 까닭. link_api 가 ProblemDetails 로 바꾼다. detail 에 환자 발화와 비밀을
    넣지 않는다."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        reason: ProblemReason | None = None,
        retry_after: int | None = None,
        headers: Mapping[str, str] | None = None,
        errors: Sequence[Mapping[str, str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.reason = reason
        self.retry_after = retry_after
        self.headers = dict(headers or {})  # 응답에 더할 머리글(401 의 WWW-Authenticate)
        self.errors = [dict(item) for item in errors or []]  # 요청 본문에서 어긋난 칸들(400 일 때만)


class PackageNotFoundError(Exception):
    """레지스트리에 그 digest 의 패키지(또는 파일)가 없다."""


class PackageInvalidError(Exception):
    """받은 패키지가 계약과 다르다(PACKAGE_INVALID). 메시지에 어느 조건을 어겼는지만 쓴다."""


class RegistryUnavailableError(Exception):
    """레지스트리에 닿지 못했거나 인증이 거절되었다."""


class EngineError(Exception):
    """추론 엔진이 요청을 처리하지 못했다(연결 실패, 오류 응답, 빈 답)."""


@dataclass(frozen=True)
class RawManifest:
    """레지스트리에서 받은 OCI 매니페스트의 원래 바이트와 digest 를 요청한 값."""

    digest: str
    content: bytes


class PackageSource(Protocol):
    """레지스트리에서 모델 패키지를 digest 로 받는 길(OCI Distribution, link_registry 가 구현)."""

    async def fetch_manifest(self, digest: str) -> RawManifest:
        """매니페스트를 받는다. 없으면 PackageNotFoundError, 닿지 못하면 RegistryUnavailableError."""
        ...

    async def download_blob(self, digest: str, destination: Path) -> None:
        """파일(config 또는 layer)을 destination 에 받는다. 내용 검증은 받는 컴포넌트가 한다."""
        ...


class AdapterRegistry(Protocol):
    """추론 엔진에 어댑터를 올리고 내리는 길(link 가 구현)."""

    async def load_adapter(self, name: str, path: Path) -> None:
        """어댑터 폴더를 name 으로 올린다. 못 올리면 EngineError."""
        ...

    async def unload_adapter(self, name: str) -> None:
        """name 의 어댑터를 내린다. 없는 이름이면 무시한다."""
        ...


@dataclass(frozen=True)
class ChatRequest:
    """추론 엔진에 보내는 채팅 요청 하나. 모델 입력 글자(user)는 학습 데이터와 글자 단위로 같다."""

    adapter: str  # 엔진에 올린 어댑터 이름(OpenAI 호환 API 의 model)
    system: str
    user: str
    max_new_tokens: int
    temperature: float
    json_schema: Mapping[str, object] | None = None  # 제약 디코딩을 켰을 때만. 출력이 따를 JSON Schema


class ChatEngine(Protocol):
    """추론 엔진의 OpenAI 호환 채팅 완성 호출(link 가 구현)."""

    async def complete(self, request: ChatRequest) -> str:
        """모델이 낸 글자를 돌려준다. 실패하면 EngineError."""
        ...


class AdapterRole(StrEnum):
    """어댑터 역할의 영역 안 이름(계약 AdapterRole 과 같은 값)."""

    LORA_A = "LORA_A"
    LORA_B = "LORA_B"


@dataclass(frozen=True)
class LoadedAdapter:
    """엔진에 올린 어댑터 하나와 그 짝."""

    name: str  # 엔진에 올린 이름
    system_prompt: str
    serving: ServingConfig


@dataclass(frozen=True)
class LoadedPackage:
    """적재를 마친 모델 패키지. 추론은 이 값만 본다."""

    digest: str
    manifest: ModelPackageManifest
    adapters: Mapping[AdapterRole, LoadedAdapter]
    loaded_at: datetime

    @property
    def runtime_contract_version(self) -> int:
        """이 패키지가 학습한 문항 은행 버전."""
        return self.manifest.runtime_contract_version.root

    @property
    def model_io_version(self) -> ModelIoVersion:
        """이 패키지가 학습한 모델 입출력 버전."""
        return self.manifest.model_io_version


class ReleaseEventKind(StrEnum):
    """활성화·롤백 기록 한 줄의 종류."""

    ACTIVATE_REQUESTED = "ACTIVATE_REQUESTED"
    ROLLBACK_REQUESTED = "ROLLBACK_REQUESTED"
    LOADED = "LOADED"
    LOAD_FAILED = "LOAD_FAILED"


@dataclass(frozen=True)
class ReleaseEvent:
    """활성화·롤백 기록 한 줄(승인자, 시각, 사유). 지우거나 고치지 않고 덧붙이기만 한다."""

    kind: ReleaseEventKind
    package_digest: str
    at: datetime
    actor: str | None = None  # 요청한 사람(접근 토큰의 sub). LOADED·LOAD_FAILED 에는 없다
    reason: str | None = None  # 요청한 사람이 적은 까닭. LOAD_FAILED 에는 실패한 조건
    summary: str | None = None  # LOADED: 적재한 패키지의 요약(문항 은행 버전과 모델 입출력 버전)


class ReleaseStore(Protocol):
    """활성화·롤백 기록을 덧붙여 저장하고 처음부터 읽는 길(store 가 구현)."""

    async def append(self, event: ReleaseEvent) -> None:
        """기록을 덧붙인다. 디스크에 닿은 뒤에 돌아온다."""
        ...

    async def read_all(self) -> Sequence[ReleaseEvent]:
        """저장된 기록을 순서대로 읽는다."""
        ...


@dataclass(frozen=True)
class ReleaseView:
    """release 가 낸 지금 상태(계약 ModelStatus 의 재료)."""

    state: ModelLoadState
    package_digest: str | None = None
    previous_package_digest: str | None = None
    activated_by: str | None = None
    activated_at: datetime | None = None


class ActivationOutcome(StrEnum):
    """활성화·롤백 요청을 받은 결과."""

    STARTED = "STARTED"  # 적재를 시작한다
    ALREADY_ACTIVE = "ALREADY_ACTIVE"  # 이미 활성이다(멱등)
    BUSY = "BUSY"  # 다른 적재가 진행 중이다


@dataclass(frozen=True)
class ExtractionQuestion:
    """prompt 컴포넌트의 입력: 추출 요청의 구조화된 값(JSON 으로 푼 모양). 모델 입력의 글은 prompt 가 만든다."""

    question_id: str  # 지금 묻고 있는 문항
    previous_question_id: str | None  # 대화에서 직전에 물은 문항(첫 문항이면 없다)
    current_question: str  # 상담원이 방금 한 말
    user_utterance: str  # 환자의 이번 말
    slots: Sequence[Mapping[str, object]]  # 이번 턴 전에 저장된 칸 값들(순서가 있다)


@dataclass(frozen=True)
class ExtractionTurn:
    """prompt 컴포넌트의 출력: 모델에 들어가는 입력 객체와 그 안 state 의 칸 순서."""

    input: Mapping[str, object]  # 모델 입력(question_id, current_question, user_utterance, state)
    state_key_order: Sequence[str]


@dataclass(frozen=True)
class GuardRequest:
    """output_guard 의 입력: 모델 출력 글자와 검증에 쓰는 요청 정보(JSON 으로 푼 모양)."""

    raw: str
    asked_item: str
    flow: Mapping[str, object]  # QuestionFlowTable
    fields: Sequence[Mapping[str, object]]  # QuestionFieldSpecs
    state: Mapping[str, object]


@dataclass(frozen=True)
class GuardedExtraction:
    """output_guard 의 출력: 검증된 출력(또는 출력 불가), 고치기 전 위반 코드들과 한 고쳐 쓰기들."""

    output: Mapping[str, object] | None
    violation_codes: Sequence[str]
    rewrites: Sequence[str]
