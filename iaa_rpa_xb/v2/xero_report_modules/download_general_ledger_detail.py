"""
Module for downloading General Ledger Detail reports from Xero Blue.

This module handles the complete workflow for configuring and downloading a
General Ledger Detail report from Xero Blue: resolving the reporting period,
entering the From/To dates, selecting the accounting method (Cash or Accrual)
via the More options menu, updating the report, and exporting it to Excel via
the Windows Save As dialog.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API. No direct
driver access is needed, and the module depends only on iaa_rpa_utils.

Inputs are modelled as a dataclass:
    GeneralLedgerDetailRequest - everything one download needs (period + method +
                                 file/output config). The live browser/engine is
                                 passed separately to the download function.

Structure:
    The orchestrator (download_general_ledger_detail_report) owns the order of
    operations and calls each step in sequence. The step helpers each do one
    thing and return - they do NOT call one another.

Period:
    `start_date` and `end_date` are the primary inputs (``datetime.date``). When
    either is omitted, it is derived from `financial_year` (1 Jul of the prior
    year / 30 Jun of the FY), so `financial_year` is required only as a fallback.

Accounting method:
    `accounting_method` selects Cash or Accrual via the More options menu.
    Defaults to "cash" (the report's long-standing behaviour).

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits. Overridable per run via
        GeneralLedgerDetailRequest.element_timeout.
    EXPORT_TIMEOUT          - the Update/Export/Excel buttons, which can be slow
        because Xero builds the file server-side. Intentionally longer.

How to call:
    from datetime import date
    from download_general_ledger_detail import (
        GeneralLedgerDetailRequest,
        download_general_ledger_detail_report,
    )

    request = GeneralLedgerDetailRequest(
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        download_directory=r"C:\\Reports\\Xero",
        report_file_name="ABC_GL_Detail_2024",
        # accounting_method="cash",   # "cash" (default) or "accrual"
        # financial_year=2024,        # used to derive any omitted date
        # export_format="excel",      # only "excel" supported (saved .xlsx)
        # window_title="General Ledger Detail",
        # element_timeout=5,
    )
    download_general_ledger_detail_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED, so the caller can
    detect failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

# Set up logger
logger = setup_logger(__name__)


# Public API of this module. Step helpers are intentionally left out: they are
# usable/testable individually, but only these names are the supported surface.
__all__ = [
    "GeneralLedgerDetailRequest",
    "download_general_ledger_detail_report",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5  # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10  # seconds; Update/Export/Excel - Xero builds the file server-side
_MIN_FINANCIAL_YEAR = 2000  # earliest financial year we accept

# Locale-independent month abbreviations, matching the labels Xero's date field
# expects (e.g. "1 Jul 2023"). Avoids strftime('%b') locale surprises.
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

# Accounting methods, selected via the More options menu. The value maps to the
# radio's visible label, which the selection locator matches on.
AccountingMethod = Literal["cash", "accrual"]
_ACCOUNTING_LABELS: dict[str, str] = {
    "cash": "Cash",
    "accrual": "Accrual",
}

# Stable picklist option IDs for the accounting basis (confirmed identical to the
# Trial Balance page). Scoping the click locator to these IDs is unambiguous and
# avoids the separate "Accounting Basis" row under the picklist's "Show" section.
_ACCOUNTING_OPTION_IDS: dict[str, str] = {
    "cash": "report-settings-accrualbasis-cash",
    "accrual": "report-settings-accrualbasis-accrual",
}

# Supported export format(s). This report exports Excel only; the value exists so
# the interface matches the other report modules. _EXPORT_FORMATS maps the chosen
# format to the extension Xero actually saves - the source of truth for the
# filename, so the saved file can never disagree with its bytes.
ExportFormat = Literal["excel"]
_EXPORT_FORMATS: dict[str, str] = {
    "excel": ".xlsx",
}


def _format_xero_date(d: date) -> str:
    """Format a date the way Xero's date field expects, e.g. "1 Jul 2023"
    (no leading zero on the day; locale-independent month abbreviation)."""
    return f"{d.day} {_MONTH_ABBR[d.month - 1]} {d.year}"


@dataclass(frozen=True, kw_only=True)
class GeneralLedgerDetailRequest:
    """Everything needed to download one General Ledger Detail report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename. The extension may be included or
                            omitted - ``dest_path`` normalises it and forces the
                            extension that matches the chosen export format.
        start_date:         Period start (``datetime.date``). Primary input;
                            falls back to "1 Jul {financial_year - 1}" if omitted.
        end_date:           Period end (``datetime.date``). Primary input; falls
                            back to "30 Jun {financial_year}" if omitted.
        financial_year:     FY end year as an int (e.g. 2024). Required only as a
                            fallback when start_date or end_date is omitted.
        accounting_method:  "cash" (default) or "accrual".
        export_format:      Export format. Only "excel" is supported for this
                            report (saved as .xlsx).
        window_title:       Title used to locate the Chrome Save As window.
        element_timeout:    Seconds to wait for general elements (default
                            DEFAULT_ELEMENT_TIMEOUT).
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    accounting_method: AccountingMethod = "cash"
    export_format: ExportFormat = "excel"
    window_title: str = "General Ledger Detail"
    element_timeout: int = DEFAULT_ELEMENT_TIMEOUT

    def __post_init__(self) -> None:
        # accounting_method must be one we have a label for.
        if self.accounting_method not in get_args(AccountingMethod):
            raise ValueError(
                f"accounting_method must be one of {get_args(AccountingMethod)}, "
                f"got {self.accounting_method!r}"
            )

        # export_format must be one we have a saved extension for.
        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        # Provided dates must be real date objects (datetime is a date subclass,
        # so it is accepted too - only the calendar part is used).
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
    def accounting_label(self) -> str:
        """The radio's visible label for the chosen accounting method."""
        return _ACCOUNTING_LABELS[self.accounting_method]

    @property
    def saved_extension(self) -> str:
        """The extension Xero actually produces for the chosen format (".xlsx")
        - the source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format]

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
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": (
                self.financial_year
                if self.financial_year is not None
                else "(from dates)"
            ),
            "Accounting Method": self.accounting_label,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_general_ledger_detail_report(
    browser, request: GeneralLedgerDetailRequest
) -> None:
    """
    Download a General Ledger Detail report from Xero Blue.

    Owns the order of operations and calls each step in sequence:
        STEP 1 - enter the From/To period dates
        STEP 2 - select the accounting method (Cash / Accrual)
        STEP 3 - update the report and export it to Excel

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (GeneralLedgerDetailRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it (with timing).
    """
    with ProcessLogger("Xero Blue Download General Ledger Detail Report", logger):
        # Echo the request so the log is self-describing
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report period dates...")
        enter_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: from and to dates entered")

        logger.info("STEP 2: Selecting accounting method...")
        select_accounting_method(browser, request)
        logger.info("STEP 2 COMPLETED: accounting method selected")

        logger.info("STEP 3: Updating report and exporting to Excel...")
        update_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


def enter_report_dates(browser, request: GeneralLedgerDetailRequest) -> None:
    """
    Enter the From and To period dates into the report settings.

    From <- start date, To <- end date. (The original module had these swapped;
    fixed here.)

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (GeneralLedgerDetailRequest): Supplies the resolved dates and
            element_timeout.

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


def select_accounting_method(browser, request: GeneralLedgerDetailRequest) -> None:
    """
    Select the accounting method (Cash / Accrual) via the More options menu.

    Opens the More menu, then clicks the pickitem button for the requested
    method, scoped to its stable option id. Clicking the already-selected method
    is harmless (Accrual is the page default).

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (GeneralLedgerDetailRequest): Supplies the accounting method and
            element_timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    label = request.accounting_label

    option_id = _ACCOUNTING_OPTION_IDS[request.accounting_method]
    more_button_locator = (
        "xpath://button[@type='button' and normalize-space(text())='More']"
    )
    # Click the pickitem button for the chosen option, scoped to its stable id.
    # (The radio inside it is decorative; a bare //span[...='Cash'] could also
    # collide with the "Accounting Basis" row under the picklist's "Show" section.)
    method_locator = (
        f"xpath://li[@id='{option_id}']//button[contains(@class,'xui-pickitem--body')]"
    )

    logger.info(f"Selecting accounting method: '{label}'")
    browser.click_element(more_button_locator, timeout=timeout)
    logger.info("Opened 'More' options menu")

    browser.click_element(method_locator, timeout=timeout)
    logger.info(f"Selected '{label}' accounting method")


def update_and_export_report(browser, request: GeneralLedgerDetailRequest) -> None:
    """
    Apply report settings, export to Excel, and save via the Save As dialog.

    Clicks 'Update' to apply the configured parameters, triggers Excel export,
    then hands the Chrome save dialog to ``handle_chrome_save_as_dialog`` to
    write the file to the request's destination path. The Update/Export/Excel
    buttons use EXPORT_TIMEOUT (Xero builds the file server-side).

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (GeneralLedgerDetailRequest): Supplies window title and dest path.

    Returns:
        None
    """
    logger.info("Starting report update and Excel export process...")

    update_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Update']"
    )
    export_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Export']"
    )
    excel_locator = (
        "xpath://button[@type='button']//span[normalize-space(text())='Excel']"
    )

    # Click 'Update' to apply all configured report parameters
    logger.info("Clicking 'Update' button to apply report configuration...")
    browser.click_element(update_locator, timeout=EXPORT_TIMEOUT)
    logger.info("'Update' button clicked. Report is refreshing with new parameters...")

    # Click 'Export' to open the file format selection menu
    logger.info("Clicking 'Export' button to open export format menu...")
    browser.click_element(export_locator, timeout=EXPORT_TIMEOUT)
    logger.info("Export format menu opened successfully")

    # Select 'Excel' to trigger the file download and open the Save As dialog
    logger.info("Selecting 'Excel' format to initiate file download...")
    browser.click_element(excel_locator, timeout=EXPORT_TIMEOUT)
    logger.info(
        "Excel export triggered. Waiting for Windows Save As dialog to appear..."
    )

    # Handle the Chrome save dialog and save to the requested path
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")
