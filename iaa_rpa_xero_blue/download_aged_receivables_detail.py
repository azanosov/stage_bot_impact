"""
Module for downloading Aged Receivables Detail reports from Xero Blue.

Configures and downloads an Aged Receivables Detail report: enters the report end
date, selects the ageing method, optionally adds the Outstanding GST column,
generates and exports the report (Excel), and confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour lives in common.py. This module composes those.

Inputs are modelled as a dataclass:
    AgedReceivablesRequest - everything one download needs. The live browser/engine
                          is passed separately.

Period:
    An "as at" report - only an end date. `end_date` is the primary input
    (``datetime.date``); when omitted it is derived from `financial_year`
    (30 Jun of the FY), so `financial_year` is required only as a fallback.

Ageing method:
    `aging_by` selects how invoices are aged: "Due Date" or "Invoice Date".

How to call:
    from datetime import date
    from download_aged_payables_detail import (
        AgedReceivablesRequest, download_aged_receivables_detail_report,
    )

    request = AgedReceivablesRequest(
        download_directory=r"C:\\Reports",
        report_file_name="aged_receivables_2024",
        aging_by="Due Date",
        end_date=date(2024, 6, 30),
        # financial_year=2024,    # used to derive end_date if omitted
        # add_gst_column=True,    # default False
        # export_format="excel",  # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="Aged Receivables Detail",
    )
    download_aged_receivables_detail_report(browser, request)

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
    "AgedReceivablesRequest",
    "download_aged_receivables_detail_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Ageing method: the request value maps to the dropdown option's short key.
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


@dataclass(frozen=True, kw_only=True)
class AgedReceivablesRequest:
    """Everything needed to download one Aged Receivables Detail report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        aging_by:           "Due Date" or "Invoice Date".
        end_date:           Report "as at" date (``datetime.date``); falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when end_date is omitted.
        add_gst_column:     When True, add the Outstanding GST column. Default False.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
    """

    download_directory: str
    report_file_name: str
    aging_by: AgingMethod
    end_date: date | None = None
    financial_year: int | None = None
    add_gst_column: bool = False
    export_format: ExportFormat = "excel"
    window_title: str = "Aged Receivables Detail"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")

        if self.aging_by not in get_args(AgingMethod):
            raise DataValidationError(f"aging_by must be one of {get_args(AgingMethod)}, got {self.aging_by!r}")
        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )
        if not isinstance(self.add_gst_column, bool):
            raise DataValidationError(f"add_gst_column must be a bool, got {type(self.add_gst_column).__name__}")

        common.validate_optional_date(self.end_date, "end_date")
        if self.end_date is None and self.financial_year is None:
            raise DataValidationError("financial_year is required when end_date is omitted")
        if self.financial_year is not None:
            common.validate_financial_year(self.financial_year)

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
        """Locator for the chosen ageing-method option's clickable body."""
        return config.AGED_AGEING_OPTION_TPL.format(opt=_AGING_OPTION_KEYS[self.aging_by])

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


def download_aged_receivables_detail_report(browser, request: AgedReceivablesRequest) -> None:
    """
    Download an Aged Receivables Detail report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the report end date
        STEP 2 - select the ageing method
        STEP 3 - optionally add the Outstanding GST column
        STEP 4 - update, export, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. No data,
        or a file that fails to save, raises ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download Aged Receivables Detail Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report end date...")
        configure_report_date(browser, request)
        logger.info("STEP 1 COMPLETED: end date entered")

        logger.info("STEP 2: Selecting ageing method...")
        select_ageing_by(browser, request)
        logger.info("STEP 2 COMPLETED: ageing method selected")

        logger.info("STEP 3: Configuring Outstanding GST column...")
        configure_gst_column(browser, request)
        logger.info("STEP 3 COMPLETED: GST column configured")

        logger.info("STEP 4: Generating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 4 COMPLETED: report exported and file saved")


def configure_report_date(browser, request: AgedReceivablesRequest) -> None:
    """Enter the report end date into the (pre-filled) end-date field."""
    end_date = request.resolved_end_date
    logger.info(f"Entering report end date: {end_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, end_date)
    logger.info(f"End date entered successfully: {end_date}")


def select_ageing_by(browser, request: AgedReceivablesRequest) -> None:
    """Open the Ageing By dropdown and select the requested method."""
    logger.info(f"Selecting ageing method: '{request.aging_by}'")
    common.select_listbox_option(
        browser,
        config.AGED_AGEING_BY_BUTTON,
        request.aging_option_locator,
        description=f"Ageing By '{request.aging_by}'",
    )
    logger.info(f"Ageing method selected: '{request.aging_by}'")


def configure_gst_column(browser, request: AgedReceivablesRequest) -> None:
    """When requested, add the Outstanding GST column via the Columns menu.
    Leaves the columns untouched when add_gst_column is False."""
    if not request.add_gst_column:
        logger.info("add_gst_column is False - leaving columns unchanged")
        return

    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    logger.info("Adding Outstanding GST column...")
    browser.click_element(config.SH_COLUMNS_BUTTON, timeout=timeout)
    common.ensure_pickitem_selected(browser, config.AGED_GST_COLUMN_ID, timeout)
    browser.click_element(config.SH_COLUMNS_BUTTON, timeout=timeout)   # close the menu
    logger.info("Outstanding GST column added")


def update_and_export_report(browser, request: AgedReceivablesRequest) -> None:
    """Update the report, confirm it has data, export, and verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "aged_receivables_detail", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no Aged Receivables data available for this client")
        raise DataExtractionError("No Aged Receivables Detail data available for this client.")
    logger.info("'Export' button present - report contains data")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "aged_receivables_detail", "after_update",
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

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
