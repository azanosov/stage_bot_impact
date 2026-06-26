"""
Module for downloading Activity Statement reports from Xero Blue.

This module handles the complete workflow for navigating to and downloading
Activity Statement reports from Xero Blue, including handling ATO lodge dialogs
and statement period selection.

Refactored to drive the page through the SeleniumBrowser wrapper
(iaa_rpa_utils.browser.SeleniumBrowser) instead of the raw Selenium driver.
All element interaction goes through the wrapper's locator-string API, e.g.
"xpath://button[...]" / "id:submit" / "css:.foo". No direct driver access is
needed.
"""

from __future__ import annotations

import os
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog


# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_activity_statement_report(
    browser,
    xero_statement_period: str,
    xero_financial_year: str,
    window_title: str,
    xero_download_directory: str,
    xero_report_file_name: str,
    extension: str,
):
    """
    Download Activity Statement report from Xero Blue.

    This function orchestrates the complete process of downloading an Activity Statement
    report from Xero Blue. It handles navigation through ATO lodge dialogs (if present),
    selects the appropriate statement period and financial year, and exports the report
    to the specified directory.

    Args:
        browser: SeleniumBrowser wrapper instance.
        xero_statement_period (str): Statement period to select (e.g., "July 2024 - September 2024").
        xero_financial_year (str): Financial year for the report (e.g., "2024-2025").
        window_title (str): Window title of the download dialog.
        xero_download_directory (str): Directory path where the report will be saved.
        xero_report_file_name (str): Desired filename for the downloaded report.
        extension (str): File extension for the downloaded report (e.g., ".xlsx").

    Returns:
        None

    Raises:
        Exception: If any error occurs during the download process, logs the error and returns.
    """

    # Initialize process timing and logging
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Activity Statement Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Statement Period    : {xero_statement_period}")
    logger.info(f"Financial Year      : {xero_financial_year}")
    logger.info(f"Window Title        : {window_title}")
    logger.info(f"Download Directory  : {xero_download_directory}")
    logger.info(f"Report File Name    : {xero_report_file_name}")
    logger.info(f"Extension           : {extension}")
    logger.info("=" * 80)

    try:

        # STEP 1: Navigate to the Activity Statement Report Page
        # Purpose: Access the Activity Statement report page in Xero Blue
        # Function: navigated_to_activity_statement_report()
        # - Checks if the ATO lodge dialog is present and handles it
        # - Clicks through wizard steps if the dialog appears
        # - Selects the specified statement period and financial year
        logger.info("STEP 1: Navigating to Activity Statement report page...")
        navigated_to_activity_statement_report(
            browser,
            xero_statement_period,
            xero_financial_year,
        )
        logger.info(
            "STEP 1 COMPLETED: Successfully navigated to Activity Statement report page",
        )

        # STEP 2: Export the Activity Statement Report
        # Purpose: Export the report in Excel format and save to the download directory
        # Function: run_report_export()
        # - Clicks the Export button to open export options
        # - Selects Excel format from the export options
        # - Confirms export and triggers the browser download dialog
        # - Handles the save dialog to save the file to the specified directory
        logger.info("STEP 2: Exporting Activity Statement report as Excel file...")
        run_report_export(
            browser,
            window_title,
            xero_download_directory,
            xero_report_file_name,
            extension,
        )
        logger.info("STEP 2 COMPLETED: Successfully exported Activity Statement report")

        # Log completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Download Activity Statement Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration           : {duration:.2f} seconds")
        logger.info(f"Report File Name   : {xero_report_file_name}")
        logger.info(f"Download Directory : {xero_download_directory}")
        logger.info(f"Result             : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Activity Statement Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration : {duration:.2f} seconds")
        logger.error(f"Error    : {str(e)}", exc_info=True)
        logger.error("=" * 80)
        # NOTE: behaviour preserved from original — the error is logged and
        # swallowed (the function returns None rather than re-raising). If the
        # caller needs to know this step failed, change this to `raise`.
        return


def navigated_to_activity_statement_report(
    browser,
    xero_statement_period,
    xero_financial_year,
):
    """
    Navigate to the Activity Statement report page in Xero Blue.

    This function handles the navigation flow to reach the Activity Statement report.
    If the ATO lodge dialog appears, it clicks through the dialog steps to reach
    the statement page. Finally, it selects the appropriate statement period and
    financial year.

    Args:
        browser: SeleniumBrowser wrapper instance.
        xero_statement_period (str): Statement period to select (e.g., "July 2024 - September 2024").
        xero_financial_year (str): Financial year for the report (e.g., "2024-2025").

    Returns:
        None
    """

    lodge_report_locator = (
        "xpath://button[normalize-space(text())='Lodge reports to ATO outside of Xero']"
    )

    # Check if the ATO lodge dialog is displayed
    # This dialog may appear depending on Xero account settings
    logger.info(
        "Checking if 'Lodge reports to ATO outside of Xero' dialog is present...",
    )
    if is_lodge_reports_dialog_present(browser, lodge_report_locator):

        logger.info("ATO lodge dialog detected - proceeding through dialog steps")

        # Click the "Lodge reports to ATO outside of Xero" button to proceed
        browser.click_element(lodge_report_locator, timeout=5)
        logger.info("Clicked 'Lodge reports to ATO outside of Xero' button")

        # Navigate to Activity Statement from the ATO dialog
        browser.click_element(
            "xpath://button[normalize-space(text())='Go to Activity Statement']",
            timeout=5,
        )
        logger.info("Clicked 'Go to Activity Statement' button")

        # Click through the wizard "Next" button (step 1)
        # NOTE: steps 1 and 2 share the same locator. This relies on Xero
        # re-rendering the button between steps. If both Next buttons ever
        # coexist in the DOM, give each step a more specific locator.
        next_button_locator = "xpath://button[normalize-space(text())='Next']"
        browser.click_element(next_button_locator, timeout=5)
        logger.info("Clicked 'Next' button - Step 1 of wizard")

        # Click through the wizard "Next" button (step 2)
        browser.click_element(next_button_locator, timeout=5)
        logger.info("Clicked 'Next' button - Step 2 of wizard")

        # Complete the wizard by clicking "OK" button
        browser.click_element(
            "xpath://button[normalize-space(text())='OK']",
            timeout=5,
        )
        logger.info("Clicked 'OK' button - Wizard completed")

    else:
        logger.info(
            "ATO lodge dialog not present - proceeding directly to statement period selection",
        )

    # Select the desired statement period and financial year
    # This creates a new statement or selects an existing one
    logger.info(
        f"Selecting statement period: '{xero_statement_period}' for financial year: '{xero_financial_year}'",
    )
    select_statement_period(browser, xero_statement_period, xero_financial_year)


def is_lodge_reports_dialog_present(browser, lodge_report_locator) -> bool:
    """
    Check if the 'Lodge reports to ATO outside of Xero' dialog is present on the page.

    Args:
        browser: SeleniumBrowser wrapper instance.
        lodge_report_locator (str): Wrapper locator string for the lodge reports button
            (e.g. "xpath://button[...]").

    Returns:
        bool: True if the lodge dialog button is found within the timeout, False otherwise.

    Note:
        Uses the wrapper's ``does_page_contain_element`` which checks element
        *presence* (in the DOM), whereas the original used *visibility*. For this
        button the two are equivalent in practice; if Xero ever renders a hidden
        copy of the button, switch this to a visibility-based check.
    """
    present = browser.does_page_contain_element(lodge_report_locator, timeout=5)
    if present:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is present")
    else:
        logger.info("'Lodge reports to ATO outside of Xero' dialog is not present")
    return present


def select_statement_period(browser, xero_statement_period, xero_financial_year):
    """
    Select the statement period and navigate to the Transactions tab.

    This function creates a new statement and selects the specified statement period.
    If the period is not present in the default view, it expands the financial year
    selector to find and select the correct period within the specified financial year.

    Args:
        browser: SeleniumBrowser wrapper instance.
        xero_statement_period (str): Statement period to select (e.g., "July 2024 - September 2024").
        xero_financial_year (str): Financial year for the report (e.g., "2024-2025").

    Returns:
        None
    """

    # Initiate the creation of a new activity statement
    browser.click_element(
        "xpath://button[.//span[normalize-space(text())='Create new statement']]",
        timeout=5,
    )
    logger.info("Clicked 'Create new statement' button")

    statement_locator = f"xpath://div[normalize-space(text())='{xero_statement_period}']"

    # Try to select the statement period directly if it is already in the current view.
    # NOTE: this is a presence check (replaces the original try/except on a
    # visibility wait). In Xero's period picker, periods belonging to other
    # financial years are normally not rendered until that year is expanded, so
    # presence here behaves like the original visibility test while keeping the
    # logs quiet on the expected "not in view" path.
    if browser.does_page_contain_element(statement_locator, timeout=5):
        logger.info(
            f"Statement period visible in current view - selecting directly: '{xero_statement_period}'",
        )
        browser.click_element(statement_locator, timeout=5)
        logger.info(
            f"Successfully selected statement period: '{xero_statement_period}'",
        )

    else:
        # Period belongs to a different financial year - expand the year selector.
        logger.info(
            f"Statement period not in current view - expanding financial year selector for: '{xero_financial_year}'",
        )

        # Click dropdown to show all available years.
        # BUG FIX: original XPath "//*[id='panel-select-period']//svg" was missing
        # the '@' before the attribute name (`id` -> `@id`), so it matched a child
        # element literally named "id" instead of the id attribute, and never
        # found the dropdown.
        all_years_locator = "xpath://*[@id='panel-select-period']//svg"
        browser.click_element(all_years_locator, timeout=5)
        logger.info("Clicked financial year dropdown to expand all years")

        # Select the specific financial year from the dropdown.
        # BUG FIX: original XPath "//*['{year}']//div" was invalid — a bare string
        # literal as a predicate is always truthy, so it matched every element.
        # Replaced with a text match on the year.
        # TODO: VERIFY this locator against the live Xero DOM — the exact element
        # that carries the financial-year label may differ.
        financial_year_locator = (
            f"xpath://div[normalize-space(text())='{xero_financial_year}']"
        )
        browser.click_element(financial_year_locator, timeout=5)
        logger.info(f"Selected financial year: '{xero_financial_year}'")

        # Now select the statement period within the chosen financial year
        browser.click_element(statement_locator, timeout=5)
        logger.info(
            f"Successfully selected statement period: '{xero_statement_period}'",
        )

    # Navigate to the Transactions tab to view statement details
    logger.info("Navigating to the 'Transactions' tab...")
    browser.click_element(
        "xpath://button[.//span[normalize-space()='Transactions']]",
        timeout=5,
    )
    logger.info("Clicked 'Transactions' tab - Statement details are now visible")


def run_report_export(
    browser,
    window_title,
    xero_download_directory,
    xero_report_file_name,
    extension,
):
    """
    Export the Activity Statement report as an Excel file.

    This function handles the full export process by clicking the Export button,
    selecting Excel format from the export options, and triggering the file download.
    It then uses the download file utility to handle the save dialog and save the
    file to the specified directory with the given filename.

    Args:
        browser: SeleniumBrowser wrapper instance.
        window_title (str): Window title of the browser download dialog.
        xero_download_directory (str): Directory path where the report will be saved.
        xero_report_file_name (str): Desired filename for the downloaded report.
        extension (str): File extension for the downloaded report (e.g., ".xlsx").

    Returns:
        None
    """

    # Locate the Export button to open export options
    logger.info("Locating 'Export' button on the report page...")
    export_btn_locator = (
        "xpath://button[@type='button' and normalize-space(text())='Export']"
    )

    if browser.does_page_contain_element(export_btn_locator, timeout=5):
        # Click the Export button (wrapper clicks the first match)
        browser.click_element(export_btn_locator, timeout=5)
        logger.info("Clicked 'Export' button - Export options panel is now open")

        # Select Excel format from the export options
        # This ensures the report is downloaded in .xlsx format
        logger.info("Selecting Excel format for the report export...")
        browser.click_element(
            "xpath://label[@data-automationid='bas-excel-radio-button']",
            timeout=5,
        )
        logger.info("Selected 'Excel' radio button as the export format")

        # Confirm the export by clicking the final Export button
        # This triggers the browser's download/save dialog
        logger.info("Confirming export by clicking the final 'Export' button...")
        browser.click_element(
            "xpath://button[@type='button' and @data-automationid='bas-export-button' and normalize-space(text())='Export']",
            timeout=5,
        )
        logger.info("Clicked final 'Export' button - File download dialog triggered")

        # Handle the file save dialog and save to the specified directory
        dest_path = os.path.join(
            xero_download_directory, f"{xero_report_file_name}{extension}"
        )
        logger.info(
            f"Handling file save dialog - saving to: '{dest_path}'",
        )
        handle_chrome_save_as_dialog(
            window_locator=f"regex:.*{window_title}.* - Google Chrome",
            dest_path=dest_path,
        )
        logger.info(
            f"File successfully saved: '{xero_report_file_name}{extension}' in '{xero_download_directory}'",
        )

    else:
        logger.warning(
            "'Export' button was not found on the page - skipping export step",
        )