"""deploy/schedule.py: 잡 주기·일정 계산, systemd 파일, 감시 지표와 규칙(docker·systemd 실행 없음, ADR 0028). 시간은 모두 주입한 시계다."""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

import jsonschema
import pytest
import yaml

from .conftest import REPO, _load

SURVEY_JOBS = json.loads((REPO / "services" / "survey-service" / "jobs.json").read_text(encoding="utf-8"))
COMPONENTS = yaml.safe_load((REPO / "contracts" / "components.yaml").read_text(encoding="utf-8"))["components"]
KST = ZoneInfo("Asia/Seoul")


@pytest.fixture(scope="module")
def sc() -> ModuleType:
    return _load("schedule_under_test", REPO / "deploy" / "schedule.py")


def by_job(schedules: list) -> dict:  # type: ignore[type-arg]
    return {schedule.job: schedule for schedule in schedules}


def test_period_is_the_smallest_multiple_of_300_above_the_declared_timeout(sc: ModuleType) -> None:
    """D131: 선언한 상한보다 큰 가장 작은 300초 배수. 같은 값이면 다음 배수라 상한까지 걸린 실행이 다음 실행과 겹치지 않는다."""
    assert [sc.period_from_timeout(t) for t in (1, 299, 300, 301, 600, 899, 900, 259200)] == [300, 300, 600, 600, 900, 900, 1200, 259500]
    for timeout in range(1, 3000, 7):
        period = sc.period_from_timeout(timeout)
        assert period % 300 == 0 and period > timeout and period - 300 <= timeout
    with pytest.raises(sc.ScheduleError):
        sc.period_from_timeout(0)


def test_declared_jobs_of_the_real_survey_service_become_15_minute_intervals(sc: ModuleType) -> None:
    schedules = by_job(sc.declared_schedules({"survey-service": SURVEY_JOBS}))
    assert set(schedules) == {"DETECT_FAILURES", "PURGE_EXPIRED"}
    for schedule in schedules.values():
        assert (schedule.owner, schedule.kind, schedule.timeout_seconds, schedule.period_seconds) == ("survey-service", "interval", 600, 900)
        assert schedule.stale_after_seconds == 1800
        assert "D131" in schedule.basis and "측정하지 않았다" in schedule.basis


def test_deploy_jobs_follow_the_decided_schedules_and_restore_is_never_scheduled(sc: ModuleType) -> None:
    schedules = by_job(sc.deploy_schedules())
    assert set(schedules) == {"BACKUP", "OFFSITE_SYNC", "RESTORE_TEST"}  # RESTORE 는 덮어쓰는 복구라 사람이 --yes 로 한다
    assert (schedules["BACKUP"].kind, schedules["BACKUP"].period_seconds, schedules["BACKUP"].at) == ("daily", 86400, time(2, 0))
    assert schedules["OFFSITE_SYNC"].at > schedules["BACKUP"].at  # 서버 밖 동기는 백업 뒤
    assert (schedules["RESTORE_TEST"].kind, schedules["RESTORE_TEST"].weekday, schedules["RESTORE_TEST"].period_seconds) == ("weekly", 6, 604800)
    assert all(s.owner == "deploy" and s.command in {"backup", "offsite-sync", "restore-test"} for s in schedules.values())
    assert "U31" in schedules["BACKUP"].basis and "D88 U6" in schedules["RESTORE_TEST"].basis


def test_every_job_name_is_a_contract_job_name_and_declared_ones_cannot_collide(sc: ModuleType) -> None:
    names = set(COMPONENTS["schemas"]["JobName"]["enum"])
    assert {s.job for s in sc.build_schedules({"survey-service": SURVEY_JOBS})} <= names
    with pytest.raises(sc.ScheduleError, match="deploy 의 잡"):
        sc.declared_schedules({"x": {"jobs": [{"job": "BACKUP", "timeout_seconds": 60}]}})
    with pytest.raises(sc.ScheduleError, match="모두 선언"):
        sc.declared_schedules({"a": SURVEY_JOBS, "b": SURVEY_JOBS})
    assert sc.declared_schedules({"model-runtime": {"jobs": []}}) == []


def test_interval_next_runs_follow_the_injected_clock(sc: ModuleType) -> None:
    schedule = by_job(sc.declared_schedules({"survey-service": SURVEY_JOBS}))["PURGE_EXPIRED"]
    now = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
    assert sc.next_runs(schedule, now, 3) == [now + timedelta(minutes=15 * n) for n in (1, 2, 3)]
    anchor = now - timedelta(minutes=40)  # 마지막으로 시작한 때가 40분 전이면 다음은 45분째(5분 뒤)다
    assert sc.next_runs(schedule, now, 2, anchor=anchor) == [now + timedelta(minutes=5), now + timedelta(minutes=20)]
    with pytest.raises(sc.ScheduleError):
        sc.next_runs(schedule, datetime(2026, 11, 11, 9, 0))


def test_daily_and_weekly_next_runs_use_the_local_clock_and_handle_dst(sc: ModuleType) -> None:
    schedules = by_job(sc.deploy_schedules())
    backup, test = schedules["BACKUP"], schedules["RESTORE_TEST"]
    before = datetime(2026, 11, 11, 1, 0, tzinfo=KST)
    assert sc.next_runs(backup, before, 2) == [datetime(2026, 11, 11, 2, 0, tzinfo=KST), datetime(2026, 11, 12, 2, 0, tzinfo=KST)]
    assert sc.next_runs(backup, datetime(2026, 11, 11, 2, 0, tzinfo=KST), 1) == [datetime(2026, 11, 12, 2, 0, tzinfo=KST)]  # 정각은 이미 지났다
    assert sc.next_runs(backup, datetime(2026, 11, 11, 2, 0, 1, tzinfo=KST), 1)[0].day == 12
    wednesday = datetime(2026, 11, 11, 12, 0, tzinfo=KST)
    assert wednesday.weekday() == 2
    assert sc.next_runs(test, wednesday, 2) == [datetime(2026, 11, 15, 4, 0, tzinfo=KST), datetime(2026, 11, 22, 4, 0, tzinfo=KST)]
    assert sc.next_runs(test, datetime(2026, 11, 15, 3, 0, tzinfo=KST), 1) == [datetime(2026, 11, 15, 4, 0, tzinfo=KST)]  # 일요일 새벽 전이면 그날
    berlin = ZoneInfo("Europe/Berlin")  # 2026-10-25 에 서머타임이 끝난다. 벽시계 02:00 에 도는 것은 그대로다
    runs = sc.next_runs(backup, datetime(2026, 10, 24, 12, 0, tzinfo=berlin), 3)
    assert [(r.month, r.day, r.hour) for r in runs] == [(10, 25, 2), (10, 26, 2), (10, 27, 2)]


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze 가 없다")
def test_next_runs_agree_with_systemd_calendar_parsing(sc: ModuleType) -> None:
    """같은 시각 표현을 systemd 가 읽어 구한 다음 시각과 우리 계산이 같다(시계는 --base-time 으로 주입, 시간대는 UTC 로 고정)."""
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    for schedule in (s for s in sc.deploy_schedules()):
        out = subprocess.run(["systemd-analyze", "calendar", "--iterations=3", f"--base-time={now:%Y-%m-%d %H:%M:%S}", sc.oncalendar(schedule)],
                             env={"TZ": "UTC", "PATH": os.environ["PATH"]}, capture_output=True, text=True, check=True).stdout
        elapses = [line.split(":", 1)[1].split("(")[0].strip() for line in out.splitlines() if "Next elapse" in line or "Iteration #" in line]
        theirs = [datetime.strptime(" ".join(e.split()[1:3]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC) for e in elapses]
        assert theirs == sc.next_runs(schedule, now, 3), schedule.job


def test_stale_is_two_periods_after_the_last_success(sc: ModuleType) -> None:
    purge = by_job(sc.declared_schedules({"survey-service": SURVEY_JOBS}))["PURGE_EXPIRED"]
    assert not sc.stale(purge, None, 10_000)  # 한 번도 성공하지 않은 잡은 따로 경보(OpenitJobNeverSucceeded)
    assert not sc.stale(purge, 10_000 - 1800, 10_000)
    assert sc.stale(purge, 10_000 - 1801, 10_000)


def render(sc: ModuleType, schedules: list, **kwargs: str) -> dict:  # type: ignore[type-arg]
    values = {"project": "openit", "deploy_path": str(REPO / "deploy" / "deploy"), "working_directory": str(REPO / "deploy"), "user": "root",
              "path_env": "/usr/local/bin:/usr/bin:/bin", "doc": sc.doc_url("/srv/openit/docs/adr/0028-잡-스케줄러는-systemd-타이머.md")} | kwargs
    return sc.render_units(schedules, **values)  # type: ignore[no-any-return]


def test_units_run_each_job_once_with_the_declared_timeout_and_calendar(sc: ModuleType) -> None:
    schedules = sc.build_schedules({"survey-service": SURVEY_JOBS})
    files = render(sc, schedules)
    assert sorted(files) == sorted(f"openit-job-{job}.{kind}" for job in ("backup", "detect-failures", "offsite-sync", "purge-expired", "restore-test") for kind in ("service", "timer"))
    purge, backup, weekly = files["openit-job-purge-expired.service"], files["openit-job-backup.service"], files["openit-job-restore-test.timer"]
    assert "Type=oneshot" in purge and "ExecStart=" + str(REPO / "deploy" / "deploy") + " schedule run PURGE_EXPIRED" in purge
    assert "TimeoutStartSec=600" in purge and "SuccessExitStatus=75" in purge and "NoNewPrivileges=yes" in purge
    assert "TimeoutStartSec=86400" in backup
    interval = files["openit-job-detect-failures.timer"]
    assert "OnBootSec=900s" in interval and "OnUnitActiveSec=900s" in interval and "OnCalendar" not in interval and "Unit=openit-job-detect-failures.service" in interval
    assert "OnCalendar=Sun *-*-* 04:00:00" in weekly and "Persistent=true" in weekly
    assert "OnCalendar=*-*-* 02:00:00" in files["openit-job-backup.timer"]
    assert all("WantedBy=timers.target" in text for name, text in files.items() if name.endswith(".timer"))
    other = render(sc, schedules, project="openit-sch")
    assert "openit-sch-job-backup.service" in other and "openit-job-backup.service" not in other  # 한 서버에 설치를 둘 이상 둘 수 있다


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze 가 없다")
def test_generated_units_pass_systemd_analyze_verify(sc: ModuleType, tmp_path: Path) -> None:
    import getpass

    files = render(sc, sc.build_schedules({"survey-service": SURVEY_JOBS}), user=getpass.getuser())
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    result = subprocess.run(["systemd-analyze", "verify", *sorted(str(tmp_path / n) for n in files)], capture_output=True, text=True, check=False, env={"PATH": os.environ["PATH"]})
    problems = [line for line in (result.stdout + result.stderr).splitlines() if line.strip()]
    assert result.returncode == 0 and not problems, problems  # 한글 경로의 Documentation URL 도 거절당하지 않는다(퍼센트 인코딩)


def test_install_replaces_only_this_installations_stale_job_units(sc: ModuleType) -> None:
    rendered = render(sc, sc.build_schedules({"survey-service": SURVEY_JOBS}))
    existing = ["openit-job-backup.service", "openit-job-old-job.service", "openit-job-old-job.timer", "openit-sch-job-backup.timer", "openit-other.service", "unrelated.timer"]
    write, remove = sc.install_plan(rendered, existing, project="openit")
    assert write == sorted(rendered) and remove == ["openit-job-old-job.service", "openit-job-old-job.timer"]
    commands = sc.systemctl_commands("systemctl", rendered, remove)
    assert commands[0] == ["systemctl", "disable", "--now", "openit-job-old-job.timer"] and commands[1] == ["systemctl", "daemon-reload"]
    assert commands[2][:3] == ["systemctl", "enable", "--now"] and all(name.endswith(".timer") for name in commands[2][3:]) and len(commands[2]) == 3 + 5


def result_line(job: str = "PURGE_EXPIRED", code: int = 0, **extra: object) -> str:
    return json.dumps({"job": job, "exit_code": code, "started_at": "2026-11-11T09:00:00Z", "finished_at": "2026-11-11T09:00:07Z", **extra})


def test_parse_result_accepts_only_the_contract_job_run_result_of_the_same_job(sc: ModuleType) -> None:
    schema = {"$ref": "#/components/schemas/JobRunResult", "components": COMPONENTS}
    good = result_line(processed_count=3)
    jsonschema.validate(json.loads(good), schema, format_checker=jsonschema.FormatChecker())
    assert sc.parse_result("로그 한 줄\n" + good + "\n", "PURGE_EXPIRED")["processed_count"] == 3
    for bad in ("", "no json", result_line("BACKUP"), result_line(code=2), result_line(extra_key=1), '{"job": "PURGE_EXPIRED"}', "{broken"):
        assert sc.parse_result(bad, "PURGE_EXPIRED") is None


def test_metrics_keep_the_last_success_when_a_run_fails(sc: ModuleType) -> None:
    purge = by_job(sc.declared_schedules({"survey-service": SURVEY_JOBS}))["PURGE_EXPIRED"]
    ok = sc.metrics_text(purge, json.loads(result_line(processed_count=3)))
    assert "openit_job_last_exit_code 0\n" in ok and "openit_job_last_success_timestamp_seconds 1794387607\n" in ok
    assert "openit_job_last_duration_seconds 7\n" in ok and "openit_job_period_seconds 900\n" in ok and "openit_job_last_processed_count 3\n" in ok
    failed = sc.metrics_text(purge, json.loads(result_line(code=1)))
    assert "openit_job_last_exit_code 1\n" in failed
    assert "last_success" not in failed  # Pushgateway 의 POST 는 같은 이름의 지표만 바꾸므로 마지막 성공 시각이 남는다
    assert sc.push_path("PURGE_EXPIRED") == "/metrics/job/openit-jobs/job_name/PURGE_EXPIRED"


def test_job_presence_rules_exist_for_every_scheduled_job_and_wait_two_periods(sc: ModuleType) -> None:
    schedules = sc.build_schedules({"survey-service": SURVEY_JOBS})
    document = yaml.safe_load(sc.job_rules_yaml(schedules))
    rules = {rule["labels"]["job_name"]: rule for rule in document["groups"][0]["rules"]}
    assert set(rules) == {s.job for s in schedules}
    assert rules["BACKUP"]["for"] == "172800s" and rules["PURGE_EXPIRED"]["for"] == "1800s"
    assert 'job_name="BACKUP"' in rules["BACKUP"]["expr"] and rules["BACKUP"]["expr"].startswith("absent(")
    assert yaml.safe_load(sc.job_rules_yaml([])) == {"groups": []}


def test_static_job_rules_use_the_same_push_job_and_metric_names(sc: ModuleType) -> None:
    """플랫폼의 정적 규칙·긁기 설정과 deploy 가 올리는 지표의 이름이 같다(어긋나면 경보가 조용하다)."""
    rules = (REPO / "platform" / "monitoring" / "rules.yml").read_text(encoding="utf-8")
    config = yaml.safe_load((REPO / "platform" / "monitoring" / "prometheus.yml").read_text(encoding="utf-8"))
    scrape = next(job for job in config["scrape_configs"] if job["job_name"] == sc.PUSH_JOB)
    assert scrape["honor_labels"] is True and scrape["static_configs"][0]["targets"] == ["pushgateway:9091"]
    assert "/etc/prometheus/job-rules.yml" in config["rule_files"]
    metrics = sc.metrics_text(by_job(sc.build_schedules({"survey-service": SURVEY_JOBS}))["BACKUP"], json.loads(result_line("BACKUP")))
    for name in ("openit_job_last_exit_code", "openit_job_last_success_timestamp_seconds", "openit_job_period_seconds"):
        assert name in metrics and name in rules
    assert f'job="{sc.PUSH_JOB}"' in rules


def test_product_compose_has_the_pushgateway_inside_the_backend_network_only() -> None:
    compose = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))["services"]
    gateway, client, prometheus = compose["pushgateway"], compose["pushgateway-client"], compose["prometheus"]
    assert gateway["image"] == client["image"] and "@sha256:" in gateway["image"]  # 같은 이미지, digest 고정
    assert gateway["labels"]["io.openit.service"] == client["labels"]["io.openit.service"] == "platform"
    assert "ports" not in gateway and gateway["networks"] == client["networks"] == ["backend"]  # 호스트 포트 없음, 안쪽 네트워크뿐
    assert client["profiles"] == ["tools"] and "profiles" not in gateway  # 일회용 클라이언트는 up 이 띄우지 않는다
    assert gateway["read_only"] is True and gateway["cap_drop"] == ["ALL"]
    assert "--persistence.file" not in " ".join(gateway.get("command", []))  # 영속을 쓰지 않는 선택(ADR 0028)
    assert "./generated/monitoring/job-rules.yml:/etc/prometheus/job-rules.yml:ro" in prometheus["volumes"]


def test_the_generated_job_rule_file_is_one_of_the_files_that_recreate_prometheus() -> None:
    script = (REPO / "deploy" / "deploy").read_text(encoding="utf-8")
    assert 'JOB_RULES: ("prometheus",)' in script and 'JOB_RULES = "monitoring/job-rules.yml"' in script
