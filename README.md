# ksef2-skills

A skills.sh-compatible [Agent Skill](skills/ksef2/SKILL.md) that teaches
assistants (Grok, Codex, Claude/Anthropic, and any agent that loads standard
`SKILL.md` packages) how to work with **KSeF 2.0** — Poland's National e-Invoicing
System — through the [`ksef2`](https://github.com/stacking-hq/ksef2) Python SDK
and [`ksef2-cli`](https://github.com/stacking-hq/ksef2-cli):

- CLI usage: queries, exit codes, pagination, `--wait`/receipt workflows
- SDK/API integration: stable imports, async handles, retries, error handling
- Authentication & security: methods, secrets, environment/tenant boundaries
- Bot integration: read-only defaults, credential boundaries, production gating

The skill is **documentation, not runtime**: it ships no tools, no credentials,
and no network access. Everything it states is pinned to upstream commits in
[`skills/ksef2/provenance.md`](skills/ksef2/provenance.md), with recorded
offline checks and their limitations.

## Layout

```text
skills/ksef2/
├── SKILL.md                 Entrypoint: safety defaults + routing
├── references/
│   ├── cli.md               ksef2-cli commands, output, pagination, async
│   ├── sdk-api.md           ksef2 SDK imports, clients, handles, retries, errors
│   ├── auth-security.md     credentials, secrets, environment boundaries
│   └── bot-integration.md   assistant/bot operating rules
├── scripts/verify.py        offline verification (no KSeF contact)
├── evals/prompts.md         10 eval prompts with pass/fail criteria
└── provenance.md            pinned source SHAs, recorded checks, limitations
```

Frontmatter uses only the portable `name` + `description` fields required by
the open skill format, so the same package works across skill loaders.

## Install

**With the open skills CLI (skills.sh-compatible):**

```bash
npx skills add stacking-hq/ksef2-skills --skill ksef2
```

`--skill ksef2` selects the skill by its frontmatter `name` (the CLI's
`-s, --skill` option). The skills CLI discovers `skills/<name>/SKILL.md` in a
repository and installs it into your agent's
skills directory (`.claude/skills/`, `.codex/skills/`, `.grok/skills/`,
`.agents/skills/`, …).

**Manual:**

```bash
git clone https://github.com/stacking-hq/ksef2-skills
cp -r ksef2-skills/skills/ksef2 ~/.agents/skills/    # or your agent's skills dir
```

Then confirm discovery using your agent's skill listing. For installs managed
by the skills CLI, use `npx skills list` or `npx skills list --global` as appropriate.

**Runtime prerequisites** (the skill does not provide these):

```bash
# Python 3.12+
uv tool install ksef2-cli        # CLI: ksef2 / ksef2-cli
pip install ksef2                # or: uv add ksef2
```

Credentials are configured locally by the user — profiles or `KSEF2_*`
environment variables — and never enter chat
([auth-security.md](skills/ksef2/references/auth-security.md)).

## Use

- The agent selects the skill from its description when a task mentions KSeF,
  `ksef2`, `ksef2-cli`, FA(3)/FA3 invoices, UPO, invoice metadata, or exports.
- Explicit invocation: `$ksef2`.
- Once loaded, the skill routes to exactly one reference per task and applies
  its safety defaults: TEST-first, read-only-first, production and submissions
  only on explicit request, credentials referenced by name only.
- Run `ksef2 <group> <subcommand> --help` before quoting any flag you have not
  seen in a reference — the skill instructs the agent to do this rather than
  trust memory.

## Verify

Offline verification (no KSeF host is ever contacted):

```bash
python skills/ksef2/scripts/verify.py
python skills/ksef2/scripts/verify.py --source /path/to/ksef2-cli-checkout \
                                      --source-sdk /path/to/ksef2-checkout
python skills/ksef2/scripts/verify.py --python /path/to/venv/bin/python
python skills/ksef2/scripts/verify.py --json
```

It checks extracted commands/flags against installed CLI `--help` and/or
the pinned source command reference, documented SDK import paths and selected model fields
against the installed SDK, and the pinned SHAs against `git rev-parse HEAD`.
Exit `0` = all checks pass (SKIPs allowed), `1` = at least one failure.
Recorded results and what they cannot prove: [provenance.md](skills/ksef2/provenance.md).

## Evaluate

[`skills/ksef2/evals/prompts.md`](skills/ksef2/evals/prompts.md) contains 10
realistic prompts with pass/fail criteria (read-only queries, production
gating, timeout recovery, secret handling, flag-fabrication pressure). Give an
agent the skill plus one prompt in a scratch workspace; do not include the
criteria in the prompt.

## Publish

1. Keep the package intact: `skills/ksef2/SKILL.md` must stay at that path
   with its `name`/`description` frontmatter — the skills CLI discovers
   `skills/<name>/SKILL.md` up to two category levels deep.
2. Push this repository to a **public** GitHub repo (this checkout's remote is
   `stacking-hq/ksef2-skills`). Review `SKILL.md` and references before the
   first push; keep [provenance.md](skills/ksef2/provenance.md) pins current
   whenever upstream moves.
3. Install once from the published repo to smoke-test discovery:
   `npx skills add stacking-hq/ksef2-skills --skill ksef2`.
4. [skills.sh](https://skills.sh) indexes public skills shipped through the
   open skills CLI — no separate submission step is required for listing.
5. Optional README badge:

```markdown
[![skills.sh](https://skills.sh/b/stacking-hq/ksef2-skills)](https://skills.sh/stacking-hq/ksef2-skills)
```

The package has been reviewed and verified offline. Live authenticated KSeF
workflows remain untested. These changes have not been pushed.

## License

[MIT](LICENSE)
