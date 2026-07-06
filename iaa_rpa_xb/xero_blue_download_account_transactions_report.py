from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By

from . import selenium_helper as helper
from .download_file import generate_and_export_report

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_account_transactions_report(
    browser: Any,
    client_name: str,
    xero_start_date: str | None,
    xero_end_date: str | None,
    xero_financial_year: str,
    window_title: str,
    download_directory_path: str,
    xero_report_file_name: str,
    extension: list[str],
    accounts: list[str] | None,
) -> None:
    """
    Download Account Transactions report from Xero Blue with optional account filtering.

    This function orchestrates the complete workflow to download an Account Transactions report
    from Xero, including configuring the date range, selecting specific accounts to filter by,
    generating the report, and exporting it as an Excel file to a specified directory.

    Args:
        browser: Browser instance containing the Selenium WebDriver with an active Xero session.
        client_name (str): Name of the Xero client/organization for logging purposes.
        xero_start_date (str | None): Start date for the report in format "DD Mon YYYY"
            (e.g., "01 Jul 2023"). If None or empty, defaults to financial year start
            (1 Jul of xero_financial_year - 1).
        xero_end_date (str | None): End date for the report in format "DD Mon YYYY"
            (e.g., "30 Jun 2024"). If None or empty, defaults to financial year end
            (30 Jun of xero_financial_year).
        xero_financial_year (str): Financial year for the report (e.g., "2024").
            Used as fallback when xero_start_date or xero_end_date is not provided.
        window_title (str): Title of the browser window, used to locate the save dialog.
        download_directory_path (str): Absolute path to the directory where the file will be saved.
        xero_report_file_name (str): Desired filename for the downloaded report (without extension).
        extension (list[str]): File formats to export. Accepted values: ".xlsx", ".pdf".
            Defaults to [".xlsx"] if None or empty. Pass [".xlsx", ".pdf"] to export both formats.
        accounts (list[str] | None): List of account names to filter the report by
            (e.g., ["Sales", "Bank Fees"]). Each account name is typed into the accounts
            search field and selected from the dropdown. Pass None or empty list to include
            all accounts (no filter applied).

    Returns:
        None: The function saves the report file to disk and logs the operation status.

    Raises:
        Exception: If any step in the download workflow fails (element not found, timeout,
            no data available, file save error, etc.). All exceptions are logged with
            detailed error information before being re-raised.

    Example:
        >>> xero_blue_download_account_transactions_report(
        ...     browser=my_browser,
        ...     client_name="ABC Company",
        ...     xero_start_date="01 Jul 2023",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     window_title="Account Transactions - Xero",
        ...     download_directory_path="C:/Reports",
        ...     xero_report_file_name="account_transactions_2024",
        ...     extension=[".xlsx"],
        ...     accounts=["Sales", "Bank Fees"],
        ... )
    """
    start_time = datetime.now()

    logger.info("STARTING: xero_blue_download_account_transactions_report")
    logger.info(json.dumps({
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "client_name": client_name,
        "xero_start_date": xero_start_date,
        "xero_end_date": xero_end_date,
        "xero_financial_year": xero_financial_year,
        "window_title": window_title,
        "download_directory_path": download_directory_path,
        "xero_report_file_name": xero_report_file_name,
        "extension": extension,
        "accounts": accounts,
    }, indent=2))

    try:
        driver = browser.driver

        # STEP 1: Set Report Date Range
        logger.info("STEP 1: Configuring report date range...")
        str_start_date, str_end_date = resolve_report_dates(xero_start_date, xero_end_date, xero_financial_year)
        configure_report_dates(driver, str_start_date, str_end_date)

        # STEP 2: Configure Account Filter (if specified)
        # Purpose: Select specific accounts to filter the report by using the accounts search input.
        # Function: configure_accounts(driver, accounts)
        # - For each account in accounts, types the name into the search field and selects
        #   the matching option from the dropdown.
        # - Pass None or empty list to skip filtering (all accounts included).
        logger.info(f"STEP 2: Configuring account filter: {accounts}...")
        configure_accounts(driver, accounts)
      

        # STEP 3: Generate Report and Export
        # Purpose: Trigger report generation, verify data exists, export in requested formats, and save files
        # Function: generate_and_export_report(driver, window_title, download_directory_path, xero_report_file_name, extension)
        # - Clicks Update button to generate the report with configured settings
        # - Verifies Export button is present (confirms report has data)
        # - For each requested extension, clicks Export, selects the format, and saves the file
        logger.info("STEP 3: Generating report and exporting...")
        screenshot_file_path = generate_and_export_report(
            driver,
            window_title,
            download_directory_path,
            xero_report_file_name,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("COMPLETED: Xero Blue Download Account Transactions Report")
        logger.info(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {client_name}")
        logger.info(f"Report File Name  : {xero_report_file_name}")
        logger.info(f"Screenshot Path   : {screenshot_file_path}")
        logger.info(f"Status            : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error("FAILED: Xero Blue Download Account Transactions Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {client_name}")
        logger.error(f"Report File Name  : {xero_report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error("xero_blue_download_account_transactions_report failed", exc_info=True)
        raise


def resolve_report_dates(xero_start_date: str | None, xero_end_date: str | None, xero_financial_year: str) -> tuple[str, str]:
    """
    Determine and format the start and end dates for the Account Transactions report.

    Decides which dates to use based on whether custom dates are provided.
    If no custom start date is given, defaults to 1 July of the prior financial year.
    If no custom end date is given, defaults to 30 June of the financial year.

    Args:
        xero_start_date (str | None): Custom start date in format "DD Mon YYYY"
            (e.g., "01 Jul 2023"). If None or empty, uses the financial year default.
        xero_end_date (str | None): Custom end date in format "DD Mon YYYY"
            (e.g., "30 Jun 2024"). If None or empty, uses the financial year default.
        xero_financial_year (str): Financial year (e.g., "2024") used to construct
            default dates when custom dates are not provided.

    Returns:
        tuple[str, str]: Formatted (start_date, end_date) strings in "DD Mon YYYY" format.

    Example:
        >>> resolve_report_dates(None, None, "2024")
        ("01 Jul 2023", "30 Jun 2024")
        >>> resolve_report_dates("01 Jan 2024", "30 Jun 2024", "2024")
        ("01 Jan 2024", "30 Jun 2024")
    """
    prior_year = str(int(xero_financial_year) - 1)

    if not xero_start_date:
        str_start_date = f"01 Jul {prior_year}"
        logger.info(f"No custom start date provided. Using financial year default: {str_start_date}")
    else:
        str_start_date = xero_start_date
        logger.info(f"Using provided start date: {str_start_date}")

    if not xero_end_date:
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"No custom end date provided. Using financial year default: {str_end_date}")
    else:
        str_end_date = xero_end_date
        logger.info(f"Using provided end date: {str_end_date}")

    return str_start_date, str_end_date


def configure_report_dates(
    driver: Any,
    str_start_date: str,
    str_end_date: str,
) -> None:
    """
    Enter the start and end dates into the Account Transactions date fields.

    Date resolution (raw input → formatted string) is the caller's responsibility via
    resolve_report_dates().

    Args:
        driver: Selenium WebDriver instance for browser automation.
        str_start_date (str): Resolved start date in format "DD Mon YYYY" (e.g., "01 Jul 2023").
        str_end_date (str): Resolved end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").

    Returns:
        None

    Raises:
        TimeoutException: If the date input fields cannot be located within 10 seconds.
    """
    helper.type_into_date_element(driver, "report-settings-custom-date-input-from", str_start_date, by=By.ID)
    helper.type_into_date_element(driver, "report-settings-custom-date-input-to", str_end_date, by=By.ID)


def configure_accounts(driver: Any, accounts: list[str] | None) -> None:
    """
    Select accounts in the Account Transactions report accounts filter.

    Opens the accounts dropdown by clicking the search input, then either:
    - Clicks "Select all" when accounts is None or empty (if the button is visible).
    - For each account name, types it into the search input and selects the result:
        * Exact match: the <li> whose aria-label equals the account name is clicked.
        * No exact match: every visible <li> whose aria-label contains the account name
          is clicked (partial/fuzzy fallback).

    Args:
        driver: Selenium WebDriver instance for browser automation.
        accounts (list[str] | None): Account names to filter by (e.g., ["Sales", "Bank Fees"]).
            Pass None or empty list to select all accounts.

    Returns:
        None

    Raises:
        TimeoutException: If the accounts search input cannot be located within 10 seconds,
            or if no matching dropdown items appear within 5 seconds.
    """
    # Anchored on the stable <label for="Accounts-selector"> — avoids dynamic placeholder/aria-label
    accounts_open_btn_xpath = "//label[@for='Accounts-selector']/..//button[@aria-label='Open']"
    accounts_input_xpath = "//label[@for='Accounts-selector']/..//input[@role='combobox']"
    select_all_xpath = "//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='Select all']]"
    deselect_all_xpath = "//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='Deselect all']]"

    # Verify the accounts filter exists on this page
    if not helper.element_exists(driver, accounts_open_btn_xpath, timeout=5):
        logger.warning("Accounts selector not found on this page — skipping account filter")
        return

    # Open the dropdown via the Open button
    helper.click_element(driver, accounts_open_btn_xpath)

    # Ensure clean state: select all (if not already) then deselect all → nothing selected
    if helper.element_exists(driver, select_all_xpath, timeout=3):
        helper.click_element(driver, select_all_xpath)
        logger.info("Clicked 'Select all' to prepare for full deselection")
    if helper.element_exists(driver, deselect_all_xpath, timeout=3):
        helper.click_element(driver, deselect_all_xpath)
        logger.info("Clicked 'Deselect all' — accounts filter cleared")

    if not accounts:
        if helper.element_exists(driver, select_all_xpath, timeout=5):
            helper.click_element(driver, select_all_xpath, timeout=5)
            logger.info("Clicked 'Select all' for accounts")
        else:
            logger.info("'Select all' button not visible — skipping")
        return

    for account in accounts:
        logger.info(f"Searching for account: '{account}'...")
        # Re-open dropdown and focus input before each search
        helper.click_element(driver, accounts_open_btn_xpath)
        helper.type_into_element(driver, accounts_input_xpath, account)

        literal = helper.format_xpath_selector_text(account)
        exact_xpath = f"//li[@aria-label={literal}]//button[contains(@class,'xui-pickitem--body')]"

        if helper.element_exists(driver, exact_xpath, timeout=5):
            helper.click_element(driver, exact_xpath)
            logger.info(f"Exact match found and selected: '{account}'")
        else:
            logger.info(f"No exact match for '{account}' — selecting all visible items containing text")
            partial_xpath = f"//li[contains(@aria-label,{literal})]//button[contains(@class,'xui-pickitem--body')]"
            items = helper.find_elements(driver, partial_xpath)
            for item in items:
                try:
                    item.click()
                    li_label = item.find_element(By.XPATH, "..").get_attribute("aria-label")
                    logger.info(f"Clicked partial match: '{li_label or account}'")
                except Exception as ex:
                    logger.warning(f"Could not click partial match item for '{account}': {ex}")
