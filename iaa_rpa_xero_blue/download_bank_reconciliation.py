"""
Module for downloading Bank Reconciliation reports from Xero Blue.

Configures and downloads a Bank Reconciliation report for ONE named bank
account: selects the account, enters the From/To period dates, generates the
report, exports it (Excel or PDF), and confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour (date formatting, validation, the input/pick-list primitives,
the save-path/file-check helpers) lives in common.py. This module composes those.

Inputs are modelled as a dataclass:
    BankReconciliationRequest - everything one download needs. The live
                                browser/engine is passed separately.

One call -> one file: a request names a single bank_account and a single
export_format. To cover several accounts or both formats, the caller loops and
calls once per combination.

Period:
    A date-range report (From + To). `start_date`/`end_date` are the primary
    inputs (``datetime.date``); when either is omitted they are derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY), so
    `financial_year` is required only as a fallback.

Account discovery:
    list_all_bank_accounts(browser) is a standalone helper that returns the
    available account labels (or [] if none). Use it to pick a valid
    `bank_account` value; it does not generate a report.

How to call:
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
        # financial_year=2024,     # used to derive dates if either is omitted
        # export_format="excel",   # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="Bank Reconciliation",
    )
    download_bank_reconciliation_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. A named account not
    found in the dropdown raises on the selection click. No report data, or a
    file that fails to save, raises ``RuntimeError``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog, xpath_literal

import common
import config


logger = setup_logger(__name__)


__all__ = [
    "BankReconciliationRequest",
    "download_bank_reconciliation_report",
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


@dataclass(frozen=True, kw_only=True)
class BankReconciliationRequest:
    """Everything needed to download one Bank Reconciliation report.

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
    """

    download_directory: str
    report_file_name: str
    bank_account: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "Bank Reconciliation"

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")
        common.validate_non_empty_str(self.bank_account, "bank_account")

        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        common.validate_optional_date(self.start_date, "start_date")
        common.validate_optional_date(self.end_date, "end_date")
        if (self.start_date is None or self.end_date is None) and self.financial_year is None:
            raise ValueError("financial_year is required when start_date or end_date is omitted")
        if self.financial_year is not None:
            common.validate_financial_year(self.financial_year)
        common.validate_date_order(self.start_date, self.end_date)

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
        return common.build_dest_path(self.download_directory, self.report_file_name, self.saved_extension)

    def summary_lines(self) -> list[str]:
        """Aligned "label : value" rows for the opening log block."""
        rows = {
            "Bank Account": self.bank_account,
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from dates)",
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def list_all_bank_accounts(browser, *, element_timeout: int = common.DEFAULT_ELEMENT_TIMEOUT) -> list[str]:
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
    if not browser.does_page_contain_element(config.BRR_ACCOUNT_ANY_ITEM, timeout=element_timeout):
        logger.info("No bank accounts available for this organisation")
        return []

    accounts = browser.execute_javascript(_ENUMERATE_ACCOUNTS_JS) or []
    accounts = [a for a in accounts if a]  # drop any empty/None labels
    logger.info(f"Found {len(accounts)} bank account(s): {accounts}")
    return accounts


def download_bank_reconciliation_report(browser, request: BankReconciliationRequest) -> None:
    """
    Download a Bank Reconciliation report for one named bank account.

    Steps, in order (each returns; none calls the next):
        STEP 1 - select the bank account
        STEP 2 - enter the From/To period dates
        STEP 3 - update the report, export it, and verify the saved file

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (BankReconciliationRequest): All configuration for the download.

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. A missing
        account raises on the selection click; no data, or a file that fails to
        save, raises ``RuntimeError``.
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
        generate_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


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
    common.clear_and_type(browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date)
    logger.info(f"Entered From date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered To date: {request.resolved_end_date}")


def generate_and_export_report(browser, request: BankReconciliationRequest) -> None:
    """Update the report, confirm it has data, export to the chosen format, and
    verify the saved file."""
    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)
    logger.info("'Update' clicked. Waiting for the report to render...")

    # The Export button only renders once the report has data.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no Bank Reconciliation data for this account")
        raise RuntimeError("No Bank Reconciliation data available for this account.")
    logger.info("'Export' button present - report contains data")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export menu opened")

    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)
    logger.info(f"Selected '{request.export_format}' export format")

    # Brief settle so the download/save dialog has rendered before we drive it.
    time.sleep(3)

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
