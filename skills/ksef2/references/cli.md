# ksef2-cli reference

Written for `ksef2-cli 1.0.0` / `ksef2 1.1.0`
([../provenance.md](../provenance.md)). The full option table is generated
upstream in `docs/reference/commands.md`; this file carries the shape,
guarantees, and worked examples. For any flag not shown here, run
`ksef2 <group> <subcommand> --help` — that output is authoritative and works
without credentials.

## Install

KSeF2 CLI 1.0 needs Python 3.12+ and the `ksef2` SDK `>=1.1,<2`:

```bash
uv tool install ksef2-cli
# or
pipx install ksef2-cli
```

Two equivalent executables: `ksef2` and `ksef2-cli`. Check what is running —
CLI version first, SDK version second, no config read, no credentials:

```bash
ksef2 --version
```

```text
ksef2-cli 1.0.0
ksef2 1.1.0
```

## Command shape

```bash
ksef2 [GLOBAL OPTIONS] GROUP [SUBCOMMAND] [COMMAND OPTIONS]
```

Global options come **before** the command group — `--profile`, `--env`,
`--json`, `--nip`, `--token`, `--auth-state` after the group are unknown
options and exit `2`.

| Global option | Env var | Meaning |
| --- | --- | --- |
| `--env`, `-e` `[production\|demo\|test]` | – | Environment. **Default is TEST** when neither flag nor profile sets one. |
| `--json` (or `--output json`) | – | One JSON document on stdout instead of text. |
| `--profile NAME` | `KSEF2_PROFILE` (selects at runtime) | Named local profile for this invocation. |
| `--nip` | `KSEF2_NIP` | Taxpayer/context NIP. |
| `--token` / `--ksef-token` | `KSEF2_TOKEN` | KSeF token auth. |
| `--test-cert` | `KSEF2_TEST_CERT` | SDK-generated TEST certificate — TEST only. |
| `--cert` / `--key` / `--p12` (+ password options) | `KSEF2_CERT` … | PEM or PKCS#12 XAdES credentials. |
| `--auth-state FILE` | `KSEF2_AUTH_STATE` | Reuse state from `auth login --save-state`. |
| `--config FILE` | `KSEF2_CONFIG` | Local config file (default `~/.config/ksef2/config.toml`). |
| `--no-config` | – | Ignore local profiles; combining it with `--profile` exits `2`. |
| `--verbose`, `-v` | – | Tracebacks on CLI errors. |

Precedence: `--env` beats the profile; the profile beats the default TEST. A
pasted command that names no environment and no profile talks to **TEST**.
Exactly one authentication method per command (see
[auth-security.md](auth-security.md)).

Profiles hold non-secret defaults in `~/.config/ksef2/config.toml`:

```bash
ksef2 profile create test-company --env test --nip 5261040828 --test-cert
ksef2 profile use test-company
ksef2 profile list
ksef2 config path
ksef2 config show
```

## Read-only queries

```bash
# Sales invoices; --date-from is required, --date-to defaults to now
ksef2 --profile test-company --json invoices metadata \
  --role seller \
  --date-from 2026-10-01T00:00:00Z --date-to 2026-10-31T23:59:59Z \
  --all

# Purchase invoices: the profile's NIP as buyer
ksef2 --profile test-company --json invoices metadata \
  --role buyer --date-from 2026-10-26 --all

# Same query with direct options instead of a profile (e.g. in CI)
ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-10-01T00:00:00Z \
  --all

ksef2 sessions invoice-list --type online --status succeeded --all
ksef2 sessions auth-list --all
ksef2 tokens list --status active --all
ksef2 certificates list --status active --all
ksef2 permissions entity-roles --all
ksef2 collective list --date-from 2026-10-01T00:00:00Z --all
ksef2 peppol providers --all
ksef2 encryption certificates
ksef2 limits get api
```

The range from `--date-from` to `--date-to` may not exceed 100 days, so set
`--date-to` whenever the start lies far back. Dates without an offset are read
in Europe/Warsaw time.

Group map: `auth` `batch` `certificates` `collective` `config` `encryption`
`fa3` `invoices` `limits` `online` `peppol` `permissions` `profile` `sessions`
`testdata` `tokens`. `testdata` is TEST-only fixtures (subjects, persons,
permissions, `testdata sandbox`).

## Output, JSON, exit codes

A successful command writes to stdout: aligned text by default, exactly one
JSON document with `--json`. Command errors go to stderr and leave stdout
empty — check the exit code before parsing stdout. In JSON mode an error is
one object:

```json
{"error": {"code": "...", "ksef_code": 21405, "trace_id": "...", "type": "RemoteServiceError", "title": "KSeF rejected the request", "message": "...", "details": [], "hints": [], "exit_code": 1, "ksef": {"status_code": 400, "exception_code": "...", "message": "..."}}}
```

`code`, `ksef_code`, `trace_id`, `type`, `title`, `message`, `details`,
`hints`, and `exit_code` are always present (`ksef_code` and `trace_id` may be
`null`); `ksef` appears when KSeF answered. Quote `trace_id` in incident
reports. As an agent, add `--json` to every command, and on an error read
`message` and `hints` before retrying: exit `2` means the command line itself
was wrong. Secrets recognized on the command line or in secret env
vars are replaced with `<redacted>` before the payload is encoded.

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure: rejected request, KSeF timeout, missing/contradictory credentials, bad file. |
| `2` | Usage failure: unknown option or command, missing argument, invalid value (bad NIP checksum), nonexistent `--profile`. |
| `130` | Interrupted (Ctrl-C) — KSeF may already have accepted work. |

`invoices send` prints every per-file result and exits `1` when any file
failed; read the items before concluding nothing was submitted.

Text tables: one row per record, `No results.` when empty, identifiers kept
complete while long names may end in `…`, UTC datetimes, pagination metadata
below the table. Use `--json` when a script consumes the output — JSON keeps
SDK fields, values, and nulls.

## Pagination

Two mechanisms, per command family:

- **Offset paging** — `--page-size` sets items per API request (default 10 on
  most list commands) and `--all` fetches every page. Available on:
  `invoices metadata`, `certificates list`, `tokens list`, `collective list`,
  `collective list-for-invoice`, `collective list-invoices`,
  `peppol providers`, `permissions entity-roles`, `permissions query`,
  `sessions auth-list`, `sessions invoice-list`.
- **`--page-offset`** — single-page offset (default 0; with `--all` it must
  stay `0`) exists on a subset: `invoices metadata`, `certificates list`,
  `peppol providers`, `permissions entity-roles`, `permissions query`.
- **Continuation-token paging** — `online list` and `batch list` page with
  `--continuation-token` (pass the token printed by the previous page;
  `sessions auth-list --continuation-token` is unsupported since ksef2 1.0,
  where paging is handled internally).

A page that comes back empty can still name the next page; only the absence of
a next token/cursor ends the collection.

## Async workflows

KSeF is asynchronous: commands start work and return references. Wait flags
are uniform — `--wait` polls, `--timeout` bounds it (sends default `120.0`,
online invoices default `60.0`), `--poll-interval` spaces checks (default
`2.0`). A local timeout is a local deadline, never proof that KSeF rejected
the work.

Send one invoice, wait, save the UPO later from a receipt:

```bash
ksef2 --profile test-company invoices send invoice.xml \
  --wait --upo-dir upos --receipt invoice-receipt.json

ksef2 --profile test-company invoices status --receipt invoice-receipt.json --wait
ksef2 --profile test-company invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

Batch (one session, many files), with a retry-safe prepare step:

```bash
ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch prepare invoice-1.xml invoice-2.xml --out batch-parts

ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch submit --prepared batch-parts --state-file batch-state.json --wait

ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch status --state-file batch-state.json --wait
```

After a failed upload, `batch upload --prepared … --state-file …` resends the
stored parts — no re-encryption, no new invoices.

Online session across several commands:

```bash
ksef2 --profile test-company online open --state-file session.json
ksef2 --profile test-company online send invoice.xml \
  --state-file session.json --save-state session.json --wait
ksef2 --profile test-company online invoice-status \
  --state-file session.json --invoice-reference <ref> --wait
ksef2 --profile test-company online list --state-file session.json
ksef2 --profile test-company online close --state-file session.json
```

`online send` closes a session it opened itself and keeps a session resumed
with `--state-file` open; `--close` / `--keep-open` override either way.

Exports are asynchronous and resumable:

```bash
ksef2 --profile test-company invoices export \
  --date-from 2026-10-01T00:00:00Z --handle-file export-handle.json

ksef2 --profile test-company invoices export-status --reference <export-ref>

ksef2 --profile test-company invoices export-fetch \
  --handle-file export-handle.json --out-dir downloads --wait
```

`invoices export-download` does schedule + wait + fetch in one command.

**Before resending after a timeout, Ctrl-C, or a dropped connection**, read
the saved receipt or ask `invoices status --receipt …`, `online list`, or
`batch status`: KSeF may already hold the invoice, and stopping the command
does not unsubmit it. State and receipt files carry session AES keys in plain
text — treat them as credentials ([auth-security.md](auth-security.md)).

## Build an FA(3) invoice

`fa3` runs locally, with no KSeF access and no credentials. You write a JSON
draft; `fa3 build` computes the amounts and the VAT summary, then checks the
XML against the FA(3) schema:

```bash
ksef2 fa3 draft-example --out draft.json      # template to edit
ksef2 --json fa3 build --in draft.json --out invoice.xml
ksef2 --json fa3 inspect invoice.xml          # what the XML actually says
ksef2 fa3 render --in invoice.xml --out invoice.html
```

The template holds sample data. Before sending, replace:

- `seller.tax_id` with the NIP of the sending profile
  (`ksef2 profile show NAME`) — KSeF rejects another seller NIP with a
  permission error;
- `body.issue_date` (fixed at `2026-04-09`), `body.invoice_number`, and the
  rows.

A row carries `name`, `quantity`, `unit_of_measure`, `unit_price_net`, and
`vat_rate`. Write numbers as strings (`"10"`, `"100.00"`); `vat_rate` must be
a string from `23 22 8 7 5 4 3 0 zw np oo` — a JSON number crashes the build.
Write no totals.

A correction sets `body.invoice_type` to the full label
`"Faktura korygująca"` (the short code `KOR` is rejected) and lists the
corrected invoice under `body.correction.corrected_invoices`
(`issue_date`, `invoice_number`, `ksef_id`). Rows with
`"before_correction": true` give the state before the correction.

**Check `fa3 inspect` before sending.** Unknown keys inside `seller`, `buyer`,
`body`, and rows are dropped without an error: a row with `"qty"` instead of
`"quantity"` builds a schema-valid invoice for 0.00 and exits `0`. Compare
parties, rows, and totals in the inspect output with the request.

For fields beyond the template (advances, payment, foreign currency), read
the draft's JSON Schema from the SDK and look up only the definitions you
need:

```bash
python3 -c 'import json; from ksef2.fa3 import KsefInvoiceDraft; print(json.dumps(KsefInvoiceDraft.model_json_schema()))' > draft-schema.json
```
