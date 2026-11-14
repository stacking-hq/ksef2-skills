# Provenance

Everything in this skill was distilled from the two upstream repositories at
the commits below.

## Pinned sources

- **ksef2** (Python SDK) — <https://github.com/stacking-hq/ksef2>
  — `sha=f0699fac6cc40ffa736e15f0a4afd0d35633fd8d` (`v1.3.0`) — version 1.3.0
  — released 2026-10-30 (docs under `docs/en/`)
- **ksef2-cli** (command-line tool) — <https://github.com/stacking-hq/ksef2-cli>
  — `sha=8cd8e81aa959b500769384770823de3143d33e59` (`v1.1.0`) — version 1.1.0
  — released 2026-10-29 (generated command reference under
  `docs/reference/commands.md`)

## Offline checks

Run on 2026-11-13 against `ksef2-cli 1.1.0` and `ksef2 1.3.0` from PyPI, with
no KSeF credentials and no request to a KSeF host:

- `--help` for every command quoted in the references matched the installed
  CLI, including defaults.
- Fail-fast paths behaved as documented: unknown command (exit 2), TEST
  certificate on production (exit 2), two auth methods at once (exit 1), a
  global option placed after the group (exit 2), the over-100-day filter, and
  TEST-only SDK helpers outside TEST.
- `fa3 draft-example` → `fa3 build` → `fa3 inspect` → `fa3 render` and the SDK
  `InvoiceBuilder` snippet produced valid FA(3) XML.

## Changes since the 1.1.0 / 1.0.0 pins

- **ksef2 1.2.0 rejects unknown nested FA(3) draft fields.** They used to be
  dropped silently, so a misspelled key produced a valid-looking invoice. The
  FA(3) section of [references/cli.md](references/cli.md) now states the
  current behaviour, and keeps the advice to inspect before sending because an
  *omitted* field is still accepted quietly.
- ksef2 1.2.0 moved the bundled OpenAPI specification to KSeF API 2.9.0.
- **ksef2 1.3.0 added `footer_text` and `watermark_text` to the HTML and PDF
  renderers**, and made FA(3) schema validation opt-in on the renderer.
- **ksef2-cli 1.1.0 added `ksef2 fa3 schema`**, which prints the same draft
  JSON Schema the previous revision reached by importing the SDK directly.
- A numeric `vat_rate` in a draft is now a clean usage error (exit 2) rather
  than a crash.
- The SDK's public surface is unchanged between 1.1.0 and 1.3.0: no documented
  import path, class, or method was renamed or removed.

## Limitations

Offline checks cannot cover anything that needs credentials or a live KSeF
response: real authentication, submission acceptance, UPO content, export
payloads, and the exact shape of server-side errors. Behaviour described from
the upstream docs rather than from a local run is limited to what
`--help`, the SDK's public objects, and the pinned sources show.
