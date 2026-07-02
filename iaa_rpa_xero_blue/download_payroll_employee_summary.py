"""
Module for downloading Payroll Employee Summary reports from Xero Blue.

A payroll date-range report on the shared modern report toolbar - the same shape
as Leave Balances, but with a start date as well as an end date. Every control
it touches is shared (the SH_ config section); it has no report-specific locators.

Configures and downloads one report: enters the date range, updates the report,
confirms payroll data exists, exports it (Excel or PDF), and verifies the saved
file.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour (date formatting, the input/pick-list primitives, save-path)
lives in common.py. This module composes those.

ERROR HANDLING: like leave balances and the other recently-added reports, this
module raises the library's TYPED exceptions from ``iaa_rpa_utils.exceptions``:
  - DataValidationError - a request input failed validation
  - DataExtractionError - the client has no payroll data
  - DownloadError       - the export file did not land on disk

Period:
    A date range. `start_date`/`end_date` are the primary inputs
    (``datetime.date``); when either is omitted it is derived independently from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY).

How to call:
    from datetime import date
    from download_payroll_employee_summary import (
        PayrollEmployeeSummaryRequest, download_payroll_employee_summary_report,
    )

    request = PayrollEmployeeSummaryRequest(
        download_directory=r"C:\\Reports",
        report_file_name="payroll_employee_summary_2024",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        # financial_year=2024,     # alternative to start/end; either can fall back to FY
        # export_format="excel",   # "excel" (default, .xlsx) or "pdf" (.pdf)
    )
    download_payroll_employee_summary_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. A client with no
    payroll data raises ``DataExtractionError``; a file that fails to save
    raises ``DownloadError``; invalid inputs raise ``DataValidationError``.
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
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "PayrollEmployeeSummaryRequest",
    "download_payroll_employee_summary_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Export formats: format name -> (shared format-menu option id, saved extension).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}


@dataclass(frozen=True, kw_only=True)
class PayrollEmployeeSummaryRequest:
    """Everything needed to download one Payroll Employee Summary report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
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
    export_format: ExportFormat = "excel"
    window_title: str = "Payroll Employee Summary"
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
        rows = {
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from dates)",
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


def download_payroll_employee_summary_report(browser, request: PayrollEmployeeSummaryRequest) -> None:
    """
    Download a Payroll Employee Summary report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the date range
        STEP 2 - update, confirm payroll data, export, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it.
        DataExtractionError if the client has no payroll data; DownloadError if
        the file fails to save.
    """
    with ProcessLogger("Xero Blue Download Payroll Employee Summary Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report date range...")
        configure_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: date range entered")

        logger.info("STEP 2: Updating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 2 COMPLETED: report exported and file saved")


def configure_report_dates(browser, request: PayrollEmployeeSummaryRequest) -> None:
    """Enter the From (start) and To (end) dates."""
    common.clear_and_type(browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date)
    logger.info(f"Entered start date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered end date: {request.resolved_end_date}")


def update_and_export_report(browser, request: PayrollEmployeeSummaryRequest) -> None:
    """Update the report, confirm payroll data exists, export to the chosen
    format, and verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "payroll_employee_summary", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # Payroll report: the Export button only renders when the client has payroll
    # data for the selected period. Its absence means there is nothing to export.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no payroll data for this client")
        raise DataExtractionError("No payroll data available for this client.")
    logger.info("'Export' button present - payroll data confirmed")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "payroll_employee_summary", "after_update",
        enabled=request.capture_screenshots,
    )

    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)

    time.sleep(2)   # brief settle so the save dialog has rendered

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
