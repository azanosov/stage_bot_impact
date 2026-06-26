"""
Module for downloading Activity Statement reports from Xero Blue.

This module handles the complete workflow for navigating to and downloading
Activity Statement reports from Xero Blue, including handling ATO lodge dialogs
and statement period selection.

Drives the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) rather than the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API, e.g.
"xpath://button[...]" / "id:submit" / "css:.foo". No direct driver access is
needed.

Inputs are modelled as dataclasses:
    StatementPeriod          - a single BAS quarter-end period (month + calendar year)
    ActivityStatementRequest - everything one download needs (period + file/output config)

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
        # extension="xlsx",                        # optional, has a default
    )
    download_activity_statement_report(browser, request)

Note on month + year:
    `year` is the CALENDAR year shown beside the month in Xero, NOT a financial-year
    label. September 2024 and December 2024 -> year=2024; March 2025 and June 2025 ->
    year=2025. All four belong to financial year "2024/25", which is derived
    automatically. Pass the year you see on screen next to the month.

Failure behaviour:
    Errors are logged and swallowed - the function returns None rather than raising.
    To make failures propagate to the caller, change the `except` block in
    `download_activity_statement_report` from `return` to `raise`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog


# Set up logger
logger = setup_logger(__name__)


# The four BAS quarter-end months. Constrained so an invalid month is a
# type-check error at the call site, before anything runs.
Month = Literal["March", "June", "September", "December"]


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
        if not 1000 <= self.year <= 9999:
            raise ValueError(f"year must be a 4-digit calendar year, got {self.year}")

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
    extension: str = "xlsx"

    @property
    def dest_path(self) -> str:
        """Full save path, e.g. ".../BAS_Q1.xlsx". Tolerates an extension
        passed with or without a leading dot."""
        ext = self.extension.lstrip(".")
        return os.path.join(self.download_directory, f"{self.report_file_name}.{ext}")

    def summary_lines(self) -> list[str]:
        """Human-readable "label : value" rows describing this request, with
        the colons aligned. Used for the run's opening log block."""
        rows = {
            "Statement Period": self.period,
            "Financial Year": self.period.fiscal_year_label,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Extension": self.extension,
            "Window Title": self.window_title,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_activity_statement_report(browser, request: ActivityStatementRequest) -> None:
    """
    Download an Activity Statement report from Xero Blue.

    Orchestrates the complete process: navigates through ATO lodge dialogs (if
    present), selects the statement period and its financial year, and exports
    the report to the requested directory.

    Args:
        browser: SeleniumBrowser wrapper instance (the live engine).
        request (ActivityStatementRequest): All configuration for the download -
            the period, output directory, filename, window title and extension.

    Returns:
        None

    Raises:
        Nothing. Any error during the download is logged (by ``ProcessLogger``)
        and swallowed here, so the function returns None. Change the ``except``
        block to re-raise if the caller needs to detect failure.
    """

    try:
        with ProcessLogger("Xero Blue Download Activity Statement Report", logger):
            # Echo the request so the log is self-describing
            for line in request.summary_lines():
                logger.info(line)

            # STEP 1: reach the report page (handles the ATO lodge wizard if
            # present) and select the period within its financial year.
            logger.info("STEP 1: Navigating to Activity Statement report page...")
            navigated_to_activity_statement_report(browser, request.period)
            logger.info("STEP 1 COMPLETED: navigated to report page")

            # STEP 2: export the report as Excel and save it.
            logger.info("STEP 2: Exporting Activity Statement report as Excel file...")
            run_report_export(browser, request)
            logger.info("STEP 2 COMPLETED: report exported")

    except Exception:
        # The failure was already logged by ProcessLogger. Swallow it here so the
        # caller receives None. Change this to `raise` to propagate instead.
        return


def navigated_to_activity_statement_report(browser, period: StatementPeriod) -> None:
    """
    Navigate to the Activity Statement report page in Xero Blue.

    If the ATO lodge dialog appears, clicks through its wizard steps to reach
    the statement page, then selects the requested period.

    Args:
        browser: SeleniumBrowser wrapper instance.
        period (StatementPeriod): The period to select (e.g. September 2024).

    Returns:
        None
    """

    lodge_report_locator = (
        "xpath://button[normalize-space(text())='Lodge reports to ATO outside of Xero']"
    )

    logger.info(
        "Checking if 'Lodge reports to ATO outside of Xero' dialog is present...",
    )
    if is_lodge_reports_dialog_present(browser, lodge_report_locator):

        logger.info("ATO lodge dialog detected - proceeding through dialog steps")

        browser.click_element(lodge_report_locator, timeout=5)
        logger.info("Clicked 'Lodge reports to ATO outside of Xero' button")

        browser.click_element(
            "xpath://button[normalize-space(text())='Go to Activity Statement']",
            timeout=5,
        )
        logger.info("Clicked 'Go to Activity Statement' button")

        # Steps 1 and 2 share the same locator. This relies on Xero re-rendering
        # the button between steps. If both Next buttons ever coexist in the DOM,
        # give each step a more specific locator.
        next_button_locator = "xpath://button[normalize-space(text())='Next']"
        browser.click_element(next_button_locator, timeout=5)
        logger.info("Clicked 'Next' button - Step 1 of wizard")

        browser.click_element(next_button_locator, timeout=5)
        logger.info("Clicked 'Next' button - Step 2 of wizard")

        browser.click_element(
            "xpath://button[normalize-space(text())='OK']",
            timeout=5,
        )
        logger.info("Clicked 'OK' button - Wizard completed")

    else:
        logger.info(
            "ATO lodge dialog not present - proceeding directly to period selection",
        )

    logger.info(
        f"Selecting statement period '{period}' (financial year '{period.fiscal_year_label}')",
    )

    try:
    	select_statement_period(browser, period)
    except Exception as e:
    	raise RuntimeError(f"Failed selecting period {period}") from 

def is_lodge_reports_dialog_present(browser, lodge_report_locator) -> bool:
    """
    Check whether the 'Lodge reports to ATO outside of Xero' dialog is present.

    Args:
        browser: SeleniumBrowser wrapper instance.
        lodge_report_locator (str): Wrapper locator string for the lodge button.

    Returns:
        bool: True if the button is found within the timeout, else False.

    Note:
        Uses the wrapper's ``does_page_contain_element`` (DOM presence). If Xero
        ever renders a hidden copy of the button, switch to a visibility check.
    """
    present = browser.does_page_contain_element(lodge_report_locator, timeout=5)
    if present:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is present")
    else:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is not present")
    return present


def select_statement_period(browser, period: StatementPeriod) -> None:
    """
    Create a new statement and select the requested period.

    Expands the financial-year selector, picks the FY range that contains the
    period, selects the period itself, then opens the Transactions tab.

    Args:
        browser: SeleniumBrowser wrapper instance.
        period (StatementPeriod): The period to select (e.g. September 2024).

    Returns:
        None
    """

    # Initiate creation of a new activity statement
    browser.click_element(
        "xpath://button[.//span[normalize-space(text())='Create new statement']]",
        timeout=5,
    )
    logger.info("Clicked 'Create new statement' button")

    # Periods belonging to other financial years are not rendered until that
    # year is expanded, so we always open the year selector first.
    all_years_locator = (
        "xpath://button[@data-automationid='financial-period-header--button-back']"
    )
    browser.click_element(all_years_locator, timeout=5)
    logger.info("Opened financial year selector")

    # Select the FY range that contains this period (e.g. "2024/25").
    financial_year_locator = (
        f"xpath://button[contains(@class,'xui-pickitem--body')]"
        f"[.//div[normalize-space(.)='{period.fiscal_year_label}']]"
    )
    browser.click_element(financial_year_locator, timeout=5)
    logger.info(f"Selected financial year: '{period.fiscal_year_label}'")

    # Select the period itself within the chosen year (e.g. "September 2024").
    statement_locator = (
        f"xpath://button[contains(@class,'xui-pickitem--body')]"
        f"[.//div[normalize-space(.)='{period}']]"
    )
    browser.click_element(statement_locator, timeout=5)
    logger.info(f"Successfully selected statement period: '{period}'")

    # Navigate to the Transactions tab to view statement details
    logger.info("Navigating to the 'Transactions' tab...")
    browser.click_element(
        "xpath://button[.//span[normalize-space()='Transactions']]",
        timeout=5,
    )
    logger.info("Clicked 'Transactions' tab - Statement details are now visible")


def run_report_export(browser, request: ActivityStatementRequest) -> None:
    """
    Export the Activity Statement report as an Excel file and save it.

    Clicks Export, picks the Excel format, confirms, then handles the Chrome
    save dialog to write the file to the request's destination path.

    Args:
        browser: SeleniumBrowser wrapper instance.
        request (ActivityStatementRequest): Supplies window title and dest path.

    Returns:
        None
    """

    logger.info("Locating 'Export' button on the report page...")
    export_btn_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Export']"
    )

    if not browser.does_page_contain_element(export_btn_locator, timeout=5):
  		raise RuntimeError("'Export' button not found - cannot export report")

    browser.click_element(export_btn_locator, timeout=5)
    logger.info("Clicked 'Export' button - Export options panel is now open")

    # Choose Excel as the export format
    logger.info("Selecting Excel format for the report export...")
    browser.click_element(
        "xpath://label[@data-automationid='bas-excel-radio-button']",
        timeout=5,
    )
    logger.info("Selected 'Excel' radio button as the export format")

    # Confirm the export - triggers the browser's download/save dialog
    logger.info("Confirming export by clicking the final 'Export' button...")
    browser.click_element(
        "xpath://button[@type='button' and @data-automationid='bas-export-button' "
        "and normalize-space(text())='Export']",
        timeout=5,
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