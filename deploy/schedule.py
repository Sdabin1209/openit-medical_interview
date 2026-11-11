"""잡 스케줄의 순수 계산(ADR 0028). docker·systemd 를 부르지 않는다. 명령(schedule list·render·install·run)의 조립은 ./deploy 가 한다.

- 어떤 잡을 얼마마다 돌리는가: 영역이 이미지 라벨(io.openit.jobs)로 선언한 잡은 선언한 시간 상한에서 주기를 만들고(D131), deploy 가 도는 잡(백업·서버 밖 동기·복구 시험)은 정본 결정의 일정을 쓴다.
- 다음 실행 시각: 시계를 주입받는다(실제로 기다리지 않는다).
- systemd 서비스·타이머 파일 글, 잡 결과를 감시에 올리는 지표 글, 한 번도 성공하지 못한 잡의 경보 규칙.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

import yaml
from urllib.parse import quote

# 왜 300초 단위: D131 이 정했다(영역은 잡의 timeout_seconds 만 선언하고 deploy 가 선언 상한보다 큰 가장 작은 300초 배수를 주기로 정한다. 계약 JobTimeoutSeconds)
PERIOD_STEP_SECONDS = 300
DAY_SECONDS = 24 * 60 * 60
WEEK_SECONDS = 7 * DAY_SECONDS
# 왜 2배: 잡 하나가 한 번 못 돌거나 늦어도 경보가 울리지 않고, 두 주기를 건너뛰면 울린다(D131: JobStale 도 그 주기에서). 근거가 되는 표준이 없는 선택값이고 측정하지 않았다(ADR 0028)
STALE_PERIODS = 2
PUSH_JOB = "openit-jobs"  # Pushgateway 의 job 라벨(플랫폼 감시 설정의 scrape job 이름과 같다. 시험이 같은지 본다)
EXIT_OK, EXIT_TEMPFAIL, EXIT_FAIL = 0, 75, 1  # 계약 JobExitCode
JOB_EXIT_CODES = (EXIT_OK, EXIT_TEMPFAIL, EXIT_FAIL)

# deploy 가 도는 잡과 그것을 한 번 실행하는 ./deploy 명령. RESTORE 는 덮어쓰는 복구라 사람이 --yes 로 한다(스케줄에 넣지 않는다)
DEPLOY_COMMANDS: dict[str, str] = {"BACKUP": "backup", "OFFSITE_SYNC": "offsite-sync", "RESTORE_TEST": "restore-test"}
JOB_NAME = re.compile(r"^[A-Z][A-Z_]*$")


class ScheduleError(Exception):
    """스케줄을 만들 수 없다(선언이 서로 겹치거나 모양이 틀렸다)."""


def period_from_timeout(timeout_seconds: int) -> int:
    """선언한 시간 상한보다 큰 가장 작은 300초 배수(D131). 같은 값이면 다음 배수다(상한까지 걸린 실행이 다음 실행과 겹치지 않는다)."""
    if timeout_seconds < 1:
        raise ScheduleError("timeout_seconds 는 1 이상이다(계약 JobTimeoutSeconds)")
    return (timeout_seconds // PERIOD_STEP_SECONDS + 1) * PERIOD_STEP_SECONDS


@dataclass(frozen=True)
class Schedule:
    job: str  # 계약 JobName
    owner: str  # 잡을 가진 영역(계약 ServiceName) 또는 deploy
    period_seconds: int  # 이름뿐인 주기. interval 은 이 간격마다, daily·weekly 는 하루·한 주
    timeout_seconds: int  # 한 번이 끝나야 하는 시간 상한. 넘으면 멈추고 실패다
    kind: str  # interval | daily | weekly
    at: time | None = None  # daily·weekly 의 시각(관리 노드의 지역 시각)
    weekday: int | None = None  # weekly 의 요일(월요일 0)
    basis: str = ""  # 주기의 근거(문서에 적는다)

    @property
    def stale_after_seconds(self) -> int:
        return STALE_PERIODS * self.period_seconds

    @property
    def command(self) -> str | None:
        """deploy 가 도는 잡이면 그 ./deploy 명령(영역의 잡이면 없다. 이미지의 선언대로 부른다)."""
        return DEPLOY_COMMANDS.get(self.job) if self.owner == "deploy" else None


def deploy_schedules() -> list[Schedule]:
    """deploy 가 도는 잡의 일정. 하루 중 시각은 관리 노드의 지역 시각의 새벽이다(환자가 쓰는 시간을 피한다. 측정하지 않았다).

    왜 02시·03시·일요일 04시: 서버 밖 동기는 백업이 끝난 뒤여야 하므로 한 시간 뒤에 둔다. 백업이 한 시간을 넘기면 그날은 앞의 스냅샷을 옮기고 새 것은 다음 날 옮긴다(사본이 하루 늦는다.
    백업 시간은 측정하지 않았다). 복구 시험은 일주일에 한 번(정본에 주기가 없고 '정기'만 있어 관행을 따랐다: ADR 0028).
    """
    return [
        Schedule("BACKUP", "deploy", DAY_SECONDS, DAY_SECONDS, "daily", time(2, 0),
                 basis="D85(5)·U31 사용자 결정 2026-11-03: 백업은 매일. 시각은 근거가 되는 결정이 없다(새벽 02시, 측정하지 않았다)"),
        Schedule("OFFSITE_SYNC", "deploy", DAY_SECONDS, DAY_SECONDS, "daily", time(3, 0),
                 basis="D88 U6: 서버 밖 사본은 일일 백업을 따른다. 시각은 백업 뒤 한 시간(측정하지 않았다)"),
        Schedule("RESTORE_TEST", "deploy", WEEK_SECONDS, WEEK_SECONDS, "weekly", time(4, 0), 6,
                 basis="D88 U6: 정기 복원 시험(주기는 정본에 없다. 매주 일요일 04시는 관행으로 고른 값이고 측정하지 않았다)"),
    ]


def declared_schedules(declarations: Mapping[str, Mapping[str, Any]]) -> list[Schedule]:
    """영역이 이미지 라벨(io.openit.jobs, 계약 JobsDeclaration)로 선언한 잡의 일정. declarations: 영역 이름 -> 선언 객체.

    주기는 선언한 시간 상한에서 만든다(D131). deploy 가 도는 잡의 이름을 영역이 선언하거나 같은 잡을 두 영역이 선언하면 어느 쪽이 맞는지 정할 수 없어 거절한다.
    """
    found: dict[str, Schedule] = {}
    for owner in sorted(declarations):
        for item in declarations[owner].get("jobs", []):
            job, timeout = item["job"], int(item["timeout_seconds"])
            if not JOB_NAME.fullmatch(job):
                raise ScheduleError(f"{owner} 의 잡 이름이 JobName 모양이 아니다: {job!r}")
            if job in DEPLOY_COMMANDS or job == "RESTORE":
                raise ScheduleError(f"{owner} 가 deploy 의 잡 {job} 을 선언했다(백업·복구 잡은 deploy 가 도는 잡이다)")
            if job in found:
                raise ScheduleError(f"잡 {job} 을 {found[job].owner} 와 {owner} 가 모두 선언했다(스케줄의 주인이 하나여야 한다)")
            period = period_from_timeout(timeout)
            found[job] = Schedule(job, owner, period, timeout, "interval",
                                  basis=f"D131: 선언한 시간 상한 {timeout}초보다 큰 가장 작은 300초 배수({period}초). 측정하지 않았다")
    return list(found.values())


def build_schedules(declarations: Mapping[str, Mapping[str, Any]]) -> list[Schedule]:
    """스케줄 전체(deploy 가 도는 잡 + 영역이 선언한 잡). 잡 이름순."""
    return sorted([*deploy_schedules(), *declared_schedules(declarations)], key=lambda schedule: schedule.job)


# ---------------------------------------------------------------- 다음 실행 시각(시계를 주입한다)


def next_runs(schedule: Schedule, now: datetime, count: int = 3, *, anchor: datetime | None = None) -> list[datetime]:
    """now 이후의 실행 시각 count 개(systemd 타이머와 같은 규칙).

    - interval: OnBootSec=주기 와 OnUnitActiveSec=주기. anchor 는 마지막으로 시작한(또는 처음 켜진) 때이고 없으면 now 다. 다음은 anchor + 주기, 그 뒤는 주기마다.
    - daily·weekly: OnCalendar. now 의 시간대(지역 시각)에서 그 시각이 되는 때. 정각이 now 와 같으면 이미 지난 것으로 본다.
    now 는 시간대를 가진(aware) 시각이어야 한다.
    """
    if now.tzinfo is None:
        raise ScheduleError("now 는 시간대를 가진 시각이어야 한다")
    if schedule.kind == "interval":
        first = (anchor or now) + timedelta(seconds=schedule.period_seconds)
        while first <= now:  # anchor 가 오래전이면 지난 것을 건너뛴다(systemd 는 놓친 단조 시각을 몰아 실행하지 않는다)
            first += timedelta(seconds=schedule.period_seconds)
        return [first + timedelta(seconds=schedule.period_seconds * index) for index in range(count)]
    if schedule.at is None:
        raise ScheduleError(f"{schedule.job}: 달력 일정에 시각이 없다")
    runs: list[datetime] = []
    day = now.date()
    while len(runs) < count:
        if schedule.kind == "daily" or day.weekday() == schedule.weekday:
            candidate = datetime.combine(day, schedule.at, tzinfo=now.tzinfo)
            if candidate > now:
                runs.append(candidate)
        day += timedelta(days=1)
    return runs


def stale(schedule: Schedule, last_success_epoch: float | None, now_epoch: float) -> bool:
    """마지막 성공이 두 주기보다 오래됐는가(감시의 OpenitJobStale 과 같은 식). 한 번도 성공하지 않았으면 판정하지 않는다(없음은 별도 경보다)."""
    return last_success_epoch is not None and now_epoch - last_success_epoch > schedule.stale_after_seconds


# ---------------------------------------------------------------- systemd 파일


def doc_url(path: str) -> str:
    """유닛의 Documentation= 값(file: URL). 한글 경로는 퍼센트 인코딩해야 systemd 가 URL 로 받는다(`systemd-analyze verify` 가 'Invalid URL' 로 거절한다).
    유닛 파일에서 `%` 는 지정자(specifier)의 시작이라 `%%` 로 쓴다(systemd.unit)."""
    return ("file://" + quote(path, safe="/")).replace("%", "%%")


def unit_stem(project: str, job: str) -> str:
    """`<프로젝트>-job-<잡 이름>`: 소문자와 하이픈(systemd 유닛 이름 규칙). 한 서버에 설치를 둘 이상 둘 수 있다."""
    return f"{project}-job-{job.lower().replace('_', '-')}"


def oncalendar(schedule: Schedule) -> str:
    assert schedule.at is not None  # noqa: S101
    clock = schedule.at.strftime("%H:%M:%S")
    if schedule.kind == "weekly":
        assert schedule.weekday is not None  # noqa: S101
        return f"{('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[schedule.weekday]} *-*-* {clock}"
    return f"*-*-* {clock}"


def service_unit(schedule: Schedule, *, deploy_path: str, working_directory: str, user: str, path_env: str, doc: str) -> str:
    """잡 하나를 한 번 실행하는 systemd 서비스(Type=oneshot). 같은 잡의 다음 시작은 이 서비스가 끝나기를 기다린다(systemd 는 활성인 oneshot 을 다시 시작하지 않는다)."""
    return "\n".join([
        "# ./deploy schedule render 가 만든다. 손으로 고치지 않는다(ADR 0028).",
        "[Unit]",
        f"Description=openit 잡 {schedule.job} ({schedule.owner}) 한 번 실행",
        f"Documentation={doc}",
        "",
        "[Service]",
        "Type=oneshot",
        f"User={user}",
        f"WorkingDirectory={working_directory}",
        f"Environment=PATH={path_env}",
        f"ExecStart={deploy_path} schedule run {schedule.job}",
        # 왜 종료 코드 75 를 성공으로: 일시적 실패(EX_TEMPFAIL)는 다음 실행에서 다시 하는 정상 경로다. 결과는 감시 지표(마지막 종료 코드)로 본다
        "SuccessExitStatus=75",
        f"TimeoutStartSec={schedule.timeout_seconds}",
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "",
    ])


def timer_unit(schedule: Schedule, *, stem: str, doc: str) -> str:
    lines = ["# ./deploy schedule render 가 만든다. 손으로 고치지 않는다(ADR 0028).", "[Unit]", f"Description=openit 잡 {schedule.job} 일정",
             f"Documentation={doc}", "", "[Timer]"]
    if schedule.kind == "interval":
        lines += [f"OnBootSec={schedule.period_seconds}s", f"OnUnitActiveSec={schedule.period_seconds}s"]
    else:
        # 왜 Persistent: 관리 노드가 꺼져 있던 동안 놓친 일일·주간 실행을 켜질 때 한 번 한다(systemd.timer)
        lines += [f"OnCalendar={oncalendar(schedule)}", "Persistent=true"]
    lines += [f"Unit={stem}.service", "", "[Install]", "WantedBy=timers.target", ""]
    return "\n".join(lines)


def render_units(schedules: Iterable[Schedule], *, project: str, deploy_path: str, working_directory: str, user: str, path_env: str, doc: str) -> dict[str, str]:
    """유닛 파일 이름 -> 내용(잡마다 서비스와 타이머 하나씩)."""
    files: dict[str, str] = {}
    for schedule in schedules:
        stem = unit_stem(project, schedule.job)
        files[f"{stem}.service"] = service_unit(schedule, deploy_path=deploy_path, working_directory=working_directory, user=user, path_env=path_env, doc=doc)
        files[f"{stem}.timer"] = timer_unit(schedule, stem=stem, doc=doc)
    return files


# ---------------------------------------------------------------- 잡 결과 -> 감시


def parse_result(stdout: str, job: str) -> dict[str, Any] | None:
    """잡의 표준 출력 마지막 JSON 줄(계약 JobRunResult). 없거나 계약 칸이 아니면 None(호출자가 실패로 기록한다)."""
    lines = [line for line in stdout.strip().splitlines() if line.startswith("{")]
    if not lines:
        return None
    try:
        document = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    allowed = {"job", "exit_code", "started_at", "finished_at", "processed_count", "snapshot_id"}
    required = {"job", "exit_code", "started_at", "finished_at"}
    if not isinstance(document, dict) or not required <= set(document) or not set(document) <= allowed:
        return None
    if document["job"] != job or document["exit_code"] not in JOB_EXIT_CODES:
        return None
    return document


def to_epoch(timestamp: str) -> float:
    """계약 Timestamp(RFC 3339)를 초로."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC).timestamp()


def metrics_text(schedule: Schedule, result: Mapping[str, Any]) -> str:
    """Pushgateway 에 보내는 지표(Prometheus 텍스트 형식). 성공했을 때만 last_success 를 쓴다: POST 는 같은 이름의 지표만 바꾸므로 실패해도 마지막 성공 시각이 남는다."""
    finished = to_epoch(result["finished_at"])
    lines = [
        "# TYPE openit_job_last_exit_code gauge",
        f"openit_job_last_exit_code {int(result['exit_code'])}",
        "# TYPE openit_job_last_run_timestamp_seconds gauge",
        f"openit_job_last_run_timestamp_seconds {finished:.0f}",
        "# TYPE openit_job_last_duration_seconds gauge",
        f"openit_job_last_duration_seconds {max(finished - to_epoch(result['started_at']), 0):.0f}",
        "# TYPE openit_job_period_seconds gauge",
        f"openit_job_period_seconds {schedule.period_seconds}",
    ]
    if result.get("processed_count") is not None:
        lines += ["# TYPE openit_job_last_processed_count gauge", f"openit_job_last_processed_count {int(result['processed_count'])}"]
    if result["exit_code"] == EXIT_OK:
        lines += ["# TYPE openit_job_last_success_timestamp_seconds gauge", f"openit_job_last_success_timestamp_seconds {finished:.0f}"]
    return "\n".join(lines) + "\n"


def push_path(job: str) -> str:
    """Pushgateway 의 그룹 경로(`/metrics/job/<job>/job_name/<잡>`). 잡마다 그룹 하나다."""
    return f"/metrics/job/{PUSH_JOB}/job_name/{job}"


def job_rules_yaml(schedules: Iterable[Schedule]) -> str:
    """한 번도 성공하지 못한 잡의 경보 규칙(generated/monitoring/job-rules.yml). 마지막 성공 지표가 두 주기 동안 없다.

    왜 생성: 어떤 잡이 있는지는 이미지 선언과 설치에 달려 있다(정적 규칙은 목록을 모른다). 지표가 있는 잡의 실패·지연은 플랫폼의 정적 규칙(OpenitJobFailed·OpenitJobStale)이 본다.
    """
    rules = [
        {
            "alert": "OpenitJobNeverSucceeded",
            "expr": f'absent(openit_job_last_success_timestamp_seconds{{job="{PUSH_JOB}", job_name="{schedule.job}"}})',
            "for": f"{schedule.stale_after_seconds}s",
            "labels": {"severity": "critical", "job_name": schedule.job},
            "annotations": {"summary": f"잡 {schedule.job} 의 성공 기록이 없다(스케줄러가 돌지 않거나 계속 실패한다. ./deploy schedule status)"},
        }
        for schedule in schedules
    ]
    document = {"groups": [{"name": "openit-job-presence", "rules": rules}] if rules else []}
    header = "# ./deploy 가 만든다(ADR 0028). 스케줄에 있는 잡마다 '성공 기록 없음' 경보. 손으로 고치지 않는다.\n"
    return header + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------- 설치(유닛 파일을 systemd 폴더에 두고 켠다)


def install_plan(rendered: Mapping[str, str], existing: Iterable[str], *, project: str) -> tuple[list[str], list[str]]:
    """(쓸 파일, 지울 파일). 지울 것은 이 설치(프로젝트)의 잡 유닛 이름꼴인데 지금 스케줄에 없는 것뿐이다(다른 설치·다른 유닛은 건드리지 않는다)."""
    prefix = f"{project}-job-"
    stale = sorted(name for name in existing if name.startswith(prefix) and name.endswith((".service", ".timer")) and name not in rendered)
    return sorted(rendered), stale


def systemctl_commands(systemctl: str, rendered: Mapping[str, str], removed: Iterable[str]) -> list[list[str]]:
    """설치 뒤 부르는 systemctl 명령들(차례대로). 없어진 타이머는 끄고, 파일을 다시 읽고, 타이머를 켠다(켜는 것은 이미 켜져 있어도 같다)."""
    commands = [[systemctl, "disable", "--now", name] for name in removed if name.endswith(".timer")]
    commands.append([systemctl, "daemon-reload"])
    timers = sorted(name for name in rendered if name.endswith(".timer"))
    if timers:
        commands.append([systemctl, "enable", "--now", *timers])
    return commands
