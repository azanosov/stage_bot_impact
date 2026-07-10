"""
Module for downloading Bank Reconciliation reports from Xero Blue.

Two entry points, one per shape of job:

    download_bank_reconciliation_report(browser, request)
        ONE named bank account -> ONE file. Configured by
        ``BankReconciliationRequest``.

    download_bank_reconciliation_multi_accounts(browser, request)
        Several accounts, or every account ("All") -> one file per account.
        Configured by ``BankReconciliationMultiRequest``.

The two request classes are FLAT SIBLINGS (neither inherits the other): the
single models exactly one download -> one file (and owns ``dest_path``); the
multi models a fan-out over accounts (and has no single ``dest_path``). Each
reads as what it is at the call site - a multi job uses the multi class, a
single job uses the single class - with no dataclass nested inside a dataclass.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour (date formatting, validation, the input/pick-list primitives,
the save-path/file-check helpers) lives in common.py. This module composes those.

Period (both requests):
    A date-range report (From + To). `start_date`/`end_date` are the primary
    inputs (``datetime.date``); when either is omitted they are derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY), so
    `financial_year` is required only as a fallback.

Account discovery:
    list_all_bank_accounts(browser) is a standalone helper that returns the
    available account labels (or [] if none). Use it to pick a valid
    `bank_account` value; it does not generate a report.

Screenshots:
    Both requests take `capture_screenshots` (default True) and `screenshot_path`.
    When capturing is on, a before/after screenshot of the report is written to
    `screenshot_path` around the export step, and `screenshot_path` is required
    (validated at construction). Set `capture_screenshots=False` to disable it;
    `screenshot_path` may then be omitted.

How to call (single):
    from datetime import date
    from download_bank_reconciliation import (
        BankReconciliationRequest, download_bank_reconciliation_report,
    )

    request = BankReconciliationRequest(
        download_directory=r"C:\\Reports",
        report_file_name="bank_rec_2024",
        bank_account="1-0100 - Impact Operating Account",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
    )
    saved_path = download_bank_reconciliation_report(browser, request)

How to call (multi):
    from download_bank_reconciliation import (
        BankReconciliationMultiRequest, download_bank_reconciliation_multi_accounts,
    )

    request = BankReconciliationMultiRequest(
        accounts="All",                       # or ["1-0100 - Op", "1-1000 - Cheque"]
        download_directory=r"C:\\Reports",
        report_file_name="bank_rec_2024",     # BASE name; "_<account>" appended per file
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
    )
    saved_paths = download_bank_reconciliation_multi_accounts(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED with their original
    types. A named account not found in the dropdown raises on the selection
    click. No report data raises ``DataExtractionError``; a file that fails to
    save raises ``DownloadError`` (from the save/verify helpers). The multi entry
    point is fail-fast: it stops on the first failing account and re-raises that
    account's original exception (files already saved remain on disk).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog, xpath_literal

from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError

from . import common
from . import config

logger = setup_logger(__name__)


__all__ = [
    "BankReconciliationRequest",
    "BankReconciliationMultiRequest",
    "download_bank_reconciliation_report",
    "download_bank_reconciliation_multi_accounts",
    "list_all_bank_accounts",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Read every account label (the <li> aria-label) from the open dropdown in one
# JS call (the wrapper exposes no multi-element find). Targets the same list
# automation-id as config.BRR_ACCOUNT_LIST.
_ENUMERATE_ACCOUNTS_JS = (
    "return Array.from("
    "document.querySelectorAll("
    "'div[data-automationid=\"Bank Account-selector-autocompleter--list\"] li[aria-label]'"
    ")).map(function (el) { return el.getAttribute('aria-label'); });"
)

# Export formats: format name -> (shared format-menu option id, saved extension).
# The extension is the source of truth for the filename.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}

# The only bare-string value ``accounts`` accepts on the multi request; anything
# else must be a list. Compared case-insensitively.
_ALL_ACCOUNTS = "All"

# Characters Windows forbids in a filename; replaced with '_' in account names.
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


# ====================================================================
# SHARED VALIDATION (used by both request classes; declared once)
# ====================================================================
def _validate_common_report_fields(
    *,
    download_directory: str,
    report_file_name: str,
    export_format: str,
    start_date: date | None,
    end_date: date | None,
    financial_year: int | None,
    capture_screenshots: bool,
    screenshot_path: str | None,
) -> None:
    """Validate the fields shared by the single and multi requests.

    Kept as one function (rather than duplicated in each __post_init__) so the
    period/format/screenshot rules can never drift between the two classes.
    Raises DataValidationError on the first problem found.
    """
    common.validate_non_empty_str(download_directory, "download_directory")
    common.validate_non_empty_str(report_file_name, "report_file_name")

    if export_format not in get_args(ExportFormat):
        raise DataValidationError(
            f"export_format must be one of {get_args(ExportFormat)}, got {export_format!r}"
        )

    common.validate_optional_date(start_date, "start_date")
    common.validate_optional_date(end_date, "end_date")
    if (start_date is None or end_date is None) and financial_year is None:
        raise DataValidationError(
            "financial_year is required when start_date or end_date is omitted"
        )
    if financial_year is not None:
        common.validate_financial_year(financial_year)
    common.validate_date_order(start_date, end_date)

    if capture_screenshots and not (screenshot_path or "").strip():
        raise DataValidationError(
            "screenshot_path is required when capture_screenshots is True"
        )


@dataclass(frozen=True, kw_only=True)
class BankReconciliationRequest:
    """Everything needed to download ONE Bank Reconciliation report (one file).

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        bank_account:       Exact account label as shown in the dropdown, e.g.
                            "1-0100 - Impact Operating Account". Required.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
        capture_screenshots: Whether to capture before/after screenshots of the
                            report during export (default True). When True,
                            ``screenshot_path`` is required.
        screenshot_path:    Directory the screenshots are written to. Required
                            when ``capture_screenshots`` is True; ignored (and may
                            be None) when it is False.
    """

    download_directory: str
    report_file_name: str
    bank_account: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "Bank Reconciliation"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.bank_account, "bank_account")
        _validate_common_report_fields(
            download_directory=self.download_directory,
            report_file_name=self.report_file_name,
            export_format=self.export_format,
            start_date=self.start_date,
            end_date=self.end_date,
            financial_year=self.financial_year,
            capture_screenshots=self.capture_screenshots,
            screenshot_path=self.screenshot_path,
        )

    @property
    def resolved_start_date(self) -> str:
        """Start date as a Xero-formatted string, deriving from the financial
        year (1 Jul of the prior year) when no explicit start_date was given."""
        if self.start_date is not None:
            return common.format_xero_date(self.start_date)
        return f"1 Jul {self.financial_year - 1}"

    @property
    def resolved_end_date(self) -> str:
        """End date as a Xero-formatted string, deriving from the financial year
        (30 Jun of the FY) when no explicit end_date was given."""
        if self.end_date is not None:
            return common.format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def export_menu_id(self) -> str:
        """The shared export-menu option id for the chosen format."""
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def saved_extension(self) -> str:
        """The extension Xero produces for the chosen format (source of truth)."""
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def dest_path(self) -> str:
        """Full save path, extension forced to match the export format."""
        return common.build_dest_path(
            self.download_directory, self.report_file_name, self.saved_extension
        )

    def summary_lines(self) -> list[str]:
        """Aligned "label : value" rows for the opening log block."""
        rows = {
            "Bank Account": self.bank_account,
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": (
                self.financial_year
                if self.financial_year is not None
                else "(from dates)"
            ),
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Capture Screenshots": self.capture_screenshots,
            "Screenshot Path": (
                self.screenshot_path if self.capture_screenshots else "(disabled)"
            ),
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


@dataclass(frozen=True, kw_only=True)
class BankReconciliationMultiRequest:
    """A Bank Reconciliation job spanning several, or all, accounts (one file each).

    A FLAT sibling of ``BankReconciliationRequest`` - it carries the same report
    configuration fields directly (no nested request), plus ``accounts``. The
    downloader builds one ``BankReconciliationRequest`` per account from these
    fields, so the shared configuration is expressed once, at this call site.

    Attributes:
        accounts: Either the literal ``"All"`` (case-insensitive) to enumerate and
            run EVERY account on the page, or a non-empty LIST of exact account
            labels. NOTE: a single account is passed as a one-element list
            (e.g. ``["1-0100 - Operating"]``); a bare account-name string is NOT
            accepted - only ``"All"`` is valid as a string.
        download_directory: Directory the report files are saved to.
        report_file_name:   BASE output filename. Per account, a filesystem-safe
            ``_<account>`` fragment is appended (and de-duplicated) - so this is
            the base name, NOT the literal filename of any one file.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
        capture_screenshots: Whether to capture before/after screenshots of each
                            account's report during export (default True). When
                            True, ``screenshot_path`` is required. Applied to every
                            per-account download.
        screenshot_path:    Directory the screenshots are written to. Required
                            when ``capture_screenshots`` is True; ignored (and may
                            be None) when it is False.
    """

    accounts: Literal["All"] | list[str] = _ALL_ACCOUNTS
    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "Bank Reconciliation"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        # accounts: "All" (case-insensitive) OR a non-empty list of non-empty
        # strings. A bare account-name string is rejected - one account goes in a
        # one-element list.
        if isinstance(self.accounts, str):
            if self.accounts.strip().lower() != _ALL_ACCOUNTS.lower():
                raise DataValidationError(
                    "accounts as a string is only valid as 'All'; pass a single "
                    f"account as a one-element list (e.g. ['{self.accounts}']), "
                    "not as a bare string"
                )
        elif isinstance(self.accounts, list):
            if not self.accounts:
                raise DataValidationError(
                    "accounts list must be non-empty; use 'All' or account name(s)"
                )
            if not all(isinstance(a, str) and a.strip() for a in self.accounts):
                raise DataValidationError(
                    "accounts list must contain only non-empty account-name strings"
                )
        else:
            raise DataValidationError(
                "accounts must be 'All' or a list[str], got "
                f"{type(self.accounts).__name__}"
            )

        # Reuse the single request's field rules (period/format/screenshot) so
        # they cannot drift. Any problem raises DataValidationError here, at
        # construction, before the browser is touched.
        _validate_common_report_fields(
            download_directory=self.download_directory,
            report_file_name=self.report_file_name,
            export_format=self.export_format,
            start_date=self.start_date,
            end_date=self.end_date,
            financial_year=self.financial_year,
            capture_screenshots=self.capture_screenshots,
            screenshot_path=self.screenshot_path,
        )

    def to_single_request(self, *, bank_account: str, report_file_name: str) -> "BankReconciliationRequest":
        """Build the per-account single request from this job's shared fields."""
        return BankReconciliationRequest(
            download_directory=self.download_directory,
            report_file_name=report_file_name,
            bank_account=bank_account,
            start_date=self.start_date,
            end_date=self.end_date,
            financial_year=self.financial_year,
            export_format=self.export_format,
            window_title=self.window_title,
            capture_screenshots=self.capture_screenshots,
            screenshot_path=self.screenshot_path,
        )


def list_all_bank_accounts(
    browser, *, element_timeout: int = common.DEFAULT_ELEMENT_TIMEOUT
) -> list[str]:
    """
    Enumerate every bank account available on the Bank Reconciliation page.

    Opens the dropdown and returns each option's full label (e.g.
    "1-0100 - Impact Operating Account"), or [] when the organisation has no
    bank accounts. A pure query - it does not select an account or generate a
    report.

    Args:
        browser: SeleniumBrowser wrapper instance.
        element_timeout: Seconds to wait for the dropdown to populate.

    Returns:
        list[str]: Full account labels, or [] if none are available.
    """
    logger.info("Opening bank account dropdown to enumerate accounts...")
    browser.click_element(config.BRR_ACCOUNT_INPUT, timeout=element_timeout)

    # LEGACY: no-accounts is signalled by the absence of any account <li>. This
    # detection is inherited as-is and has NOT been re-verified against a real
    # organisation that has zero bank accounts - treat the empty-list path with
    # caution and confirm against a no-accounts org before relying on it.
    if not browser.does_page_contain_element(
        config.BRR_ACCOUNT_ANY_ITEM, timeout=element_timeout
    ):
        logger.info("No bank accounts available for this organisation")
        return []

    accounts = browser.execute_javascript(_ENUMERATE_ACCOUNTS_JS) or []
    accounts = [a for a in accounts if a]  # drop any empty/None labels
    logger.info(f"Found {len(accounts)} bank account(s): {accounts}")
    return accounts


def download_bank_reconciliation_report(
    browser, request: BankReconciliationRequest
) -> str:
    """
    Download a Bank Reconciliation report for one named bank account.

    Steps, in order:
        STEP 1 - select the bank account
        STEP 2 - enter the From/To period dates
        STEP 3 - update the report, export it, and verify the saved file

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (BankReconciliationRequest): All configuration for the download.

    Returns:
        str: The full path of the saved report (directory + filename + extension).

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. A missing
        account raises on the selection click; no data raises
        ``DataExtractionError``; a file that fails to save raises ``DownloadError``.
    """
    with ProcessLogger("Xero Blue Download Bank Reconciliation Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Selecting bank account...")
        select_bank_account(browser, request)
        logger.info("STEP 1 COMPLETED: bank account selected")

        logger.info("STEP 2: Entering report period dates...")
        enter_report_dates(browser, request)
        logger.info("STEP 2 COMPLETED: from and to dates entered")

        logger.info("STEP 3: Generating report and exporting...")
        dest_path = generate_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")

        return dest_path


def select_bank_account(browser, request: BankReconciliationRequest) -> None:
    """Open the bank-account dropdown, filter to the requested account, and
    select it. Raises (on the click) if the account is not in the dropdown."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    account = request.bank_account

    logger.info(f"Selecting bank account: '{account}'")
    # Open the combobox (also exits its readonly resting state) and type to filter.
    browser.click_element(config.BRR_ACCOUNT_INPUT, timeout=timeout)
    browser.send_keys_to_active_element(account)

    # Click the matching option, scoped to the list and keyed on the exact
    # aria-label (safely quoted for apostrophes etc.).
    select_locator = config.BRR_ACCOUNT_ITEM_TPL.format(account=xpath_literal(account))
    browser.click_element(select_locator, timeout=timeout)
    logger.info(f"Bank account selected: '{account}'")


def enter_report_dates(browser, request: BankReconciliationRequest) -> None:
    """Enter the From (start) and To (end) period dates."""
    logger.info("Entering report period dates...")
    common.clear_and_type(
        browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date
    )
    logger.info(f"Entered From date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered To date: {request.resolved_end_date}")


def generate_and_export_report(browser, request: BankReconciliationRequest) -> str:
    """Update the report, confirm it has data, export to the chosen format, and
    verify the saved file. Returns the saved file's full path."""
    common.capture_report_screenshot(
        browser,
        request.screenshot_path,
        "bank_reconciliation",
        "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)
    logger.info("'Update' clicked. Waiting for the report to render...")

    # The Export button only renders once the report has data.
    if not browser.does_page_contain_element(
        config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT
    ):
        logger.warning(
            "Export button not found - no Bank Reconciliation data for this account"
        )
        raise DataExtractionError(
            "No Bank Reconciliation data available for this account."
        )
    logger.info("'Export' button present - report contains data")

    logger.info(
        f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')..."
    )
    common.capture_report_screenshot(
        browser,
        request.screenshot_path,
        "bank_reconciliation",
        "after_update",
        enabled=request.capture_screenshots,
    )

    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export menu opened")

    common.click_pickitem_by_id(
        browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT
    )
    logger.info(f"Selected '{request.export_format}' export format")

    # Brief settle so the download/save dialog has rendered before we drive it.
    time.sleep(3)

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)
    logger.info(f"File successfully saved: '{dest_path}'")
    return dest_path


# --------------------------------------------------------------------
# Multi-account fan-out
# --------------------------------------------------------------------
def _safe_account_filename_part(account: str) -> str:
    """Turn a bank-account label into a filesystem-safe filename fragment:
    replace forbidden characters with '_', collapse runs of whitespace, and trim
    trailing dots/spaces (which Windows silently strips). Never returns empty."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", account)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(" .")
    return cleaned or "account"


def _dedupe_filename(name: str, seen: set[str]) -> str:
    """Return ``name`` if unused, else ``name_2``, ``name_3``, ... Comparison is
    case-insensitive because the target filesystem (Windows) is."""
    if name.lower() not in seen:
        seen.add(name.lower())
        return name
    n = 2
    while True:
        candidate = f"{name}_{n}"
        if candidate.lower() not in seen:
            seen.add(candidate.lower())
            return candidate
        n += 1


def download_bank_reconciliation_multi_accounts(
    browser, request: BankReconciliationMultiRequest
) -> list[str]:
    """
    Download Bank Reconciliation reports for several, or all, bank accounts.

    Resolves ``request.accounts`` ("All" -> enumerate; otherwise the given list),
    then builds one ``BankReconciliationRequest`` per account from the job's
    shared fields - overriding ``bank_account`` and appending a filesystem-safe,
    de-duplicated ``_<account>`` fragment to ``report_file_name`` so each account
    lands in its own file. Each download is delegated to
    ``download_bank_reconciliation_report`` and its saved path collected.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (BankReconciliationMultiRequest): The accounts to run and the
            shared report configuration.

    Returns:
        list[str]: Absolute paths of the saved files, in processing order.

    Raises:
        DataExtractionError: ``"All"`` resolved to no accounts - failed loudly
            rather than silently saving nothing (an empty result can also mean the
            account dropdown never populated).
        Any exception from ``download_bank_reconciliation_report`` propagates on the
        first failing account (fail-fast); files already saved for earlier accounts
        remain on disk and their count is logged.
    """
    with ProcessLogger(
        "Xero Blue Download Bank Reconciliation (multiple accounts)", logger
    ):
        # ---- resolve request.accounts into a concrete list of account labels ----
        accounts = request.accounts
        if isinstance(accounts, str):
            # Validated to be "All" (case-insensitive) at construction.
            logger.info("Resolving 'All' - enumerating available bank accounts...")
            resolved = list_all_bank_accounts(browser)
            if not resolved:
                raise DataExtractionError(
                    "No bank accounts found for this organisation (requested "
                    "'All'); nothing to download. If accounts do exist, the "
                    "account dropdown may not have populated."
                )
        else:
            # A non-empty list of non-empty strings (validated at construction).
            resolved = list(accounts)

        logger.info(f"Processing {len(resolved)} bank account(s): {resolved}")

        # ---- fan out: one download per account, fail-fast ----
        saved_paths: list[str] = []
        seen_names: set[str] = set()
        base_name = request.report_file_name

        for index, account in enumerate(resolved, start=1):
            file_name = _dedupe_filename(
                f"{base_name}_{_safe_account_filename_part(account)}", seen_names
            )
            per_account = request.to_single_request(
                bank_account=account, report_file_name=file_name
            )
            logger.info(
                f"[{index}/{len(resolved)}] Bank Reconciliation for '{account}' "
                f"-> '{file_name}'"
            )
            try:
                saved_path = download_bank_reconciliation_report(browser, per_account)
            except Exception:
                logger.error(
                    f"Bank Reconciliation failed on account {index}/{len(resolved)} "
                    f"('{account}') - saved {len(saved_paths)} of {len(resolved)} "
                    f"before failure."
                )
                raise
            saved_paths.append(saved_path)
            logger.info(f"[{index}/{len(resolved)}] Saved: {saved_path}")

        logger.info(
            f"All {len(saved_paths)} Bank Reconciliation report(s) saved successfully"
        )
        return saved_paths
