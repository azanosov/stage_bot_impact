"""
Module for downloading GST Reconciliation reports from Xero Blue (legacy interface).

This module handles the complete workflow for configuring and downloading a GST
Reconciliation report from Xero Blue: resolving the reporting period, entering
the From/To dates into the legacy UI, updating the report, and exporting it to a
single format (Excel or PDF) via the Windows Save As dialog.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API. No direct
driver access is needed, and the module depends only on iaa_rpa_utils.

Inputs are modelled as a dataclass:
    GstReconciliationRequest - everything one download needs (period + file/output
                               config). The live browser/engine is passed
                               separately to the download function.

Structure:
    The orchestrator (download_gst_reconciliation_report) owns the order of
    operations and calls each step in sequence. The step helpers each do one
    thing and return - they do NOT call one another.

Period:
    `start_date` and `end_date` are the primary inputs (``datetime.date``). When
    either is omitted, it is derived from `financial_year` (1 Jul of the prior
    year / 30 Jun of the FY), so `financial_year` is required only as a fallback.

Export format:
    Xero's Excel link produces an ``.xls`` file (old binary format), not ``.xlsx``.
    The saved file's extension is taken from the _EXPORT_FORMATS table - NOT from
    any value the caller supplies - so the file on disk always matches its bytes.
    Only one format is exported per run; call again to export another.

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits. Overridable per run via
        GstReconciliationRequest.element_timeout.
    EXPORT_TIMEOUT          - the Update/Export/format buttons, which can be slow
        because Xero builds the file server-side. Intentionally longer.

How to call:
    from datetime import date
    from download_gst_reconciliation import (
        GstReconciliationRequest,
        download_gst_reconciliation_report,
    )

    # Explicit period:
    request = GstReconciliationRequest(
        start_date=date(2023, 7, 1),
        end_date=date(2024, 6, 30),
        download_directory=r"C:\\reports",
        report_file_name="GST_Recon_2024",
        # export_format="excel",   # "excel" -> .xls, "pdf" -> .pdf (default "excel")
        # window_title="GST Reconciliation",
        # element_timeout=5,
    )

    # Or fall back to the financial year for either/both dates:
    request = GstReconciliationRequest(
        financial_year=2024,                 # used to derive any omitted date
        download_directory=r"C:\\reports",
        report_file_name="GST_Recon_2024",
    )
    download_gst_reconciliation_report(browser, request)

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
    "GstReconciliationRequest",
    "download_gst_reconciliation_report",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5   # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10           # seconds; Update/Export/format - Xero builds the file server-side
_MIN_FINANCIAL_YEAR = 2000    # earliest financial year we accept

# Locale-independent month abbreviations, matching the labels Xero's legacy date
# field expects (e.g. "1 Jul 2023"). Avoids strftime('%b') locale surprises.
_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# Page locators for the Update and Export buttons. Xero ships two UI variants of
# this legacy page; we probe the "default" locator first and fall back to "legacy".
_DEFAULT_UPDATE_LOCATOR = "xpath://button[@type='button' and normalize-space(text())='Update']"
_LEGACY_UPDATE_LOCATOR = "xpath://a[normalize-space(text())='Update' and contains(@onclick,'UpdateReport')]"
_DEFAULT_EXPORT_LOCATOR = "xpath://button[@type='button' and normalize-space(text())='Export']"
_LEGACY_EXPORT_LOCATOR = "xpath://span[@class='words' and normalize-space(text())='Export']"

# Supported export formats. Each maps the caller-facing format name to:
#   (default-variant format-link locator, legacy-variant locator, SAVED extension)
# The saved extension is what Xero actually downloads - the Excel link yields .xls.
# Google Sheets is intentionally excluded (it opens Drive, not a local download).
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str, str]] = {
    "excel": (
        "xpath://button[@type='button']//span[normalize-space(text())='Excel']",
        "xpath://a[@title='Export to Excel' and normalize-space(text())='Excel']",
        ".xls",
    ),
    "pdf": (
        "xpath://button[@type='button']//span[normalize-space(text())='PDF']",
        "xpath://a[@title='Export to PDF' and normalize-space(text())='PDF']",
        ".pdf",
    ),
}


def _format_xero_date(d: date) -> str:
    """Format a date the way Xero's legacy field expects, e.g. "1 Jul 2023"
    (no leading zero on the day; locale-independent month abbreviation)."""
    return f"{d.day} {_MONTH_ABBR[d.month - 1]} {d.year}"


@dataclass(frozen=True, kw_only=True)
class GstReconciliationRequest:
    """Everything needed to download one GST Reconciliation report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.

    Attributes:
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename. The extension may be included or
                            omitted - ``dest_path`` normalises it and forces the
                            extension that matches the chosen export format.
        start_date:         Period start (``datetime.date``). Primary input;
                            falls back to "1 Jul {financial_year - 1}" if omitted.
        end_date:           Period end (``datetime.date``). Primary input; falls
                            back to "30 Jun {financial_year}" if omitted.
        financial_year:     FY end year as an int (e.g. 2024). Required only as a
                            fallback when start_date or end_date is omitted.
        export_format:      "excel" (saved as .xls) or "pdf" (saved as .pdf).
        window_title:       Title used to locate the Chrome Save As window.
        element_timeout:    Seconds to wait for general elements (default
                            DEFAULT_ELEMENT_TIMEOUT).
    """

    download_directory: str
    report_file_name: str
    start_date: date | None = None
    end_date: date | None = None
    financial_year: int | None = None
    export_format: ExportFormat = "excel"
    window_title: str = "GST Reconciliation"
    element_timeout: int = DEFAULT_ELEMENT_TIMEOUT

    def __post_init__(self) -> None:
        # export_format must be one we have links + a saved extension for.
        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        # Provided dates must be real date objects (datetime is a date subclass,
        # so it is accepted too - only the calendar part is used).
        for label, value in (("start_date", self.start_date), ("end_date", self.end_date)):
            if value is not None and not isinstance(value, date):
                raise TypeError(f"{label} must be a datetime.date, got {type(value).__name__}")

        # financial_year is the fallback source; required only when a date is missing.
        if (self.start_date is None or self.end_date is None) and self.financial_year is None:
            raise ValueError(
                "financial_year is required when start_date or end_date is omitted"
            )

        # Validate financial_year when present. bool is an int subclass, exclude it.
        if self.financial_year is not None:
            if not isinstance(self.financial_year, int) or isinstance(self.financial_year, bool):
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
    def resolved_start_date(self) -> str:
        """Start date as a Xero-formatted string, deriving from the financial
        year when no explicit start_date was given."""
        if self.start_date is not None:
            return _format_xero_date(self.start_date)
        return f"1 Jul {self.financial_year - 1}"

    @property
    def resolved_end_date(self) -> str:
        """End date as a Xero-formatted string, deriving from the financial year
        when no explicit end_date was given."""
        if self.end_date is not None:
            return _format_xero_date(self.end_date)
        return f"30 Jun {self.financial_year}"

    @property
    def saved_extension(self) -> str:
        """The extension Xero actually produces for the chosen format (e.g.
        ".xls" for Excel) - the source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format][2]

    @property
    def dest_path(self) -> str:
        """Full save path. The extension is forced to match the export format's
        real output, and is not doubled if ``report_file_name`` already ends in it."""
        ext = self.saved_extension  # includes the leading dot, e.g. ".xls"
        name = self.report_file_name
        if name.lower().endswith(ext.lower()):
            name = name[: -len(ext)]
        return os.path.join(self.download_directory, f"{name}{ext}")

    def summary_lines(self) -> list[str]:
        """Human-readable "label : value" rows describing this request, with
        the colons aligned. Used for the run's opening log block."""
        rows = {
            "Start Date": self.resolved_start_date,
            "End Date": self.resolved_end_date,
            "Financial Year": self.financial_year if self.financial_year is not None else "(from dates)",
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_gst_reconciliation_report(
    browser, request: GstReconciliationRequest
) -> None:
    """
    Download a GST Reconciliation report from Xero Blue (legacy interface).

    Owns the order of operations and calls each step in sequence:
        STEP 1 - enter the From/To period dates
        STEP 2 - update the report and export it to the chosen format

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (GstReconciliationRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it (with
        timing). A client with no report data raises ``RuntimeError``.
    """
    with ProcessLogger("Xero Blue Download GST Reconciliation Report", logger):
        # Echo the request so the log is self-describing
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Entering report period dates...")
        enter_report_dates(browser, request)
        logger.info("STEP 1 COMPLETED: from and to dates entered")

        logger.info("STEP 2: Updating report and exporting...")
        update_and_export_report(browser, request)
        logger.info("STEP 2 COMPLETED: report exported and file saved")


def enter_report_dates(browser, request: GstReconciliationRequest) -> None:
    """
    Enter the From and To period dates into the legacy GST Reconciliation UI.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (GstReconciliationRequest): Supplies the resolved dates and
            element_timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    logger.info("Entering report period dates...")

    _type_date(browser, "id:fromDate", request.resolved_start_date, timeout)
    logger.info(f"Entered From date: {request.resolved_start_date}")

    _type_date(browser, "id:toDate", request.resolved_end_date, timeout)
    logger.info(f"Entered To date: {request.resolved_end_date}")


def _type_date(browser, locator: str, value: str, timeout: int) -> None:
    """Focus a type-in date field and replace its contents with ``value``
    (CTRL+A / DELETE / type / TAB), via the wrapper's active-element keys."""
    browser.click_element(locator, timeout=timeout)
    browser.send_keys_to_active_element("\ue009" + "a")  # CTRL + A to select all
    browser.send_keys_to_active_element("\ue003")        # DELETE to clear existing value
    browser.send_keys_to_active_element(value)           # Type the date
    browser.send_keys_to_active_element("\ue004")        # TAB to confirm and move on


def update_and_export_report(browser, request: GstReconciliationRequest) -> None:
    """
    Update the report and export it to the chosen format, then save it.

    Clicks Update (default UI variant, falling back to legacy), verifies the
    Export button is present - its absence means the client has no report data,
    which raises ``RuntimeError`` - then opens the Export menu, clicks the format
    link, and hands the Chrome save dialog to ``handle_chrome_save_as_dialog``.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (GstReconciliationRequest): Supplies the export format, window
            title, dest path and element_timeout.

    Returns:
        None

    Raises:
        RuntimeError: If no Export button is present (no report data for client).
    """
    timeout = request.element_timeout
    logger.info("Starting report update and export process...")

    # --- Click 'Update' (default variant, falling back to legacy) ---
    if browser.does_page_contain_element(_DEFAULT_UPDATE_LOCATOR, timeout=timeout):
        browser.click_element(_DEFAULT_UPDATE_LOCATOR, timeout=EXPORT_TIMEOUT)
    else:
        browser.click_element(_LEGACY_UPDATE_LOCATOR, timeout=EXPORT_TIMEOUT)
    logger.info("Clicked 'Update' button")

    # --- Locate 'Export'; its absence is a business signal of no report data ---
    if browser.does_page_contain_element(_DEFAULT_EXPORT_LOCATOR, timeout=timeout):
        export_locator = _DEFAULT_EXPORT_LOCATOR
    elif browser.does_page_contain_element(_LEGACY_EXPORT_LOCATOR, timeout=timeout):
        export_locator = _LEGACY_EXPORT_LOCATOR
    else:
        logger.warning("Export button not found - no report data available for this client")
        raise RuntimeError("No report data available for this client.")
    logger.info("'Export' button located")

    # --- Open the Export menu and click the chosen format link ---
    default_format, legacy_format, _ = _EXPORT_FORMATS[request.export_format]
    logger.info(
        f"Exporting as '{request.export_format}' (saved as '{request.saved_extension}')..."
    )
    browser.click_element(export_locator, timeout=EXPORT_TIMEOUT)
    logger.info("Export menu opened")

    if browser.does_page_contain_element(default_format, timeout=timeout):
        format_locator = default_format
    else:
        format_locator = legacy_format
    browser.click_element(format_locator, timeout=EXPORT_TIMEOUT)
    logger.info(f"Selected '{request.export_format}' export format")

    # --- Save via the Chrome save dialog ---
    # Brief settle so the download/save dialog has rendered before we drive it.
    time.sleep(3)
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")
