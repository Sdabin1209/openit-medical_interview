"""명령 인자 규약."""

from __future__ import annotations

from pathlib import Path

import pytest

from openit_e2e import cli


def test_pipeline_takes_no_adapters_and_fixes_the_profile() -> None:
    assert cli.parse(["--mode", "pipeline"]).profile == "gpu-12g"
    with pytest.raises(SystemExit):
        cli.parse(["--mode", "pipeline", "--adapters-a", "a"])
    with pytest.raises(SystemExit):
        cli.parse(["--mode", "pipeline", "--profile", "rtx4090-24g"])


def test_product_needs_both_adapters_and_a_profile() -> None:
    args = cli.parse(["--mode", "product", "--adapters-a", "a", "--adapters-b", "b", "--profile", "rtx4090-24g"])
    assert args.adapters_a == Path("a") and args.profile == "rtx4090-24g"
    for missing in (
        ["--adapters-b", "b", "--profile", "p"],
        ["--adapters-a", "a", "--profile", "p"],
        ["--adapters-a", "a", "--adapters-b", "b"],
    ):
        with pytest.raises(SystemExit):
            cli.parse(["--mode", "product", *missing])


def test_unknown_mode_is_refused() -> None:
    with pytest.raises(SystemExit):
        cli.parse(["--mode", "full"])
