# ksef2 SDK reference

Verified against `ksef2 1.1.0` at the commit pinned in
[../provenance.md](../provenance.md). Public-API contract and exception
hierarchy come from the pinned source docs; the checks marked *verified* were
executed offline (no KSeF credentials, no network).

## Install

```bash
pip install ksef2
# or
uv add ksef2
```

Python 3.12+. Extras: `ksef2[pdf]` (local invoice PDF rendering),
`ksef2[runtime-checks]` (opt-in via `KSEF2_RUNTIME_CHECKS=1`).

## Stable import paths

These are the paths intended to survive the 1.x line (verified importable):

| Import | Use for |
| --- | --- |
| `ksef2` | `Client`, `AsyncClient`, `Environment`, `TransportConfig`, `TimeoutConfig`, `RetryConfig`, `TlsConfig`, `ConnectionPoolConfig`, `FormSchema`, public `KSeF*` exceptions, `__version__`. |
| `ksef2.clients` | Workflow types: `InvoicesService`, `BatchService`, `InvoiceSubmission`, `ExportJob`, `GeneratedToken`, `PermissionOperation`, `CertificateEnrollment`, `ExportedInvoices`, `Pager`, `OperationHandle` (+ async twins). |
| `ksef2.models` | Request/response/filter/pagination models (`InvoicesFilter`, `InvoiceMetadataParams`, `Page`), resume-state models, `XAdESCredentials`, signing-certificate records. |
| `ksef2.fa3` | `InvoiceBuilder` (canonical FA(3) builder), drafts and FA(3) domain models. |
| `ksef2.xades` | Certificate/key loading, TEST certificate generation, local XAdES signing, `LocalSigner`. |
| `ksef2.profiles` | `Profile`, `ProfileStore`, auth descriptors — read/write `ksef2-cli` profile config. |
| `ksef2.logging` | `configure_logging()` (opt-in; the SDK is silent by default). |
| `ksef2.certificate_stores` | Signing-certificate store protocols and adapters. |
| `ksef2.testdata` | TEST-only `generate_nip`, `generate_pesel`. |
| `ksef2.renderers` | `InvoiceXSLTRenderer`, `InvoicePDFExporter` (PDF needs `[pdf]`). |
| `ksef2.raw`, `ksef2.raw.mappers` | Low-level endpoint clients and schema-native `spec` / `supp` models. |

Rules from the contract: a module path without an underscore is public,
anything with an underscore is private (`ksef2._core` …) and may change in a
minor release; never import generated models from the private schema package.
Prefer the highest-level import that fits:

```python
from ksef2 import Client, Environment, FormSchema, KSeFApiError
from ksef2.fa3 import InvoiceBuilder, KsefInvoiceDraft, VatRate
from ksef2.models import InvoicesFilter, InvoiceMetadataParams
from ksef2.xades import XAdESCredentials, load_certificate_from_pem
```

## Clients and environments

```python
from ksef2 import Client, Environment

with Client(Environment.TEST) as client:      # construction is local; no request yet
    ...
```

| Environment | Base URL *(verified)* | Role |
| --- | --- | --- |
| `Environment.TEST` | `https://api-test.ksef.mf.gov.pl/v2` | Development, TEST-only helpers, real work only with test data. |
| `Environment.DEMO` | `https://api-demo.ksef.mf.gov.pl/v2` | Production-like behavior, non-production credentials. |
| `Environment.PRODUCTION` | `https://api.ksef.mf.gov.pl/v2` | Real taxpayer workflows — explicit user request only. |

`AsyncClient` mirrors `Client` with `await`. Environment choice is an
operational boundary: credentials, profiles, persisted session data, invoice
numbers, and download URLs are scoped to it. `with_profile()` rejects a
profile whose environment does not match the client's, and TEST-only helpers
enforce themselves — `with_test_certificate()` outside `Environment.TEST`
raises `KSeFUnsupportedEnvironmentError` before any request *(verified)*.

## Authentication → AuthenticatedClient

```text
Client(Environment.X)
  -> client.authentication
     .with_token(ksef_token=..., nip=...)        # KSeF token
     .with_xades(nip=..., cert=..., private_key=...)  # XAdES from loaded material
     .with_test_certificate(nip=...)             # TEST only, generated material
     .with_profile("name") | .with_profile()     # local ksef2-cli profile
  -> AuthenticatedClient (access + refresh tokens)
```

Each `with_*` call authenticates one context — these hit KSeF and need real
credentials. Access tokens renew automatically: shortly before expiry and once
after a `401`, concurrent requests share one refresh
(`TransportConfig(auto_refresh_tokens=True)` is the default). A dead refresh
token raises `KSeFAuthenticationExpiredError` — authenticate again. Rejected
inputs fail locally: an invalid NIP checksum raises `KSeFArgumentError` with
a `hint` before any request *(verified)*.

## Offline-verified snippet

Local FA(3) building plus client construction — runs with no credentials
(executed at the pinned version):

```python
from datetime import date, datetime, timezone
from decimal import Decimal

from ksef2 import Client, Environment, FormSchema
from ksef2.fa3 import InvoiceBuilder, VatRate

SELLER_NIP = "5261040828"
invoice_number = f"QS/{datetime.now(timezone.utc):%Y%m%d%H%M%S}"

invoice_xml = (
    InvoiceBuilder()
    .header(system_info="ksef2 quickstart")
    .seller(name="Demo Seller Sp. z o.o.", tax_id=SELLER_NIP, country_code="PL",
            address_line_1="Prosta 1", address_line_2="00-001 Warszawa")
    .buyer(name="Demo Buyer Sp. z o.o.", country_code="PL",
           address_line_1="Kwiatowa 2", address_line_2="00-002 Warszawa")
    .standard()
    .issue_date(date.today())
    .issue_place("Warszawa")
    .invoice_number(invoice_number)
    .rows()
    .add_line(name="Consulting service", quantity=Decimal("1"),
              unit_price_net=Decimal("100.00"), vat_rate=VatRate.VAT_23)
    .done().done()
    .to_xml().encode("utf-8")
)

client = Client(Environment.TEST)               # no network at construction
```

## Sending invoices (needs credentials)

```python
from ksef2 import Client, Environment, FormSchema

with Client(Environment.TEST) as client:
    auth = client.authentication.with_test_certificate(nip=SELLER_NIP)
    with auth.online_session(form_code=FormSchema.FA3) as session:
        submission = session.send_invoice(invoice_xml)   # InvoiceSubmission handle
        status = submission.wait(timeout=120.0)          # polls until KSeF number or failure
        upo = submission.download_upo()                  # never waits; KSeFNotReadyError if early
    processed = auth.invoices.download(status.ksef_number, timeout=120.0)
```

Handles and their waits *(names verified on the installed classes)*:

| Handle | Wait for | Later reads |
| --- | --- | --- |
| `InvoiceSubmission` | `.wait(timeout)` → invoice status with `ksef_number` | `.download_upo()`, `.reference_number`, `.resume_state()` |
| `GeneratedToken` | `.wait()` → activation | `.token` readable immediately; `.resume_state()` |
| `PermissionOperation` | `.wait()` → grant/revoke applied | `.resume_state()` |
| `CertificateEnrollment` | `.wait()` → issued | `.resume_state()` |
| `ExportJob` | `.wait()` → decrypted `ExportedInvoices` | `.resume_state()` (**carries AES secrets**) |

Rules that matter in practice:

- A local timeout is a deadline, not a verdict: resume with the stored
  reference number instead of resubmitting blindly.
- `download_upo()` never waits — call `wait()` first; too early raises
  `KSeFNotReadyError` carrying a `hint`.
- A session summary can report success while individual invoices inside it
  failed — inspect per-invoice status (`session.list_failed_invoices()`).
- `model_dump()` / `model_dump_json()` / `repr()` redact secrets and are for
  logging only — **not a persistence format**. Persist with `to_dict()` /
  `to_json()` on resume states, `to_sensitive_dict()` on secret-bearing
  responses, and `PreparedBatch.to_sensitive_json()`; restore with the
  matching `from_*` methods.

## Querying, downloads, exports

```python
from ksef2.models import InvoicesFilter, InvoiceMetadataParams

filters = InvoicesFilter.for_seller(
    date_type="issue_date",
    date_from="2026-10-01T00:00:00Z",
    date_to="2026-10-31T00:00:00Z",     # range must not exceed 100 days
)
pager = auth.invoices.search(filters, InvoiceMetadataParams(sort_order="asc"))
for page in pager.responses():           # typed pages; .pages(), .first_response(), .wait() also exist
    for invoice in page.invoices:
        ...
```

- `auth.invoices.search(...)` returns `InvoiceSearchPager` with `responses()`,
  `pages()`, `page(cursor)`, `first_page()`, `first_response()`, `wait()`
  *(methods verified)*. Generic `Pager` (tokens, certificates, permissions,
  sessions, …) exposes `pages()`, `page(cursor)`, `first_page()`, `wait()`.
- `page(cursor)` returns `next_cursor` (`Page` fields: `items`,
  `next_cursor` *(verified)*); store it to resume the same search in another
  process. Only `next_cursor is None` ends the search — an empty page can
  still name the next one.
- The filter's date span is validated client-side: over 100 days raises
  `KSeFValidationError` before any request *(verified)*.
- Direct download: `auth.invoices.download(ksef_number, timeout=...)` polls
  until the document is available.
- Export: `auth.invoices.export(filters)` → `ExportJob`; `.wait()` downloads,
  decrypts, and returns `ExportedInvoices` (`.invoices()`, `.metadata`,
  `.archive`, `.save()`). Persist `job.resume_state().to_json()` as a
  credential to survive a restart; resume with
  `auth.invoices.export(state=...)`.

### Incremental sync (HWM)

For unattended sync, KSeF's `permanent_storage_hwm_date` is the safe boundary:
filter with `date_type="permanent_storage"` and
`restrict_to_permanent_storage_hwm_date=True`, persist all pages deduplicated
by `ksef_number`, then store the HWM as the next start point — only after every
page was consumed. Keep the previous checkpoint when KSeF omits the HWM or the
final response is truncated.

## Retries and transport

`TransportConfig(retry=RetryConfig(), timeouts=TimeoutConfig(), …)` — defaults
*(verified against the installed classes)*:

| `RetryConfig` | Default |
| --- | --- |
| `max_attempts` | `3` |
| `initial_delay` / `max_delay` / `backoff_multiplier` | `0.5` / `4.0` / `2.0` |
| `max_retry_after` | `120.0` |
| `retryable_status_codes` | `(429, 502, 503, 504)` |
| `jitter` | `True` (full jitter; `Retry-After` never jittered) |

What the retry middleware actually covers:

- `GET` and most permission/certificate/metadata-query `POST`s retry;
  `Retry-After` above `max_retry_after` gives up immediately with
  `KSeFRateLimitError` carrying `retry_after`.
- Invoice submission retries only on `429` — that response proves the invoice
  was not processed. After `5xx` or a lost response, check
  `session.list_invoices()` before resending.
- Permission grants, certificate enrollment, token generation, and session
  opening are **not** retried — persist the reference and resume by status.
- Authentication redemption is never retried: a lost response raises
  `KSeFAuthTokenRedemptionError` with `outcome_ambiguous=True`.
- `wait()` pollers count retry backoff against their own `timeout`.

Concurrency: the SDK does not throttle downloads — bound them in your
application and consult `auth.limits` for current KSeF limits.

## Errors

Branch on the exception class or `exc.ksef_code`; never on message text or
`hint` (wording changes between releases). Narrow subclasses first:

```python
from ksef2 import (
    KSeFApiError, KSeFException, KSeFNotReadyError,
    KSeFRateLimitError, KSeFTransportError,
)

try:
    ...
except KSeFRateLimitError as exc:
    schedule_after(exc.retry_after)
except KSeFNotReadyError:
    ...  # KSeF not done yet; ask again later
except KSeFApiError as exc:
    report(trace_id=exc.trace_id, ksef_code=exc.ksef_code)
except KSeFTransportError as exc:
    if exc.outcome_ambiguous:
        check_before_resending()   # KSeF may have taken the request
except KSeFException as exc:
    log(exc.context, exc.hint)
```

Key classes: `KSeFApiError` (`status_code`, `ksef_code`, `trace_id`),
`KSeFTransportError` (`outcome_ambiguous`), `KSeFNotReadyError`,
`KSeFRateLimitError` (`retry_after`), `KSeFValidationError` (local input,
also subclasses `ValueError`), `KSeFPollingTimeoutError` (local deadline),
`KSeFInvoiceRejectedError` (invoice refused inside a session),
`KSeFSessionFailedError`, `KSeFAuthenticationExpiredError`. Catching
`KSeFException` covers every SDK-classified failure — no `httpx` exception
reaches the caller.

## Logging

Silent by default, structured through the standard `ksef2` logger; opt in with
`configure_logging(level="INFO", renderer="console")`. Tokens, keys, and
presigned URLs are excluded from log events.

## Verifying SDK claims

Compare imports, attributes, and defaults with the pinned upstream SDK source.
See [../provenance.md](../provenance.md) for the recorded offline checks and
their limitations.
