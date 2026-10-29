# Provenance

Everything in this skill was distilled from the two upstream repositories at
the commits below, then checked with the recorded runs.

## Pinned sources

- **ksef2** (Python SDK) — <https://github.com/stacking-hq/ksef2>
  — `sha=90a6238d40f54b962eb736d286fae3cea5047e2a` — version 1.1.0
  — commit 2026-10-28 (merge of feat/update-openapi-spec; docs under `docs/en/`)
- **ksef2-cli** (command-line tool) — <https://github.com/stacking-hq/ksef2-cli>
  — `sha=26ee611f80e0f72265b1ca90887ad0835bd5608b` — version 1.0.0
  — commit 2026-10-28 (merge of polish-cli-docs; generated command reference
  under `docs/reference/commands.md`)

Re-verify after moving a pin:

```bash
git -C <checkout> rev-parse HEAD     # must equal the sha= line above
```

## Recorded checks (2026-10-29, macOS, CPython 3.12.11, temporary venv)

Packages installed from PyPI: `ksef2-cli 1.0.0`, `ksef2 1.1.0` — matching
both pinned `pyproject.toml` versions. No KSeF credentials were used and no
request was sent to any KSeF host.

| # | Check | Result |
| --- | --- | --- |
| 1 | `ksef2 --version` | `ksef2-cli 1.0.0` / `ksef2 1.1.0` — matches pins |
| 2 | `ksef2 --help` | 16 command groups, identical to pinned `commands.md` group table |
| 3 | `--help` for `invoices send`, `invoices metadata`, `profile create`, `auth login`, `fa3 build`, `online send`, `tokens generate`, `invoices export`, `limits get`, `sessions auth-list` | exit 0; options match the pinned reference (long flags fully rendered at `COLUMNS=240`) |
| 4 | Unknown command `ksef2 definitely-not-a-command` | exit 2, as documented |
| 5 | `ksef2 --env production --nip 5261040828 --test-cert --json auth login` | exit 2 before any request: "Test certificates require the TEST environment." |
| 6 | `ksef2 --env test --nip 5261040828 --test-cert --token <value> --json auth login` | exit 1 before any request: "Provide only one auth method…" |
| 7 | Offline `fa3` roundtrip: `fa3 draft-example` → `fa3 build` → `fa3 inspect` | exit 0; valid FA(3) XML (`xmlns http://crd.gov.pl/wzor/2025/06/25/13775/`) |
| 8 | Import every stable path in the SDK table (`ksef2`, `ksef2.clients`, `ksef2.models`, `ksef2.fa3`, `ksef2.xades`, `ksef2.profiles`, `ksef2.logging`, `ksef2.certificate_stores`, `ksef2.testdata`, `ksef2.renderers`, `ksef2.raw`) | all importable |
| 9 | `Client` / `AsyncClient` construction on all three environments; base URLs | match the documented `api[-test\|-demo].ksef.mf.gov.pl/v2` table |
| 10 | `FormSchema` values (5), `RetryConfig` defaults (7 fields), `Page` fields (`items`, `next_cursor`) | match documented values |
| 11 | Handle/service method names: `InvoiceSearchPager.responses/pages/page/first_page/first_response/wait`, `InvoicesService.search/download/export`, `InvoiceSubmission.wait/download_upo/resume_state`, `ExportJob.wait/resume_state`, `ExportedInvoices.invoices/metadata/archive/save`, exception constructor params (`ksef_code`, `trace_id`, `retry_after`, `outcome_ambiguous`, …) | all present |
| 12 | `InvoicesFilter.for_seller(...)` with a >100-day range | raises `KSeFValidationError` client-side, as documented |
| 13 | `InvoiceBuilder` quickstart snippet (offline portion) | builds 1459-byte FA(3) XML |
| 14 | `Client(Environment.PRODUCTION).authentication.with_test_certificate(...)` | raises `KSeFUnsupportedEnvironmentError` before any request |
| 15 | `with_test_certificate(nip="1234567890")` (bad checksum) | raises `KSeFArgumentError` with hint, before any request |

## Final-review re-run (same venv, same pins)

Re-executed after the last content edits, with the two checkouts above:

| Check | Actual result |
| --- | --- |
| Historical offline verification, before the verification script was removed | 99 checks, all PASS, exit 0 |
| `npx skills list --json` in this repo | one skill discovered: `name=ksef2`, path `skills/ksef2` |
| `ksef2 --help` | 16 command groups |
| `ksef2 definitely-not-a-command` | exit 2 |
| `ksef2 --env production --nip 5261040828 --test-cert --json auth login` | exit 2 |
| `ksef2 --env test --nip 5261040828 --test-cert --token <value> --json auth login` | exit 1 |
| offline `fa3 draft-example` → `fa3 build` → `fa3 inspect` | exit 0 each; FA(3) xmlns `http://crd.gov.pl/wzor/2025/06/25/13775/` |
| quickstart FA(3) snippet from `references/sdk-api.md` | builds 1459-byte XML |
| API spot-checks in pinned source | `with_xades(nip, cert, private_key, credentials)`, `authentication.resume(state)`, `load_certificate_and_key_from_p12`, `InvoicesFilter.for_seller(..., restrict_to_permanent_storage_hwm_date=…)`, `configure_logging(level=…, renderer=…)`, `online_session` / `send_invoice` / `list_failed_invoices` — all present |
| CLI defaults from `--help` | `--page-size` 10, `--page-offset` 0, `--timeout` 120.0 (sends) / 60.0 (online), `--poll-interval` 2.0, `--no-config` + `--profile` → exit 2, bad `--env`/`--nip` → exit 2 |

Not covered, same limits as above: no live KSeF request, no credential use,
no push or publish; `--help` output and attribute presence do not prove
runtime semantics.

## Limitations — what these checks do NOT prove

- **No live KSeF interaction.** Authentication, invoice sending, status
  polling, downloads, and exports were never executed against KSeF; those
  commands and SDK calls are verified only for flag/import existence.
  Behavior described from the pinned docs (wait semantics, UPO readiness,
  retry middleware internals) was read, not executed.
- **Help output is not validation.** `--help` short-circuits argument
  checking, so env/auth conflicts were exercised by running real commands
  that fail fast (rows 5–6), not through `--help`.
- **PyPI wheels.** Installed versions match the pinned version numbers; the
  wheel build attestation chain was not independently checked.
- **Renderer effects.** Rich help tables wrap or truncate on narrow
  terminals; the recorded checks used `COLUMNS=240`, but a differing terminal or
  Typer/Rich version can still change rendering and produce false negatives.
- **Presence ≠ semantics.** Attribute and field checks prove a name exists,
  not that its runtime behavior matches the prose.
- **Pins age.** The commits are dated 2026-10-28; upstream moves on. Update
  the `sha=` lines and repeat the CLI and SDK checks when refreshing the skill.
