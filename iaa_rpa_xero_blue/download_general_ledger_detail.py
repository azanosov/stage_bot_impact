"""
Module for downloading General Ledger Detail reports from Xero Blue.

Configures and downloads a General Ledger Detail report: enters the From/To
period dates, selects the accounting basis (Cash or Accrual), generates and
exports the report (Excel or PDF), and confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour lives in common.py. This module composes those - it touches
only shared controls, so it has no report-specific locators of its own.

Inputs are modelled as a dataclass:
    GeneralLedgerDetailRequest - everything one download needs. The live
                                 browser/engine is passed separately.

Period:
    A date-range report (From + To). `start_date`/`end_date` are the primary
    inputs (``datetime.date``); when either is omitted they are derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY), so
    `financial_year` is required only as a fallback.

Accounting basis:
    `accounting_method` selects Cash or Accrual via the More options menu. It is
    always set (forced). Defaults to "Cash".

How to call:
    from datetime import date
    from download_general_ledger_detail import (
        GeneralLedgerDetailRequest, download_general_ledger_detail_report,
    )

    request = GeneralLedgerDetailRequest(
        download_directory=r"C:\\Reports",
        report_file_name="general_ledger_2024",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        # accounting_method="Cash",  # "Cash" (default) or "Accrual"
        # financial_year=2024,       # used to derive dates if either is omitted
        # export_format="excel",     # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="General Ledger Detail",
    )
    download_general_ledger_detail_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. No report data, or a
    file that fails to save, raises ``RuntimeError``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "GeneralLedgerDetailRequest",
    "download_general_ledger_detail_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Accounting basis: request value -> visible label (logging) and shared option id.
AccountingMethod = Literal["Accrual", "Cash"]
_ACCOUNTING_OPTION_IDS: dict[str, str] = {
    "Accrual": config.SH_BASIS_ACCRUAL_ID,
    "Cash": config.SH_BASIS_CASH_ID,
}

# Export formats: format name -> (shared format-menu option id, saved extension).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}


@dataclass(frozen=True, kw_only=True)
class GeneralLedgerDetailRequest:
    """Everything needed to download one General Ledger Detail report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
        accounting_method:  "Cash" (default) or "Accrual". Always set.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    accounting_method: AccountingMethod = "Cash"
    export_format: ExportFormat = "excel"
    window_title: str = "General Ledger Detail"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")

        if self.accounting_method not in get_args(AccountingMethod):
            raise DataValidationError(
                f"accounting_method must be one of {get_args(AccountingMethod)}, "
                f"got {self.accounting_method!r}"
            )
        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        common.validate_optional_date(self.start_date, "start_date")
        common.validate_optional_date(self.end_date, "end_date")
        if (self.start_date is None or self.end_date is None) and self.financial_year is None:
            raise DataValidationError("financial_year is required when start_date or end_date is omitted")
        if self.financial_year is not None:
            common.validate_financial_year(self.financial_year)
        common.validate_date_order(self.start_date, self.end_date)

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
    def basis_option_id(self) -> str:
        return _ACCOUNTING_OPTION_IDS[self.accounting_method]

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
            "Accounting Method": self.accounting_method,
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


def download_general_ledger_detail_report(browser, request: GeneralLedgerDetailRequest) -> None:
    """
    Download a General Ledger Detail report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the From/To period dates
        STEP 2 - select the accounting basis (Cash / Accrual)
        STEP 3 - update, export, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. No data,
        or a file that fails to save, raises ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download General Ledger Detail Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report period dates...")
        enter_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: from and to dates entered")

        logger.info("STEP 2: Selecting accounting basis...")
        configure_accounting_basis(browser, request)
        logger.info("STEP 2 COMPLETED: accounting basis selected")

        logger.info("STEP 3: Generating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


def enter_report_dates(browser, request: GeneralLedgerDetailRequest) -> None:
    """Enter the From (start) and To (end) period dates."""
    logger.info("Entering report period dates...")
    common.clear_and_type(browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date)
    logger.info(f"Entered From date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered To date: {request.resolved_end_date}")


def configure_accounting_basis(browser, request: GeneralLedgerDetailRequest) -> None:
    """Force the requested accounting basis via the More menu."""
    logger.info(f"Selecting accounting basis: '{request.accounting_method}'")
    common.select_accounting_basis_via_more(browser, request.basis_option_id)
    logger.info(f"Accounting basis '{request.accounting_method}' selected")


def update_and_export_report(browser, request: GeneralLedgerDetailRequest) -> None:
    """Update the report, confirm it has data, export to the chosen format, and
    verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "general_ledger_detail", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # NOTE (consistency addition): the original GL module had no no-data guard.
    # Added here to match the other reports - the Export button only renders once
    # the report has data, so its absence means "no data". 
    # Remove if GL is found to behave differently.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no General Ledger data available for this client")
        raise DataExtractionError("No General Ledger Detail data available for this client.")
    logger.info("'Export' button present - report contains data")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "general_ledger_detail", "after_update",
        enabled=request.capture_screenshots,
    )

    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)

    time.sleep(3)   # brief settle so the save dialog has rendered

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)
    logger.info(f"File successfully saved: '{dest_path}'")
