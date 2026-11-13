"""Run ``scripts/check_skill_sync.py`` under pytest.

The checker is a standalone script first, so it works in any environment
without pytest installed. This wrapper only exposes it as a test so a
repository check picks it up automatically.

Point it at the build under test the same way:

    KSEF2_BIN=~/.local/bin/ksef2 pytest -q
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_skill_sync.py"


def _binary() -> str | None:
    return os.environ.get("KSEF2_BIN") or shutil.which("ksef2")


requires_cli = pytest.mark.skipif(
    _binary() is None,
    reason="ksef2 executable not found; set KSEF2_BIN or install ksef2-cli",
)


def _load():
    spec = importlib.util.spec_from_file_location("check_skill_sync", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register before executing: the module defines a dataclass, whose field
    # resolution looks the defining module up in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@requires_cli
def test_skill_matches_installed_packages(tmp_path: Path) -> None:
    """Every documented command, flag, default, and API still holds."""
    module = _load()
    binary = _binary()
    python = sys.executable

    workdir = tmp_path
    env = module.make_sandbox(workdir, binary)
    report = module.Report()
    tree: dict[str, str] = {}

    def command_surface() -> None:
        tree.update(module.command_tree(binary))
        module.check_groups(report, tree)
        module.check_pagination(report, tree)
        module.check_global_options(report, tree)
        module.check_wait_defaults(report, tree)

    steps = [
        ("versions", lambda: module.check_versions(report, binary, python)),
        (
            "cli examples",
            lambda: module.check_cli_commands(report, binary, REPO, env, workdir),
        ),
        ("command surface", command_surface),
        (
            "failure modes",
            lambda: module.check_documented_failures(report, binary, env),
        ),
        ("python floor", lambda: module.check_python_floor(report, python)),
        ("sdk symbols", lambda: module.check_sdk_symbols(report, python)),
        ("sdk defaults", lambda: module.check_sdk_defaults(report, python)),
        (
            "runnable examples",
            lambda: module.check_runnable_examples(report, python, REPO, env, workdir),
        ),
    ]
    for name, step in steps:
        report.section = name
        step()

    assert not report.failures, "\n".join(report.failures)


@requires_cli
def test_checker_reports_drift(tmp_path: Path) -> None:
    """A broken documented command must make the check fail, not pass quietly."""
    module = _load()
    binary = _binary()
    env = module.make_sandbox(tmp_path, binary)

    broken = tmp_path / "repo"
    (broken / "skills").mkdir(parents=True)
    (broken / "skills" / "drift.md").write_text(
        "```bash\nksef2 invoices no-such-subcommand\n```\n", encoding="utf-8"
    )

    report = module.Report(section="drift")
    module.check_cli_commands(report, binary, broken, env, tmp_path)
    assert report.failures, "the checker passed a repository with invented commands"


@requires_cli
def test_examples_are_marked_for_execution() -> None:
    """The references must keep marking credential-free examples as runnable."""
    module = _load()
    marked = [
        (path, offset)
        for path, offset, info, _ in module.markdown_blocks(REPO)
        if info in {"python exec", "bash exec"}
    ]
    assert len(marked) >= 3, (
        "expected at least three runnable examples; a sync that removes them "
        "silently stops executing anything"
    )
