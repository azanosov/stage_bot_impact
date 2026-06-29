"""
Module for downloading Activity Statement reports from Xero Blue.

This module handles the complete workflow for navigating to and downloading
Activity Statement reports from Xero Blue, including handling ATO lodge dialogs
and statement period selection.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API, e.g.
"xpath://button[...]". No direct driver access is needed.

Inputs are modelled as dataclasses:
    StatementPeriod          - a single BAS quarter-end period (month + calendar year)
    ActivityStatementRequest - everything one download needs (period + file/output config)

Structure:
    The orchestrator (download_activity_statement_report) owns the order of
    operations and calls each step in sequence. The step helpers each do one
    thing and return - they do NOT call one another. This keeps the workflow
    readable top-to-bottom and lets each step be run/tested in isolation.

Timeouts:
    DEFAULT_ELEMENT_TIMEOUT - general element waits. Overridable per run via
        ActivityStatementRequest.element_timeout.
    EXPORT_TIMEOUT          - the export buttons, which can be slow because Xero
        builds the file server-side. Intentionally longer; not configurable.

How to call:
    from download_activity_statement import (
        StatementPeriod,
        ActivityStatementRequest,
        download_activity_statement_report,
    )

    request = ActivityStatementRequest(
        period=StatementPeriod("March", 2025),   # the period as it appears in Xero
        download_directory=r"C:\\reports",
        report_file_name="BAS_Q3_2025",
        # window_title="Activity Statement",      # optional, has a default
        # export_format="excel",                 # only "excel" supported (saved .xlsx)
        # element_timeout=5,                       # optional, has a default
    )
    download_activity_statement_report(browser, request)

Note on month + year:
    `year` is the CALENDAR year shown beside the month in Xero, NOT a financial-year
    label. September 2024 and December 2024 -> year=2024; March 2025 and June 2025 ->
    year=2025. All four belong to financial year "2024/25", which is derived
    automatically. Pass the year you see on screen next to the month.

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and SWALLOWED - the function
    returns None rather than raising. To make failures propagate to the caller,
    remove the surrounding try/except (or change ``return`` to ``raise``).
"""

from __future__ import annotations

import os
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
    "StatementPeriod",
    "ActivityStatementRequest",
    "download_activity_statement_report",
]


# --------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------
DEFAULT_ELEMENT_TIMEOUT = 5   # seconds; general element waits (overridable per run)
EXPORT_TIMEOUT = 10           # seconds; export buttons - Xero builds the file server-side
_MIN_STATEMENT_YEAR = 2000    # earliest period year we accept


# The four BAS quarter-end months. Constrained so an invalid month is a
# type-check error at the call site, before anything runs.
Month = Literal["March", "June", "September", "December"]

# Supported export format(s). This report exports Excel only; the value exists so
# the interface matches the other report modules. _EXPORT_FORMATS maps the chosen
# format to the extension Xero actually saves - the source of truth for the
# filename, so the saved file can never disagree with its bytes.
ExportFormat = Literal["excel"]
_EXPORT_FORMATS: dict[str, str] = {
    "excel": ".xlsx",
}


@dataclass(frozen=True)
class StatementPeriod:
    """A BAS quarter-end statement period, e.g. September 2024.

    `year` is the CALENDAR year shown next to the month in Xero's UI
    (September 2024 -> year=2024; March 2025 -> year=2025) - NOT a
    financial-year label. The FY range that contains the period is derived
    from it via `fiscal_year_label`.
    """

    month: Month
    year: int

    def __post_init__(self) -> None:
        # Validate the month at runtime - the Literal only constrains type
        # checkers, and a typo here would otherwise surface as a Selenium
        # timeout deep in select_statement_period. get_args keeps this in sync
        # with the Month definition automatically.
        if self.month not in get_args(Month):
            raise ValueError(
                f"month must be one of {get_args(Month)}, got {self.month!r}"
            )

        # year is typed int but that is not enforced at runtime; guard it so a
        # stringified year gives this clear error rather than a TypeError from
        # the comparison below. bool is an int subclass, so exclude it.
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise TypeError(f"year must be an int, got {type(self.year).__name__}")

        # Reject implausible years. +2 allows entering a period slightly ahead
        # of the current calendar year (a BAS quarter can sit in the next one).
        max_year = datetime.now().year + 2
        if not _MIN_STATEMENT_YEAR <= self.year <= max_year:
            raise ValueError(
                f"year must be between {_MIN_STATEMENT_YEAR} and {max_year}, got {self.year}"
            )

    def __str__(self) -> str:
        # Label Xero shows for the period itself, e.g. "September 2024".
        return f"{self.month} {self.year}"

    @property
    def fiscal_year_label(self) -> str:
        """FY range label that contains this period, e.g. "2024/25".

        Sep/Dec sit in the financial year's start calendar year; Mar/Jun roll
        into the following one. So both September 2024 and March 2025 belong to
        the "2024/25" range.
        """
        start = self.year if self.month in ("September", "December") else self.year - 1
        return f"{start}/{str(start + 1)[-2:]}"


@dataclass(frozen=True, kw_only=True)
class ActivityStatementRequest:
    """Everything needed to download one Activity Statement report.

    Holds configuration data only - the live browser/engine is passed
    separately to the download function.
    """

    period: StatementPeriod
    download_directory: str
    report_file_name: str
    window_title: str = "Activity Statement"
    export_format: ExportFormat = "excel"
    element_timeout: int = DEFAULT_ELEMENT_TIMEOUT

    def __post_init__(self) -> None:
        # export_format must be one we have a saved extension for.
        if self.export_format not in get_args(ExportFormat):
            raise ValueError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

    @property
    def saved_extension(self) -> str:
        """The extension Xero actually produces for the chosen format (".xlsx")
        - the source of truth for the saved filename."""
        return _EXPORT_FORMATS[self.export_format]

    @property
    def dest_path(self) -> str:
        """Full save path, e.g. ".../BAS_Q1.xlsx". Tolerates an extension passed
        with or without a leading dot, and avoids doubling the extension if
        ``report_file_name`` already carries it."""
        ext = self.saved_extension  # includes the leading dot, e.g. ".xlsx"
        name = self.report_file_name
        if name.lower().endswith(ext.lower()):
            name = name[: -len(ext)]
        return os.path.join(self.download_directory, f"{name}{ext}")

    def summary_lines(self) -> list[str]:
        """Human-readable "label : value" rows describing this request, with
        the colons aligned. Used for the run's opening log block."""
        rows = {
            "Statement Period": self.period,
            "Financial Year": self.period.fiscal_year_label,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Window Title": self.window_title,
            "Element Timeout": self.element_timeout,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_activity_statement_report(
    browser, request: ActivityStatementRequest
) -> None:
    """
    Download an Activity Statement report from Xero Blue.

    Owns the order of operations and calls each step in sequence:
        STEP 1 - reach the report page (clicking through the ATO lodge wizard
                 if it is present)
        STEP 2 - select the statement period within its financial year
        STEP 3 - export the report to Excel and save it

    Each step helper returns when done; none calls the next.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (ActivityStatementRequest): All configuration for the download.

    Returns:
        None

    Raises:
        Nothing. Any error during the download is logged (by ``ProcessLogger``)
        and swallowed here, so the function returns None. Remove the try/except
        to propagate instead.
    """
    try:
        with ProcessLogger("Xero Blue Download Activity Statement Report", logger):
            # Echo the request so the log is self-describing
            for line in request.summary_lines():
                logger.info(line)

            logger.info("STEP 1: Navigating to Activity Statement report page...")
            navigate_to_report_page(browser, request)
            logger.info("STEP 1 COMPLETED: report page reached")

            logger.info(
                f"STEP 2: Selecting statement period '{request.period}' "
                f"(financial year '{request.period.fiscal_year_label}')..."
            )
            try:
                select_statement_period(browser, request)
            except Exception as e:
                raise RuntimeError(f"Failed selecting period {request.period}") from e
            logger.info("STEP 2 COMPLETED: statement period selected")

            logger.info("STEP 3: Exporting report to Excel...")
            run_report_export(browser, request)
            logger.info("STEP 3 COMPLETED: report exported and file saved")

    except Exception:
        # The failure was already logged by ProcessLogger. Swallow it here so
        # the caller receives None. Remove this try/except to propagate instead.
        return


def navigate_to_report_page(browser, request: ActivityStatementRequest) -> None:
    """
    Reach the Activity Statement report page in Xero Blue.

    If the ATO lodge dialog appears, clicks through its wizard steps to reach
    the statement page. Otherwise proceeds directly. Does NOT select a period -
    that is a separate step owned by the orchestrator.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (ActivityStatementRequest): Supplies element_timeout.

    Returns:
        None
    """
    timeout = request.element_timeout
    lodge_report_locator = (
        "xpath://button[normalize-space(text())='Lodge reports to ATO outside of Xero']"
    )

    logger.info("Checking if 'Lodge reports to ATO outside of Xero' dialog is present...")
    if lodge_reports_dialog_present(browser, lodge_report_locator, timeout):

        logger.info("ATO lodge dialog detected - proceeding through dialog steps")

        browser.click_element(lodge_report_locator, timeout=timeout)
        logger.info("Clicked 'Lodge reports to ATO outside of Xero' button")

        browser.click_element(
            "xpath://button[normalize-space(text())='Go to Activity Statement']",
            timeout=timeout,
        )
        logger.info("Clicked 'Go to Activity Statement' button")

        # Steps 1 and 2 share the same locator. This relies on Xero re-rendering
        # the button between steps. If both Next buttons ever coexist in the DOM,
        # give each step a more specific locator.
        next_button_locator = "xpath://button[normalize-space(text())='Next']"
        browser.click_element(next_button_locator, timeout=timeout)
        logger.info("Clicked 'Next' button - Step 1 of wizard")

        browser.click_element(next_button_locator, timeout=timeout)
        logger.info("Clicked 'Next' button - Step 2 of wizard")

        browser.click_element(
            "xpath://button[normalize-space(text())='OK']",
            timeout=timeout,
        )
        logger.info("Clicked 'OK' button - Wizard completed")

    else:
        logger.info(
            "ATO lodge dialog not present - proceeding directly to period selection",
        )


def lodge_reports_dialog_present(browser, lodge_report_locator, timeout) -> bool:
    """
    Check whether the 'Lodge reports to ATO outside of Xero' dialog is present.

    Args:
        browser: SeleniumBrowser wrapper instance.
        lodge_report_locator (str): Wrapper locator string for the lodge button.
        timeout (int): Seconds to wait for the button.

    Returns:
        bool: True if the button is found within the timeout, else False.

    Note:
        Uses the wrapper's ``does_page_contain_element`` (DOM presence). If Xero
        ever renders a hidden copy of the button, switch to a visibility check.
    """
    present = browser.does_page_contain_element(lodge_report_locator, timeout=timeout)
    if present:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is present")
    else:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is not present")
    return present


def select_statement_period(browser, request: ActivityStatementRequest) -> None:
    """
    Create a new statement and select the requested period.

    Expands the financial-year selector, picks the FY range that contains the
    period, selects the period itself, then opens the Transactions tab.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (ActivityStatementRequest): Supplies the period and element_timeout.

    Returns:
        None
    """
    period = request.period
    timeout = request.element_timeout

    # Initiate creation of a new activity statement
    browser.click_element(
        "xpath://button[.//span[normalize-space(text())='Create new statement']]",
        timeout=timeout,
    )
    logger.info("Clicked 'Create new statement' button")

    # Periods belonging to other financial years are not rendered until that
    # year is expanded, so we always open the year selector first.
    all_years_locator = (
        "xpath://button[@data-automationid='financial-period-header--button-back']"
    )
    browser.click_element(all_years_locator, timeout=timeout)
    logger.info("Opened financial year selector")

    # Select the FY range that contains this period (e.g. "2024/25").
    financial_year_locator = (
        f"xpath://button[contains(@class,'xui-pickitem--body')]"
        f"[.//div[normalize-space(.)='{period.fiscal_year_label}']]"
    )
    browser.click_element(financial_year_locator, timeout=timeout)
    logger.info(f"Selected financial year: '{period.fiscal_year_label}'")

    # Select the period itself within the chosen year (e.g. "September 2024").
    statement_locator = (
        f"xpath://button[contains(@class,'xui-pickitem--body')]"
        f"[.//div[normalize-space(.)='{period}']]"
    )
    browser.click_element(statement_locator, timeout=timeout)
    logger.info(f"Successfully selected statement period: '{period}'")

    # Navigate to the Transactions tab to view statement details
    logger.info("Navigating to the 'Transactions' tab...")
    browser.click_element(
        "xpath://button[.//span[normalize-space()='Transactions']]",
        timeout=timeout,
    )
    logger.info("Clicked 'Transactions' tab - Statement details are now visible")


def run_report_export(browser, request: ActivityStatementRequest) -> None:
    """
    Export the Activity Statement report as an Excel file and save it.

    Clicks Export, picks the Excel format, confirms, then handles the Chrome
    save dialog to write the file to the request's destination path. The export
    buttons use EXPORT_TIMEOUT (Xero builds the file server-side); the presence
    pre-check uses the configurable element_timeout.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (ActivityStatementRequest): Supplies window title, dest path and
            element_timeout.

    Returns:
        None
    """
    logger.info("Locating 'Export' button on the report page...")
    export_btn_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Export']"
    )

    if not browser.does_page_contain_element(export_btn_locator, timeout=request.element_timeout):
        raise RuntimeError("'Export' button not found - cannot export report")

    browser.click_element(export_btn_locator, timeout=EXPORT_TIMEOUT)
    logger.info("Clicked 'Export' button - Export options panel is now open")

    # Choose Excel as the export format
    logger.info("Selecting Excel format for the report export...")
    browser.click_element(
        "xpath://label[@data-automationid='bas-excel-radio-button']",
        timeout=EXPORT_TIMEOUT,
    )
    logger.info("Selected 'Excel' radio button as the export format")

    # Confirm the export - triggers the browser's download/save dialog
    logger.info("Confirming export by clicking the final 'Export' button...")
    browser.click_element(
        "xpath://button[@type='button' and @data-automationid='bas-export-button' "
        "and normalize-space(text())='Export']",
        timeout=EXPORT_TIMEOUT,
    )
    logger.info("Clicked final 'Export' button - File download dialog triggered")

    # Handle the Chrome save dialog and save to the requested path
    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=f"regex:.*{request.window_title}.* - Google Chrome",
        dest_path=dest_path,
    )
    logger.info(f"File successfully saved: '{dest_path}'")
