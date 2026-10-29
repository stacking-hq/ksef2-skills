# Authentication

Use one auth method per invocation. Prefer a named profile so commands do
not contain secret values.

```bash
ksef2 profile create company --env production --nip 5261040828 --token-env KSEF2_TOKEN
ksef2 --profile company --json auth login
```

Configure `KSEF2_TOKEN` locally through the host's secret mechanism. Profiles
store environment, NIP, paths, and secret variable names, not secret values.
Config lives at `~/.config/ksef2/config.toml`; inspect its location with
`ksef2 config path`. Select a profile with `--profile NAME` or `KSEF2_PROFILE`.

| Method | CLI configuration | SDK |
| --- | --- | --- |
| KSeF token | `KSEF2_TOKEN`, `KSEF2_NIP` | `with_token(ksef_token=…, nip=…)` |
| TEST certificate | `--env test --nip … --test-cert` | `with_test_certificate(nip=…)` |
| PEM certificate | `--cert FILE --key FILE`, `KSEF2_KEY_PASSWORD` | `with_xades(nip=…, cert=…, private_key=…)` |
| PKCS#12 | `--p12 FILE`, `KSEF2_P12_PASSWORD` | `load_certificate_and_key_from_p12`, then `with_xades(nip=…, credentials=…)` |
| Saved auth | `--auth-state FILE` | `client.authentication.resume(state)` |

TEST certificates work only in TEST. TEST data is not private; use synthetic
invoices. Credentials and references cannot move between TEST, DEMO, and
production. An SDK client's environment must match its profile.

Auth resume files contain access/refresh tokens; receipts, session state,
batch artifacts, and export handles can contain AES keys. Store them in a
private directory outside the repository. CLI continuation files use mode
`0600`, but remain unencrypted. Avoid `--show-tokens` in assistant workflows.

Successful login does not imply permission to read or send invoices. For an
authorization failure, check the context NIP, environment, and
`ksef2 --profile company permissions entity-roles --all`.
