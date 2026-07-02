"""
Module for downloading Account Transactions reports from Xero Blue.

A date-range report with a MULTI-select accounts filter. It uses the shared
modern report toolbar; the accounts selector is report-specific (the ACCT_
config section).

Configures and downloads one report: enters the date range, sets the accounts
filter (all accounts, or an exact set), exports (Excel or PDF), and verifies the
saved file. Everything selected in the filter lands in a SINGLE exported file.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(shared SH_ + ACCT_ sections); shared behaviour lives in common.py.

ERROR HANDLING: like leave balances and the summary reports, this module raises
the library's TYPED exceptions from ``iaa_rpa_utils.exceptions``:
  - DataValidationError - a request input failed validation
  - DataExtractionError - no report data, or a requested account is not present
  - DownloadError       - the export file did not land on disk

Accounts filter:
    `accounts` is either the literal "All" (every account - the default) or a
    list of exact account labels as shown in the selector (e.g.
    ["1-0100 - Impact Operating Account", "200 - Sales"]). Account labels are
    per-organisation, so they are matched EXACTLY against the live dropdown at
    runtime (not a baked-in list); a requested account with no exact match
    raises rather than silently selecting the wrong rows.

Period:
    A date range. `start_date`/`end_date` are the primary inputs
    (``datetime.date``); when either is omitted it is derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY).

How to call:
    from datetime import date
    from download_account_transactions import (
        AccountTransactionsRequest, download_account_transactions_report,
    )

    request = AccountTransactionsRequest(
        download_directory=r"C:\\Reports",
        report_file_name="account_transactions_2024",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        # financial_year=2024,     # alternative to start/end; either can fall back to FY
        # accounts=["200 - Sales", "6-1400 - Bank charges"],   # default "All"
        # export_format="excel",   # "excel" (default, .xlsx) or "pdf" (.pdf)
    )
    download_account_transactions_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. No data, or a
    requested account not found, raises the relevant typed exception; a file
    that fails to save raises ``DownloadError``.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.exceptions import (
    DataExtractionError,
    DataValidationError,
    DownloadError,
)
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog, xpath_literal

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "AccountTransactionsRequest",
    "download_account_transactions_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Sentinel meaning "every account". Anything else must be a list of exact labels.
ALL_ACCOUNTS = "All"

# Export formats: format name -> (shared format-menu option id, saved extension).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}

# Keystrokes for clearing the search box (no trailing TAB - that would close the
# dropdown; common.clear_and_type commits with TAB, which we don't want here).
_CTRL_A = "\ue009" + "a"
_DELETE = "\ue003"


@dataclass(frozen=True, kw_only=True)
class AccountTransactionsRequest:
    """Everything needed to download one Account Transactions report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
        accounts:           "All" (default) or a list of exact account labels.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.

    Raises (on construction):
        DataValidationError: if any input fails validation.
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    accounts: list[str] | Literal["All"] = ALL_ACCOUNTS
    export_format: ExportFormat = "excel"
    window_title: str = "Account Transactions"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.download_directory, str) or not self.download_directory.strip():
            raise DataValidationError("download_directory is required and must be a non-empty string")
        if not isinstance(self.report_file_name, str) or not self.report_file_name.strip():
            raise DataValidationError("report_file_name is required and must be a non-empty string")

        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        # accounts: either the "All" sentinel, or a non-empty list of non-empty strings.
        if isinstance(self.accounts, str):
            if self.accounts != ALL_ACCOUNTS:
                raise DataValidationError(
                    f"accounts must be a list of account labels or the literal {ALL_ACCOUNTS!r}, "
                    f"got the string {self.accounts!r}"
                )
        elif isinstance(self.accounts, list):
            if not self.accounts:
                raise DataValidationError(
                    f"accounts list is empty; pass {ALL_ACCOUNTS!r} to include every account"
                )
            for a in self.accounts:
                if not isinstance(a, str) or not a.strip():
                    raise DataValidationError("each account must be a non-empty string")
        else:
            raise DataValidationError(
                f"accounts must be a list[str] or the literal {ALL_ACCOUNTS!r}, "
                f"got {type(self.accounts).__name__}"
            )

        for value, name in ((self.start_date, "start_date"), (self.end_date, "end_date")):
            if value is not None and not isinstance(value, date):
                raise DataValidationError(f"{name} must be a datetime.date, got {type(value).__name__}")

        if (self.start_date is None or self.end_date is None) and self.financial_year is None:
            raise DataValidationError("financial_year is required when start_date or end_date is omitted")

        if self.financial_year is not None:
            if not isinstance(self.financial_year, int) or isinstance(self.financial_year, bool):
                raise DataValidationError(
                    f"financial_year must be an int, got {type(self.financial_year).__name__}"
                )
            max_year = datetime.now().year + 2
            if not common.MIN_FINANCIAL_YEAR <= self.financial_year <= max_year:
                raise DataValidationError(
                    f"financial_year must be between {common.MIN_FINANCIAL_YEAR} and {max_year}, "
                    f"got {self.financial_year}"
                )

        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise DataValidationError(
                f"start_date ({self.start_date}) must not be after end_date ({self.end_date})"
            )

        if self.capture_screenshots and not (self.screenshot_path or "").strip():
            raise DataValidationError(
                "screenshot_path is required when capture_screenshots is True"
            )

    @property
    def select_all_accounts(self) -> bool:
        return self.accounts == ALL_ACCOUNTS

    @property
    def resolved_start_date(self) -> str:
        if self.start_date is not None:
            return common.format_xero_date(self.start_date)
        return f"1 Jul {self.financial_year - 1}"

    @property
    def resolved_end_date(self) -> str:
        if self.end_date is not None:
            return common.format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def export_menu_id(self) -> str:
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def saved_extension(self) -> str:
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def dest_path(self) -> str:
        return common.build_dest_path(self.download_directory, self.report_file_name, self.saved_extension)

    def summary_lines(self) -> list[str]:
        accounts_desc = "All accounts" if self.select_all_accounts else f"{len(self.accounts)} account(s)"
        rows = {
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from dates)",
            "Accounts": accounts_desc,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Capture Screenshots": self.capture_screenshots,
            "Screenshot Path": self.screenshot_path if self.capture_screenshots else "(disabled)",
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_account_transactions_report(browser, request: AccountTransactionsRequest) -> None:
    """
    Download an Account Transactions report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the date range
        STEP 2 - set the accounts filter (all, or an exact set)
        STEP 3 - update, confirm data, export, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it.
        DataExtractionError if there is no data or a requested account is absent;
        DownloadError if the file fails to save.
    """
    with ProcessLogger("Xero Blue Download Account Transactions Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report date range...")
        configure_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: date range entered")

        logger.info("STEP 2: Configuring accounts filter...")
        configure_accounts(browser, request)
        logger.info("STEP 2 COMPLETED: accounts filter set")

        logger.info("STEP 3: Updating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


def configure_report_dates(browser, request: AccountTransactionsRequest) -> None:
    """Enter the From (start) and To (end) dates."""
    common.clear_and_type(browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date)
    logger.info(f"Entered start date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered end date: {request.resolved_end_date}")


def configure_accounts(browser, request: AccountTransactionsRequest) -> None:
    """Set the accounts filter. "All" clicks Select all; a list first resets to a
    clean slate (Select all -> Deselect all) then selects each requested account
    by its exact aria-label, raising if one is not present."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    logger.info("Opening the accounts selector...")
    browser.click_element(config.ACCT_SELECTOR_OPEN_BUTTON, timeout=timeout)

    if request.select_all_accounts:
        # Select all unless everything is already selected (toggle already reads
        # "Deselect all"); clicking is a no-op we simply skip.
        if browser.does_page_contain_element(config.ACCT_SELECT_ALL, timeout=timeout):
            browser.click_element(config.ACCT_SELECT_ALL, timeout=timeout)
        logger.info("Selected all accounts")
        return

    # Reset to an empty selection so the final set is exactly what was requested.
    # If nothing is selected yet, Select all is showing - click it so a Deselect
    # all becomes available; then Deselect all clears everything.
    if browser.does_page_contain_element(config.ACCT_SELECT_ALL, timeout=timeout):
        browser.click_element(config.ACCT_SELECT_ALL, timeout=timeout)
    browser.click_element(config.ACCT_DESELECT_ALL, timeout=timeout)
    logger.info("Cleared existing account selection")

    for account in request.accounts:
        logger.info(f"Selecting account: '{account}'...")
        _search_accounts(browser, account, timeout)
        item_locator = config.ACCT_ITEM_BODY_TPL.format(label=xpath_literal(account))
        if not browser.does_page_contain_element(item_locator, timeout=timeout):
            raise DataExtractionError(f"Requested account not found in the selector: {account!r}")
        browser.click_element(item_locator, timeout=timeout)
        logger.info(f"Selected account: '{account}'")


def _search_accounts(browser, term: str, timeout: int) -> None:
    """Clear the accounts search box and type a filter term (no trailing TAB, so
    the dropdown stays open)."""
    browser.click_element(config.ACCT_SELECTOR_INPUT, timeout=timeout)
    browser.send_keys_to_active_element(_CTRL_A)
    browser.send_keys_to_active_element(_DELETE)
    browser.send_keys_to_active_element(term)


def update_and_export_report(browser, request: AccountTransactionsRequest) -> None:
    """Update the report, confirm data exists, export to the chosen format, and
    verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "account_transactions", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # The Export button only renders when the report has data.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no account transactions data for this selection")
        raise DataExtractionError("No Account Transactions data available for this selection.")
    logger.info("'Export' button present - data confirmed")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "account_transactions", "after_update",
        enabled=request.capture_screenshots,
    )

    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)

    time.sleep(2)   # brief settle so the save dialog has rendered

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
