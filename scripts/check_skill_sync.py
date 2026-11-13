#!/usr/bin/env python3
"""Check this repository against the installed ksef2 SDK and ksef2-cli.

Offline by design: it never contacts KSeF, needs no credentials, and runs no
state-changing command. CLI examples are validated by appending ``--help``,
which makes the parser check the command path, every option, option placement,
and choice values, then exit before authenticating or sending a request.

Run it with the interpreter that has the packages under test:

    python scripts/check_skill_sync.py

Environment overrides:

    KSEF2_BIN     ksef2 executable to check      (default: found on PATH)
    KSEF2_PYTHON  interpreter with ksef2 importable (default: this interpreter,
                  then the ``python3`` on PATH)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# What this repository documents. The version checks below compare these to the
# installed packages, so bump them together with the prose.
DOCUMENTED_SDK_VERSION = "1.3.0"
DOCUMENTED_CLI_VERSION = "1.1.0"

# Groups documented in references/cli.md ("Group map"). Must equal the real set.
DOCUMENTED_GROUPS = {
    "auth",
    "batch",
    "certificates",
    "collective",
    "config",
    "encryption",
    "fa3",
    "invoices",
    "limits",
    "online",
    "peppol",
    "permissions",
    "profile",
    "sessions",
    "testdata",
    "tokens",
}

# Pagination families documented in references/cli.md.
DOCUMENTED_OFFSET_PAGING = {
    "invoices metadata",
    "certificates list",
    "tokens list",
    "collective list",
    "collective list-for-invoice",
    "collective list-invoices",
    "peppol providers",
    "permissions entity-roles",
    "permissions query",
    "sessions auth-list",
    "sessions invoice-list",
}
DOCUMENTED_PAGE_OFFSET = {
    "invoices metadata",
    "certificates list",
    "peppol providers",
    "permissions entity-roles",
    "permissions query",
}
DOCUMENTED_CONTINUATION = {"online list", "batch list"}

# Import paths documented as stable, with the symbols this repository names.
# A dotted path under "ksef2" with no underscore-prefixed segment is public.
DOCUMENTED_SDK_SYMBOLS: dict[str, list[str]] = {
    "ksef2": [
        "Client",
        "AsyncClient",
        "Environment",
        "TransportConfig",
        "TimeoutConfig",
        "RetryConfig",
        "TlsConfig",
        "ConnectionPoolConfig",
        "FormSchema",
        "KSeFException",
        "KSeFApiError",
        "KSeFTransportError",
        "KSeFNotReadyError",
        "KSeFRateLimitError",
        "KSeFValidationError",
        "KSeFPollingTimeoutError",
        "KSeFInvoiceRejectedError",
        "KSeFSessionFailedError",
        "KSeFAuthenticationExpiredError",
        "KSeFArgumentError",
        "KSeFUnsupportedEnvironmentError",
        "KSeFAuthTokenRedemptionError",
        "__version__",
    ],
    "ksef2.clients": [
        "InvoicesService",
        "BatchService",
        "InvoiceSubmission",
        "ExportJob",
        "GeneratedToken",
        "PermissionOperation",
        "CertificateEnrollment",
        "ExportedInvoices",
        "Pager",
        "OperationHandle",
        "InvoiceSearchPager",
        "AsyncInvoicesService",
        "AsyncBatchService",
        "AsyncInvoiceSubmission",
        "AsyncExportJob",
        "AsyncGeneratedToken",
        "AsyncPermissionOperation",
        "AsyncCertificateEnrollment",
        "AsyncPager",
        "AsyncOperationHandle",
    ],
    "ksef2.models": [
        "InvoicesFilter",
        "InvoiceMetadataParams",
        "Page",
        "XAdESCredentials",
        "PreparedBatch",
    ],
    "ksef2.fa3": ["InvoiceBuilder", "KsefInvoiceDraft", "VatRate"],
    "ksef2.xades": [
        "XAdESCredentials",
        "load_certificate_from_pem",
        "load_certificate_and_key_from_p12",
        "LocalSigner",
    ],
    "ksef2.profiles": ["Profile", "ProfileStore"],
    "ksef2.logging": ["configure_logging"],
    "ksef2.certificate_stores": [],
    "ksef2.testdata": ["generate_nip", "generate_pesel"],
    "ksef2.renderers": ["InvoiceXSLTRenderer", "InvoicePDFExporter"],
    "ksef2.raw": [],
    "ksef2.raw.mappers": [],
}

# Defaults documented in references/sdk-api.md ("Retries and transport").
DOCUMENTED_RETRY_DEFAULTS = {
    "max_attempts": 3,
    "initial_delay": 0.5,
    "max_delay": 4.0,
    "backoff_multiplier": 2.0,
    "max_retry_after": 120.0,
    "retryable_status_codes": (429, 502, 503, 504),
    "jitter": True,
}

# Environment base URLs documented in references/sdk-api.md.
DOCUMENTED_BASE_URLS = {
    "TEST": "https://api-test.ksef.mf.gov.pl/v2",
    "DEMO": "https://api-demo.ksef.mf.gov.pl/v2",
    "PRODUCTION": "https://api.ksef.mf.gov.pl/v2",
}

# Wait-flag defaults documented in references/cli.md ("Async workflows").
DOCUMENTED_WAIT_DEFAULTS = {
    "invoices send": {"--timeout": "120.0", "--poll-interval": "2.0"},
    "online send": {"--timeout": "60.0", "--poll-interval": "2.0"},
    "invoices status": {"--timeout": "120.0", "--poll-interval": "2.0"},
    "batch submit": {"--timeout": "120.0", "--poll-interval": "2.0"},
}

# Global options documented in the cli.md global options table.
DOCUMENTED_GLOBAL_OPTIONS = {
    "--env",
    "-e",
    "--json",
    "--output",
    "--profile",
    "--nip",
    "--token",
    "--ksef-token",
    "--context-type",
    "--test-cert",
    "--cert",
    "--key",
    "--p12",
    "--auth-state",
    "--config",
    "--no-config",
    "--verbose",
    "-v",
    "--version",
    "--key-password",
    "--p12-password",
    "--auth-timeout",
    "--auth-poll-interval",
}

# Profiles the references name in examples. The checker creates throwaway TEST
# profiles under these names in a temporary config so the documented command
# lines resolve; no credential and no real profile is ever read.
DOCUMENTED_PROFILES = ["test-company", "acme", "prod-token"]

# Commands the references show as failing, with the exit code they document.
# Each is checked for real: they all fail locally, before any request.
DOCUMENTED_FAILURES = [
    (
        "unknown command exits 2",
        ["bogus-command"],
        2,
    ),
    (
        "global option placed after the group exits 2",
        ["invoices", "--json", "metadata", "--help"],
        2,
    ),
    (
        "two authentication methods at once exits 1",
        [
            "--no-config",
            "--env",
            "test",
            "--nip",
            "5261040828",
            "--test-cert",
            "--token",
            "not-a-real-token",
            "--json",
            "auth",
            "login",
        ],
        1,
    ),
    (
        "TEST certificate against PRODUCTION exits 2",
        [
            "--no-config",
            "--env",
            "production",
            "--nip",
            "5261040828",
            "--test-cert",
            "--json",
            "auth",
            "login",
        ],
        2,
    ),
]


# Some documented command lines exist to show a failure. Keyed by their exact
# arguments, these are checked for the exit code the prose states instead of 0.
DOCUMENTED_EXAMPLE_FAILURES: dict[tuple[str, ...], int] = {
    tuple("--env production --nip 5261040828 --test-cert --json auth login".split()): 2,
    tuple(
        "--env test --nip 5261040828 --test-cert --token check-only --json auth login".split()
    ): 1,
}


# Option defaults documented in references/cli.md, checked against --help.
DOCUMENTED_OPTION_DEFAULTS = {
    "invoices metadata": {
        "--page-size": "10",
        "--page-offset": "0",
        "--role": "seller",
        "--date-type": "issue_date",
        "--amount-type": "brutto",
    },
    "invoices send": {"--form": "FA3"},
}


@dataclass
class Report:
    passed: int = 0
    failures: list[str] = field(default_factory=list)
    section: str = ""

    def ok(self, detail: str) -> None:
        self.passed += 1
        print(f"  ok   {detail}")

    def fail(self, detail: str) -> None:
        self.failures.append(f"[{self.section}] {detail}")
        print(f"  FAIL {detail}")

    def check(self, condition: bool, ok_detail: str, fail_detail: str) -> bool:
        if condition:
            self.ok(ok_detail)
        else:
            self.fail(fail_detail)
        return condition


# --------------------------------------------------------------------------
# helpers


def run(
    cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env
        or {
            **os.environ,
            "KSEF2_CONFIG": "/nonexistent-for-check.toml",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "COLUMNS": "200",
        },
    )


def markdown_blocks(repo: Path) -> list[tuple[Path, int, str, list[str]]]:
    """Yield (file, first line number, fence info, lines) for fenced blocks."""
    out: list[tuple[Path, int, str, list[str]]] = []
    for path in sorted(repo.rglob("*.md")):
        if ".git" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            match = re.match(r"^\s*```(.*)$", lines[i])
            if not match:
                i += 1
                continue
            info, start, body = match.group(1).strip(), i + 1, []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```\s*$", lines[i]):
                body.append(lines[i])
                i += 1
            out.append((path, start, info, body))
            i += 1
    return out


def join_continuations(body: list[str]) -> list[tuple[int, str]]:
    """Join backslash-continued lines; return (index into body, command)."""
    commands: list[tuple[int, str]] = []
    buffer, start = "", 0
    for index, line in enumerate(body):
        stripped = line.strip()
        if not buffer:
            start = index
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        commands.append((start, (buffer + stripped).strip()))
        buffer = ""
    if buffer:
        commands.append((start, buffer.strip()))
    return commands


PLACEHOLDER = re.compile(r"\[[A-Z ]+\]")

# Angle-bracket arguments in the references stand for a value the reader fills
# in. Substituting a benign value keeps the command runnable for parsing while
# still checking the real option name around it.
ARG_PLACEHOLDERS = {
    "<value>": "check-only",
    "<ref>": "check-ref",
    "<export-ref>": "check-export-ref",
    "<n>": "30",
}

# ``$VAR`` in a documented command line names an environment variable the user
# exports. The checker substitutes its own values so the line parses; the real
# variable is never read.
SHELL_EXPANSIONS = {
    "KSEF2_NIP": "5261040828",
    "KSEF2_TOKEN": "check-only-not-a-real-token",
}


def extract_cli_commands(repo: Path) -> list[tuple[Path, int, list[str]]]:
    """Every ``ksef2`` invocation in a bash/sh fence, as an argument list.

    Fenced ``text`` blocks are output samples rather than commands, and lines
    holding schematic placeholders such as ``[GLOBAL OPTIONS]`` or ``<value>``
    describe a shape instead of a runnable command; both are skipped.
    """
    found: list[tuple[Path, int, list[str]]] = []
    for path, offset, info, body in markdown_blocks(repo):
        if info not in {"bash", "sh", "console", "shell", "bash exec"}:
            continue
        for index, command in join_continuations(body):
            if not command.startswith("ksef2"):
                continue
            if PLACEHOLDER.search(command):
                continue
            for token, replacement in ARG_PLACEHOLDERS.items():
                command = command.replace(token, replacement)
            # Shell expansions stand for values the sandbox supplies.
            command = re.sub(
                r"\$\{?(\w+)\}?",
                lambda m: SHELL_EXPANSIONS.get(m.group(1), m.group(0)),
                command,
            )
            command = re.sub(r"\s+#.*$", "", command).strip()
            try:
                argv = shlex.split(command)
            except ValueError:
                continue
            if argv[0] == "ksef2-cli":
                argv[0] = "ksef2"
            # Installation commands belong to pip/uv/pipx, not to the CLI itself.
            if len(argv) > 1 and argv[1] in {"install", "add", "tool", "pipx", "index"}:
                continue
            found.append((path, offset + index + 1, argv[1:]))
    return found


def make_sandbox(tmp: Path, ksef2_bin: str) -> dict[str, str]:
    """Create the profile names the references use, in a throwaway config.

    Returns the environment to run documented commands under. Nothing here
    touches the user's real config, and no secret value is written: the TEST
    profiles authenticate with a locally generated certificate, and the token
    variables are set to a dummy string purely so that a documented command
    line parses.
    """
    env_path = os.environ.get("PATH", "/usr/bin")
    # Remove the real user config from the picture before anything else runs.
    os.environ.pop("KSEF2_CONFIG", None)
    config = tmp / "check-config.toml"
    # Put the checked executable on PATH so a marked example can call `ksef2`
    # exactly as the reference shows it.
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    link = bin_dir / "ksef2"
    if not link.exists():
        link.symlink_to(Path(ksef2_bin).resolve())
    env = {
        **os.environ,
        "KSEF2_CONFIG": str(config),
        "NO_COLOR": "1",
        "TERM": "dumb",
        "COLUMNS": "200",
        "PATH": f"{bin_dir}{os.pathsep}" + env_path,
    }
    # 5261040828 is the TEST example NIP the references already use.
    env["KSEF2_NIP"] = "5261040828"
    env["KSEF2_TOKEN"] = "check-only-not-a-real-token"
    for name in DOCUMENTED_PROFILES:
        subprocess.run(
            [
                ksef2_bin,
                "profile",
                "create",
                name,
                "--env",
                "test",
                "--nip",
                "5261040828",
                "--test-cert",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
    if not config.exists():
        raise SystemExit(
            f"error: could not create the throwaway profiles in {config}; "
            "the documented --profile examples cannot be resolved"
        )
    return env


# --------------------------------------------------------------------------
# checks


def check_versions(report: Report, ksef2_bin: str, python: str) -> None:
    proc = run([ksef2_bin, "--version"])
    if report.check(
        proc.returncode == 0, "--version runs", f"--version exited {proc.returncode}"
    ):
        text = proc.stdout
        print(textwrap.indent(text.strip(), "         "))
        report.check(
            f"ksef2-cli {DOCUMENTED_CLI_VERSION}" in text,
            f"CLI reports documented version {DOCUMENTED_CLI_VERSION}",
            f"CLI reports something other than {DOCUMENTED_CLI_VERSION}: {text.strip()!r}",
        )
        report.check(
            f"ksef2 {DOCUMENTED_SDK_VERSION}" in text,
            f"SDK reports documented version {DOCUMENTED_SDK_VERSION}",
            f"SDK reports something other than {DOCUMENTED_SDK_VERSION}: {text.strip()!r}",
        )

    # Version claims about the release the skill documents must match what runs.
    # Historical notes elsewhere in the prose ("ksef2 1.2.0 added ...") are not
    # claims about the current release and are deliberately not matched here.
    checked = 0
    for path in sorted(REPO.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO)
        for match in re.finditer(
            r"Written for `ksef2-cli ([\d.]+)`(?:\s*/\s*`ksef2 ([\d.]+))?"
            r"|Written for `ksef2 ([\d.]+)`",
            text,
        ):
            cli_ver = match.group(1)
            sdk_ver = match.group(2) or match.group(3)
            if cli_ver:
                checked += 1
                report.check(
                    cli_ver == DOCUMENTED_CLI_VERSION,
                    f"{relative} documents CLI {cli_ver}",
                    f"{relative} says 'Written for ksef2-cli {cli_ver}' but "
                    f"the installed CLI is {DOCUMENTED_CLI_VERSION}",
                )
            if sdk_ver:
                checked += 1
                report.check(
                    sdk_ver == DOCUMENTED_SDK_VERSION,
                    f"{relative} documents SDK {sdk_ver}",
                    f"{relative} says 'Written for ksef2 {sdk_ver}' but "
                    f"the installed SDK is {DOCUMENTED_SDK_VERSION}",
                )
        for match in re.finditer(r"version (\d+\.\d+\.\d+)", text):
            checked += 1
            line = text[: match.start()].count("\n") + 1
            is_cli = "ksef2-cli" in text[max(0, match.start() - 400) : match.start()]
            expected = DOCUMENTED_CLI_VERSION if is_cli else DOCUMENTED_SDK_VERSION
            report.check(
                match.group(1) == expected,
                f"{relative}:{line} pins {match.group(1)}",
                f"{relative}:{line} pins {match.group(1)} but the installed "
                f"release is {expected}",
            )
    report.check(
        checked >= 4,
        f"{checked} prose version claims cross-checked",
        f"only {checked} prose version claims found; the check is too weak",
    )


def check_cli_commands(
    report: Report, ksef2_bin: str, repo: Path, env: dict[str, str], workdir: Path
) -> None:
    """Validate each documented command line by parsing it.

    ``--help`` makes the parser resolve the command path, every option, option
    placement, and choice values, then exit before authenticating or sending a
    request. A documented line that no longer parses is drift in either the
    reference or the installed CLI.
    """
    commands = extract_cli_commands(repo)
    if not report.check(
        bool(commands),
        f"found {len(commands)} CLI examples",
        "no ksef2 CLI examples found in any markdown file",
    ):
        return

    def probe_command(item: tuple[Path, int, list[str]]) -> tuple[str, bool, str]:
        path, line, argv = item
        expected = DOCUMENTED_EXAMPLE_FAILURES.get(tuple(argv))
        # A documented failure is a real behaviour claim, so run it for real;
        # every such example is designed to fail locally, before any request.
        probe = list(argv) if expected is not None else [*argv, "--help"]
        proc = run([ksef2_bin, *probe], cwd=workdir, env=env)
        location = f"{path.relative_to(repo)}:{line}"
        shown = " ".join(argv)
        want = expected if expected is not None else 0
        detail = f"{location}  ksef2 {shown}"
        if expected is not None:
            detail = f"{location}  documented failure exits {expected}: ksef2 {shown}"
        if proc.returncode == want:
            return detail, True, ""
        first = next(
            (
                ln.strip()
                for ln in (proc.stderr + proc.stdout).splitlines()
                if ln.strip().lower().startswith("error")
            ),
            (proc.stderr or proc.stdout).strip()[:160] or "no error line",
        )
        return detail, False, f"exit {proc.returncode}: {first}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe_command, commands))
    for detail, passed, error in results:
        report.check(passed, detail, f"{detail} -> {error}")


_HELP_CACHE: dict[tuple[str, tuple[str, ...]], str] = {}


_TREE_CACHE: dict[str, dict[str, str]] = {}


def command_tree(ksef2_bin: str) -> dict[str, str]:
    """Full command-path to help-text map, built once per binary per process."""
    if ksef2_bin not in _TREE_CACHE:
        with ThreadPoolExecutor(max_workers=8) as pool:
            _TREE_CACHE[ksef2_bin] = walk_commands(ksef2_bin, 3, pool)
    return _TREE_CACHE[ksef2_bin]


def cli_help(ksef2_bin: str, argv: list[str]) -> str:
    key = (ksef2_bin, tuple(argv))
    if key not in _HELP_CACHE:
        proc = run([ksef2_bin, *argv, "--help"])
        _HELP_CACHE[key] = proc.stdout + proc.stderr
    return _HELP_CACHE[key]


def walk_commands(
    ksef2_bin: str,
    max_depth: int = 3,
    pool: ThreadPoolExecutor | None = None,
) -> dict[str, str]:
    """Map every command path to its help text.

    Walked level by level so a worker never waits on work queued behind
    itself. Each ``--help`` is a fresh interpreter start and the tree runs to
    over a hundred nodes, so siblings are fetched together.
    """
    panel = "\u256d\u2500 Commands \u2500"

    def children_of(text: str) -> list[str]:
        if panel not in text:
            return []
        section = text.split(panel, 1)[1].split("\u2570")[0]
        return [
            m.group(1)
            for m in re.finditer(
                r"^(?:\u2502\s*)?([a-z][a-z0-9-]*)\s{2,}", section, re.M
            )
            if m.group(1) != "help"
        ]

    out: dict[str, str] = {"": cli_help(ksef2_bin, [])}
    frontier: list[list[str]] = [[c] for c in children_of(out[""])]
    depth = 1
    while frontier and depth <= max_depth:
        if pool is None:
            texts = [cli_help(ksef2_bin, path) for path in frontier]
        else:
            texts = list(pool.map(lambda path: cli_help(ksef2_bin, path), frontier))
        nxt: list[list[str]] = []
        for path, text in zip(frontier, texts):
            out[" ".join(path)] = text
            if depth < max_depth:
                nxt.extend(path + [child] for child in children_of(text))
        frontier, depth = nxt, depth + 1
    return out


def check_groups(report: Report, tree: dict[str, str]) -> None:
    real = set(
        tree[""].split("╭─ Commands ─", 1)[1:2]
        and [
            m.group(1)
            for m in re.finditer(
                r"^(?:│\s*)?([a-z][a-z0-9-]*)\s{2,}",
                tree[""].split("╭─ Commands ─", 1)[1].split("╰")[0],
                re.M,
            )
        ]
        or set()
    )
    real.discard("help")
    missing = sorted(DOCUMENTED_GROUPS - real)
    extra = sorted(real - DOCUMENTED_GROUPS)
    report.check(
        not missing,
        f"all {len(DOCUMENTED_GROUPS)} documented groups exist",
        f"documented group map names unknown groups: {missing}",
    )
    report.check(
        not extra,
        "documented group map is complete",
        f"CLI has groups the documented map omits: {extra}",
    )


def check_pagination(report: Report, tree: dict[str, str]) -> None:
    for option, documented in (
        ("--all", DOCUMENTED_OFFSET_PAGING),
        ("--page-offset", DOCUMENTED_PAGE_OFFSET),
        ("--continuation-token", DOCUMENTED_CONTINUATION),
    ):
        real = {
            path
            for path, text in tree.items()
            if path and option in text and "╭─ Commands ─" not in text
        }
        if option == "--all":
            # --all also appears on commands that merely mention it in help text;
            # restrict to leaves that actually declare it as an option.
            real = {
                path
                for path in real
                if re.search(rf"^\s*│?\s*{re.escape(option)}\s", tree[path], re.M)
            }
        missing = sorted(documented - real)
        report.check(
            not missing,
            f"{option} documented only on commands that support it ({len(documented)})",
            f"{option} documented on commands that do not offer it: {missing}",
        )


def check_global_options(report: Report, tree: dict[str, str]) -> None:
    root = tree[""]
    for option in sorted(DOCUMENTED_GLOBAL_OPTIONS):
        report.check(
            option in root,
            f"global option {option} documented and real",
            f"documented global option {option} is not in 'ksef2 --help'",
        )
    # Every option the real CLI offers globally should be documented.
    declared = set(
        re.findall(
            r"│ (?:-[a-z], )?\s*(--[a-z][a-z0-9-]*)",
            root.split("╭─ Options", 1)[1].split("╰", 1)[0],
        )
    )
    declared |= {m.group(1) for m in re.finditer(r"│\s+(-[a-z])\s", root)}
    # --no-pretty/--pretty and completion helpers are renderer plumbing, not auth.
    ignored = {"--install-completion", "--show-completion", "--help", "-h"}
    undocumented = sorted(declared - DOCUMENTED_GLOBAL_OPTIONS - ignored)
    report.check(
        not undocumented,
        "global options table covers the CLI's global options",
        f"global options the CLI offers but the table omits: {undocumented}",
    )


def option_default(help_text: str, option: str) -> str | None:
    """Read ``[default: ...]`` from the block that declares ``option``.

    Rich wraps option help across several rows, so the block runs from the
    option to the next option declaration rather than a fixed character window.
    """
    starts = [
        m.start() for m in re.finditer(r"^\s*│?\s*(?:-[a-z], )?--", help_text, re.M)
    ]
    for index, start in enumerate(starts):
        line = help_text[start:].splitlines()[0]
        if re.search(rf"(?:^|\s){re.escape(option)}(?=\s|$|,)", line):
            end = starts[index + 1] if index + 1 < len(starts) else len(help_text)
            match = re.search(r"\[default: ([^\]\n]+)\]", help_text[start:end])
            return match.group(1).strip() if match else None
    return None


def check_wait_defaults(report: Report, tree: dict[str, str]) -> None:
    for command, expected in {
        **DOCUMENTED_WAIT_DEFAULTS,
        **DOCUMENTED_OPTION_DEFAULTS,
    }.items():
        text = tree.get(command, "")
        if not report.check(
            bool(text), f"{command} exists", f"{command} not found in CLI"
        ):
            continue
        for option, default in expected.items():
            actual = option_default(text, option)
            report.check(
                actual == default,
                f"{command} {option} defaults to {default}",
                f"{command} {option} default is {actual!r}, docs say {default!r}",
            )


def check_documented_failures(
    report: Report, ksef2_bin: str, env: dict[str, str]
) -> None:
    for label, argv, expected in DOCUMENTED_FAILURES:
        proc = run([ksef2_bin, *argv], env=env)
        report.check(
            proc.returncode == expected,
            f"{label} (exit {expected})",
            f"{label}: got exit {proc.returncode}, docs say {expected} :: "
            f"{(proc.stderr or proc.stdout).strip()[:160]}",
        )


def check_python_floor(report: Report, python: str) -> None:
    code = "import sys;print('.'.join(map(str, sys.version_info[:3])))"
    proc = run([python, "-c", code])
    if not report.check(
        proc.returncode == 0, "python probe runs", "python probe failed"
    ):
        return
    version = tuple(int(p) for p in proc.stdout.strip().split(".")[:2])
    report.check(
        version >= (3, 12),
        f"interpreter {proc.stdout.strip()} meets the documented 3.12+ floor",
        f"interpreter {proc.stdout.strip()} is below the documented 3.12+ floor",
    )


def check_sdk_symbols(report: Report, python: str) -> None:
    script = r"""
import importlib, json, sys
symbols = json.loads(sys.argv[1])
result = {}
for mod, names in symbols.items():
    try:
        module = importlib.import_module(mod)
    except Exception as exc:
        result[mod] = {"import_error": type(exc).__name__ + ": " + str(exc)}
        continue
    result[mod] = {
        "missing": [n for n in names if not hasattr(module, n)],
        "public": all(not part.startswith("_") for part in mod.split(".")[1:]),
    }
print(json.dumps(result))
"""
    proc = run([python, "-c", script, json.dumps(DOCUMENTED_SDK_SYMBOLS)])
    if proc.returncode != 0:
        report.fail(f"SDK symbol probe failed: {proc.stderr.strip()[:300]}")
        return
    data = json.loads(proc.stdout)
    for mod, info in data.items():
        if "import_error" in info:
            report.fail(f"import {mod} -> {info['import_error']}")
            continue
        names = DOCUMENTED_SDK_SYMBOLS[mod]
        report.check(
            not info["missing"],
            f"{mod}: all {len(names)} documented symbols exist"
            if names
            else f"{mod}: importable",
            f"{mod}: missing documented symbols {info['missing']}",
        )
        report.check(
            info["public"],
            f"{mod} is a public path",
            f"{mod} reaches a private module but is documented as stable",
        )


def check_sdk_defaults(report: Report, python: str) -> None:
    script = r"""
import json
from ksef2 import RetryConfig, TimeoutConfig, TransportConfig, Environment
retry = RetryConfig()
print(json.dumps({
    "retry": {k: getattr(retry, k) for k in [
        "max_attempts", "initial_delay", "max_delay", "backoff_multiplier",
        "max_retry_after", "retryable_status_codes", "jitter"]},
    "auto_refresh": TransportConfig().auto_refresh_tokens,
    "urls": {e.name: e.base_url for e in Environment},
}))
"""
    proc = run([python, "-c", script])
    if proc.returncode != 0:
        report.fail(f"SDK config probe failed: {proc.stderr.strip()[:300]}")
        return
    data = json.loads(proc.stdout)
    actual = {
        k: tuple(v) if isinstance(v, list) else v for k, v in data["retry"].items()
    }
    for key, expected in DOCUMENTED_RETRY_DEFAULTS.items():
        value = actual.get(key)
        report.check(
            value == expected,
            f"RetryConfig.{key} = {expected}",
            f"RetryConfig.{key} is {value!r}, docs say {expected!r}",
        )
    report.check(
        data["auto_refresh"] is True,
        "TransportConfig(auto_refresh_tokens=True) is the default",
        f"auto_refresh_tokens default is {data['auto_refresh']!r}, docs say True",
    )
    for name, url in DOCUMENTED_BASE_URLS.items():
        report.check(
            data["urls"].get(name) == url,
            f"Environment.{name} -> {url}",
            f"Environment.{name} is {data['urls'].get(name)!r}, docs say {url!r}",
        )


def check_runnable_examples(
    report: Report, python: str, repo: Path, env: dict[str, str], workdir: Path
) -> None:
    """Run every fence marked ``python exec`` or ``bash exec`` in the repository.

    Marking is deliberate: only examples that need no KSeF credentials are
    marked, so the whole check stays offline. Blocks that authenticate are
    labelled as needing credentials in the prose and stay unmarked.
    """
    ran = 0
    for path, offset, info, body in markdown_blocks(repo):
        if info not in {"python exec", "bash exec"}:
            continue
        script = textwrap.dedent("\n".join(body))
        location = f"{path.relative_to(repo)}:{offset}"
        lang = info.split()[0]
        command = [python, "-c", script] if lang == "python" else ["bash", "-c", script]
        proc = run(command, cwd=workdir, env=env)
        ran += 1
        report.check(
            proc.returncode == 0,
            f"runnable example {location} exits 0",
            f"runnable example {location} exited {proc.returncode} :: "
            f"{(proc.stderr or proc.stdout).strip()[-400:]}",
        )
    if not report.check(
        ran > 0,
        f"{ran} marked examples executed",
        "no 'python exec' or 'bash exec' examples found to run",
    ):
        report.fail(
            "the references mark no runnable examples; the check would pass vacuously"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(REPO), help="repository root to check")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    ksef2_bin = os.environ.get("KSEF2_BIN") or shutil.which("ksef2")
    if not ksef2_bin:
        print(
            "error: no ksef2 executable found. Set KSEF2_BIN or put it on PATH.",
            file=sys.stderr,
        )
        return 2
    python = os.environ.get("KSEF2_PYTHON") or sys.executable
    probe = run([python, "-c", "import ksef2"])
    if probe.returncode != 0 and shutil.which("python3"):
        python = shutil.which("python3")

    report = Report()
    print(f"ksef2 binary: {ksef2_bin}")
    print(f"python:       {python}")
    print(f"repo:         {repo}\n")

    with tempfile.TemporaryDirectory(prefix="ksef2-skill-check-") as tmpname:
        workdir = Path(tmpname)
        env = make_sandbox(workdir, ksef2_bin)
        status = run_all(report, ksef2_bin, python, repo, env, workdir)
    return status


def run_all(
    report: Report,
    ksef2_bin: str,
    python: str,
    repo: Path,
    env: dict[str, str],
    workdir: Path,
) -> int:
    tree: dict[str, str] = {}

    def command_surface() -> None:
        tree.update(command_tree(ksef2_bin))
        check_groups(report, tree)
        check_pagination(report, tree)
        check_global_options(report, tree)
        check_wait_defaults(report, tree)

    sections = [
        ("versions", lambda: check_versions(report, ksef2_bin, python)),
        (
            "cli examples",
            lambda: check_cli_commands(report, ksef2_bin, repo, env, workdir),
        ),
        ("command surface", command_surface),
        ("failure modes", lambda: check_documented_failures(report, ksef2_bin, env)),
        ("python floor", lambda: check_python_floor(report, python)),
        ("sdk symbols", lambda: check_sdk_symbols(report, python)),
        ("sdk defaults", lambda: check_sdk_defaults(report, python)),
        (
            "runnable examples",
            lambda: check_runnable_examples(report, python, repo, env, workdir),
        ),
    ]

    for name, fn in sections:
        report.section = name
        print(f"== {name}")
        fn()
        print()

    if report.failures:
        print(f"{len(report.failures)} FAILURE(S) / {report.passed} passed\n")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print(f"all {report.passed} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
