"""
Module for downloading Trial Balance reports from Xero Blue.

Configures and downloads a Trial Balance report: selects the accounting basis
(Cash or Accrual), enters the report end date, generates the report (with
before/after-update audit screenshots), exports it to Excel, and confirms the
file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour (date formatting, validation, pick-list and input primitives,
the save-path/file-check helpers, the audit screenshot) lives in common.py.
This module composes those.

Inputs are modelled as a dataclass:
    TrialBalanceRequest - everything one download needs. The live browser/engine
                          is passed separately to the download function.

Audit screenshots:
    Two full-page screenshots are taken when ``capture_screenshots`` is True
    (the default): one after all selections are made (before Update) and one
    after the report has rendered with data (before Export). They land in
    ``screenshot_path``, which is therefore required when capture is on.

Period:
    The Trial Balance is an "as at" report - only an end date. `end_date` is the
    primary input (``datetime.date``); when omitted it is derived from
    `financial_year` (30 Jun of the FY), so `financial_year` is required only as
    a fallback.

Accounting basis:
    `accounting_method` selects Cash or Accrual via the More options menu. It is
    always set (forced). Defaults to "Cash" (the report's long-standing default).

How to call:
    from datetime import date
    from download_trial_balance import TrialBalanceRequest, download_trial_balance_report

    request = TrialBalanceRequest(
        download_directory=r"C:\\Reports",
        report_file_name="trial_balance_2024",
        end_date=date(2024, 6, 30),
        # accounting_method="Cash",   # "Cash" (default) or "Accrual"
        # financial_year=2024,        # used to derive end_date if omitted
        # export_format="excel",      # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="Trial Balance",
    )
    download_trial_balance_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. Invalid inputs raise
    ``DataValidationError``; a client with no report data raises
    ``DataExtractionError``; a file that fails to save raises ``DownloadError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "TrialBalanceRequest",
    "download_trial_balance_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
# Accounting basis: the request value maps to the radio's visible label (for
# logging) and to the shared picklist option id (for clicking).
AccountingMethod = Literal["Accrual", "Cash"]
_ACCOUNTING_OPTION_IDS: dict[str, str] = {
    "Accrual": config.SH_BASIS_ACCRUAL_ID,
    "Cash": config.SH_BASIS_CASH_ID,
}

# Export formats: format name -> (shared format-menu option id, saved extension).
# The extension is the source of truth for the filename.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}


@dataclass(frozen=True, kw_only=True)
class TrialBalanceRequest:
    """Everything needed to download one Trial Balance report.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; the extension is normalised and
                            forced to match the export format by ``dest_path``.
        end_date:           Report "as at" date (``datetime.date``). Primary
                            input; falls back to "30 Jun {financial_year}".
        financial_year:     FY end year (e.g. 2024). Required only as a fallback
                            when end_date is omitted.
        accounting_method:  "Cash" (default) or "Accrual". Always set.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
        capture_screenshots: When True (default), take before/after-update audit
                            screenshots. Requires screenshot_path.
        screenshot_path:    Folder the audit screenshots are written to. Required
                            when capture_screenshots is True.
    """

    download_directory: str
    report_file_name: str
    end_date: date | None = None
    financial_year: int | None = None
    accounting_method: AccountingMethod = "Cash"
    export_format: ExportFormat = "excel"
    window_title: str = "Trial Balance"
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
        """End date as a Xero-formatted string, derived from the financial year
        when no explicit end_date was given."""
        if self.end_date is not None:
            return common.format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def basis_option_id(self) -> str:
        """The shared picklist option id for the chosen accounting method."""
        return _ACCOUNTING_OPTION_IDS[self.accounting_method]

    @property
    def export_menu_id(self) -> str:
        """The shared export-menu option id for the chosen format."""
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def saved_extension(self) -> str:
        """The extension Xero produces for the chosen format (source of truth)."""
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def dest_path(self) -> str:
        """Full save path, extension forced to match the export format."""
        return common.build_dest_path(self.download_directory, self.report_file_name, self.saved_extension)

    def summary_lines(self) -> list[str]:
        """Aligned "label : value" rows for the opening log block."""
        end_display = (
            self.resolved_end_date if self.end_date
            else f"{self.resolved_end_date} (default)"
        )
        rows = {
            "End Date": end_display,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from end date)",
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


def download_trial_balance_report(browser, request: TrialBalanceRequest) -> None:
    """
    Download a Trial Balance report from Xero Blue.

    Steps, in order:
        STEP 1 - select the accounting basis (Cash / Accrual)
        STEP 2 - enter the report end date
        STEP 3 - generate the report and export it to Excel, then verify the file

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (TrialBalanceRequest): All configuration for the download.

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. Invalid
        inputs raise ``DataValidationError``; no report data raises
        ``DataExtractionError``; a file that fails to save raises ``DownloadError``.
    """
    with ProcessLogger("Xero Blue Download Trial Balance Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Selecting accounting basis...")
        configure_accounting_basis(browser, request)
        logger.info("STEP 1 COMPLETED: accounting basis selected")

        logger.info("STEP 2: Entering report end date...")
        configure_report_date(browser, request)
        logger.info("STEP 2 COMPLETED: end date entered")

        logger.info("STEP 3: Generating report and exporting...")
        generate_and_export_report(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


def configure_accounting_basis(browser, request: TrialBalanceRequest) -> None:
    """Force the requested accounting basis via the More menu."""
    logger.info(f"Selecting accounting basis: '{request.accounting_method}'")
    common.select_accounting_basis_via_more(browser, request.basis_option_id)
    logger.info(f"Accounting basis '{request.accounting_method}' selected")


def configure_report_date(browser, request: TrialBalanceRequest) -> None:
    """Enter the report end date into the (pre-filled) end-date field."""
    end_date = request.resolved_end_date
    logger.info(f"Entering report end date: {end_date}")
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, end_date)
    logger.info(f"End date entered successfully: {end_date}")


def generate_and_export_report(browser, request: TrialBalanceRequest) -> None:
    """Screenshot the configured report, update it, confirm it has data,
    screenshot the rendered result, export it, and verify the saved file."""
    # All selections are done: capture the configured report before Update.
    common.capture_report_screenshot(
        browser, request.screenshot_path, "trial_balance", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # Wait for the report title input to confirm the report has rendered.
    if browser.does_page_contain_element(config.SH_REPORT_TITLE_INPUT, timeout=common.EXPORT_TIMEOUT):
        logger.info("Report rendered successfully - report title is visible")
    else:
        logger.warning("Report title not visible within timeout - proceeding to data check")

    # No Export button means the client has no report data.
    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no Trial Balance data available for this client")
        raise DataExtractionError("No Trial Balance data available for this client.")
    logger.info("'Export' button located - report contains data")

    # Report has rendered with data: capture the result before exporting.
    common.capture_report_screenshot(
        browser, request.screenshot_path, "trial_balance", "after_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Opening export menu and selecting format...")
    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export triggered. Waiting for the Windows Save As dialog...")

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
