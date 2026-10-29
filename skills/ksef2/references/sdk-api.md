# Python SDK and API

Install `ksef2` with `uv add ksef2` or `pip install ksef2` on Python 3.12+.
Use public imports: `ksef2` for clients, environments, and exceptions;
`ksef2.models` for filters; `ksef2.fa3` for invoice building;
`ksef2.xades` for certificate loading. Avoid private `ksef2._*` modules.

## Connect

```python
from ksef2 import Client, Environment

with Client(Environment.PRODUCTION) as client:
    auth = client.authentication.with_profile("company")
    # Use auth.invoices, auth.online_session, etc. within this context.
```

Match environment to the configured profile. For synthetic development,
use `Environment.TEST` with `with_test_certificate(nip=…)`. See
[auth-security.md](auth-security.md) for other auth methods.
`AsyncClient` provides async counterparts. For direct endpoint access, use
`ksef2.raw` and its schema models; consult the linked upstream docs for the
endpoint's exact request/response rather than guessing REST payloads.

## Build FA(3) locally

This portion needs no credentials:

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

Use `auth` inside the authenticated client context shown above.
For purchases, replace `for_seller` with `for_buyer`.

```python
from ksef2.models import InvoicesFilter, InvoiceMetadataParams

filters = InvoicesFilter.for_seller(
    date_type="issue_date",
    date_from="2026-10-01T00:00:00Z",
    date_to="2026-11-01T00:00:00Z",     # range must not exceed 100 days
)
pager = auth.invoices.search(filters, InvoiceMetadataParams(sort_order="asc"))
for page in pager.responses():           # typed pages; .pages(), .first_response(), .wait() also exist
    for invoice in page.invoices:
        ...
```

- `auth.invoices.search(...)` returns `InvoiceSearchPager` with `responses()`,
  `pages()`, `page(cursor)`, `first_page()`, `first_response()`, `wait()`.
  Generic `Pager` (tokens, certificates, permissions,
  sessions, …) exposes `pages()`, `page(cursor)`, `first_page()`, `wait()`.
- `page(cursor)` returns `next_cursor` (`Page` fields: `items`,
  `next_cursor`); store it to resume the same search in another
  process. Only `next_cursor is None` ends the search — an empty page can
  still name the next one.
- The filter's date span is validated client-side: over 100 days raises
  `KSeFValidationError` before any request.
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

## Errors and retries

Handle SDK exception classes or `ksef_code`, not message wording:

- `KSeFApiError`: inspect `status_code`, `ksef_code`, `trace_id`.
- `KSeFRateLimitError`: respect `retry_after`.
- `KSeFNotReadyError`: poll later; UPO may not be ready yet.
- `KSeFPollingTimeoutError`: local deadline, resume status checks.
- `KSeFTransportError`: inspect `outcome_ambiguous` before retrying writes.
- `KSeFAuthenticationExpiredError`: authenticate again.

The SDK handles token refresh and selected transient retries. Invoice
submission retries only on `429`; after a lost response or `5xx`, inspect
session status before resending. Bound application download concurrency.
Configure transport through `TransportConfig`, `RetryConfig`, and
`TimeoutConfig`; inspect installed signatures for tuning options.
