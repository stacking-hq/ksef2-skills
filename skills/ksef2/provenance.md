# Provenance

Everything in this skill was distilled from the two upstream repositories at
the commits below.

## Pinned sources

- **ksef2** (Python SDK) — <https://github.com/stacking-hq/ksef2>
  — `sha=90a6238d40f54b962eb736d286fae3cea5047e2a` — version 1.1.0
  — commit 2026-10-28 (docs under `docs/en/`)
- **ksef2-cli** (command-line tool) — <https://github.com/stacking-hq/ksef2-cli>
  — `sha=26ee611f80e0f72265b1ca90887ad0835bd5608b` — version 1.0.0
  — commit 2026-10-28 (generated command reference under
  `docs/reference/commands.md`)

## Offline checks

Run on 2026-10-29 against `ksef2-cli 1.0.0` and `ksef2 1.1.0` from PyPI,
without KSeF credentials and without any request to a KSeF host:

- `--help` for the commands quoted in the references matched the pinned
  command reference, including defaults.
- Fail-fast paths behaved as documented: unknown command (exit 2), TEST
  certificate on production (exit 2), two auth methods at once (exit 1), the
  over-100-day filter, and TEST-only SDK helpers outside TEST.
- `fa3 draft-example` → `fa3 build` → `fa3 inspect` and the SDK
  `InvoiceBuilder` snippet produced valid FA(3) XML.
- Every stable SDK import path, and the class, method, and default names in
  the SDK reference, exist in the installed packages.

## Limitations

- Authentication, sending, status polling, downloads, and exports were never
  run against KSeF. Their behavior comes from the pinned docs and source.
- A name that exists is not proof that it behaves as described.
- Upstream moves on. When refreshing the skill, update the `sha=` lines and
  repeat these checks.
