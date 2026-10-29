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

## Operating rules

These apply on every path below.

- **Work in the configured context.** Use the profile the user set up —
  normally their production account — and name it in every command
  (`--profile NAME`, or `--env` with direct options): a command with neither
  silently targets TEST. Ask only when the target is unclear — no profile,
  several candidates, or a request that does not fit the configured
  environment. TEST is for experiments and test data.
- **Know whose name you act in.** Check the environment and context NIP
  behind the profile (`ksef2 profile show NAME`). Name them to the user when
  you start working with a profile, and again before sending invoices or
  changing permissions, tokens, or certificates.
- **Read-only first.** Answer data questions with query commands
  (`invoices metadata`, `sessions invoice-list`, `tokens list`, …). Commands
  that change state run only when the user asked for that action. A request
  made earlier in the task still counts — do not ask for it again.
- **Preview invoices you drafted.** When you wrote the invoice content
  yourself, show the `fa3 inspect` preview and send only after the user
  confirms it. An invoice file the user supplied needs no extra confirmation.
- **Credentials stay local.** Chat, displayed commands, and logs carry profile
  names, environment-variable names, and file paths — never token values,
  certificate material, passwords, or session keys. Receipts, state files,
  and export handles hold secrets too
  ([references/auth-security.md](references/auth-security.md)).
- **Environments never mix.** Tokens, session references, invoice numbers, and
  download URLs belong to the environment that produced them.

## Choose the reference

Read only the reference the current task needs.

| Task | Read |
| --- | --- |
| Run commands, read output and exit codes, paginate, drive `--wait` workflows | [references/cli.md](references/cli.md) |
| Build an FA(3) invoice from a request, or a correction | [references/cli.md](references/cli.md#build-an-fa3-invoice) |
| Write Python against the SDK: clients, models, async handles, retries, errors | [references/sdk-api.md](references/sdk-api.md) |
| Authenticate, store secrets, configure profiles and environments | [references/auth-security.md](references/auth-security.md) |
| Drive KSeF from an assistant or bot (Grok, Codex, Claude, …) | [references/bot-integration.md](references/bot-integration.md) |

## Trust the source, not memory

Flags and model fields drift between releases. Before quoting a command or
field you have not seen in a reference here, confirm it:

- CLI: `ksef2 <group> <subcommand> --help` — offline, needs no credentials.
- SDK: compare imports, signatures, and models with the pinned upstream source.

[provenance.md](provenance.md) records what was checked at the pinned commits,
and what offline checks cannot cover.
