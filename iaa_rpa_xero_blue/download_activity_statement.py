"""
Module for downloading Activity Statement (BAS) reports from Xero Blue.

The Activity Statement is structurally different from the other reports: it uses
the BAS flow rather than the modern report toolbar - an ATO lodge wizard (when
present), a statement-period selector, and its own radio-based export panel.

Configures and downloads one statement: reaches the report page (clicking
through the lodge wizard if shown), selects the statement period within its
financial year, exports it (Excel or PDF), and confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(the ASR_ section); shared behaviour (validation, save-path, file-check) lives
in common.py. This module composes those.

Inputs are modelled as dataclasses:
    StatementPeriod          - a single BAS quarter-end period (month + calendar year)
    ActivityStatementRequest - everything one download needs (period + file/output config)

How to call:
    from download_activity_statement import (
        StatementPeriod, ActivityStatementRequest, download_activity_statement_report,
    )

    request = ActivityStatementRequest(
        period=StatementPeriod("March", 2025),   # the period as it appears in Xero
        download_directory=r"C:\\Reports",
        report_file_name="bas_mar_2025",
        # export_format="excel",                 # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="Activity Statement",
    )
    download_activity_statement_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. A failure selecting
    the period is wrapped in RuntimeError; a missing Export control, or a file
    that fails to save, also raises RuntimeError.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "StatementPeriod",
    "ActivityStatementRequest",
    "download_activity_statement_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
_MIN_STATEMENT_YEAR = 2000   # earliest period year we accept

# The four BAS quarter-end months. An invalid month is a type error at the call
# site (and a runtime ValueError via __post_init__) before anything runs.
Month = Literal["March", "June", "September", "December"]

# Export formats: format name -> (format radio locator, saved extension).
# Activity statement picks the format via a radio in its export panel (not the
# shared export menu), so the map holds the radio locator rather than a menu id.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.ASR_FORMAT_EXCEL_RADIO, ".xlsx"),
    "pdf": (config.ASR_FORMAT_PDF_RADIO, ".pdf"),
}


@dataclass(frozen=True)
class StatementPeriod:
    """A BAS quarter-end statement period, e.g. September 2024.

    `year` is the CALENDAR year shown next to the month in Xero's UI
    (September 2024 -> year=2024; March 2025 -> year=2025) - NOT a financial-year
    label. The FY range that contains the period is derived via `fiscal_year_label`.
    """

    month: Month
    year: int

    def __post_init__(self) -> None:
        if self.month not in get_args(Month):
            raise DataValidationError(f"month must be one of {get_args(Month)}, got {self.month!r}")
        # year is typed int but not enforced at runtime; guard it. bool is an int subclass.
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise DataValidationError(f"year must be an int, got {type(self.year).__name__}")
        max_year = datetime.now().year + 2
        if not _MIN_STATEMENT_YEAR <= self.year <= max_year:
            raise DataValidationError(f"year must be between {_MIN_STATEMENT_YEAR} and {max_year}, got {self.year}")

    def __str__(self) -> str:
        return f"{self.month} {self.year}"   # e.g. "September 2024"

    @property
    def fiscal_year_label(self) -> str:
        """FY range label that contains this period, e.g. "2024/25". Sep/Dec sit
        in the FY's start calendar year; Mar/Jun roll into the following one."""
        start = self.year if self.month in ("September", "December") else self.year - 1
        return f"{start}/{str(start + 1)[-2:]}"

    @property
    def tax_year(self) -> int:
        """The FY END year, as used in the tax-year automation-id (e.g. 2025 for
        the "2024/25" range). Both September 2024 and March 2025 give 2025."""
        start = self.year if self.month in ("September", "December") else self.year - 1
        return start + 1


@dataclass(frozen=True, kw_only=True)
class ActivityStatementRequest:
    """Everything needed to download one Activity Statement report.

    Attributes:
        period:             StatementPeriod (quarter-end month + calendar year).
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
    """

    period: StatementPeriod
    download_directory: str
    report_file_name: str
    export_format: ExportFormat = "excel"
    window_title: str = "Activity Statement"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")
        if not isinstance(self.period, StatementPeriod):
            raise DataValidationError(f"period must be a StatementPeriod, got {type(self.period).__name__}")
        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        if self.capture_screenshots and not (self.screenshot_path or "").strip():
            raise DataValidationError(
                "screenshot_path is required when capture_screenshots is True"
            )

    @property
    def format_radio_locator(self) -> str:
        """The export-panel radio locator for the chosen format."""
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def saved_extension(self) -> str:
        """The extension Xero produces for the chosen format (source of truth)."""
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def dest_path(self) -> str:
        return common.build_dest_path(self.download_directory, self.report_file_name, self.saved_extension)

    def summary_lines(self) -> list[str]:
        rows = {
            "Statement Period": self.period,
            "Financial Year": self.period.fiscal_year_label,
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


def download_activity_statement_report(browser, request: ActivityStatementRequest) -> None:
    """
    Download an Activity Statement report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - reach the report page (clicking through the ATO lodge wizard if shown)
        STEP 2 - select the statement period within its financial year
        STEP 3 - export to the chosen format, and verify the saved file

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. Invalid
        inputs raise ``DataValidationError``; a period/control that cannot be
        found raises ``ElementNotFoundError``; a missing Export control raises
        ``DataExtractionError``; a file that fails to save raises ``DownloadError``.
    """
    with ProcessLogger("Xero Blue Download Activity Statement Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Navigating to Activity Statement report page...")
        navigate_to_report_page(browser, request)
        logger.info("STEP 1 COMPLETED: report page reached")

        logger.info(
            f"STEP 2: Selecting statement period '{request.period}' "
            f"(financial year '{request.period.fiscal_year_label}')..."
        )
        select_statement_period(browser, request)
        logger.info("STEP 2 COMPLETED: statement period selected")

        logger.info(f"STEP 3: Exporting report as '{request.export_format}'...")
        run_report_export(browser, request)
        logger.info("STEP 3 COMPLETED: report exported and file saved")


def navigate_to_report_page(browser, request: ActivityStatementRequest) -> None:
    """Reach the report page, clicking through the ATO lodge wizard if present.
    Does NOT select a period (that is a separate step)."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    logger.info("Checking if the ATO lodge dialog is present...")
    if browser.does_page_contain_element(config.ASR_LODGE_BUTTON, timeout=timeout):
        logger.info("ATO lodge dialog detected - proceeding through wizard steps")
        browser.click_element(config.ASR_LODGE_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_GO_TO_STATEMENT_BUTTON, timeout=timeout)
        # Steps 1 and 2 of the wizard share the same Next locator; this relies on
        # Xero re-rendering the button between steps. If both ever coexist in the
        # DOM, give each a more specific locator.
        browser.click_element(config.ASR_WIZARD_NEXT_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_WIZARD_NEXT_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_WIZARD_OK_BUTTON, timeout=timeout)
        logger.info("Lodge wizard completed")
    else:
        logger.info("ATO lodge dialog not present - proceeding directly to period selection")


def select_statement_period(browser, request: ActivityStatementRequest) -> None:
    """Create a new statement and select the requested period: open the year
    selector, pick the FY range that contains the period, pick the period, then
    open the Transactions tab."""
    period = request.period
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    browser.click_element(config.ASR_CREATE_NEW_STATEMENT_BUTTON, timeout=timeout)
    logger.info("Clicked 'Create new statement'")

    # Periods in other financial years are not rendered until that year is
    # selected, so open the year selector (back button) and pick the tax year first.
    browser.click_element(config.ASR_YEAR_SELECTOR_BUTTON, timeout=timeout)
    logger.info("Opened financial year selector")

    browser.click_element(config.ASR_TAX_YEAR_TPL.format(tax_year=period.tax_year), timeout=timeout)
    logger.info(f"Selected tax year: '{period.fiscal_year_label}' (id {period.tax_year})")

    browser.click_element(
        config.ASR_STATEMENT_PERIOD_TPL.format(month=period.month, year=period.year), timeout=timeout
    )
    logger.info(f"Selected statement period: '{period}'")

    browser.click_element(config.ASR_TRANSACTIONS_TAB, timeout=timeout)
    logger.info("Opened the 'Transactions' tab - statement details visible")


def run_report_export(browser, request: ActivityStatementRequest) -> None:
    """Open the export panel, pick the format radio, confirm, save, and verify."""
    # The statement has rendered by now (period selected). Capture it before we
    # touch the export panel. Best-effort: BAS has no stable render-confirmation
    # element, so this is taken right after selection without a render gate.
    common.capture_report_screenshot(
        browser, request.screenshot_path, "activity_statement", "rendered",
        enabled=request.capture_screenshots,
    )

    if not browser.does_page_contain_element(config.ASR_EXPORT_DROPDOWN_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise DataExtractionError("'Export' control not found - cannot export report")

    logger.info("Opening the export panel...")
    browser.click_element(config.ASR_EXPORT_DROPDOWN_BUTTON, timeout=common.EXPORT_TIMEOUT)

    logger.info(f"Selecting '{request.export_format}' format...")
    browser.click_element(request.format_radio_locator, timeout=common.EXPORT_TIMEOUT)

    logger.info("Confirming export...")
    browser.click_element(config.ASR_EXPORT_CONFIRM_BUTTON, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export triggered. Waiting for the Windows Save As dialog...")

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
