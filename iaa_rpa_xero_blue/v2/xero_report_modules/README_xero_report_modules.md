# Xero Blue report download modules

Seven refactored, parallel modules for downloading reports from Xero Blue.
Each depends only on `iaa_rpa_utils` (the SeleniumBrowser wrapper,
`handle_chrome_save_as_dialog`, `xpath_literal`, `ProcessLogger`, `setup_logger`).

| Module | Orchestrator | Request dataclass | Formats | Saved ext | On failure |
|---|---|---|---|---|---|
| `download_activity_statement.py` | `download_activity_statement_report` | `ActivityStatementRequest` | excel | `.xlsx` | swallow |
| `download_aged_receivables_detail.py` | `download_aged_receivables_detail_report` | `AgedReceivablesRequest` | excel | `.xlsx` | raise |
| `download_aged_payables_detail.py` | `download_aged_payables_detail_report` | `AgedPayablesRequest` | excel | `.xlsx` | raise |
| `download_general_ledger_detail.py` | `download_general_ledger_detail_report` | `GeneralLedgerDetailRequest` | excel | `.xlsx` | raise |
| `download_trial_balance.py` | `download_trial_balance_report` | `TrialBalanceRequest` | excel | `.xlsx` | raise |
| `download_bank_reconciliation.py` | `download_bank_reconciliation_report` (+ `list_all_bank_accounts`) | `BankReconciliationRequest` | excel, pdf | `.xlsx`, `.pdf` | raise |
| `download_gst_reconciliation.py` | `download_gst_reconciliation_report` | `GstReconciliationRequest` | excel, pdf | `.xls`, `.pdf` | raise |

(Activity statement is the only module that swallows on failure, matching its original.)

## Shared conventions
- Inputs are frozen, kw-only dataclasses; the live `browser` is passed separately.
- Orchestrator owns the step sequence; step helpers return rather than chain.
  Paired `STEP N` / `STEP N COMPLETED` logging.
- `__all__` declares the public surface (dataclass(es) + orchestrator [+ query]).
- `DEFAULT_ELEMENT_TIMEOUT = 5` (overridable per run via `element_timeout`);
  `EXPORT_TIMEOUT = 10` for the Update/Export/format buttons.
- `export_format` is a validated `Literal`; the SAVED extension comes from each
  module's `_EXPORT_FORMATS` table, never from a caller-supplied string, so the
  file on disk always matches its bytes. (GST Excel = `.xls`; the others `.xlsx`.)
- Locators are verbatim from the source, routed through the wrapper's `xpath:` /
  `id:` locator API. Where Xero exposes stable `data-automationid`s or option
  `id`s (basis picklist, bank-account list, export menu), locators key off those.

## Per-module specifics
- **GST Reconciliation**: dates are `datetime.date` (primary input), `financial_year`
  is the int fallback (required only when a date is omitted). Two formats
  (excel -> `.xls`, pdf -> `.pdf`). Handles default/legacy UI variants. Raises
  `RuntimeError("No report data available for this client.")` when Export is
  absent (client has no data).
- **Bank Reconciliation**: TWO public functions.
  `list_all_bank_accounts(browser) -> list[str]` enumerates the available account
  labels (returns `[]` when none - the no-accounts signal, not an error).
  `download_bank_reconciliation_report(browser, request)` downloads ONE named
  account (no return value). For several accounts, the operator loops their own
  names; for all, they loop `list_all_bank_accounts(...)`. `bank_account` must be
  the FULL label as returned by enumeration. Two formats (excel -> `.xlsx`,
  pdf -> `.pdf`; Styled PDF / Google Sheets intentionally excluded). After Update,
  an absent Export button means no data -> `RuntimeError`. Account selection
  raises if the label is not found. Account names are quoted with `xpath_literal`
  (handles apostrophes); enumeration reads the dropdown via the wrapper's
  `execute_javascript` (no multi-element find on the wrapper).
- **General Ledger Detail**: `start_date` + `end_date` (`datetime.date`), int FY
  fallback. Adds `accounting_method: Literal["cash", "accrual"]` (default
  `"cash"`) via the More menu, scoped to the stable picklist option IDs
  (`report-settings-accrualbasis-cash/-accrual`), consistent with Trial Balance.
  Original date-placement bug (From/To swapped) is fixed.
- **Trial Balance**: "as at" report - `end_date` only (`datetime.date`), int FY
  fallback. `accounting_method` (default `"cash"`) selected via the picklist,
  scoped to stable option IDs to avoid the separate "Accounting basis" row under
  the picklist's "Show" section. `add_gst_column`. Captures an audit screenshot
  (see below). Raises `RuntimeError("No Trial Balance data available for this
  client.")` on no data.
- **Aged Receivables / Aged Payables**: `financial_year` (int) primary; `end_date`
  optional. Aging method is a validated literal. `add_gst_column`.
- **Activity Statement**: period is a `StatementPeriod(month, year)` value object.

## Breaking changes vs the originals
- `financial_year` is now `int` (was a string) in all modules that take it.
  Callers pass `financial_year=2024`, not `"2024"`.
- `extension` (free string) is replaced by `export_format` (validated literal,
  default `"excel"`). The saved suffix is forced by the module.
- `client_name` and `xero_report_name` removed (logging-only, unused by the UI).
- GST / GL / Bank Rec: dates are `datetime.date` (primary input).
- General Ledger: `accounting_method` is now a parameter (was hardcoded Cash);
  and the From/To dates are no longer swapped.
- Trial Balance: `accounting_method` is now a parameter (was hardcoded Cash).
- Bank Reconciliation: split into a single-account download (no return value)
  plus `list_all_bank_accounts`. The old all-accounts loop and `list[str]` return
  are gone - the caller owns the loop. The dead `is_no_bank_accounts` param is
  removed; `bank_account` is required.

## Behaviour to keep in mind
- A `report_file_name` that already contains a *non-matching* extension is
  appended to, not replaced (e.g. `report.xls` -> `report.xls.xlsx`). Pass a
  bare name; the module adds the correct suffix.
- GST / Trial Balance / Bank Rec `time.sleep(3)` before the save dialog is a
  fixed wait carried over from the originals (candidate to harden later).
- Trial Balance audit screenshot mirrors the (unsupported) take_screenshot
  helper: saved to the current working directory as
  `ExceptionScreenshot_<%y%m%d.%H%M%S>.png`, via the wrapper's `screenshot()`.
  Best-effort - a screenshot failure is logged but does not abort the run.
- General Ledger / Trial Balance assume the Accrual radio is the page default
  (selecting it is an idempotent confirm-click).

---

## Latest update — full contents of this bundle

**Report download modules (the original seven):**
- `download_activity_statement.py`
- `download_aged_receivables_detail.py`
- `download_aged_payables_detail.py`
- `download_general_ledger_detail.py`
- `download_trial_balance.py`
- `download_bank_reconciliation.py`  (+ `list_all_bank_accounts` query)
- `download_gst_reconciliation.py`

**Additional modules:**
- `xero_blue_switch_client.py` — refactor of the client/organisation switcher.
  Plain `xero_blue_switch_client(browser, account_name)` signature (no request
  dataclass — single meaningful input). Fixes carried in: name quoting via
  `xpath_literal` (the old HTML-entity escaping silently failed for names with
  `&`/`'`); every failure path raises (the original could log success while
  switching nothing); post-switch verification; dead code removed; narrow
  exception handling. Timeouts are module constants. Locators are verbatim from
  observed HTML; the "first button" org-selector locator is flagged as fragile.
- `consolidate_workbooks.py` — `consolidate_workbook(request)` moves selected tabs
  from one source workbook into one target, preserving full formatting via Excel
  COM automation (win32com). Mixed `.xls`/`.xlsx` in, always `.xlsx` out. Target
  created on first call, appended thereafter; operator loops sources. Duplicate
  tab names get a truncation-safe `_copy(N)` suffix (respects Excel's 31-char
  limit). Windows + Excel required; COM cleanup in a finally block.

**Tests:**
- `tests/test_request_dataclasses.py` — 52 unit tests over all seven report
  request dataclasses (validation, date resolution, extension-as-source-of-truth,
  `dest_path` normalisation). Pure logic, no browser.
- `tests/conftest.py` — stubs `iaa_rpa_utils` so the modules import in isolation.
- Run with: `python -m pytest tests/ -q`

**Docs:**
- `CODING_GUARDRAILS.md` — coding guide distilled from this work.

### Bug fixed in this update
`dest_path` in the three earliest modules (activity statement, aged receivables,
aged payables) used `name[: -(len(ext) + 1)]`, which stripped one character too
many when a `report_file_name` already ended in its extension (e.g.
`BAS_Q4.xlsx` → `BAS_Q.xlsx`). Corrected to `name[: -len(ext)]`, matching the
other modules. Surfaced and verified by the new test suite.

### Verification status
All nine modules pass `ast.parse`; the 52 dataclass tests pass. The browser- and
COM-driving code paths have NOT been run in a live environment here and still need
a smoke test on a real Windows/Excel/Chrome/Xero box before being trusted —
particularly the switch-client active-organisation locator and the consolidator's
COM flow.
