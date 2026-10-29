# CLI workflows

Install with `uv tool install ksef2-cli` and check `ksef2 --version`.
Global options precede the group: `ksef2 --profile company --json invoices …`.
Use [auth-security.md](auth-security.md) to configure a profile. Examples below
use `company` for real data and `test-company` for synthetic invoice submission.

## Query a month's invoices

```bash
ksef2 --profile company --json invoices metadata \
  --role seller --date-from 2026-10-01T00:00:00Z \
  --date-to 2026-11-01T00:00:00Z --all
```

Use `--role buyer` for purchases. Choose dates for the user's request; each
query window must stay within 100 days. `--all` consumes offset-paged results.
For a full document or a collection of XML invoices, use the export workflow.
Check `invoices --help` for individual download commands and their arguments.

## Export invoice XML

Exports are asynchronous and resumable:

```bash
ksef2 --profile company invoices export \
  --date-from 2026-10-01T00:00:00Z --handle-file export-handle.json

ksef2 --profile company invoices export-status --reference <export-ref>

ksef2 --profile company invoices export-fetch \
  --handle-file export-handle.json --out-dir downloads --wait
```

`invoices export-download` does schedule + wait + fetch in one command.

## Send an invoice and retrieve UPO

Send one invoice, wait, save the UPO later from a receipt:

```bash
ksef2 --profile test-company invoices send invoice.xml \
  --wait --upo-dir upos --receipt invoice-receipt.json

ksef2 --profile test-company invoices status --receipt invoice-receipt.json --wait
ksef2 --profile test-company invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

A send can partially succeed: inspect per-file results even on exit `1`.
Use the saved receipt to recover status after interruption. For batch or
multi-command sessions, inspect `batch --help` or `online --help`.

## Build FA(3) locally

```bash
ksef2 fa3 draft-example --out draft.json
ksef2 fa3 build --in draft.json --out invoice.xml
ksef2 fa3 inspect invoice.xml
ksef2 fa3 render --in invoice.xml --out invoice.html
```

## Results and pagination

`--json` writes successful results to stdout; errors go to stderr. Exit codes:
`0` success, `1` runtime failure, `2` usage error, `130` interruption.
Parse stdout after checking the exit code. Remote errors include
`error.ksef.trace_id` when available.

Most lists use `--all` or `--page-size`/`--page-offset`; `online list` and
`batch list` use `--continuation-token`. Check the command help because flags
vary. An empty page alone does not prove pagination is complete.

`--wait` polls with a bounded `--timeout`; `--poll-interval` sets spacing.
