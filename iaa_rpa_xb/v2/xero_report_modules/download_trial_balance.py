"""
Module for downloading Trial Balance reports from Xero Blue.

This module handles the complete workflow for configuring and downloading a
Trial Balance report from Xero Blue: selecting the accounting basis (Cash or
Accrual), entering the report end date, optionally adding the Outstanding GST
column, generating the report (with an audit screenshot), and exporting it to
Excel via the Windows Save As dialog.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API. No direct
driver access is needed, and the module depends only on iaa_rpa_utils.

Inputs are modelled as a dataclass:
    TrialBalanceRequest - everything one download needs (period + method + GST +
                          file/output config). The live browser/engine is passed
                          separately to the download function.

Structure:
    The orchestrator (download_trial_balance_report) owns the order of operations
    and calls each step in sequence. The step helpers each do one thing and
    return - they do NOT call one another.

Period:
    The Trial Balance is an "as at" report - only an end date. `end_date` is the
    primary input (``datetime.date``); when omitted it is derived from
    `financial_year` (30 Jun of the FY), so `financial_year` is required only as
    a fallback.

Accounting basis:
    `accounting_method` selects Cash or Accrual via the More options menu.
    Defaults to "cash" (the report's long-standing behaviour).

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits. Overridable per run via
        TrialBalanceRequest.element_timeout.
    EXPORT_TIMEOUT          - the Update/Export/Excel buttons, which can be slow
        because Xero builds the file server-side. Intentionally longer.

How to call:
    from datetime import date
    from download_trial_balance import (
        TrialBalanceRequest,
        download_trial_balance_report,
    )

    request = TrialBalanceRequest(
        end_date=date(2024, 6, 30),
        download_directory=r"C:\\Reports",
        report_file_name="trial_balance_2024",
        # accounting_method="cash",   # "cash" (default) or "accrual"
        # add_gst_column=True,        # default False
        # financial_year=2024,        # used to derive end_date if omitted
        # export_format="excel",      # only "excel" supported (saved .xlsx)
        # window_title="Trial Balance",
        # element_timeout=5,
    )
    download_trial_balance_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED, so the caller can
    detect failure. A client with no report data raises a clear RuntimeError.
"""

from __future__ import annotations

import os
import time
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
    "TrialBalanceRequest",
    "download_trial_balance_report",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5  # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10  # seconds; Update/Export/Excel - Xero builds the file server-side
_MIN_FINANCIAL_YEAR = 2000  # earliest financial year we accept

# Locale-independent month abbreviations, matching the labels Xero's date field
# expects (e.g. "30 Jun 2024"). Avoids strftime('%b') locale surprises.
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

# Stable picklist option IDs for the accounting basis. Scoping the click locator
# to these IDs is unambiguous and avoids the separate "Accounting basis" row that
# lives under the "Show" section of the same picklist.
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
    """Format a date the way Xero's date field expects, e.g. "30 Jun 2024"
    (no leading zero on the day; locale-independent month abbreviation)."""
    return f"{d.day} {_MONTH_ABBR[d.month - 1]} {d.year}"


@dataclass(frozen=True, kw_only=True)
class TrialBalanceRequest:
    """Everything needed to download one Trial Balance report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename. The extension may be included or
                            omitted - ``dest_path`` normalises it and forces the
                            extension that matches the chosen export format.
        end_date:           Report "as at" date (``datetime.date``). Primary
                            input; falls back to "30 Jun {financial_year}".
        financial_year:     FY end year as an int (e.g. 2024). Required only as a
                            fallback when end_date is omitted.
        accounting_method:  "cash" (default) or "accrual".
        add_gst_column:     Whether to add the 'Outstanding GST' column.
        export_format:      Export format. Only "excel" is supported for this
                            report (saved as .xlsx).
        window_title:       Title used to locate the Chrome Save As window.
        element_timeout:    Seconds to wait for general elements (default
                            DEFAULT_ELEMENT_TIMEOUT).
    """

    download_directory: str
    report_file_name: str
    end_date: date | None = None
    financial_year: int | None = None
    accounting_method: AccountingMethod = "cash"
    add_gst_column: bool = False
    export_format: ExportFormat = "excel"
    window_title: str = "Trial Balance"
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

        # Provided end_date must be a real date object (datetime is a date
        # subclass, so it is accepted too - only the calendar part is used).
        if self.end_date is not None and not isinstance(self.end_date, date):
            raise TypeError(
                f"end_date must be a datetime.date, got {type(self.end_date).__name__}"
            )

        # financial_year is the fallback source; required only when end_date is missing.
        if self.end_date is None and self.financial_year is None:
            raise ValueError("financial_year is required when end_date is omitted")

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
        end_date_display = (
            self.resolved_end_date
            if self.end_date
            else f"{self.resolved_end_date} (default)"
        )
        rows = {
            "End Date": end_date_display,
            "Financial Year": (
                self.financial_year
                if self.financial_year is not None
                else "(from end date)"
            ),
            "Accounting Method": self.accounting_label,
            "Add GST Column": self.add_gst_column,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_trial_balance_report(browser, request: TrialBalanceRequest) -> None:
    """
    Download a Trial Balance report from Xero Blue.

    Owns the order of operations and calls each step in sequence:
        STEP 1 - select the accounting basis (Cash / Accrual)
        STEP 2 - enter the report end date
        STEP 3 - configure the Outstanding GST column (optional)
        STEP 4 - generate the report and export it to Excel

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (TrialBalanceRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it (with timing).
        A client with no report data raises ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download Trial Balance Report", logger):
        # Echo the request so the log is self-describing
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Selecting accounting basis...")
        configure_accounting_basis(browser, request)
        logger.info("STEP 1 COMPLETED: accounting basis selected")

        logger.info("STEP 2: Entering report end date...")
        configure_report_date(browser, request)
        logger.info("STEP 2 COMPLETED: end date entered")

        logger.info("STEP 3: Configuring Outstanding GST column...")
        configure_gst_column(browser, request)
        logger.info("STEP 3 COMPLETED: GST column configuration applied")

        logger.info("STEP 4: Generating report and exporting to Excel...")
        generate_and_export_report(browser, request)
        logger.info("STEP 4 COMPLETED: report exported and file saved")


def configure_accounting_basis(browser, request: TrialBalanceRequest) -> None:
    """
    Select the accounting basis (Cash / Accrual) via the More options menu.

    Opens the More menu, then clicks the radio whose visible label matches the
    requested method. Clicking the already-selected method is harmless.

    NOTE: The basis control is a xui-picklist whose clickable target is the
    'xui-pickitem--body' button (the radio inside it is decorative). The click
    locator is scoped to each option's stable id (report-settings-accrualbasis-
    cash / -accrual), which avoids the separate "Accounting basis" row under the
    picklist's "Show" section.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (TrialBalanceRequest): Supplies the accounting method and
            element_timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    label = request.accounting_label

    option_id = _ACCOUNTING_OPTION_IDS[request.accounting_method]
    more_button_locator = "xpath://button[normalize-space()='More']"
    # Click the pickitem button for the chosen option, scoped to its stable id.
    # (Original label-based form:
    #  //button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='Cash']])
    method_locator = (
        f"xpath://li[@id='{option_id}']//button[contains(@class,'xui-pickitem--body')]"
    )

    logger.info(f"Selecting accounting basis: '{label}'")
    browser.click_element(more_button_locator, timeout=timeout)
    logger.info("Opened 'More' options menu")

    browser.click_element(method_locator, timeout=timeout)
    logger.info(f"Selected '{label}' accounting basis")


def configure_report_date(browser, request: TrialBalanceRequest) -> None:
    """
    Enter the report end date into the report settings.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (TrialBalanceRequest): Supplies the resolved end date and
            element_timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    end_date = request.resolved_end_date
    to_date_locator = "id:report-settings-custom-date-input-to"

    logger.info(f"Entering report end date: {end_date}")
    browser.click_element(to_date_locator, timeout=timeout)
    browser.send_keys_to_active_element("\ue009" + "a")  # CTRL + A to select all
    browser.send_keys_to_active_element("\ue003")  # DELETE to clear existing value
    browser.send_keys_to_active_element(end_date)  # Type the resolved end date
    browser.send_keys_to_active_element("\ue004")  # TAB to confirm and move on
    logger.info(f"End date entered successfully: {end_date}")


def configure_gst_column(browser, request: TrialBalanceRequest) -> None:
    """
    Optionally add the 'Outstanding GST' column to the report.

    When ``request.add_gst_column`` is True, opens the columns menu, selects
    'Outstanding GST', and closes the menu to apply. When False, does nothing.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (TrialBalanceRequest): Supplies the GST flag and element_timeout.

    Returns:
        None
    """
    if not request.add_gst_column:
        logger.info(
            "GST column not requested (add_gst_column=False). Skipping GST configuration.",
        )
        return

    timeout = request.element_timeout
    gst_button_locator = "xpath://*[@id='report-settings-columns-button']"
    outstanding_gst_locator = (
        "xpath://span[contains(@class,'xui-pickitem-multiselect--label')]"
        "[.//span[normalize-space()='Outstanding GST']]"
    )

    logger.info("GST column addition requested. Opening columns settings menu...")

    # Open the columns dropdown to access column visibility options
    browser.click_element(gst_button_locator, timeout=timeout)
    logger.info("Columns settings menu opened")

    # Select the 'Outstanding GST' checkbox to add the GST column
    browser.click_element(outstanding_gst_locator, timeout=timeout)
    logger.info("'Outstanding GST' option selected")

    # Close the columns menu to confirm and apply the selection
    browser.click_element(gst_button_locator, timeout=timeout)
    logger.info("Columns settings menu closed. GST column added successfully.")


def generate_and_export_report(browser, request: TrialBalanceRequest) -> None:
    """
    Generate the report, capture an audit screenshot, export to Excel, and save.

    Clicks 'Update' to generate the report, waits for it to render, captures an
    audit screenshot, then verifies the Export button is present - its absence
    means the client has no report data, which raises ``RuntimeError``. Finally
    opens Export, selects Excel, and hands the Chrome save dialog to
    ``handle_chrome_save_as_dialog``.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (TrialBalanceRequest): Supplies window title, dest path and
            element_timeout.

    Returns:
        None

    Raises:
        RuntimeError: If no Export button is present (no report data for client).
    """
    timeout = request.element_timeout
    logger.info("Starting report generation and Excel export process...")

    update_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Update']"
    )
    export_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Export']"
    )
    excel_locator = (
        "xpath://button[@type='button']//span[normalize-space(text())='Excel']"
    )
    report_title_locator = "xpath://input[@placeholder='Report title']"

    # Click 'Update' to generate the report with the configured settings
    logger.info("Clicking 'Update' button to generate the Trial Balance report...")
    browser.click_element(update_locator, timeout=EXPORT_TIMEOUT)
    logger.info("'Update' button clicked. Waiting for report to render...")

    # Wait for the report title input to confirm the report has rendered
    if browser.does_page_contain_element(report_title_locator, timeout=EXPORT_TIMEOUT):
        logger.info("Report rendered successfully - report title is visible")
    else:
        logger.warning(
            "Report title not visible within timeout - proceeding to data check"
        )

    # Capture an audit screenshot into the browser's configured directory.
    _capture_audit_screenshot(browser)

    # Verify the Export button is present; its absence means the client has no data.
    if not browser.does_page_contain_element(export_locator, timeout=timeout):
        logger.warning(
            "Export button not found - no Trial Balance data available for this client"
        )
        raise RuntimeError("No Trial Balance data available for this client.")
    logger.info("'Export' button located - report contains data")

    # Open the Export menu
    logger.info("Clicking 'Export' button to open export format menu...")
    browser.click_element(export_locator, timeout=EXPORT_TIMEOUT)
    logger.info("Export format menu opened successfully")

    # Select 'Excel' to trigger the file download and open the Save As dialog
    logger.info("Selecting 'Excel' format to initiate file download...")
    browser.click_element(excel_locator, timeout=EXPORT_TIMEOUT)
    logger.info(
        "Excel export triggered. Waiting for Windows Save As dialog to appear..."
    )

    # Brief settle so the download/save dialog has rendered before we drive it.
    time.sleep(3)

    # Handle the Chrome save dialog and save to the requested path
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")


def _capture_audit_screenshot(browser) -> None:
    """Capture an audit screenshot of the rendered report.

    Mirrors where the (unsupported) take_screenshot helper saved it: the current
    working directory, named ExceptionScreenshot_<timestamp>.png with the same
    %y%m%d.%H%M%S format. Taken via the wrapper's screenshot() since the helper
    itself is unsupported. Best effort - a screenshot failure must not abort the
    export.
    """
    try:
        folder_path = os.getcwd()
        os.makedirs(folder_path, exist_ok=True)
        timestamp = datetime.now().strftime("%y%m%d.%H%M%S")
        screenshot_path = os.path.join(
            folder_path, f"ExceptionScreenshot_{timestamp}.png"
        )
        browser.screenshot(screenshot_path)
        logger.info(f"Screenshot saved at: {screenshot_path}")
    except Exception as e:
        logger.warning(f"Could not capture audit screenshot: {e}")
