# ksef2-skills

A skills.sh-compatible [Agent Skill](skills/ksef2/SKILL.md) that teaches
assistants (Grok, Codex, Claude/Anthropic, and any agent that loads standard
`SKILL.md` packages) how to work with **KSeF 2.0** — Poland's National e-Invoicing
System — through the [`ksef2`](https://github.com/stacking-hq/ksef2) Python SDK
and [`ksef2-cli`](https://github.com/stacking-hq/ksef2-cli):

- CLI usage: queries, exit codes, pagination, `--wait`/receipt workflows
- SDK/API integration: stable imports, async handles, retries, error handling
- Authentication & security: methods, secrets, profiles, environments
- Bot integration: host prerequisites, tenant authorization, safe reporting

The skill is **documentation, not runtime**: it ships no tools, no credentials,
and no network access. Its content is pinned to upstream commits in
[`skills/ksef2/provenance.md`](skills/ksef2/provenance.md).

## Layout

```text
skills/ksef2/
├── SKILL.md                 Entrypoint: operating rules + routing
├── references/
│   ├── cli.md               ksef2-cli commands, output, pagination, async
│   ├── sdk-api.md           ksef2 SDK imports, clients, handles, retries, errors
│   ├── auth-security.md     credentials, secrets, profiles, environments
│   └── bot-integration.md   assistant/bot integration
├── evals/prompts.md         11 eval prompts with pass/fail criteria
└── provenance.md            pinned source SHAs, offline checks, limitations
```

## Install

```bash
npx skills add stacking-hq/ksef2-skills --skill ksef2
```

The skills CLI installs into your agent's skills directory
(`.claude/skills/`, `.codex/skills/`, `.grok/skills/`, `.agents/skills/`, …).
Or copy it manually:

```bash
git clone https://github.com/stacking-hq/ksef2-skills
cp -r ksef2-skills/skills/ksef2 ~/.agents/skills/    # or your agent's skills dir
```

**Runtime prerequisites** (the skill does not provide these):

```bash
# Python 3.12+
uv tool install ksef2-cli        # CLI: ksef2 / ksef2-cli
pip install ksef2                # or: uv add ksef2
```

Configure credentials locally — a `ksef2` profile or `KSEF2_*` environment
variables. The agent works in the configured profile and never needs secret
values in chat.

## Use

The agent loads the skill when a task mentions KSeF, `ksef2`, `ksef2-cli`,
FA(3)/FA3 invoices, UPO, invoice metadata, or exports. Invoke it explicitly
with `$ksef2`.

## Evaluate

[`skills/ksef2/evals/prompts.md`](skills/ksef2/evals/prompts.md) contains 11
realistic prompts with pass/fail criteria. Give an agent the skill plus one
prompt in a scratch workspace; do not include the criteria in the prompt.

## Publish

[skills.sh](https://skills.sh) indexes public repositories installed through
the skills CLI; no separate submission is needed. Keep
`skills/ksef2/SKILL.md` at that path, and update the pins in
[provenance.md](skills/ksef2/provenance.md) when upstream moves.

## License

[MIT](LICENSE)
