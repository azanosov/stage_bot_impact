"""
Module for downloading Aged Payables Detail reports from Xero Blue.

This module handles the complete workflow for configuring and downloading an
Aged Payables Detail report from Xero Blue: resolving the report end date,
selecting the aging method, optionally adding the Outstanding GST column,
updating the report, and exporting it to Excel via the Windows Save As dialog.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API, e.g.
"xpath://input[...]" / "xpath://button[...]". No direct driver access is needed.

Inputs are modelled as a dataclass:
    AgedPayablesRequest - everything one download needs (report config +
                          file/output config). The live browser/engine is
                          passed separately to the download function.

Structure:
    The orchestrator (download_aged_payables_detail_report) owns the order of
    operations and calls each step in sequence. The step helpers each do one
    thing and return - they do NOT call one another. This keeps the workflow
    readable top-to-bottom and lets each step be run/tested in isolation.

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits. Overridable per run via
        AgedPayablesRequest.element_timeout.
    EXPORT_TIMEOUT          - the Update/Export/Excel buttons, which can be slow
        because Xero builds the file server-side. Intentionally longer.

How to call:
    from download_aged_payables_detail import (
        AgedPayablesRequest,
        download_aged_payables_detail_report,
    )

    request = AgedPayablesRequest(
        financial_year=2024,                   # FY end year (int)
        aging_by="Due date",                    # type-checked literal
        download_directory=r"C:\\Reports",
        report_file_name="ACME_Payables_2024",
        # end_date="31 Dec 2024",               # optional; defaults to 30 Jun {FY}
        # add_gst_column=True,                   # optional, default False
        # window_title="Aged Payables Detail",   # optional, has a default
        # export_format="excel",                 # only "excel" supported (saved .xlsx)
        # element_timeout=5,                     # optional, has a default
    )
    download_aged_payables_detail_report(browser, request)

Note on the financial year:
    `financial_year` follows the Australian convention: FY "2024" ends
    30 Jun 2024. When `end_date` is omitted, the report end date defaults to
    "30 Jun {financial_year}".

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and SWALLOWED - the function
    returns None rather than raising. To make failures propagate to the caller,
    remove the surrounding try/except (or change ``return`` to ``raise``).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog


# Set up logger
logger = setup_logger(__name__)


# Public API of this module. Step helpers are intentionally left out: they are
# usable/testable individually, but only these names are the supported surface.
__all__ = [
    "AgedPayablesRequest",
    "download_aged_payables_detail_report",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5   # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10           # seconds; Update/Export/Excel - Xero builds the file server-side
_MIN_FINANCIAL_YEAR = 2000    # earliest financial year we accept


# The aging methods Xero exposes for this report. Constrained so an invalid
# method is a type-check error at the call site, before anything runs.
AgingMethod = Literal["Due date", "Invoice date"]

# Supported export format(s). This report exports Excel only; the value exists so
# the interface matches the other report modules. _EXPORT_FORMATS maps the chosen
# format to the extension Xero actually saves - the source of truth for the
# filename, so the saved file can never disagree with its bytes.
ExportFormat = Literal["excel"]
_EXPORT_FORMATS: dict[str, str] = {
    "excel": ".xlsx",
}


@dataclass(frozen=True, kw_only=True)
class AgedPayablesRequest:
    """Everything needed to download one Aged Payables Detail report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.

    Attributes:
        financial_year:     FY end year as an int (e.g. 2024). Used to
                            derive the default end date when ``end_date`` is
                            omitted.
        aging_by:           Aging calculation method (type-checked literal).
        download_directory: Directory the Excel file is saved to.
        report_file_name:   Output filename. The extension may be included or
                            omitted - ``dest_path`` normalises it either way.
        window_title:       Title used to locate the Chrome Save As window.
        end_date:           Custom end date in 'DD MMM YYYY' format. Empty ->
                            defaults to "30 Jun {financial_year}".
        add_gst_column:     Whether to add the 'Outstanding GST' column.
        export_format:      Export format. Only "excel" is supported for this
                            report (saved as .xlsx).
        element_timeout:    Seconds to wait for general elements (default
                            DEFAULT_ELEMENT_TIMEOUT).
    """

    financial_year: int
    aging_by: AgingMethod
    download_directory: str
    report_file_name: str
    window_title: str = "Aged Payables Detail"
    end_date: str = ""
    add_gst_column: bool = False
    export_format: ExportFormat = "excel"
    element_timeout: int = DEFAULT_ELEMENT_TIMEOUT

    def __post_init__(self) -> None:
        # export_format must be one we have a saved extension for.
        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        # Validate the aging method at runtime - the Literal only constrains type
        # checkers, and a typo would otherwise surface as a Selenium timeout.
        if self.aging_by not in get_args(AgingMethod):
            raise ValueError(
                f"aging_by must be one of {get_args(AgingMethod)}, got {self.aging_by!r}"
            )

        # financial_year is typed int but that is not enforced at runtime; guard
        # it so a stringified year gives a clear error. bool is an int subclass,
        # so exclude it.
        if not isinstance(self.financial_year, int) or isinstance(self.financial_year, bool):
            raise TypeError(
                f"financial_year must be an int, got {type(self.financial_year).__name__}"
            )

        # Reject implausible years. +2 mirrors the activity-statement bound.
        max_year = datetime.now().year + 2
        if not _MIN_FINANCIAL_YEAR <= self.financial_year <= max_year:
            raise ValueError(
                f"financial_year must be between {_MIN_FINANCIAL_YEAR} and {max_year}, "
                f"got {self.financial_year}"
            )

    @property
    def resolved_end_date(self) -> str:
        """End date to enter into the report: the custom value if given,
        otherwise the financial-year end "30 Jun {financial_year}"."""
        return self.end_date if self.end_date else f"30 Jun {self.financial_year}"

    @property
    def saved_extension(self) -> str:
        """The extension Xero actually produces for the chosen format (".xlsx")
        - the source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format]

    @property
    def dest_path(self) -> str:
        """Full save path, e.g. ".../ACME_Payables_2024.xlsx". Tolerates an
        extension passed with or without a leading dot, and avoids doubling the
        extension if ``report_file_name`` already carries it."""
        ext = self.saved_extension  # includes the leading dot, e.g. ".xlsx"
        name = self.report_file_name
        if name.lower().endswith(ext.lower()):
            name = name[: -len(ext)]
        return os.path.join(self.download_directory, f"{name}{ext}")

    def summary_lines(self) -> list[str]:
        """Human-readable "label : value" rows describing this request, with
        the colons aligned. Used for the run's opening log block."""
        end_date_display = (
            self.resolved_end_date if self.end_date
            else f"{self.resolved_end_date} (default)"
        )
        rows = {
            "End Date": end_date_display,
            "Financial Year": self.financial_year,
            "Add GST Column": self.add_gst_column,
            "Aging By": self.aging_by,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Window Title": self.window_title,
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_aged_payables_detail_report(
    browser, request: AgedPayablesRequest
) -> None:
    """
    Download an Aged Payables Detail report from Xero Blue.

    Owns the order of operations and calls each step in sequence:
        STEP 1 - configure the report end date and aging method
        STEP 2 - configure the Outstanding GST column (optional)
        STEP 3 - update the report and export it to Excel

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (AgedPayablesRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Nothing. Any error during the download is logged (by ``ProcessLogger``)
        and swallowed here, so the function returns None. Remove the try/except
        to propagate instead.
    """
    try:
        with ProcessLogger("Xero Blue Download Aged Payables Detail Report", logger):
            # Echo the request so the log is self-describing
            for line in request.summary_lines():
                logger.info(line)
            _log_resolved_end_date(request)

            logger.info("STEP 1: Configuring report end date and aging method...")
            configure_report_dates_and_aging(browser, request)
            logger.info("STEP 1 COMPLETED: end date entered and aging method selected")

            logger.info("STEP 2: Configuring Outstanding GST column...")
            configure_gst_column(browser, request)
            logger.info("STEP 2 COMPLETED: GST column configuration applied")

            logger.info("STEP 3: Updating report and exporting to Excel...")
            update_and_export_report(browser, request)
            logger.info("STEP 3 COMPLETED: report exported and file saved")

    except Exception:
        # The failure was already logged by ProcessLogger. Swallow it here so
        # the caller receives None. Remove this try/except to propagate instead.
        return


def _log_resolved_end_date(request: AgedPayablesRequest) -> None:
    """Log how the report end date was resolved (custom vs FY default)."""
    if request.end_date:
        logger.info(f"Using provided End Date: {request.resolved_end_date}")
    else:
        logger.info(f"Using default End Date: {request.resolved_end_date}")


def configure_report_dates_and_aging(browser, request: AgedPayablesRequest) -> None:
    """
    Configure the report end date and aging method in the Xero Blue UI.

    Populates the custom end-date field (clear via CTRL+A / DELETE, type the
    resolved end date, confirm with TAB), opens the aging-method dropdown, and
    selects the requested method if present. Returns when done.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (AgedPayablesRequest): Supplies the resolved end date,
            aging method and element_timeout.

    Returns:
        None
    """
    end_date = request.resolved_end_date
    timeout = request.element_timeout
    logger.info("Configuring report date and aging method parameters in Xero UI...")

    # Allow the report settings panel to settle before interacting.
    time.sleep(2)

    custom_date_locator = "xpath://*[@id='report-settings-custom-date-input-to']"

    # Focus the end-date field, then send the key sequence to the active element.
    logger.info(f"Entering report end date: {end_date}")
    browser.click_element(custom_date_locator, timeout=timeout)
    browser.send_keys_to_active_element("\ue009" + "a")  # CTRL + A to select all
    browser.send_keys_to_active_element("\ue003")        # DELETE to clear existing value
    browser.send_keys_to_active_element(end_date)        # Type the resolved end date
    browser.send_keys_to_active_element("\ue004")        # TAB to confirm and move on
    logger.info(f"End date entered successfully: {end_date}")

    # Open the aging method dropdown to reveal available options
    logger.info(f"Opening aging method dropdown to select: '{request.aging_by}'")
    ageing_button_locator = (
        "xpath://button[contains(@class,'xui-select--button')]"
        "[.//span[contains(@class,'xui-select--content-truncated')]]"
    )
    browser.click_element(ageing_button_locator, timeout=timeout)
    logger.info("Aging method dropdown opened")

    ageing_option_locator = (
        f"xpath://button[contains(@class,'xui-pickitem--body') "
        f"and .//span[normalize-space()='{request.aging_by}']]"
    )

    # Confirm the requested aging method is available before clicking it.
    if aging_option_available(browser, ageing_option_locator, request.aging_by, timeout):
        browser.click_element(ageing_option_locator, timeout=timeout)
        logger.info(f"Aging method selected successfully: '{request.aging_by}'")
    else:
        logger.warning(
            f"Aging method '{request.aging_by}' not found in dropdown. "
            f"Proceeding with current default selection.",
        )


def aging_option_available(
    browser, ageing_option_locator: str, aging_by: str, timeout: int
) -> bool:
    """
    Check whether the specified aging method option is present in the dropdown.

    Uses the wrapper's ``does_page_contain_element`` (DOM presence) so the
    caller can decide whether to click the option or fall back to the default.
    Never raises - returns False on absence or timeout.

    Args:
        browser: SeleniumBrowser wrapper instance.
        ageing_option_locator (str): Wrapper locator for the aging option button.
        aging_by (str): Human-readable label, for log messages only.
        timeout (int): Seconds to wait for the option.

    Returns:
        bool: True if the option is found within the timeout, else False.
    """
    present = browser.does_page_contain_element(ageing_option_locator, timeout=timeout)
    if present:
        logger.info(f"Aging option '{aging_by}' found in dropdown")
    else:
        logger.warning(f"Aging option '{aging_by}' not found in dropdown within timeout")
    return present


def configure_gst_column(browser, request: AgedPayablesRequest) -> None:
    """
    Optionally add the 'Outstanding GST' column to the report.

    When ``request.add_gst_column`` is True, opens the columns menu, selects
    'Outstanding GST', and closes the menu to apply. When False, does nothing.
    Returns when done.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (AgedPayablesRequest): Supplies the GST flag and element_timeout.

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


def update_and_export_report(browser, request: AgedPayablesRequest) -> None:
    """
    Apply report settings, export to Excel, and save via the Save As dialog.

    Clicks 'Update' to apply the configured parameters, triggers Excel export,
    then hands the Chrome save dialog to ``handle_chrome_save_as_dialog`` to
    write the file to the request's destination path. The Update/Export/Excel
    buttons use EXPORT_TIMEOUT (Xero builds the file server-side).

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (AgedPayablesRequest): Supplies window title and dest path.

    Returns:
        None
    """
    logger.info("Starting report update and Excel export process...")

    update_locator = "xpath://button[@type='button' and normalize-space(text())='Update']"
    export_locator = "xpath://button[@type='button' and normalize-space(text())='Export']"
    excel_locator = "xpath://button[@type='button']//span[normalize-space(text())='Excel']"

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
    logger.info("Excel export triggered. Waiting for Windows Save As dialog to appear...")

    # Allow the download/save dialog to render before handing it off.
    time.sleep(2)

    # Handle the Chrome save dialog and save to the requested path
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")
