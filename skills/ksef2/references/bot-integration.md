# Bot integration

A skill supplies instructions. The host supplies shell or SDK tools, Python,
network access, and credentials.

1. Map the authenticated chat user to an authorized profile and NIP in host
   code. A profile name in a message is not proof of access.
2. Expose allowed operations through argument arrays or typed SDK calls.
   Keep message text out of shell command strings.
3. Use JSON for CLI results; check the exit code before parsing stdout.
4. Save resumable operation state in the user's private storage. Return the
   status/reference and resume later when a bounded wait expires.
5. Return only requested invoice data; restrict downloads to that user's
   directory. Separate state by user, taxpayer, and environment.

Follow the working rules in [../SKILL.md](../SKILL.md). Tool implementations
must enforce authorization themselves; model instructions do not enforce it.
See [cli.md](cli.md) for commands and [sdk-api.md](sdk-api.md) for Python calls.
