"""
Module for downloading Activity Statement reports from Xero Blue.

This module handles the complete workflow for navigating to and downloading
Activity Statement reports from Xero Blue, including handling ATO lodge dialogs
and statement period selection.
"""

from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file


# Set up logger
logger = setup_logger(__name__)

# Arguments

"""
window_title = Aged Payables Detail
"""


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
        browser: The browser instance with Selenium driver.
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

    driver = browser.driver
    try:

        # STEP 1: Navigate to the Activity Statement Report Page
        # Purpose: Access the Activity Statement report page in Xero Blue
        # Function: navigated_to_activity_statement_report()
        # - Checks if the ATO lodge dialog is present and handles it
        # - Clicks through wizard steps if the dialog appears
        # - Selects the specified statement period and financial year
        logger.info("STEP 1: Navigating to Activity Statement report page...")
        navigated_to_activity_statement_report(
            driver,
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
            driver,
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
        return


def navigated_to_activity_statement_report(
    driver,
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
        driver: Selenium WebDriver instance.
        xero_statement_period (str): Statement period to select (e.g., "July 2024 - September 2024").
        xero_financial_year (str): Financial year for the report (e.g., "2024-2025").

    Returns:
        None
    """

    lodge_reporpt_xpath = (
        "//button[normalize-space(text())='Lodge reports to ATO outside of Xero']"
    )

    # Check if the ATO lodge dialog is displayed
    # This dialog may appear depending on Xero account settings
    logger.info(
        "Checking if 'Lodge reports to ATO outside of Xero' dialog is present...",
    )
    if is_lodge_reports_dialog_present(driver, lodge_reporpt_xpath):

        logger.info("ATO lodge dialog detected - proceeding through dialog steps")

        # Click the "Lodge reports to ATO outside of Xero" button to proceed
        driver.find_element(By.XPATH, lodge_reporpt_xpath).click()
        logger.info("Clicked 'Lodge reports to ATO outside of Xero' button")

        # Navigate to Activity Statement from the ATO dialog
        activity_statement_xpath = (
            "//button[normalize-space(text())='Go to Activity Statement']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, activity_statement_xpath)),
        ).click()
        logger.info("Clicked 'Go to Activity Statement' button")

        # Click through the wizard "Next" button (step 1)
        next_button_xpath = "//button[normalize-space(text())='Next']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, next_button_xpath)),
        ).click()
        logger.info("Clicked 'Next' button - Step 1 of wizard")

        # Click through the wizard "Next" button (step 2)
        next_button_xpath = "//button[normalize-space(text())='Next']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, next_button_xpath)),
        ).click()
        logger.info("Clicked 'Next' button - Step 2 of wizard")

        # Complete the wizard by clicking "OK" button
        ok_button_xpath = "//button[normalize-space(text())='OK']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ok_button_xpath)),
        ).click()
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
    select_statement_period(driver, xero_statement_period, xero_financial_year)


def is_lodge_reports_dialog_present(driver, lodge_reporpt_xpath) -> bool:
    """
    Check if the 'Lodge reports to ATO outside of Xero' dialog is present on the page.

    This function attempts to locate the ATO lodge dialog button on the page.
    The presence of this dialog varies based on account settings and previous interactions.

    Args:
        driver: Selenium WebDriver instance.
        lodge_reporpt_xpath (str): XPath selector for the lodge reports button.

    Returns:
        bool: True if the lodge dialog button is found and visible, False otherwise.
    """
    try:
        # Wait up to 5 seconds for the lodge reports button to appear
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, lodge_reporpt_xpath)),
        )
        logger.info("'Lodge reports to ATO outside of Xero' dialog is present")
        return True

    except Exception:
        # If element is not found within timeout, the dialog is not present
        logger.info("'Lodge reports to ATO outside of Xero' dialog is not present")
        return False


def select_statement_period(driver, xero_statement_period, xero_financial_year):
    """
    Select the statement period and navigate to the Transactions tab.

    This function creates a new statement and selects the specified statement period.
    If the period is not visible in the default view, it expands the financial year
    selector to find and select the correct period within the specified financial year.

    Args:
        driver: Selenium WebDriver instance.
        xero_statement_period (str): Statement period to select (e.g., "July 2024 - September 2024").
        xero_financial_year (str): Financial year for the report (e.g., "2024-2025").

    Returns:
        None
    """

    # Initiate the creation of a new activity statement
    create_new_statement_xpath = (
        "//button[.//span[normalize-space(text())='Create new statement']]"
    )
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, create_new_statement_xpath)),
    ).click()
    logger.info("Clicked 'Create new statement' button")

    try:
        # Attempt to select the statement period directly if visible in the current view
        logger.info(
            f"Attempting to select statement period directly: '{xero_statement_period}'",
        )
        statement_xpath = f"//div[normalize-space(text())='{xero_statement_period}']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, statement_xpath)),
        ).click()
        logger.info(
            f"Successfully selected statement period: '{xero_statement_period}'",
        )

    except Exception:
        # If statement period is not visible, expand the year selector
        # This happens when the period belongs to a different financial year
        logger.info(
            f"Statement period not visible in current view - expanding financial year selector for: '{xero_financial_year}'",
        )

        # Click dropdown to show all available years
        all_year = "//*[id='panel-select-period']//svg"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, all_year)),
        ).click()
        logger.info("Clicked financial year dropdown to expand all years")

        # Select the specific financial year from the dropdown
        financial_year_xpath = f"//*['{xero_financial_year}']//div"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, financial_year_xpath)),
        ).click()
        logger.info(f"Selected financial year: '{xero_financial_year}'")

        # Now select the statement period within the chosen financial year
        statement_xpath = f"//div[normalize-space(text())='{xero_statement_period}']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, statement_xpath)),
        ).click()
        logger.info(
            f"Successfully selected statement period: '{xero_statement_period}'",
        )

    # Navigate to the Transactions tab to view statement details
    logger.info("Navigating to the 'Transactions' tab...")
    transaction_xpath = "//button[.//span[normalize-space()='Transactions']]"
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, transaction_xpath)),
    ).click()
    logger.info("Clicked 'Transactions' tab - Statement details are now visible")


def run_report_export(
    driver,
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
        driver: Selenium WebDriver instance.
        window_title (str): Window title of the browser download dialog.
        xero_download_directory (str): Directory path where the report will be saved.
        xero_report_file_name (str): Desired filename for the downloaded report.
        extension (str): File extension for the downloaded report (e.g., ".xlsx").

    Returns:
        None
    """

    # Locate and click the Export button to open export options
    logger.info("Locating 'Export' button on the report page...")
    export_btn_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    export_btn_ele = WebDriverWait(driver, 5).until(
        EC.presence_of_all_elements_located((By.XPATH, export_btn_xpath)),
    )

    if export_btn_ele:
        # Click the first Export button found (handles multiple matches)
        export_btn_ele[0].click()
        logger.info("Clicked 'Export' button - Export options panel is now open")

        # Select Excel format from the export options
        # This ensures the report is downloaded in .xlsx format
        logger.info("Selecting Excel format for the report export...")
        radio_excel_xpath = "//label[@data-automationid='bas-excel-radio-button']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, radio_excel_xpath)),
        ).click()
        logger.info("Selected 'Excel' radio button as the export format")

        # Confirm the export by clicking the final Export button
        # This triggers the browser's download/save dialog
        logger.info("Confirming export by clicking the final 'Export' button...")
        save_export_btn = "//button[@type='button' and @data-automationid='bas-export-button' and normalize-space(text())='Export']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, save_export_btn)),
        ).click()
        logger.info("Clicked final 'Export' button - File download dialog triggered")

        # Handle the file save dialog and save to the specified directory
        logger.info(
            f"Handling file save dialog - saving to: '{xero_download_directory}' as '{xero_report_file_name}{extension}'",
        )
        download_file(
            window_title,
            xero_download_directory,
            xero_report_file_name,
            extension,
        )
        logger.info(
            f"File successfully saved: '{xero_report_file_name}{extension}' in '{xero_download_directory}'",
        )

    else:
        logger.warning(
            "'Export' button was not found on the page - skipping export step",
        )
