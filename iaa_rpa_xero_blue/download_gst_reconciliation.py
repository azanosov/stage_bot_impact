"""
Module for downloading GST Reconciliation reports from Xero Blue.

NOTE: GST Reconciliation is a LEGACY report surface - an older ExtJS page that
differs from every other report here. It has its own date inputs (`fromDate` /
`toDate`), no settings panel, and a dropdown Export menu of <a> links. Xero
ships two UI variants of the page (a modern button form and the legacy form),
so the Update / Export / format controls each probe a "default" locator and
fall back to a "legacy" one at runtime. Excel exports as ``.xls`` (old binary
format), not ``.xlsx``.

Configures and downloads one report: enters the From/To period dates, updates
the report, exports it (Excel -> .xls, or PDF -> .pdf), and confirms the file
was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(the GSTR_ section); shared behaviour lives in common.py. This module composes
those, and keeps the legacy dual-probe behaviour local (no other report needs it).

Period:
    A date-range report (From + To). `start_date`/`end_date` are the primary
    inputs (``datetime.date``); when either is omitted they are derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY).

How to call:
    from datetime import date
    from download_gst_reconciliation import (
        GstReconciliationRequest, download_gst_reconciliation_report,
    )

    request = GstReconciliationRequest(
        download_directory=r"C:\\Reports",
        report_file_name="gst_recon_2024",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        # financial_year=2024,     # used to derive any omitted date
        # export_format="excel",   # "excel" -> .xls, "pdf" -> .pdf
        # window_title="GST Reconciliation",
    )
    download_gst_reconciliation_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. No report data raises ``DataExtractionError``; a file that fails to save
    raises ``DownloadError``.
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
    "GstReconciliationRequest",
    "download_gst_reconciliation_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Export formats: format name -> (default format locator, legacy format locator,
# saved extension). NOTE the Excel link yields .xls, not .xlsx.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str, str]] = {
    "excel": (
        config.GSTR_FORMAT_EXCEL_DEFAULT,
        config.GSTR_FORMAT_EXCEL_LEGACY,
        ".xls",
    ),
    "pdf": (config.GSTR_FORMAT_PDF_DEFAULT, config.GSTR_FORMAT_PDF_LEGACY, ".pdf"),
}


@dataclass(frozen=True, kw_only=True)
class GstReconciliationRequest:
    """Everything needed to download one GST Reconciliation report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        start_date:         Period start (``datetime.date``). Falls back to FY.
        end_date:           Period end (``datetime.date``). Falls back to FY.
        financial_year:     FY end year (e.g. 2024); fallback when a date is omitted.
        export_format:      "excel" (saved as .xls) or "pdf" (saved as .pdf).
        window_title:       Title used to locate the Chrome Save As window.
        capture_screenshots: Whether to capture before/after screenshots during
            export (default True). When True, screenshot_path is required.
        screenshot_path: Directory screenshots are written to. Required when
            capture_screenshots is True; may be None when it is False.
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "GST Reconciliation"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")

        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        common.validate_optional_date(self.start_date, "start_date")
        common.validate_optional_date(self.end_date, "end_date")
        if (
            self.start_date is None or self.end_date is None
        ) and self.financial_year is None:
            raise DataValidationError(
                "financial_year is required when start_date or end_date is omitted"
            )
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
    def saved_extension(self) -> str:
        """The extension Xero produces for the chosen format (.xls / .pdf) -
        the source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format][2]

    @property
    def dest_path(self) -> str:
        return common.build_dest_path(
            self.download_directory, self.report_file_name, self.saved_extension
        )

    def summary_lines(self) -> list[str]:
        rows = {
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
            "Capture Screenshots": self.capture_screenshots,
            "Screenshot Path": (
                self.screenshot_path if self.capture_screenshots else "(disabled)"
            ),
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_gst_reconciliation_report(
    browser, request: GstReconciliationRequest
) -> str:
    """
    Download a GST Reconciliation report from Xero Blue (legacy surface).

    Steps, in order (each returns; none calls the next):
        STEP 1 - enter the From/To period dates
        STEP 2 - update the report, export to the chosen format, verify the file

    Returns:
        str: The full path of the saved report (directory + filename + extension).

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. No data raises ``DataExtractionError``; a file that fails to save raises
        ``DownloadError``.
    """
    with ProcessLogger("Xero Blue Download GST Reconciliation Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report period dates...")
        enter_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: from and to dates entered")

        logger.info("STEP 2: Updating report and exporting...")
        _dest = update_and_export_report(browser, request)
        logger.info("STEP 2 COMPLETED: report exported and file saved")
        return _dest


def enter_report_dates(browser, request: GstReconciliationRequest) -> None:
    """Enter the From (start) and To (end) period dates into the legacy fields."""
    logger.info("Entering report period dates...")
    common.clear_and_type(
        browser, config.GSTR_DATE_FROM_INPUT, request.resolved_start_date
    )
    logger.info(f"Entered From date: {request.resolved_start_date}")
    common.clear_and_type(browser, config.GSTR_DATE_TO_INPUT, request.resolved_end_date)
    logger.info(f"Entered To date: {request.resolved_end_date}")


def update_and_export_report(browser, request: GstReconciliationRequest) -> str:
    """Update the report (probing the default UI variant then legacy), confirm it
    has data, export to the chosen format, save, and verify the file."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    # Dates are entered: capture the configured report before Update.
    common.capture_report_screenshot(
        browser,
        request.screenshot_path,
        "gst_reconciliation",
        "before_update",
        enabled=request.capture_screenshots,
    )

    # --- Click 'Update' (default variant, falling back to legacy) ---
    if browser.does_page_contain_element(config.GSTR_UPDATE_DEFAULT, timeout=timeout):
        browser.click_element(config.GSTR_UPDATE_DEFAULT, timeout=common.EXPORT_TIMEOUT)
    else:
        browser.click_element(config.GSTR_UPDATE_LEGACY, timeout=common.EXPORT_TIMEOUT)
    logger.info("Clicked 'Update'")

    # --- Locate 'Export'; its absence is a business signal of no report data ---
    if browser.does_page_contain_element(config.GSTR_EXPORT_DEFAULT, timeout=timeout):
        export_locator = config.GSTR_EXPORT_DEFAULT
    elif browser.does_page_contain_element(config.GSTR_EXPORT_LEGACY, timeout=timeout):
        export_locator = config.GSTR_EXPORT_LEGACY
    else:
        logger.warning(
            "Export button not found - no report data available for this client"
        )
        raise DataExtractionError(
            "No GST Reconciliation data available for this client."
        )
    logger.info("'Export' control located")

    # Report has rendered with data: capture the result before exporting.
    common.capture_report_screenshot(
        browser,
        request.screenshot_path,
        "gst_reconciliation",
        "after_update",
        enabled=request.capture_screenshots,
    )

    # --- Open the Export menu and click the chosen format link ---
    default_format, legacy_format, _ = _EXPORT_FORMATS[request.export_format]
    logger.info(
        f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')..."
    )
    browser.click_element(export_locator, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export menu opened")

    if browser.does_page_contain_element(default_format, timeout=timeout):
        format_locator = default_format
    else:
        format_locator = legacy_format
    browser.click_element(format_locator, timeout=common.EXPORT_TIMEOUT)
    logger.info(f"Selected '{request.export_format}' export format")

    # --- Save via the Chrome save dialog ---
    time.sleep(3)  # brief settle so the save dialog has rendered
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)  # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
    return dest_path
