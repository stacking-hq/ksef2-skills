#!/usr/bin/env python3
"""Offline verification for the ksef2 skill.

Re-checks everything this skill documents against real artifacts — never
against memory:

  * CLI commands/flags  -> `ksef2 <group> <sub> --help` of the installed
                           ksef2-cli, and/or a pinned source checkout's
                           generated docs/reference/commands.md
  * SDK import paths    -> import/getattr probes of the installed ksef2
  * SDK model fields    -> curated attribute/default checks on the installed ksef2
  * pinned source SHAs  -> `git rev-parse HEAD` of a given checkout
  * exit codes          -> local runs (`--help`, unknown command)

No KSeF host is ever contacted: only `--help` / `--version` / an unknown
command are executed, all of which exit before any network or credential use.
Live KSeF behavior (auth, sends, polling, downloads) is therefore *not*
covered — see ../provenance.md for the recorded run and its limitations.

Usage:
  python skills/ksef2/scripts/verify.py
  python skills/ksef2/scripts/verify.py --source /path/to/ksef2-cli \
                                        --source-sdk /path/to/ksef2
  python skills/ksef2/scripts/verify.py --python /path/to/venv/bin/python
  python skills/ksef2/scripts/verify.py --json

Exit code 0 = every check passed (SKIPs allowed), 1 = at least one FAIL.
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
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_FILE = SKILL_ROOT / "provenance.md"
REF_FILES = sorted((SKILL_ROOT / "references").glob("*.md"))

CMD_LANGS = {"", "bash", "sh", "shell"}

# Global options of ksef2-cli 1.0 (see pinned docs/reference/commands.md).
GLOBAL_VALUE_OPTS = {
    "--env", "-e", "--output", "-o", "--config", "--profile", "--nip",
    "--token", "--ksef-token", "--context-type", "--auth-state", "--cert",
    "--key", "--key-password", "--p12", "--p12-password",
    "--auth-poll-interval", "--auth-timeout",
}
GLOBAL_FLAG_OPTS = {
    "--version", "--json", "--verbose", "-v", "--no-config", "--test-cert",
    "--help", "-h", "--install-completion", "--show-completion",
}

HELP_ENV = {
    **os.environ,
    "COLUMNS": "240",      # keep long option names un-truncated in rich tables
    "NO_COLOR": "1",
    "TERM": "dumb",
}


class Report:
    def __init__(self, as_json: bool = False) -> None:
        self.rows: list[dict[str, str]] = []
        self.as_json = as_json

    def add(self, check: str, status: str, detail: str = "") -> None:
        self.rows.append({"check": check, "status": status, "detail": detail})
        if not self.as_json:
            print(f"{status:4}  {check}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> bool:
        return any(r["status"] == "FAIL" for r in self.rows)

    def finish(self) -> None:
        counts: dict[str, int] = {}
        for r in self.rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if self.as_json:
            print(json.dumps({"summary": counts, "checks": self.rows}, indent=2))
        else:
            print(f"\n{summary or 'no checks run'}")
            print(
                "Note: offline only — no KSeF request was made; live behavior "
                "is not covered (see ../provenance.md)."
            )


# ---------------------------------------------------------------- provenance

def parse_provenance() -> dict[str, dict[str, str]]:
    """Read the `sha=` / `version` pins from ../provenance.md."""
    if not PROVENANCE_FILE.is_file():
        return {}
    text = PROVENANCE_FILE.read_text(encoding="utf-8")
    pins: dict[str, dict[str, str]] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        label = None
        if "**ksef2-cli**" in line:
            label = "ksef2-cli"
        elif "**ksef2**" in line:
            label = "ksef2"
        if label is None:
            continue
        window = " ".join(lines[i:i + 3])
        sha = re.search(r"sha=([0-9a-f]{40})", window)
        ver = re.search(r"version\s+([0-9][0-9A-Za-z.+~-]*)", window)
        pins[label] = {
            "sha": sha.group(1) if sha else "",
            "version": ver.group(1) if ver else "",
        }
    return pins


# ------------------------------------------------------------ markdown parsing

def _fenced_blocks(text: str):
    for m in re.finditer(r"^```([a-zA-Z]*)\n(.*?)^```", text, re.S | re.M):
        yield (m.group(1) or "").lower(), m.group(2)


def extract_commands(path: Path) -> list[dict]:
    """Pull `ksef2 ...` invocations out of shell fences of one markdown file."""
    found: list[dict] = []
    for lang, body in _fenced_blocks(path.read_text(encoding="utf-8")):
        if lang not in CMD_LANGS:
            continue
        body = re.sub(r"\\\n", " ", body)          # join continuations
        for raw in body.splitlines():
            line = raw.strip()
            if not line.startswith("ksef2 ") or line.startswith("#"):
                continue
            try:
                tokens = shlex.split(line)
            except ValueError:
                continue
            if not tokens or tokens[0] != "ksef2":
                continue
            if re.search(r"\[GLOBAL|\[SUBCOMMAND|\[COMMAND", line):
                continue            # usage syntax line, not an invocation
            tokens = [t for t in tokens[1:] if not re.fullmatch(r"<[^>]*>", t)]
            # strip leading global options
            i = 0
            global_flags: list[str] = []
            while i < len(tokens) and tokens[i].startswith("-"):
                tok = tokens[i]
                base = tok.split("=", 1)[0]
                if base in GLOBAL_FLAG_OPTS:
                    global_flags.append(base)
                    i += 1
                elif base in GLOBAL_VALUE_OPTS:
                    global_flags.append(base)
                    i += 1 if "=" in tok else 2
                else:
                    break    # first token of the command group
            rest = tokens[i:]
            if not rest:
                found.append({"group": None, "sub": None, "flags": global_flags,
                              "file": path.name, "line": line})
                continue
            group = rest[0]
            if group.startswith("-") or group.startswith("["):
                continue
            sub = None
            j = 1
            if j < len(rest) and not rest[j].startswith("-"):
                sub = rest[j]
                j += 1
            flags = [t for t in rest[j:] if t.startswith("--")]
            found.append({"group": group, "sub": sub, "flags": flags,
                          "file": path.name, "line": line})
    return found


def extract_backticked_flags(path: Path) -> set[str]:
    return set(re.findall(r"`(--[a-z][a-z0-9-]*)", path.read_text(encoding="utf-8")))


def extract_dotted_paths(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for p in paths:
        out.update(re.findall(
            r"`(ksef2(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`",
            p.read_text(encoding="utf-8"),
        ))
    return out


def extract_from_imports(paths: list[Path]) -> list[tuple[str, list[str]]]:
    """(module, names) from `from ksef2... import ...` in fenced python blocks."""
    results: list[tuple[str, list[str]]] = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for _, body in _fenced_blocks(text):
            pending_module: str | None = None
            for line in body.splitlines():
                stripped = line.strip()
                if pending_module is not None:
                    chunk = stripped.rstrip(")")
                    if not chunk:
                        if ")" in stripped:
                            pending_module = None
                        continue
                    if ")" in stripped:
                        pending_module = None
                    names = [n.strip() for n in chunk.split(",") if n.strip()]
                    results.append((module, names))  # noqa: F821 (module set below)
                    continue
                m = re.match(r"^from\s+(ksef2(?:\.[A-Za-z_][\w]*)*)\s+import\s+(.+)$", stripped)
                if not m:
                    continue
                module, rest = m.group(1), m.group(2).strip()
                if rest.startswith("("):
                    pending_module = module
                    continue
                names = [n.strip().split(" as ")[0] for n in rest.split(",") if n.strip()]
                results.append((module, names))
            if pending_module is not None:
                # unbalanced parens: fall back to outer scan of the raw text
                pass
    # multi-line import whose names span the `(` line: re-scan raw text too
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(
            r"from\s+(ksef2(?:\.[A-Za-z_][\w]*)*)\s+import\s+\((.*?)\)",
            text, re.S,
        ):
            names = [n.strip().split(" as ")[0] for n in m.group(2).replace("\n", " ").split(",") if n.strip()]
            results.append((m.group(1), names))
    # de-duplicate (names as tuples so the rows are hashable)
    seen: set[tuple[str, tuple[str, ...]]] = set()
    uniq: list[tuple[str, list[str]]] = []
    for module, names in results:
        key = (module, tuple(names))
        if key not in seen:
            seen.add(key)
            uniq.append((module, names))
    return uniq


# ------------------------------------------------------------------ CLI checks

def run_cli(args_list: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args_list, capture_output=True, text=True, timeout=60,
            env=HELP_ENV, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"could not run: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr)


def discover_cli(explicit: str | None) -> str | None:
    if explicit:
        return explicit if shutil.which(explicit) or Path(explicit).is_file() else None
    # PATH first, then beside the current interpreter (venv / uv tool)
    candidates = [Path(sys.executable).parent]
    for name in ("ksef2", "ksef2-cli"):
        found = shutil.which(name)
        if found:
            return found
        for directory in candidates:
            exe = directory / name
            if exe.is_file() and os.access(exe, os.X_OK):
                return str(exe)
    return None


def check_cli(report: Report, cli: str, pins: dict[str, dict[str, str]],
              commands: list[dict], standalone_flags: set[str]) -> None:
    # --version, matches pinned versions
    code, out = run_cli([cli, "--version"])
    if code != 0:
        report.add("cli --version", "FAIL", f"exit {code}")
        return
    expected_cli = pins.get("ksef2-cli", {}).get("version", "")
    expected_sdk = pins.get("ksef2", {}).get("version", "")
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    detail = "; ".join(lines)
    if expected_cli and expected_sdk:
        ok = (lines[:2] == [f"ksef2-cli {expected_cli}", f"ksef2 {expected_sdk}"])
        report.add(
            "cli --version matches provenance",
            "PASS" if ok else "FAIL",
            detail if ok else f"got [{detail}], want [ksef2-cli {expected_cli}; ksef2 {expected_sdk}]",
        )
    else:
        report.add("cli --version matches provenance", "SKIP", f"pins missing; got [{detail}]")

    # top-level help + unknown-command exit code (both local, no credentials)
    code, _ = run_cli([cli, "--help"])
    report.add("cli --help exits 0", "PASS" if code == 0 else "FAIL", f"exit {code}")
    code, _ = run_cli([cli, "definitely-not-a-command"])
    report.add("unknown command exits 2", "PASS" if code == 2 else "FAIL", f"exit {code}")

    # per-command help + documented flags
    seen: dict[tuple[str | None, str | None], list[str]] = {}
    global_only = False
    for cmd in commands:
        if cmd["group"] is None:
            global_only = True
            continue
        key = (cmd["group"], cmd["sub"])
        seen.setdefault(key, [])
        for f in cmd["flags"]:
            if f not in seen[key]:
                seen[key].append(f)

    help_cache: dict[tuple[str | None, str | None], str] = {}
    for (group, sub), flags in sorted(seen.items(), key=lambda kv: str(kv[0])):
        argv = [cli] + ([group] if group else []) + ([sub] if sub else []) + ["--help"]
        code, out = run_cli(argv)
        label = " ".join(str(x) for x in [group, sub])
        if code != 0:
            report.add(f"help: {label}", "FAIL", f"exit {code}")
            continue
        help_cache[(group, sub)] = out
        missing = [f for f in flags if f not in out]
        report.add(
            f"flags of {label}",
            "FAIL" if missing else "PASS",
            "missing: " + ", ".join(missing) if missing else f"{len(flags)} flag(s) present",
        )

    # global-only invocations (ksef2 --version / --help) already covered above
    if global_only:
        report.add("global-only invocation documented", "PASS", "covered by --version/--help checks")

    # standalone backticked flags: must exist somewhere in CLI help output
    union = ""
    code, top = run_cli([cli, "--help"])
    union += top
    for text in help_cache.values():
        union += text
    if not standalone_flags:
        report.add("standalone flags", "SKIP", "none extracted")
        return
    missing = sorted(f for f in standalone_flags if f not in union)
    report.add(
        "standalone documented flags",
        "FAIL" if missing else "PASS",
        "missing everywhere: " + ", ".join(missing)
        if missing else f"{len(standalone_flags)} flag(s) present across help outputs",
    )


# ------------------------------------------------------------------ SDK checks

def _sdk_check_lines(pins: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    """Run the curated SDK checks; returns (check, status, detail)."""
    rows: list[tuple[str, str, str]] = []

    def add(check: str, ok: bool, detail: str = "") -> None:
        rows.append((check, "PASS" if ok else "FAIL", detail))

    try:
        import ksef2  # noqa: F401
    except ImportError as exc:
        return [("sdk importable", "SKIP", f"ksef2 not installed: {exc}")]

    # 1. dotted paths from the references: import module, getattr the rest
    paths = sorted(extract_dotted_paths(REF_FILES))
    import importlib
    bad: list[str] = []
    for dotted in paths:
        parts = dotted.split(".")
        resolved = False
        for cut in range(len(parts), 1, -1):
            module = ".".join(parts[:cut])
            try:
                obj = importlib.import_module(module)
            except Exception:
                continue
            resolved = True
            try:
                for attr in parts[cut:]:
                    obj = getattr(obj, attr)
            except AttributeError:
                resolved = False
                bad.append(dotted + " (name missing)")
            break
        if not resolved:
            bad.append(dotted)
    add("dotted paths import", not bad, ", ".join(bad) if bad else f"{len(paths)} path(s)")

    # 2. `from ksef2... import ...` statements in documented snippets
    imports = extract_from_imports(REF_FILES)
    bad_imp: list[str] = []
    for module, names in imports:
        try:
            mod = importlib.import_module(module)
        except Exception as exc:
            bad_imp.append(f"{module} ({exc})")
            continue
        for n in names:
            if not hasattr(mod, n):
                bad_imp.append(f"{module}.{n}")
    add("documented imports resolve", not bad_imp,
        ", ".join(bad_imp) if bad_imp else f"{len(imports)} import statement(s)")

    # 3. environments
    from ksef2 import Environment
    want_env = {
        "TEST": "https://api-test.ksef.mf.gov.pl/v2",
        "DEMO": "https://api-demo.ksef.mf.gov.pl/v2",
        "PRODUCTION": "https://api.ksef.mf.gov.pl/v2",
    }
    got_env = {name: Environment[name].base_url for name in want_env}
    add("environment base URLs", got_env == want_env, json.dumps(got_env))

    # 4. RetryConfig defaults
    from ksef2 import RetryConfig
    rc = RetryConfig()
    got_rc = {
        "max_attempts": rc.max_attempts, "initial_delay": rc.initial_delay,
        "max_delay": rc.max_delay, "max_retry_after": rc.max_retry_after,
        "backoff_multiplier": rc.backoff_multiplier,
        "retryable_status_codes": tuple(rc.retryable_status_codes),
        "jitter": rc.jitter,
    }
    want_rc = {
        "max_attempts": 3, "initial_delay": 0.5, "max_delay": 4.0,
        "max_retry_after": 120.0, "backoff_multiplier": 2.0,
        "retryable_status_codes": (429, 502, 503, 504), "jitter": True,
    }
    add("RetryConfig defaults", got_rc == want_rc, json.dumps(got_rc))

    # 5. FormSchema member names (the CLI --form choices are these names)
    from ksef2 import FormSchema
    got_fs = [f.name for f in FormSchema]
    want_fs = ["FA2", "FA3", "FA_RR1", "PEF3", "PEF_KOR3"]
    add("FormSchema members", got_fs == want_fs, str(got_fs))

    # 6. version pin
    want_ver = pins.get("ksef2", {}).get("version", "")
    add("ksef2.__version__ matches provenance",
        bool(want_ver) and ksef2.__version__ == want_ver,
        f"{ksef2.__version__} vs pin {want_ver or '?'}")

    # 7. clients / models surface
    import ksef2.clients as cl
    import ksef2.models as md
    workflow = ["InvoicesService", "BatchService", "InvoiceSubmission", "ExportJob",
                "GeneratedToken", "PermissionOperation", "CertificateEnrollment",
                "ExportedInvoices", "Pager", "OperationHandle"]
    missing = [n for n in workflow if not hasattr(cl, n)]
    add("ksef2.clients workflow types", not missing, ", ".join(missing) or "all present")
    resume = ["ExportResumeState", "GeneratedTokenResumeState",
              "CertificateEnrollmentResumeState", "PermissionOperationResumeState",
              "InvoiceSubmissionResumeState"]
    missing = [n for n in resume if not hasattr(md, n)]
    add("resume-state models", not missing, ", ".join(missing) or "all present")

    # 8. pager / handle method names
    surface = {
        "InvoiceSearchPager": ["responses", "pages", "page", "first_page",
                               "first_response", "wait"],
        "Pager": ["pages", "page", "first_page", "wait"],
        "InvoiceSubmission": ["wait", "download_upo", "resume_state", "reference_number"],
        "ExportJob": ["wait", "resume_state"],
        "GeneratedToken": ["wait", "resume_state", "token"],
        "PermissionOperation": ["wait", "resume_state"],
        "CertificateEnrollment": ["wait", "resume_state"],
        "ExportedInvoices": ["invoices", "metadata", "archive", "save", "from_archive"],
        "InvoicesService": ["search", "download", "export"],
        "BatchService": ["prepare", "submit"],
    }
    missing = []
    for cls_name, attrs in surface.items():
        cls = getattr(cl, cls_name, None)
        if cls is None:
            missing.append(cls_name)
            continue
        missing += [f"{cls_name}.{a}" for a in attrs if not hasattr(cls, a)]
    add("documented method names", not missing, ", ".join(missing) or "all present")

    # 9. Page fields (pydantic model_fields, not class attributes)
    page_fields = set(md.Page.model_fields)
    add("Page fields", {"items", "next_cursor"} <= page_fields, str(sorted(page_fields)))

    # 10. exception constructor params behind documented attributes
    from ksef2 import (KSeFApiError, KSeFException, KSeFInvoiceRejectedError,
                       KSeFRateLimitError, KSeFSessionFailedError,
                       KSeFTransportError)
    import inspect
    exc_want = {
        KSeFApiError: ["status_code", "ksef_code", "trace_id", "details", "hint"],
        KSeFRateLimitError: ["retry_after"],
        KSeFTransportError: ["outcome_ambiguous", "context"],
        KSeFException: ["context", "hint"],
        KSeFInvoiceRejectedError: ["invoice_reference_number"],
        KSeFSessionFailedError: ["reference_number"],
    }
    missing = []
    for cls, attrs in exc_want.items():
        try:
            params = set(inspect.signature(cls.__init__).parameters)
        except (ValueError, TypeError):
            params = set(getattr(cls, "__annotations__", {}))
        missing += [f"{cls.__name__}.{a}" for a in attrs if a not in params]
    add("exception attributes", not missing, ", ".join(missing) or "all present")

    # 11. behavior checks that stay local (validation, no network)
    from ksef2 import Client, KSeFUnsupportedEnvironmentError, KSeFValidationError
    try:
        Client(Environment.PRODUCTION).authentication.with_test_certificate(nip="5261040828")
        add("TEST-cert blocked on PRODUCTION", False, "no error raised")
    except KSeFUnsupportedEnvironmentError:
        add("TEST-cert blocked on PRODUCTION", True, "KSeFUnsupportedEnvironmentError")
    except Exception as exc:
        add("TEST-cert blocked on PRODUCTION", False, type(exc).__name__)
    from ksef2.models import InvoicesFilter
    try:
        # today minus far more than 100 days: must fail client-side
        InvoicesFilter.for_seller(date_type="issue_date",
                                  date_from="2020-01-01T00:00:00Z",
                                  date_to="2026-01-01T00:00:00Z")
        add("InvoicesFilter 100-day validation", False, "no error raised")
    except KSeFValidationError:
        add("InvoicesFilter 100-day validation", True, "KSeFValidationError")
    except Exception as exc:
        add("InvoicesFilter 100-day validation", False, type(exc).__name__)
    try:
        from ksef2 import KSeFArgumentError
        Client(Environment.TEST).authentication.with_test_certificate(nip="1234567890")
        add("NIP checksum rejected", False, "no error raised")
    except KSeFArgumentError:
        add("NIP checksum rejected", True, "KSeFArgumentError with hint")
    except Exception as exc:
        add("NIP checksum rejected", False, type(exc).__name__)

    # 12. client construction on every environment + local FA(3) build
    try:
        for env in (Environment.TEST, Environment.DEMO, Environment.PRODUCTION):
            Client(env)
            Client(env)
        from ksef2 import AsyncClient
        AsyncClient(Environment.TEST)
        add("client construction", True, "Client/AsyncClient, 3 environments")
    except Exception as exc:
        add("client construction", False, type(exc).__name__)
    try:
        from datetime import date as _date
        from decimal import Decimal as _Decimal
        from ksef2.fa3 import InvoiceBuilder, VatRate
        xml = InvoiceBuilder().header(system_info="verify.py").seller(
            name="V Sp. z o.o.", tax_id="5261040828", country_code="PL",
            address_line_1="ul. 1",
        ).buyer(name="B Sp. z o.o.", country_code="PL",
                address_line_1="ul. 2").standard().issue_date(
            _date.today()).issue_place("W").invoice_number(
            "V/1").rows().add_line(name="x", quantity=_Decimal("1"),
                                   unit_price_net=_Decimal("1.00"),
                                   vat_rate=VatRate.VAT_23
                                   ).done().done().to_xml()
        add("InvoiceBuilder offline build", len(xml) > 500, f"{len(xml)} chars")
    except Exception as exc:
        add("InvoiceBuilder offline build", False, f"{type(exc).__name__}: {exc}")

    return rows


# ---------------------------------------------------------------- source checks

def git_head(path: Path) -> str | None:
    if not (path / ".git").exists() and not (path / ".git").is_file():
        # worktrees store .git as a file; plain check via git instead
        pass
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def check_source_cli(report: Report, src: Path, pins: dict[str, dict[str, str]],
                     commands: list[dict], standalone_flags: set[str]) -> None:
    head = git_head(src)
    want = pins.get("ksef2-cli", {}).get("sha", "")
    if head and want:
        report.add("ksef2-cli source SHA",
                   "PASS" if head == want else "FAIL", f"{head} vs pin {want}")
    else:
        report.add("ksef2-cli source SHA", "SKIP",
                   f"head={head or 'unreadable'} pin={want or 'missing'}")

    ref = src / "docs" / "reference" / "commands.md"
    if not ref.is_file():
        report.add("source command reference", "FAIL", f"missing {ref}")
        return
    text = ref.read_text(encoding="utf-8")
    report.add("source command reference", "PASS", str(ref))

    # split into `### \`group sub\`` sections
    sections: dict[str, str] = {}
    for m in re.finditer(r"^### `([^`]+)`", text, re.M):
        sections[m.group(1)] = ""
    # re-scan capturing bodies
    parts = re.split(r"^### ", text, flags=re.M)
    for part in parts[1:]:
        heading = re.match(r"`([^`]+)`", part)
        if heading:
            sections[heading.group(1)] = part

    seen: dict[tuple[str | None, str | None], list[str]] = {}
    for cmd in commands:
        if cmd["group"] is None:
            continue
        key = (cmd["group"], cmd["sub"])
        seen.setdefault(key, [])
        for f in cmd["flags"]:
            if f not in seen[key]:
                seen[key].append(f)

    for (group, sub), flags in sorted(seen.items(), key=lambda kv: str(kv[0])):
        label = f"{group} {sub}" if sub else str(group)
        body = sections.get(label)
        if body is None:
            report.add(f"source section: {label}", "FAIL", "not in commands.md")
            continue
        missing = [f for f in flags if f not in body]
        report.add(
            f"source flags of {label}",
            "FAIL" if missing else "PASS",
            "missing: " + ", ".join(missing) if missing else f"{len(flags)} flag(s) in section",
        )

    if standalone_flags:
        global_section = ""
        m = re.search(r"^## Global options$(.*?)(?=^## )", text, re.M | re.S)
        if m:
            global_section = m.group(1)
        # standalone flags may live in any section; check the whole document
        missing = sorted(f for f in standalone_flags
                         if f not in text and f not in global_section)
        report.add(
            "standalone flags in source reference",
            "FAIL" if missing else "PASS",
            "missing: " + ", ".join(missing)
            if missing else f"{len(standalone_flags)} flag(s) present",
        )


def check_source_sdk(report: Report, src: Path, pins: dict[str, dict[str, str]]) -> None:
    head = git_head(src)
    want = pins.get("ksef2", {}).get("sha", "")
    if head and want:
        report.add("ksef2 source SHA",
                   "PASS" if head == want else "FAIL", f"{head} vs pin {want}")
    else:
        report.add("ksef2 source SHA", "SKIP",
                   f"head={head or 'unreadable'} pin={want or 'missing'}")

    pkg = src / "src" / "ksef2"
    if not pkg.is_dir():
        report.add("source package layout", "FAIL", f"missing {pkg}")
        return
    report.add("source package layout", "PASS", str(pkg))

    unresolved: list[str] = []
    name_skipped: list[str] = []
    for dotted in sorted(extract_dotted_paths(REF_FILES)):
        parts = dotted.split(".")
        cur = pkg
        if parts[0] != "ksef2":
            unresolved.append(dotted)
            continue
        for idx, part in enumerate(parts[1:], start=1):
            as_file = cur / f"{part}.py"
            as_pkg = cur / part / "__init__.py"
            if as_file.is_file():
                if idx == len(parts) - 1:
                    cur = as_file
                    break
                # remaining components are attribute names: not checkable offline
                name_skipped.append(dotted)
                break
            elif as_pkg.is_file():
                cur = as_pkg.parent
                if idx == len(parts) - 1:
                    break
            else:
                unresolved.append(dotted)
                break
        else:
            continue
    report.add(
        "documented module files in source",
        "FAIL" if unresolved else "PASS",
        "missing: " + ", ".join(unresolved) if unresolved
        else f"{len(extract_dotted_paths(REF_FILES))} path(s) resolve to files",
    )
    if name_skipped:
        report.add("attribute-level checks", "SKIP",
                   "require the installed SDK: " + ", ".join(sorted(set(name_skipped))))


# ------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description="Offline verification for the ksef2 skill.")
    parser.add_argument("--source", type=Path, help="pinned ksef2-cli checkout")
    parser.add_argument("--source-sdk", type=Path, help="pinned ksef2 checkout")
    parser.add_argument("--cli", help="CLI executable (default: ksef2 / ksef2-cli on PATH)")
    parser.add_argument("--python", help="interpreter with ksef2 installed (default: this one)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    pins = parse_provenance()

    if args.inner:
        for check, status, detail in _sdk_check_lines(pins):
            print(f"RESULT\t{check}\t{status}\t{detail}")
        return 0

    report = Report(as_json=args.json)

    # provenance pins
    if pins.get("ksef2", {}).get("sha") and pins.get("ksef2-cli", {}).get("sha"):
        report.add("provenance pins", "PASS",
                   "ksef2=" + pins["ksef2"]["sha"][:12] +
                   " ksef2-cli=" + pins["ksef2-cli"]["sha"][:12])
    else:
        report.add("provenance pins", "FAIL", f"could not parse {PROVENANCE_FILE}")

    # documented commands / flags
    commands: list[dict] = []
    standalone: set[str] = set()
    for ref in REF_FILES:
        commands += extract_commands(ref)
        standalone |= extract_backticked_flags(ref)
    if commands:
        report.add("documented commands extracted", "PASS",
                   f"{len(commands)} invocation(s) in {len(REF_FILES)} reference file(s)")
    else:
        report.add("documented commands extracted", "FAIL", "none found — parser broken?")

    # installed CLI
    cli = discover_cli(args.cli)
    if cli:
        check_cli(report, cli, pins, commands, standalone)
    else:
        report.add("ksef2-cli on PATH", "SKIP",
                   "not installed; run `uv tool install ksef2-cli` or pass --cli")

    # source checkouts
    if args.source:
        if args.source.is_dir():
            check_source_cli(report, args.source, pins, commands, standalone)
        else:
            report.add("ksef2-cli checkout", "FAIL", f"not a directory: {args.source}")
    if args.source_sdk:
        if args.source_sdk.is_dir():
            check_source_sdk(report, args.source_sdk, pins)
        else:
            report.add("ksef2 checkout", "FAIL", f"not a directory: {args.source_sdk}")

    # SDK checks: in-process when importable, else re-invoke with --python
    try:
        import ksef2  # noqa: F401
        for check, status, detail in _sdk_check_lines(pins):
            report.add(check, status, detail)
    except ImportError:
        target = args.python or sys.executable
        try:
            proc = subprocess.run(
                [target, str(Path(__file__).resolve()), "--inner"],
                capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            report.add("sdk checks", "SKIP", f"could not run with {target}: {exc}")
        else:
            emitted = False
            for line in proc.stdout.splitlines():
                if line.startswith("RESULT\t"):
                    _, check, status, detail = line.split("\t", 3)
                    report.add(check, status, detail)
                    emitted = True
            if not emitted:
                report.add("sdk checks", "SKIP",
                            f"ksef2 not importable with {target}"
                            + (f": {proc.stderr.strip()[:200]}" if proc.stderr.strip() else ""))

    report.finish()
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
