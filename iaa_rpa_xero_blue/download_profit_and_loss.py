"""
Module for downloading Profit and Loss reports from Xero Blue.

Configures and downloads a Profit and Loss report: forces the accounting basis
and applies any "show" options, enters the date range, optionally configures a
comparison period, optionally sets an alternative report title, generates and
exports the report (Excel or PDF), and confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py;
shared behaviour lives in common.py. This module composes those, and keeps the
P&L-specific pieces (the ComparisonPeriod value object, the show-option logic)
local.

Inputs are modelled as a dataclass:
    ProfitAndLossRequest - everything one download needs. The live browser/engine
                           is passed separately.

Period:
    A date-range report (From + To). `start_date`/`end_date` are the primary
    inputs (``datetime.date``); when either is omitted they are derived from
    `financial_year` (1 Jul of the prior year .. 30 Jun of the FY).

Comparison:
    Pass `comparison=ComparisonPeriod(kind, count)` (or `ComparisonPeriod
    .from_count(kind, count)`, which returns None for count 0). The date range is
    configured before the comparison because Xero disables comparison kinds when
    the range is too long.

How to call:
    from datetime import date
    from download_profit_and_loss import (
        ProfitAndLossRequest, ComparisonPeriod, download_profit_and_loss_report,
    )

    request = ProfitAndLossRequest(
        download_directory=r"C:\\Reports",
        report_file_name="profit_and_loss_2024",
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        # accounting_basis="Accrual",                  # "Accrual" (default) or "Cash"
        # comparison=ComparisonPeriod("Year", 1),      # or None
        # show_options={"Decimals": False},            # tri-state per label
        # alternative_report_title="P&L FY24",         # <= 100 chars
        # export_format="excel",                       # "excel" (default, .xlsx) or "pdf"
        # window_title="Profit and Loss",
    )
    download_profit_and_loss_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED. No report data, a
    comparison kind disabled for the chosen range, or a file that fails to save,
    all raise ``RuntimeError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "ProfitAndLossRequest",
    "ComparisonPeriod",
    "download_profit_and_loss_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
_MAX_TITLE_LENGTH = 100   # Xero's report-title input maxlength

# Accounting basis: request value (visible label) -> shared option id.
AccountingBasis = Literal["Accrual", "Cash"]
_ACCOUNTING_OPTION_IDS: dict[str, str] = {
    "Accrual": config.SH_BASIS_ACCRUAL_ID,
    "Cash": config.SH_BASIS_CASH_ID,
}

# Comparison kinds -> shared-template option ids (also checked for disabled state).
ComparisonKind = Literal["Month", "Quarter", "Year"]
_COMPARISON_KIND_IDS: dict[str, str] = {
    "Month": config.PLR_COMPARISON_KIND_MONTH_ID,
    "Quarter": config.PLR_COMPARISON_KIND_QUARTER_ID,
    "Year": config.PLR_COMPARISON_KIND_YEAR_ID,
}

# Known "Show" option labels (lowercased), used only to WARN on an unrecognised
# label - unknowns are still attempted and never fatal.
_KNOWN_SHOW_OPTIONS: frozenset[str] = frozenset(
    label.lower()
    for label in (
        "Zero balance or activity",
        "Accounting basis",
        "Account codes",
        "Decimals",
        "Percentage of trading income",
        "Total",
        "Year to date",
    )
)

# Export formats: format name -> (shared format-menu option id, saved extension).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.SH_EXPORT_EXCEL_ID, ".xlsx"),
    "pdf": (config.SH_EXPORT_PDF_ID, ".pdf"),
}


@dataclass(frozen=True)
class ComparisonPeriod:
    """A Profit and Loss comparison period: a kind (Month / Quarter / Year) and
    a positive count of periods.

    The UI treats a count of 0 as "no comparison"; that normalisation lives in
    ``from_count`` (which returns None), so the object itself is always a valid,
    positive period. Pass ``comparison=None`` to skip the comparison entirely.
    """

    kind: ComparisonKind
    count: int

    def __post_init__(self) -> None:
        if self.kind not in get_args(ComparisonKind):
            raise DataValidationError(
                f"comparison kind must be one of {get_args(ComparisonKind)}, got {self.kind!r}"
            )
        # bool is an int subclass; exclude it so True/False can't pose as a count.
        if not isinstance(self.count, int) or isinstance(self.count, bool):
            raise DataValidationError(f"comparison count must be an int, got {type(self.count).__name__}")
        if self.count <= 0:
            raise DataValidationError(
                f"comparison count must be a positive int, got {self.count} "
                "(use ComparisonPeriod.from_count, or comparison=None for no comparison)"
            )

    @classmethod
    def from_count(cls, kind: ComparisonKind, count: int) -> "ComparisonPeriod | None":
        """Build a ComparisonPeriod, or return None when count is 0 - mirroring
        the dropdown, where entering 0 periods means no comparison."""
        if count == 0:
            return None
        return cls(kind=kind, count=count)


@dataclass(frozen=True, kw_only=True)
class ProfitAndLossRequest:
    """Everything needed to download one Profit and Loss report.

    Attributes:
        download_directory:       Directory the report file is saved to.
        report_file_name:         Output filename; extension normalised/forced by dest_path.
        start_date:               Range start (``datetime.date``); falls back to FY.
        end_date:                 Range end (``datetime.date``); falls back to FY.
        financial_year:           FY end year (e.g. 2024); fallback when a date is omitted.
        accounting_basis:         "Accrual" (default) or "Cash". Always set.
        show_options:             Tri-state {label: bool}. True ensures checked,
                                  False ensures unchecked, omitted leaves as-is.
                                  Unknown labels are warned about and skipped.
        comparison:               Optional ComparisonPeriod. None means no comparison.
        alternative_report_title: Optional replacement title (<= 100 chars).
        export_format:            "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:             Title used to locate the Chrome Save As window.
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    accounting_basis: AccountingBasis = "Accrual"
    show_options: dict[str, bool] | None = None
    comparison: ComparisonPeriod | None = None
    alternative_report_title: str | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "Profit and Loss"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")

        if self.accounting_basis not in get_args(AccountingBasis):
            raise DataValidationError(
                f"accounting_basis must be one of {get_args(AccountingBasis)}, "
                f"got {self.accounting_basis!r}"
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

        # comparison must be a ComparisonPeriod when provided (it self-validates).
        if self.comparison is not None and not isinstance(self.comparison, ComparisonPeriod):
            raise DataValidationError(
                f"comparison must be a ComparisonPeriod or None, got {type(self.comparison).__name__}"
            )

        # alternative_report_title, when given, must be a non-empty <=100 char string.
        if self.alternative_report_title is not None:
            if not isinstance(self.alternative_report_title, str) or not self.alternative_report_title.strip():
                raise DataValidationError("alternative_report_title must be a non-empty string when provided")
            if len(self.alternative_report_title) > _MAX_TITLE_LENGTH:
                raise DataValidationError(
                    f"alternative_report_title must be <= {_MAX_TITLE_LENGTH} characters, "
                    f"got {len(self.alternative_report_title)}"
                )

        # show_options: validate shape, and warn (do not fail) on unknown labels.
        if self.show_options is not None:
            if not isinstance(self.show_options, dict):
                raise DataValidationError(
                    f"show_options must be a dict[str, bool] or None, got {type(self.show_options).__name__}"
                )
            for key, value in self.show_options.items():
                if not isinstance(key, str) or not key.strip():
                    raise DataValidationError(f"show_options keys must be non-empty strings, got {key!r}")
                if not isinstance(value, bool):
                    raise DataValidationError(f"show_options['{key}'] must be a bool, got {type(value).__name__}")
                if key.strip().lower() not in _KNOWN_SHOW_OPTIONS:
                    logger.warning(
                        f"show_options contains an unrecognised label {key!r}; it will be "
                        "attempted but may not match any on-screen option."
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
    def basis_option_id(self) -> str:
        return _ACCOUNTING_OPTION_IDS[self.accounting_basis]

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
        start_display = self.resolved_start_date if self.start_date else f"{self.resolved_start_date} (default)"
        end_display = self.resolved_end_date if self.end_date else f"{self.resolved_end_date} (default)"
        comparison_display = "None" if self.comparison is None else f"{self.comparison.kind} x {self.comparison.count}"
        rows = {
            "Start Date": start_display,
            "End Date": end_display,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from dates)",
            "Accounting Basis": self.accounting_basis,
            "Show Options": self.show_options if self.show_options else "(unchanged)",
            "Comparison": comparison_display,
            "Report Title": self.alternative_report_title or "(default)",
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


def download_profit_and_loss_report(browser, request: ProfitAndLossRequest) -> None:
    """
    Download a Profit and Loss report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - configure report settings (accounting basis + show options)
        STEP 2 - enter the report date range
        STEP 3 - configure the comparison period (optional)
        STEP 4 - set an alternative report title (optional)
        STEP 5 - update, export, and verify the saved file

    The date range is set before the comparison because Xero disables comparison
    kinds when the range is too long; the title is set before Update because it
    must be in place when the report is generated and exported.

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. No data, a
        disabled comparison kind, or a file that fails to save, raise ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download Profit and Loss Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Configuring report settings (accounting basis and show options)...")
        configure_report_settings(browser, request)
        logger.info("STEP 1 COMPLETED: report settings configured")

        logger.info("STEP 2: Entering report date range...")
        configure_report_dates(browser, request)
        logger.info("STEP 2 COMPLETED: date range entered")

        logger.info("STEP 3: Configuring comparison period...")
        configure_comparison(browser, request)
        logger.info("STEP 3 COMPLETED: comparison configuration applied")

        logger.info("STEP 4: Setting report title...")
        set_report_title(browser, request)
        logger.info("STEP 4 COMPLETED: report title configuration applied")

        logger.info("STEP 5: Generating report and exporting...")
        generate_and_export_report(browser, request)
        logger.info("STEP 5 COMPLETED: report exported and file saved")


def configure_report_settings(browser, request: ProfitAndLossRequest) -> None:
    """Open the More menu, force the accounting basis, apply any show options as
    desired end-states, and close the menu. (Basis + show options are batched
    under a single More session, so this does not use the shared basis helper.)"""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    logger.info("Opening 'More' settings menu...")
    browser.click_element(config.SH_MORE_BUTTON, timeout=timeout)

    # Force the accounting basis (idempotent - skips the click if already selected).
    logger.info(f"Selecting accounting basis: '{request.accounting_basis}'")
    common.ensure_pickitem_selected(browser, request.basis_option_id, timeout)

    # Apply show options as desired end-states.
    if request.show_options:
        for label, desired in request.show_options.items():
            _apply_show_option(browser, label, desired, timeout)
    else:
        logger.info("No show options specified - leaving all as displayed")

    browser.click_element(config.SH_MORE_BUTTON, timeout=timeout)   # close the menu
    logger.info("'More' settings menu closed")


def _apply_show_option(browser, label: str, desired: bool, timeout: int) -> None:
    """Set a single show option to the desired checked state, by visible label.
    Located case-insensitively and scoped to checkbox options. If the label is
    not found, logs a warning and returns without failing (cosmetic, not data)."""
    label_lower = label.strip().lower()
    exists_locator = config.PLR_SHOW_OPTION_EXISTS_TPL.format(label_lower=label_lower)
    checked_locator = config.PLR_SHOW_OPTION_CHECKED_TPL.format(label_lower=label_lower)
    click_locator = config.PLR_SHOW_OPTION_CLICK_TPL.format(label_lower=label_lower)

    if not browser.does_page_contain_element(exists_locator, timeout=timeout):
        logger.warning(f"Show option '{label}' not found on the page - skipping")
        return

    currently_checked = browser.does_page_contain_element(checked_locator, timeout=timeout)
    if currently_checked == desired:
        logger.info(f"Show option '{label}' already {'checked' if desired else 'unchecked'} - skipping")
        return

    browser.click_element(click_locator, timeout=timeout)
    logger.info(f"Show option '{label}' set to {'checked' if desired else 'unchecked'}")


def configure_report_dates(browser, request: ProfitAndLossRequest) -> None:
    """Enter the report start and end dates."""
    common.clear_and_type(browser, config.SH_DATE_FROM_INPUT, request.resolved_start_date)
    common.clear_and_type(browser, config.SH_DATE_TO_INPUT, request.resolved_end_date)


def configure_comparison(browser, request: ProfitAndLossRequest) -> None:
    """Configure the comparison period when one is requested. Opens the
    'Compare with' dropdown, enters the count via the custom-number dialog, then
    selects the kind - raising if that kind is disabled for the date range."""
    comparison = request.comparison
    if comparison is None:
        logger.info("No comparison period requested - skipping comparison configuration")
        return

    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    logger.info(f"Configuring comparison: '{comparison.kind}' x {comparison.count}")

    # Open the 'Compare with' dropdown and the custom-count dialog.
    browser.click_element(config.PLR_COMPARISON_BUTTON, timeout=timeout)
    browser.click_element(config.PLR_COMPARISON_OTHER, timeout=timeout)

    # Enter the count in the dialog (clear, type, confirm with Select - no TAB).
    browser.click_element(config.PLR_COMPARISON_MODAL_INPUT, timeout=timeout)
    browser.send_keys_to_active_element("\ue009" + "a")   # CTRL + A
    browser.send_keys_to_active_element("\ue003")         # DELETE
    browser.send_keys_to_active_element(str(comparison.count))
    browser.click_element(config.PLR_COMPARISON_MODAL_SELECT, timeout=timeout)
    logger.info(f"Comparison count entered: {comparison.count}")

    # Select the kind, failing if it is disabled for the chosen range.
    kind_id = _COMPARISON_KIND_IDS[comparison.kind]
    if common.pickitem_is_disabled(browser, kind_id, timeout):
        raise DataValidationError(
            f"Comparison kind '{comparison.kind}' is unavailable for the selected date range."
        )
    common.click_pickitem_by_id(browser, kind_id, timeout)
    logger.info(f"Comparison kind selected: '{comparison.kind}'")


def set_report_title(browser, request: ProfitAndLossRequest) -> None:
    """Replace the report title when an alternative is requested. The title
    survives Update and is written into the exported file."""
    title = request.alternative_report_title
    if not title:
        logger.info("No alternative report title requested - leaving the default")
        return

    logger.info(f"Setting report title to: '{title}'")
    common.clear_and_type(browser, config.SH_REPORT_TITLE_INPUT, title)
    logger.info(f"Report title set successfully: '{title}'")


def generate_and_export_report(browser, request: ProfitAndLossRequest) -> None:
    """Update the report, screenshot it, confirm it has data, export to the
    chosen format, and verify the saved file."""
    common.capture_report_screenshot(
        browser, request.screenshot_path, "profit_and_loss", "before_update",
        enabled=request.capture_screenshots,
    )

    logger.info("Clicking 'Update' to generate the report...")
    browser.click_element(config.SH_UPDATE_BUTTON, timeout=common.EXPORT_TIMEOUT)

    # Wait for the report title input to confirm the report has rendered.
    if browser.does_page_contain_element(config.SH_REPORT_TITLE_INPUT, timeout=common.EXPORT_TIMEOUT):
        logger.info("Report rendered successfully - report title is visible")
    else:
        logger.warning("Report title not visible within timeout - proceeding to data check")

    if not browser.does_page_contain_element(config.SH_EXPORT_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        logger.warning("Export button not found - no Profit and Loss data available for this client")
        raise DataExtractionError("No Profit and Loss data available for this client.")
    logger.info("'Export' button located - report contains data")

    logger.info(f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')...")
    common.capture_report_screenshot(
        browser, request.screenshot_path, "profit_and_loss", "after_update",
        enabled=request.capture_screenshots,
    )

    browser.click_element(config.SH_EXPORT_BUTTON, timeout=common.EXPORT_TIMEOUT)
    common.click_pickitem_by_id(browser, request.export_menu_id, timeout=common.EXPORT_TIMEOUT)
    logger.info("Export triggered. Waiting for the Windows Save As dialog...")

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"File successfully saved: '{dest_path}'")
