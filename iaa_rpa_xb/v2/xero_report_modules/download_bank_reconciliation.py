"""
Module for downloading Bank Reconciliation reports from Xero Blue.

This module handles downloading a Bank Reconciliation report for a SINGLE named
bank account, plus a separate query to enumerate the available accounts. The two
are deliberately split:

    list_all_bank_accounts(browser)            -> list[str]   (a query)
    download_bank_reconciliation_report(...)    -> None        (one account)

An operator who wants one account calls download directly; for several, they loop
their own names; for all, they call list_all_bank_accounts and loop the result.
Because the download function always processes exactly one account, it needs no
return value (the caller already knows every report's name), and partial-failure
policy across many accounts is the caller's concern, not this module's.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser). Depends only on iaa_rpa_utils.

Period:
    `start_date` and `end_date` are the primary inputs (``datetime.date``); each
    falls back independently to the financial year (1 Jul prior year / 30 Jun FY)
    when omitted, so `financial_year` is required only as a fallback.

Export format:
    "excel" -> .xlsx, "pdf" -> .pdf. The saved extension comes from the
    _EXPORT_FORMATS table, never from a caller string. (Styled PDF and Google
    Sheets are intentionally unsupported - Styled PDF needs extra dialogs.)

No-data behaviour:
    After Update, the Export button only appears when the report has data. If it
    is absent, the account has nothing to reconcile for the period and a
    RuntimeError is raised (carried over from the original module's logic).

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits (overridable per run via
        BankReconciliationRequest.element_timeout).
    EXPORT_TIMEOUT          - the Update/Export/format buttons, which can be slow
        because Xero builds the report/file server-side.

How to call:
    from datetime import date
    from download_bank_reconciliation import (
        BankReconciliationRequest,
        download_bank_reconciliation_report,
        list_all_bank_accounts,
    )

    # One account:
    request = BankReconciliationRequest(
        bank_account="1-0100 - Impact Operating Account",   # full label
        end_date=date(2024, 6, 30),
        start_date=date(2023, 7, 1),
        download_directory=r"C:\\Reports",
        report_file_name="bank_rec_operating_2024",
        # export_format="excel",   # "excel" -> .xlsx (default) or "pdf" -> .pdf
        # financial_year=2024,     # used to derive any omitted date
    )
    download_bank_reconciliation_report(browser, request)

    # All accounts:
    for account in list_all_bank_accounts(browser):
        req = BankReconciliationRequest(
            bank_account=account,
            financial_year=2024,
            download_directory=r"C:\\Reports",
            report_file_name=f"bank_rec_{account}",
        )
        download_bank_reconciliation_report(browser, req)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED, so the caller can
    detect failure (and decide its own per-account policy when looping).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog, xpath_literal

# Set up logger
logger = setup_logger(__name__)


# Public API of this module. Step helpers are intentionally left out; only these
# names are the supported surface.
__all__ = [
    "BankReconciliationRequest",
    "download_bank_reconciliation_report",
    "list_all_bank_accounts",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5  # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10  # seconds; Update/Export/format - Xero builds server-side
_MIN_FINANCIAL_YEAR = 2000  # earliest financial year we accept

# Locale-independent month abbreviations, matching Xero's date-field format
# (e.g. "1 Jul 2023"). Avoids strftime('%b') locale surprises.
_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Bank-account autocompleter (combobox) and its dropdown listbox. Both functions
# open the combobox; only the download path types into it to filter.
_COMBOBOX_LOCATOR = (
    "xpath://input[@data-automationid='Bank Account-selector-autocompleter--input']"
)
_ACCOUNT_ITEM_LOCATOR = (
    "xpath://div[@data-automationid='Bank Account-selector-autocompleter--list']"
    "//li[@aria-label]"
)

# Read every account name (the <li> aria-label) from the open dropdown. The
# wrapper exposes no multi-element find, so we read them in one JS call - the
# data-automationid/aria-label hooks are the same ones we'd target via xpath.
_ENUMERATE_ACCOUNTS_JS = (
    "return Array.from("
    "document.querySelectorAll("
    "'div[data-automationid=\"Bank Account-selector-autocompleter--list\"] li[aria-label]'"
    ")).map(function (el) { return el.getAttribute('aria-label'); });"
)

# Settings panel and toolbar controls.
_UPDATE_LOCATOR = "xpath://button[@data-automationid='settings-panel-update-button']"
_EXPORT_BUTTON_LOCATOR = (
    "xpath://button[@data-automationid='report-toolbar-export-button']"
)

# Supported export formats: format name -> (menu-item locator, saved extension).
# The saved extension is the source of truth for the filename.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (
        "xpath://li[@id='report-toolbar-export-excel-menuitem']//button[contains(@class,'xui-pickitem--body')]",
        ".xlsx",
    ),
    "pdf": (
        "xpath://li[@id='report-toolbar-export-pdf-menuitem']//button[contains(@class,'xui-pickitem--body')]",
        ".pdf",
    ),
}


def _format_xero_date(d: date) -> str:
    """Format a date the way Xero's date field expects, e.g. "1 Jul 2023"
    (no leading zero on the day; locale-independent month abbreviation)."""
    return f"{d.day} {_MONTH_ABBR[d.month - 1]} {d.year}"


@dataclass(frozen=True, kw_only=True)
class BankReconciliationRequest:
    """Everything needed to download one Bank Reconciliation report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename. The extension is forced to match the
                            export format; ``dest_path`` normalises it.
        bank_account:       FULL account label exactly as shown in the dropdown /
                            returned by list_all_bank_accounts (e.g.
                            "1-0100 - Impact Operating Account"). Required.
        start_date:         Period start (``datetime.date``). Primary input; falls
                            back to "1 Jul {financial_year - 1}" if omitted.
        end_date:           Period end (``datetime.date``). Primary input; falls
                            back to "30 Jun {financial_year}" if omitted.
        financial_year:     FY end year as an int (e.g. 2024). Required only as a
                            fallback when start_date or end_date is omitted.
        export_format:      "excel" (saved .xlsx) or "pdf" (saved .pdf).
        window_title:       Title used to locate the Chrome Save As window.
        element_timeout:    Seconds to wait for general elements (default
                            DEFAULT_ELEMENT_TIMEOUT).
    """

    download_directory: str
    report_file_name: str
    bank_account: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "Bank Reconciliation"
    element_timeout: int = DEFAULT_ELEMENT_TIMEOUT

    def __post_init__(self) -> None:
        # bank_account is required and must be non-empty (it drives selection).
        if not isinstance(self.bank_account, str) or not self.bank_account.strip():
            raise ValueError("bank_account is required and must be a non-empty string")

        # export_format must be one we have a menu item + saved extension for.
        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        # Provided dates must be real date objects (datetime is a date subclass).
        for label, value in (
            ("start_date", self.start_date),
            ("end_date", self.end_date),
        ):
            if value is not None and not isinstance(value, date):
                raise TypeError(
                    f"{label} must be a datetime.date, got {type(value).__name__}"
                )

        # financial_year is the fallback source; required only when a date is missing.
        if (
            self.start_date is None or self.end_date is None
        ) and self.financial_year is None:
            raise ValueError(
                "financial_year is required when start_date or end_date is omitted"
            )

        # Validate financial_year when present. bool is an int subclass, exclude it.
        if self.financial_year is not None:
            if not isinstance(self.financial_year, int) or isinstance(
                self.financial_year, bool
            ):
                raise TypeError(
                    f"financial_year must be an int, got {type(self.financial_year).__name__}"
                )
            max_year = datetime.now().year + 2
            if not _MIN_FINANCIAL_YEAR <= self.financial_year <= max_year:
                raise ValueError(
                    f"financial_year must be between {_MIN_FINANCIAL_YEAR} and {max_year}, "
                    f"got {self.financial_year}"
                )

    @property
    def resolved_start_date(self) -> str:
        """Start date as a Xero-formatted string, deriving from the financial
        year when no explicit start_date was given."""
        if self.start_date is not None:
            return _format_xero_date(self.start_date)
        return f"1 Jul {self.financial_year - 1}"

    @property
    def resolved_end_date(self) -> str:
        """End date as a Xero-formatted string, deriving from the financial year
        when no explicit end_date was given."""
        if self.end_date is not None:
            return _format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def saved_extension(self) -> str:
        """The extension Xero actually produces for the chosen format - the
        source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def format_locator(self) -> str:
        """The export-menu item locator for the chosen format."""
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def dest_path(self) -> str:
        """Full save path. The extension is forced to match the export format's
        real output, and is not doubled if ``report_file_name`` already ends in it."""
        ext = self.saved_extension  # includes the leading dot, e.g. ".xlsx"
        name = self.report_file_name
        if name.lower().endswith(ext.lower()):
            name = name[: -len(ext)]
        return os.path.join(self.download_directory, f"{name}{ext}")

    def summary_lines(self) -> list[str]:
        """Human-readable "label : value" rows describing this request, with
        the colons aligned. Used for the run's opening log block."""
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
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def list_all_bank_accounts(
    browser, *, element_timeout: int = DEFAULT_ELEMENT_TIMEOUT
) -> list[str]:
    """
    Enumerate every bank account available on the Bank Reconciliation page.

    Opens the bank-account dropdown and returns each option's full label (e.g.
    "1-0100 - Impact Operating Account"), in the order the dropdown lists them.
    Returns an empty list when the organisation has no bank accounts - that empty
    result is the no-accounts signal, not an error.

    This is a pure query: it does not select an account or generate a report. Use
    the returned labels as the ``bank_account`` value for
    ``download_bank_reconciliation_report``.

    Args:
        browser: SeleniumBrowser wrapper instance.
        element_timeout: Seconds to wait for the dropdown to populate.

    Returns:
        list[str]: Full account labels, or [] if none are available.
    """
    logger.info("Opening bank account dropdown to enumerate accounts...")
    browser.click_element(_COMBOBOX_LOCATOR, timeout=element_timeout)

    if not browser.does_page_contain_element(
        _ACCOUNT_ITEM_LOCATOR, timeout=element_timeout
    ):
        logger.info("No bank accounts available for this organisation")
        return []

    accounts = browser.execute_javascript(_ENUMERATE_ACCOUNTS_JS) or []
    accounts = [a for a in accounts if a]  # drop any empty/None labels
    logger.info(f"Found {len(accounts)} bank account(s): {accounts}")
    return accounts


def download_bank_reconciliation_report(
    browser, request: BankReconciliationRequest
) -> None:
    """
    Download a Bank Reconciliation report for one named bank account.

    Owns the order of operations and calls each step in sequence:
        STEP 1 - select the bank account
        STEP 2 - enter the From/To period dates
        STEP 3 - update the report and export it (raising if there is no data)

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (BankReconciliationRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. If the
        named account is not found in the dropdown, the selection click raises.
        If the report has no data, raises ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download Bank Reconciliation Report", logger):
        # Echo the request so the log is self-describing
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
    """
    Open the bank-account dropdown, filter to the requested account, and select it.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (BankReconciliationRequest): Supplies the account label and timeout.

    Returns:
        None

    Raises:
        Selection raises if the account is not present in the dropdown (e.g. a
        label that does not match any option).
    """
    timeout = request.element_timeout
    account = request.bank_account

    logger.info(f"Selecting bank account: '{account}'")
    # Open the combobox (also exits its readonly resting state) and type to filter.
    browser.click_element(_COMBOBOX_LOCATOR, timeout=timeout)
    browser.send_keys_to_active_element(account)

    # Select the matching option's pickitem button, scoped to the bank-account
    # list and keyed on the exact aria-label (quoted safely for apostrophes etc.).
    select_locator = (
        f"xpath://div[@data-automationid='Bank Account-selector-autocompleter--list']"
        f"//li[@aria-label={xpath_literal(account)}]"
        f"//button[contains(@class,'xui-pickitem--body')]"
    )
    browser.click_element(select_locator, timeout=timeout)
    logger.info(f"Bank account selected: '{account}'")


def enter_report_dates(browser, request: BankReconciliationRequest) -> None:
    """
    Enter the From and To period dates into the report settings.

    From <- start date, To <- end date.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (BankReconciliationRequest): Supplies the resolved dates and timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    logger.info("Entering report period dates...")

    _type_date(
        browser,
        "id:report-settings-custom-date-input-from",
        request.resolved_start_date,
        timeout,
    )
    logger.info(f"Entered From date: {request.resolved_start_date}")

    _type_date(
        browser,
        "id:report-settings-custom-date-input-to",
        request.resolved_end_date,
        timeout,
    )
    logger.info(f"Entered To date: {request.resolved_end_date}")


def _type_date(browser, locator: str, value: str, timeout: int) -> None:
    """Focus a type-in date field and replace its contents with ``value``
    (CTRL+A / DELETE / type / TAB), via the wrapper's active-element keys."""
    browser.click_element(locator, timeout=timeout)
    browser.send_keys_to_active_element("\ue009" + "a")  # CTRL + A to select all
    browser.send_keys_to_active_element("\ue003")  # DELETE to clear existing value
    browser.send_keys_to_active_element(value)  # Type the date
    browser.send_keys_to_active_element("\ue004")  # TAB to confirm and move on


def generate_and_export_report(browser, request: BankReconciliationRequest) -> None:
    """
    Update the report, verify it has data, export to the chosen format, and save.

    Clicks 'Update' to generate the report. The Export button appears only when
    the report has data, so its absence is treated as "no data for this account"
    and raises ``RuntimeError``. Otherwise opens the Export menu, clicks the
    format item, and hands the Chrome save dialog to ``handle_chrome_save_as_dialog``.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (BankReconciliationRequest): Supplies the export format, window
            title, dest path and element_timeout.

    Returns:
        None

    Raises:
        RuntimeError: If the Export button does not appear (no report data).
    """
    timeout = request.element_timeout
    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(_UPDATE_LOCATOR, timeout=EXPORT_TIMEOUT)
    logger.info("'Update' clicked. Waiting for the report to render...")

    # The Export button only renders once the report has data.
    if not browser.does_page_contain_element(_EXPORT_BUTTON_LOCATOR, timeout=timeout):
        logger.warning(
            "Export button not found - no Bank Reconciliation data for this account"
        )
        raise RuntimeError("No Bank Reconciliation data available for this account.")
    logger.info("'Export' button present - report contains data")

    # Open the Export menu and click the chosen format item.
    logger.info(
        f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')..."
    )
    browser.click_element(_EXPORT_BUTTON_LOCATOR, timeout=EXPORT_TIMEOUT)
    logger.info("Export menu opened")

    browser.click_element(request.format_locator, timeout=EXPORT_TIMEOUT)
    logger.info(f"Selected '{request.export_format}' export format")

    # Brief settle so the download/save dialog has rendered before we drive it.
    time.sleep(3)

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")
