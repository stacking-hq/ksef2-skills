# Authentication and security

Single source for credentials, secret storage, and environments.

## Choose one method

Exactly one authentication method per command — two methods fail before any
request:

```bash
ksef2 --env test --nip 5261040828 --test-cert --token <value> --json auth login
# exit 1, AuthenticationConfigError: "Provide only one auth method: token (--token), test certificate (--test-cert)."
```

| Method | CLI options | Env vars | SDK helper |
| --- | --- | --- | --- |
| KSeF token | `--token` (alias `--ksef-token`) | `KSEF2_TOKEN`, `KSEF2_NIP`, `KSEF2_CONTEXT_TYPE` | `with_token(ksef_token=…, nip=…)` |
| TEST certificate | `--test-cert` | `KSEF2_TEST_CERT`, `KSEF2_NIP` | `with_test_certificate(nip=…)` — **TEST only** |
| PEM XAdES | `--cert`, `--key`, `--key-password` | `KSEF2_CERT`, `KSEF2_KEY`, `KSEF2_KEY_PASSWORD` | `with_xades(nip=…, cert=…, private_key=…)` |
| PKCS#12/PFX XAdES | `--p12`, `--p12-password` | `KSEF2_P12`, `KSEF2_P12_PASSWORD` | load via `ksef2.xades.load_certificate_and_key_from_p12(...)`, then `with_xades(nip=…, credentials=…)` |
| Saved auth state | `--auth-state FILE` | `KSEF2_AUTH_STATE` | `client.authentication.resume(state)` |

Most methods also need the context NIP (`--nip` / `KSEF2_NIP`).

TEST certificate material is TEST-only. Both layers enforce it before any
request is sent:

```bash
ksef2 --env production --nip 5261040828 --test-cert --json auth login
# exit 2: "Invalid value for --test-cert: Test certificates require the TEST environment."
```

```python
Client(Environment.PRODUCTION).authentication.with_test_certificate(nip="5261040828")
# KSeFUnsupportedEnvironmentError: with_test_certificate() is only available for Environment.TEST
```

## Profiles: configuration, not credentials

Profiles store non-secret defaults — environment, NIP, auth type,
certificate paths, polling settings, and the **name** of the environment
variable holding each secret:

```bash
ksef2 profile create prod-token --env production --nip 5261040828 --token-env KSEF2_TOKEN
ksef2 profile use prod-token
ksef2 profile show prod-token
```

Config file: `~/.config/ksef2/config.toml` (`ksef2 config path`; override with
`--config` / `KSEF2_CONFIG`). The SDK reads the same file via `ProfileStore` /
`with_profile()`. Selection order: explicit `--profile NAME` → `KSEF2_PROFILE`
→ `active_profile` in the file. The profile's environment must match the
client's or command's environment — `with_profile()` rejects a mismatch.

A profile never contains token values, key passwords, or PKCS#12 passwords.

## What to protect

| Value | Why |
| --- | --- |
| KSeF token | Authenticates into its context until revoked or expired. |
| Access / refresh tokens | Authorize calls; the refresh token mints new access tokens. |
| Private key, cert/key/P12 passwords | Prove the XAdES identity. |
| Auth resume state | Full access + refresh tokens, rehydrates an authenticated client. |
| Online/batch session state, receipts | Session AES key and IV — can continue the workflow. |
| Export handles, `batch prepare` artifacts | Decryption keys next to encrypted invoice payloads. |

Keep secrets in environment variables, a secret manager, or
application-owned secure storage. Chat, displayed commands, shell history,
logs, and issue comments stay credential-free: reference `KSEF2_TOKEN`,
`--token-env KSEF2_TOKEN`, `company.key`, `ksef2-auth.json` — never the value
behind them. Presigned download URLs stay out too. Never ask the user to
paste a token, password, or private key into the conversation.

## Files the CLI writes are credentials

Every continuation file below is written with mode `0600` — plain text,
unencrypted. The mode keeps other users out; it does not survive copies,
backups, Docker layers, or a commit.

| File | Holds |
| --- | --- |
| `auth login --save-state` | Access and refresh bearer tokens. |
| `online open --state-file`, `online send --save-state`, `--receipt` from an online send | Session AES key and IV (an online receipt *is* resumable session state). |
| `--handle-file` on exports | Export decryption key and IV. |
| `batch prepare --out` | Session key beside the encrypted invoice payloads. |
| `batch submit --state-file` | Session key and prepared-package digest. |

Write them only when a later command needs them — a single command
authenticates on its own, so `auth login --save-state` is rarely needed. Keep
them outside the repository, listed in `.gitignore`, in a private
directory such as `$XDG_RUNTIME_DIR` on a shared machine, and delete them when
the workflow ends (`ksef2 --auth-state ksef2-auth.json --json auth logout`
removes the state file once KSeF confirms the session ended).

## Output stays masked

`auth login`, `auth resume`, and `auth refresh` print a short prefix and
suffix of each token beside its expiry — a log or pasted comment keeps
nothing reusable. `--show-tokens` prints the raw bearer tokens instead; a
command that also uses `--save-state` stays masked even under `--show-tokens`.
Agents never pass `--show-tokens`. In `--json` mode, every recognized secret is replaced with `<redacted>`
before encoding. When a later command needs the credential, save it to a file
rather than capturing output.

## Environments

- PRODUCTION is the only environment for real workflows. DEMO is
  production-like but not for real taxpayers. TEST is intentionally loose and
  its data is not private — never put real invoice data there.
- A command with no `--env` and no profile runs against TEST. A query meant
  for production then returns TEST data, or nothing, without an error — name
  the profile or environment in every command.

## Authentication is not authorization

A credential that authenticates can still lack permissions for the operation:
sending invoices, querying metadata, managing tokens, and granting permissions
are separate rights. When a protected call fails after successful
authentication, check environment, context NIP, and the active permission set
together (`ksef2 permissions entity-roles --all`).
