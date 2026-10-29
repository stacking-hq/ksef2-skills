---
name: ksef2
description: Poland's KSeF 2.0 e-invoicing through the ksef2 Python SDK and ksef2-cli — run CLI queries and invoice workflows, build SDK/API integrations, configure authentication and secrets, or wire KSeF into an assistant bot. Use when a task mentions KSeF, ksef2, ksef2-cli, FA(3)/FA3 invoices, UPO, invoice metadata queries, or invoice exports.
---

# ksef2 — KSeF 2.0 SDK and CLI

This skill is documentation distilled from the upstream source at the commits
pinned in [provenance.md](provenance.md). It tells you which commands, flags,
import paths, and behaviors are real. It supplies no runtime: Python 3.12+,
the `ksef2` / `ksef2-cli` packages, network access, and KSeF credentials all
come from the user's environment.

## Safety defaults

These apply on every path below.

- **Environment.** Default to TEST. A production run — an explicit
  `--env production`, or a profile whose `environment = "production"` — and any
  invoice submission happen only when the user asks for them, and the command
  you run names that environment.
- **Read-only first.** Answer data questions with query commands
  (`invoices metadata`, `sessions invoice-list`, `tokens list`, …).
  Sending invoices, granting or revoking permissions, generating or revoking
  tokens, and touching TEST data run only on an explicit request.
- **Credentials stay local.** Chat, displayed commands, and logs carry profile
  names, environment-variable names, and file paths — never token values,
  certificate material, passwords, or session keys.
- **Continuation files are credentials.** Auth state, receipts, session state,
  and export handles hold secrets in plain text on disk (mode `0600`). Keep
  them outside the repository and out of anything pasted into chat.
- **Environments never mix.** Tokens, session references, invoice numbers, and
  download URLs belong to the environment that produced them.

## Choose the reference

Read only the reference the current task needs.

| Task | Read |
| --- | --- |
| Run commands, read output and exit codes, paginate, drive `--wait` workflows | [references/cli.md](references/cli.md) |
| Write Python against the SDK: clients, models, async handles, retries, errors | [references/sdk-api.md](references/sdk-api.md) |
| Authenticate, store secrets, pick environments, gate production | [references/auth-security.md](references/auth-security.md) |
| Drive KSeF from an assistant or bot (Grok, Codex, Claude, …) | [references/bot-integration.md](references/bot-integration.md) |

## Trust the source, not memory

Flags and model fields drift between releases. Before quoting a command or
field you have not seen in a reference here, confirm it:

- CLI: `ksef2 <group> <subcommand> --help` — offline, needs no credentials.
- SDK: compare imports, signatures, and models with the pinned upstream source.

[provenance.md](provenance.md) records what was verified at the pinned
commits, and what offline verification cannot cover.
