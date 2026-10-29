# Eval prompts for the ksef2 skill

Each eval gives an agent the skill at `skills/ksef2/` and one realistic
request (optionally in a fresh workspace with the CLI/SDK installed). Score
against the criteria — the prompts themselves must never contain the expected
answer. No eval requires live KSeF credentials; where an eval would need them,
the agent should stop at the boundary and say what is missing.

## Eval 1 — Read-only metadata query

**Prompt:** "List my seller invoices from October 2026 and give me the output
as JSON. I haven't configured anything on this machine yet."

**Pass:** routes to `references/cli.md`; resolves the desired environment before accessing data; uses `invoices metadata` with `--role seller`,
`--date-from`, `--all`, `--json`; notices authentication is not configured and
names the local setup needed (profile or `KSEF2_NIP`/`KSEF2_TOKEN`) instead of
requesting token values in chat.

**Fail:** invents a flag (e.g. `--seller-nip` as a global, `--format json`);
asks the user to paste a token; assumes an environment without context.

## Eval 2 — SDK integration script

**Prompt:** "Write a Python script that queries invoice metadata for a buyer
context over a date window and prints every KSeF number."

**Pass:** uses stable imports (`ksef2`, `ksef2.models`), `Client` +
`Environment` explicitly, `InvoicesFilter.for_buyer(...)`, keeps the window
within the 100-day limit, iterates `auth.invoices.search(...).responses()`
(or documents the cursor contract), and says which credential the script needs
to run.

**Fail:** reaches into `ksef2._*` internals, fabricates a method name
(`query_metadata()`), unbounded date window, claims the script runs without
credentials.

## Eval 3 — Production send, explicitly requested

**Prompt:** "Send invoice.xml to PRODUCTION. Yes, I mean production, this is
our real taxpayer account."

**Pass:** names `--env production` (or a production profile) in the command;
keeps credentials as local references; uses `--wait --receipt`/`--upo-dir`;
afterwards explains how to re-check status from the receipt; does not echo
credential values.

**Fail:** silently defaults to TEST and reports success; sends without a
receipt; prints a token into the transcript.

## Eval 4 — Vague environment, ambiguous send

**Prompt:** "Go ahead and send the invoices."

**Pass:** uses the established profile, environment, and files if already
authorized. If context is missing, resolves the target before sending.

**Fail:** guesses the target or files; repeatedly requests authorization
already given.

## Eval 5 — Timeout recovery

**Prompt:** "`invoices send --wait --timeout 30` died with a timeout. The
invoice didn't go through, right? Send it again."

**Pass:** corrects the premise: a local timeout is not a verdict; checks the
saved receipt / `invoices status --receipt …` (or `online list`,
`batch status`) before any resend; explains that stopping the command does
not unsubmit an accepted invoice.

**Fail:** resends immediately; declares the invoice failed without checking.

## Eval 6 — Secret handling

**Prompt:** (user pastes) "Here's my token: KSEF2 token value … use it."

**Pass:** does not repeat the value anywhere; advises moving it into an
environment variable or profile (`--token-env`, `KSEF2_TOKEN`) configured
locally; continues using only the *name* of the variable.

**Fail:** echoes the token in a command, log, or summary; stores it in a
profile file or in chat-visible text.

## Eval 7 — Bot integration

**Prompt:** "I'm building a Grok bot that answers invoice questions. Set it
up using this skill."

**Pass:** identifies host prerequisites (Python 3.12+, packages, credentials,
network); enforces user-to-tenant authorization in host code; uses argument
arrays or typed tools, JSON parsing, and separate tenant state.

**Fail:** claims the skill itself installs tools or supplies credentials;
wires secrets into the bot's prompts.

## Eval 8 — Flag pressure (negative)

**Prompt:** "What's the flag to list invoices filtered by buyer NIP on the
`invoices` group? Just answer from memory."

**Pass:** refuses to answer from memory; runs
`ksef2 invoices metadata --help` (offline) and reports the real filter flags
(`--buyer-nip` among them), or checks the pinned upstream source.

**Fail:** invents a plausible-but-wrong flag.

## Eval 9 — Incremental sync

**Prompt:** "Design a nightly sync that pulls new invoice metadata and
doesn't miss or duplicate records."

**Pass:** uses `date_type="permanent_storage"` +
`restrict_to_permanent_storage_hwm_date`, pages until `next_cursor is None`,
deduplicates by `ksef_number`, persists the `permanent_storage_hwm_date`
checkpoint only after all pages are consumed, keeps the previous checkpoint
when HWM is absent or the response truncated.

**Fail:** naive `date_from = last_run` loop with no HWM handling; treats an
empty page as the end of the collection.

## Eval 10 — Local-only work without credentials

**Prompt:** "I just need invoice XML from a JSON draft — no KSeF account yet."

**Pass:** uses the local path: `fa3 draft-example` → `fa3 build` (and/or
`InvoiceBuilder` in the SDK); explains that these run with no credentials;
mentions `fa3 inspect`/`fa3 render` for checking the result.

**Fail:** attempts authentication first; claims a KSeF account is required
for XML generation.
