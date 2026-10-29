# ksef2-skills

An Agent Skill for accessing KSeF invoices with
[ksef2-cli](https://github.com/stacking-hq/ksef2-cli) and developing Python
integrations with [ksef2](https://github.com/stacking-hq/ksef2).

## Install

```bash
npx skills add stacking-hq/ksef2-skills --skill ksef2
```

The host must load standard `SKILL.md` packages and provide code execution,
Python 3.12+, network access, and locally configured credentials.

```bash
uv tool install ksef2-cli  # For CLI tasks
pip install ksef2         # For Python applications
```

## Use

Ask the assistant to query purchase or sales invoices, export XML, check a
submission and retrieve UPO, or build a KSeF application integration.
The skill uses your configured environment and keeps secrets outside chat.

[SKILL.md](skills/ksef2/SKILL.md) contains the working rules and routes to four
short references: CLI workflows, Python SDK, authentication, and bot integration.
[Source versions](skills/ksef2/provenance.md) record the upstream baseline.
Live authenticated workflows have not been tested.

## Maintain

Check commands with `ksef2 <group> <command> --help` and compare SDK examples
with upstream source for the installed version. Maintainer evaluation prompts
live in [evals/prompts.md](evals/prompts.md), outside the installed skill.

To distribute updates, push the repository and smoke-test the install command.

## License

[MIT](LICENSE)
