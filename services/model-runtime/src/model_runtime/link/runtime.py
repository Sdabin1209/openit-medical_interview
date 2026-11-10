"""link_api 가 요청을 컴포넌트 호출로 바꾸는 곳: 컴포넌트의 호출 순서와 적재 작업, 지표를 맡는다.

판단은 컴포넌트가 한다(prompt, inference, output_guard, responder, package_loader, release). 여기는 순서와 연결만
정한다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Histogram

from model_runtime.components.inference import call_engine
from model_runtime.components.output_guard import guard
from model_runtime.components.package_loader import (
    InspectedPackage,
    describe_digest_dir,
    inspect_package,
    load_package,
    loaded_summary,
)
from model_runtime.components.prompt import extraction_request, response_request
from model_runtime.components.release import Release
from model_runtime.components.responder import validate_sentence
from model_runtime.contract.models import (
    ModelLoadState,
    ModelPackageManifest,
    ModelStatus,
    ProblemReason,
)
from model_runtime.types import (
    ActivationOutcome,
    AdapterRegistry,
    AdapterRole,
    ChatEngine,
    EngineError,
    ExtractionTurn,
    GuardRequest,
    LoadedPackage,
    PackageInvalidError,
    PackageNotFoundError,
    PackageSource,
    RegistryUnavailableError,
    ReleaseEventKind,
    ServiceFault,
)

logger = logging.getLogger("model_runtime")

# 왜 계약 값: 서버 쪽 시간 상한은 D125 가 정하고 계약이 ModelExtractLimitSeconds 와 ModelRespondLimitSeconds 로 둔다
EXTRACT_LIMIT_SECONDS = 20
RESPOND_LIMIT_SECONDS = 25
# 왜 이 구간: 목표 p95 2초(D125)와 상한 20·25초 사이를 두루 본다. 측정으로 정한 값이 아니다(ADR 0002)
_CALL_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 25.0)
_RESIDENT_PACKAGES = 2  # 왜 2: 활성 패키지와 롤백 대상(직전 패키지)의 어댑터는 엔진에 남겨 롤백이 빠르게 한다


class Runtime:
    """모델 패키지 적재 상태를 쥐고 추출·응답·활성화·롤백 요청을 처리한다."""

    def __init__(
        self,
        *,
        release: Release,
        source: PackageSource,
        chat: ChatEngine,
        adapters: AdapterRegistry,
        workdir: Path,
        installed_version: str,
        registry: CollectorRegistry,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._release = release
        self._source = source
        self._chat = chat
        self._adapters = adapters
        self._workdir = workdir
        self._installed_version = installed_version
        self._clock = clock
        self._serving: LoadedPackage | None = None
        self._resident: list[LoadedPackage] = []
        self._tasks: set[asyncio.Task[None]] = set()
        # 왜 필수 지표: 계약 RequiredPrometheusMetric 의 model_call_duration_seconds(op 라벨이 extract 와 respond 를
        # 가른다)
        self._call_seconds = Histogram(
            "model_call_duration_seconds", "모델 호출 시간(초)", ["op"], buckets=_CALL_BUCKETS, registry=registry
        )
        self._violations = Counter(
            "model_output_violations_total", "고쳐 쓰기 전 모델 출력의 합격 조건 위반 수", ["code"], registry=registry
        )
        self._rewrites = Counter("model_output_rewrites_total", "값 고쳐 쓰기(D115) 수", ["kind"], registry=registry)
        self._unavailable = Counter("model_output_unavailable_total", "출력 불가로 끝난 추출 수", registry=registry)

    # ---- 시작과 끝 -------------------------------------------------------------------------

    async def start(self) -> None:
        """저장된 기록에서 활성 패키지를 구해 스스로 적재한다(C05: 문진 서비스는 추론만 부른다)."""
        digest = await self._release.open()
        if digest is not None:
            self._spawn(self._load(digest, None, restored=True))

    async def aclose(self) -> None:
        """진행 중인 적재를 멈춘다."""
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _spawn(self, coroutine: Any) -> None:  # noqa: ANN401
        task: asyncio.Task[None] = asyncio.ensure_future(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        """진행 중인 적재가 끝나기를 기다린다(시험과 종료에서 쓴다)."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # ---- 상태 ------------------------------------------------------------------------------

    def ready(self) -> bool:
        """추론을 받을 수 있는가(/readyz 의 model 점검). 적재를 마친 패키지가 있어야 한다."""
        return self._serving is not None

    def status(self) -> ModelStatus:
        """계약 ModelStatus."""
        view = self._release.view()
        body: dict[str, Any] = {"state": view.state.value}
        if view.package_digest:
            body["package_digest"] = view.package_digest
        if view.previous_package_digest:
            body["previous_package_digest"] = view.previous_package_digest
        if self._serving is not None:
            body["runtime_contract_version"] = self._serving.runtime_contract_version
            body["model_io_version"] = self._serving.model_io_version.value
            body["loaded_at"] = self._serving.loaded_at.isoformat()
        if view.activated_by:
            body["activated_by"] = view.activated_by
        if view.activated_at:
            body["activated_at"] = view.activated_at.isoformat()
        return ModelStatus.model_validate(body)

    # ---- 추론 ------------------------------------------------------------------------------

    def _serving_for(self, runtime_contract_version: int) -> LoadedPackage:
        serving = self._serving
        if serving is None:
            raise ServiceFault(
                503,
                "모델 패키지를 아직 적재하지 못했다",
                "활성 모델 패키지가 적재되지 않았다",
                reason=ProblemReason.MODEL_NOT_LOADED,
                retry_after=5,
            )
        if serving.runtime_contract_version != runtime_contract_version:
            raise ServiceFault(
                409,
                "문항 은행 버전이 적재한 모델 패키지와 다르다",
                f"요청 {runtime_contract_version}, 적재한 패키지 {serving.runtime_contract_version}",
                reason=ProblemReason.QUESTION_BANK_VERSION_MISMATCH,
                retry_after=5,
            )
        return serving

    async def extract(self, request: Mapping[str, Any]) -> tuple[str, Mapping[str, object]]:
        """LoRA-A 추출. (처리한 패키지 digest, 검증을 마친 출력). 검증은 이 호출이 한 번 한다(R7)."""
        serving = self._serving_for(int(request["runtime_contract_version"]))
        adapter = serving.adapters[AdapterRole.LORA_A]
        turn = ExtractionTurn(request["input"], request["state_key_order"])
        text, seconds = await call_engine(self._chat, extraction_request(turn, adapter), EXTRACT_LIMIT_SECONDS)
        self._call_seconds.labels("extract").observe(seconds)
        guarded = guard(
            GuardRequest(
                text, request["input"]["question_id"], request["flow"], request["fields"], request["input"]["state"]
            )
        )
        for code in guarded.violation_codes:
            self._violations.labels(code).inc()
        for kind in guarded.rewrites:
            self._rewrites.labels(kind).inc()
        if guarded.output is None:
            self._unavailable.inc()
            raise ServiceFault(
                503,
                "모델 출력이 합격 조건을 지키지 못했다",
                "위반 코드: " + ", ".join(sorted(set(guarded.violation_codes))),
                reason=ProblemReason.OUTPUT_INVALID,
                retry_after=5,
            )
        return serving.digest, guarded.output

    async def respond(self, request: Mapping[str, Any]) -> tuple[str, str]:
        """LoRA-B 응답 문장. (처리한 패키지 digest, 문장)."""
        serving = self._serving_for(int(request["runtime_contract_version"]))
        adapter = serving.adapters[AdapterRole.LORA_B]
        text, seconds = await call_engine(
            self._chat, response_request(request["input"], adapter), RESPOND_LIMIT_SECONDS
        )
        self._call_seconds.labels("respond").observe(seconds)
        return serving.digest, validate_sentence(text)

    # ---- 모델 패키지 -----------------------------------------------------------------------

    def _folder(self, digest: str) -> Path:
        return self._workdir / "packages" / describe_digest_dir(digest)

    async def _inspect(self, digest: str) -> InspectedPackage:
        try:
            return await inspect_package(self._source, digest, self._folder(digest), self._installed_version)
        except PackageNotFoundError as error:
            raise ServiceFault(404, "모델 패키지를 찾을 수 없다", "레지스트리에 그 digest 의 패키지가 없다") from error
        except PackageInvalidError as error:
            raise ServiceFault(
                422, "모델 패키지가 계약과 다르다", str(error), reason=ProblemReason.PACKAGE_INVALID
            ) from error
        except RegistryUnavailableError as error:
            raise ServiceFault(503, "레지스트리에 닿지 못했다", "모델 패키지를 받지 못했다", retry_after=5) from error

    async def describe(self, digest: str) -> ModelPackageManifest:
        """레지스트리의 모델 패키지 목록표(평가 보고서 포함). 적재하거나 활성화하지 않는다."""
        return (await self._inspect(digest)).manifest

    async def activate(self, digest: str, reason: str, actor: str) -> tuple[ActivationOutcome, ModelStatus]:
        """활성화 승인. 이미 활성이면 ALREADY_ACTIVE, 적재를 시작하면 STARTED."""
        return await self._begin(ReleaseEventKind.ACTIVATE_REQUESTED, digest, reason, actor)

    async def rollback(self, target: str, reason: str, actor: str) -> tuple[ActivationOutcome, ModelStatus]:
        """이전에 활성이었던 패키지로 되돌린다. 아니면 409 ROLLBACK_TARGET_INVALID."""
        if not (self._release.was_active(target) or self._release.is_loading(target)):
            raise ServiceFault(
                409,
                "되돌아갈 수 없는 패키지다",
                "이전에 활성이었던 패키지가 아니다",
                reason=ProblemReason.ROLLBACK_TARGET_INVALID,
            )
        return await self._begin(ReleaseEventKind.ROLLBACK_REQUESTED, target, reason, actor)

    async def _begin(
        self, kind: ReleaseEventKind, digest: str, reason: str, actor: str
    ) -> tuple[ActivationOutcome, ModelStatus]:
        preview = self._release.preview(digest)
        if preview is ActivationOutcome.BUSY:
            raise ServiceFault(409, "다른 모델 패키지를 적재하는 중이다", "적재가 끝난 뒤 다시 요청한다", retry_after=5)
        if preview is ActivationOutcome.ALREADY_ACTIVE:
            return preview, self.status()
        inspected = await self._inspect(digest)  # 404, 422 는 기록하기 전에 낸다
        outcome = await self._release.request(kind, digest, actor, reason, self._clock())
        if outcome is ActivationOutcome.BUSY:
            raise ServiceFault(409, "다른 모델 패키지를 적재하는 중이다", "적재가 끝난 뒤 다시 요청한다", retry_after=5)
        if outcome is ActivationOutcome.STARTED:
            self._spawn(self._load(digest, inspected, restored=False))
        return outcome, self.status()

    async def _load(self, digest: str, inspected: InspectedPackage | None, *, restored: bool) -> None:
        """패키지를 받아 적재한다. 성공하면 활성이 되고, 실패하면 이전 패키지를 유지한다(D46)."""
        package: LoadedPackage | None = None
        try:
            ready = inspected or await inspect_package(
                self._source, digest, self._folder(digest), self._installed_version
            )
            package = await load_package(self._source, self._adapters, ready, self._folder(digest))
            if restored:
                self._release.restored(digest)
            else:
                await self._release.loaded(digest, loaded_summary(package), self._clock())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if package is not None:
                for adapter in package.adapters.values():
                    await self._adapters.unload_adapter(adapter.name)
            detail = (
                str(error)
                if isinstance(
                    error, PackageInvalidError | PackageNotFoundError | RegistryUnavailableError | EngineError
                )
                else "예기치 않은 오류"
            )
            logger.warning("모델 패키지 적재 실패 digest=%s 사유=%s", digest, detail)
            await self._release.failed(digest, detail, self._clock())
            return
        previous = self._serving
        self._serving = package
        self._resident = [p for p in self._resident if p.digest != package.digest] + [package]
        for old in self._resident[:-_RESIDENT_PACKAGES]:
            for adapter in old.adapters.values():
                await self._adapters.unload_adapter(adapter.name)
        self._resident = self._resident[-_RESIDENT_PACKAGES:]
        logger.info("모델 패키지 적재 완료 digest=%s 이전=%s", digest, previous.digest if previous else None)


def view_state(status: ModelStatus) -> ModelLoadState:
    """ModelStatus 의 상태 값."""
    return status.state
