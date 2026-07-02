"""
Module for downloading Aged Payables Summary reports from Xero Blue.

The Summary sibling of Aged Payables Detail: an "as at" report that ages
payables by Due Date or Invoice Date, optionally adds the Outstanding GST
column, and (unlike the Detail) can configure the Ageing Periods modal
("N periods of M {kind}"). It uses the shared modern report toolbar.

Configures and downloads one report: enters the end date, selects the ageing
method, optionally sets the ageing periods, optionally adds the GST column,
exports (Excel or PDF), and verifies the saved file.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(shared SH_ + AGED_ sections); shared behaviour lives in common.py.

ERROR HANDLING: like leave balances (and unlike the eight reports still pending
the sweep), this module raises the library's TYPED exceptions from
``iaa_rpa_utils.exceptions`` for its own checks:
  - DataValidationError - a request input failed validation
  - DataExtractionError - the client has no payables data
  - DownloadError       - the export file did not land on disk
The ageing-method / ageing-kind dropdowns are driven by common.select_listbox_option,
which raises RuntimeError if a (valid) option is absent on the page - kept
identical to the other aged reports, per design.

Period:
    An "as at" report - only an end date. `end_date` is the primary input
    (``datetime.date``); when omitted it is derived from `financial_year`
    (30 Jun of the FY), so `financial_year` is required only as a fallback.

Ageing method:
    `aging_by` selects how invoices are aged: "Due Date" or "Invoice Date".

Ageing periods (optional):
    `ageing_period` is a string like "4 periods of 1 Month". When omitted, the
    Ageing Periods modal is left untouched (Xero's default). A non-empty but
    unparseable value is rejected at construction (DataValidationError).

How to call:
    from datetime import date
    from download_aged_payables_summary import (
        AgedPayablesSummaryRequest, download_aged_payables_summary_report,
    )

    request = AgedPayablesSummaryRequest(
        financial_year=2024,
        aging_by="Due Date",
        download_directory=r"C:\\Reports",
        report_file_name="aged_payables_summary_2024",
        # end_date=date(2024, 5, 15),   # optional; omit to use 30 Jun {FY}
        # ageing_period="4 periods of 1 Month",
        # add_gst_column=True,
        # export_format="excel",        # "excel" (default, .xlsx) or "pdf"
    )
    download_aged_payables_summary_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. No payables data
    raises ``DataExtractionError``; a file that fails to save raises
    ``DownloadError``; invalid inputs raise ``DataValidationError``.
"""

from __future__ import annotations

import os
import re
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
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "AgedPayablesSummaryRequest",
    "download_aged_payables_summary_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Ageing method -> the short option key used in the aged-report locator template.
AgingMethod = Literal["Due Date", "Invoice Date"]
_AGING_OPTION_KEYS: dict[str, str] = {
    "Due Date": "due",
    "Invoice Date": "invoice",
}

# Export formats: format name -> (shared format-menu option id, saved extension).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}

# "N periods of M {kind}", e.g. "4 periods of 1 Month".
_AGEING_PERIOD_RE = re.compile(r"^\s*(\d+)\s+periods?\s+of\s+(\d+)\s+(\w+)\s*$", re.IGNORECASE)


def _parse_ageing_period(text: str | None) -> tuple[str, str, str] | None:
    """Parse "N periods of M {kind}" into (count, size, kind). Returns None for a
    falsy value (meaning 'leave the modal at its default'). Raises ValueError for
    a non-empty but unparseable value so the caller can reject it."""
    if not text:
        return None
    match = _AGEING_PERIOD_RE.match(text)
    if not match:
        raise DataValidationError(
            f"ageing_period must look like 'N periods of M <kind>' (e.g. '4 periods of 1 Month'), got {text!r}"
        )
    count, size, kind = match.group(1), match.group(2), match.group(3).capitalize()
    return count, size, kind


@dataclass(frozen=True, kw_only=True)
class AgedPayablesSummaryRequest:
    """Everything needed to download one Aged Payables Summary report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        aging_by:           "Due Date" or "Invoice Date".
        end_date:           Report "as at" date (``datetime.date``); falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when end_date is omitted.
        ageing_period:      Optional "N periods of M {kind}"; omit to leave default.
        add_gst_column:     When True, add the Outstanding GST column. Default False.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.

    Raises (on construction):
        DataValidationError: if any input fails validation.
    """

    download_directory: str
    report_file_name: str
    aging_by: AgingMethod
    end_date: date | None = None
    financial_year: int | None = None
    ageing_period: str | None = None
    add_gst_column: bool = False
    export_format: ExportFormat = "excel"
    window_title: str = "Aged Payables Summary"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.download_directory, str) or not self.download_directory.strip():
            raise DataValidationError("download_directory is required and must be a non-empty string")
        if not isinstance(self.report_file_name, str) or not self.report_file_name.strip():
            raise DataValidationError("report_file_name is required and must be a non-empty string")

        if self.aging_by not in get_args(AgingMethod):
            raise DataValidationError(f"aging_by must be one of {get_args(AgingMethod)}, got {self.aging_by!r}")

        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        if not isinstance(self.add_gst_column, bool):
            raise DataValidationError(f"add_gst_column must be a bool, got {type(self.add_gst_column).__name__}")

        if self.end_date is not None and not isinstance(self.end_date, date):
            raise DataValidationError(f"end_date must be a datetime.date, got {type(self.end_date).__name__}")

        if self.end_date is None and self.financial_year is None:
            raise DataValidationError("financial_year is required when end_date is omitted")

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

        # Validate ageing_period up front: a non-empty, unparseable value is a
        # bad input, caught before the browser opens.
        if self.ageing_period is not None:
            try:
                _parse_ageing_period(self.ageing_period)
            except ValueError as e:
                raise DataValidationError(str(e)) from e

        if self.capture_screenshots and not (self.screenshot_path or "").strip():
            raise DataValidationError(
                "screenshot_path is required when capture_screenshots is True"
            )

    @property
    def resolved_end_date(self) -> str:
        if self.end_date is not None:
            return common.format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def aging_option_locator(self) -> str:
        return config.AGED_AGEING_OPTION_TPL.format(opt=_AGING_OPTION_KEYS[self.aging_by])

    @property
    def parsed_ageing_period(self) -> tuple[str, str, str] | None:
        """(count, size, kind) or None when no ageing period was requested."""
        return _parse_ageing_period(self.ageing_period)

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
        rows = {
            "End Date": self.resolved_end_date if self.end_date else f"{self.resolved_end_date} (default)",
            "Financial Year": self.financial_year if self.financial_year is not None else "(from end date)",
            "Aging By": self.aging_by,
            "Ageing Period": self.ageing_period if self.ageing_period else "(default)",
            "Add GST Column": self.add_gst_column,
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


def download_aged_payables_summary_report(browser, request: AgedPayablesSummaryRequest) -> None:
    """
    Download an Aged Payables Summary report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the report end date
        STEP 2 - select the ageing method
        STEP 3 - configure the ageing periods (only if requested)
        STEP 4 - add the Outstanding GST column (only if requested)
        STEP 5 - update, confirm data, export, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it.
        DataExtractionError if the client has no payables data; DownloadError
        if the file fails to save.
    """
    with ProcessLogger("Xero Blue Download Aged Payables Summary Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report end date...")
        configure_report_date(browser, request)
        logger.info("STEP 1 COMPLETED: end date entered")

        logger.info("STEP 2: Selecting ageing method...")
        select_ageing_by(browser, request)
        logger.info("STEP 2 COMPLETED: ageing method selected")

        logger.info("STEP 3: Configuring ageing periods...")
        set_ageing_period(browser, request)
        logger.info("STEP 3 COMPLETED: ageing periods handled")

        logger.info("STEP 4: Adding GST column (if requested)...")
        add_gst_column_to_report(browser, request)
        logger.info("STEP 4 COMPLETED: GST column handled")

        logger.info("STEP 5: Updating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 5 COMPLETED: report exported and file saved")


def configure_report_date(browser, request: AgedPayablesSummaryRequest) -> None:
    """Enter the report end date into the (pre-filled) end-date field."""
    end_date = request.resolved_end_date
    logger.info(f"Entering report end date: {end_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, end_date)
    logger.info(f"End date entered successfully: {end_date}")


def select_ageing_by(browser, request: AgedPayablesSummaryRequest) -> None:
    """Open the Ageing By dropdown and select the requested method (same flow as
    the detail report: raises via common.select_listbox_option if absent)."""
    logger.info(f"Selecting ageing method: '{request.aging_by}'")
    common.select_listbox_option(
        browser,
        config.AGED_AGEING_BY_BUTTON,
        request.aging_option_locator,
        description=f"Ageing By '{request.aging_by}'",
    )
    logger.info(f"Ageing method selected: '{request.aging_by}'")


def set_ageing_period(browser, request: AgedPayablesSummaryRequest) -> None:
    """Open the Ageing Periods modal and apply 'N periods of M {kind}'. Leaves the
    modal untouched when no ageing period was requested."""
    parsed = request.parsed_ageing_period
    if parsed is None:
        logger.info("No ageing period requested - leaving modal at its default")
        return

    count, size, kind = parsed
    logger.info(f"Setting ageing periods: {count} periods of {size} {kind}")
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    browser.click_element(config.AGED_AGEING_PERIODS_TRIGGER, timeout=timeout)
    common.clear_and_type(browser, config.AGED_AGEING_PERIODS_COUNT_INPUT, count)
    common.clear_and_type(browser, config.AGED_AGEING_PERIODS_FREQ_INPUT, size)

    # Kind is a dropdown; select it the same way as any listbox (raises if absent).
    common.select_listbox_option(
        browser,
        config.AGED_AGEING_PERIODS_KIND_BUTTON,
        config.AGED_AGEING_PERIODS_KIND_OPTION_TPL.format(kind=kind),
        description=f"Ageing period kind '{kind}'",
    )

    browser.click_element(config.AGED_AGEING_PERIODS_APPLY_BUTTON, timeout=timeout)
    logger.info(f"Ageing periods applied: {count} periods of {size} {kind}")


def add_gst_column_to_report(browser, request: AgedPayablesSummaryRequest) -> None:
    """Add the Outstanding GST column via the Columns menu. Leaves the columns
    untouched when add_gst_column is False (identical to the detail report)."""
    if not request.add_gst_column:
        logger.info("add_gst_column is False - leaving columns unchanged")
        return
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    logger.info("Adding Outstanding GST column...")
    browser.click_element(config.SH_COLUMNS_BUTTON, timeout=timeout)
    common.ensure_pickitem_selected(browser, config.AGED_GST_COLUMN_ID, timeout)
    browser.click_element(config.SH_COLUMNS_BUTTON, timeout=timeout)   # close the menu
    logger.info("Outstanding GST column added")


def update_and_export_report(browser, request: AgedPayablesSummaryRequest) -> None:
    """Update the report, confirm data exists, export to the chosen format, and
    verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "aged_payables_summary", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # The Export button only renders when the report has data.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no payables data for this client")
        raise DataExtractionError("No Aged Payables Summary data available for this client.")
    logger.info("'Export' button present - data confirmed")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "aged_payables_summary", "after_update",
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
