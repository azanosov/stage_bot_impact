from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from . import selenium_helper as helper
from .download_file import generate_and_export_report

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_bank_reconciliation_report(
    browser: Any,
    client_name: str,
    xero_end_date: str | None,
    xero_financial_year: str,
    xero_start_date: str | None,
    xero_bank_account: str,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    xero_report_name: str,
    is_no_bank_accounts: bool,
    extension: list[str],
) -> list[str]:
    """
    Download Bank Reconciliation report from Xero Blue.

    Orchestrates the complete workflow for downloading a Bank Reconciliation report from
    Xero Blue. This includes checking if bank accounts exist, determining the appropriate
    date range (custom or default financial year), configuring the bank account selection,
    updating the report with these settings, and exporting it to the specified format via
    automated Windows Save As dialog handling.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for interacting
            with the Xero web application.
        client_name (str): Name of the client organization for logging and audit trail purposes.
        xero_end_date (str): Report end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty string, defaults to '30 Jun {xero_financial_year}'.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            calculate default date range (1 Jul previous year to 30 Jun current year).
        xero_start_date (str): Report start date in 'DD MMM YYYY' format (e.g., '1 Jul 2023').
            If empty string, defaults to '1 Jul {xero_financial_year - 1}'.
        xero_bank_account (str): Name of the bank account to reconcile (e.g., 'Business Cheque Account').
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Absolute or relative directory path where the report file will be saved.
        report_file_name (str): Filename for the saved report (without extension).
        xero_report_name (str): Display name of the report as shown in the Xero UI.
        is_no_bank_accounts (bool): Flag indicating whether the organization has no bank
            accounts configured in Xero.
        extension (list[str]): File extensions for the exported report (e.g., ['.xlsx']).

    Returns:
        list[str]: Absolute paths of all downloaded files (one per extension per account).

    Raises:
        Exception: If any step in the workflow fails.
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"STARTING: Xero Blue - Download Bank Reconciliation Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name: {client_name}")
    logger.info(f"Bank Account: {xero_bank_account}")
    logger.info(f"Start Date: {xero_start_date if xero_start_date else f'1 Jul {int(xero_financial_year) - 1}'}")
    logger.info(f"End Date: {xero_end_date if xero_end_date else f'30 Jun {xero_financial_year}'}")
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report Name in Xero: {xero_report_name}")
    logger.info(f"Has No Bank Accounts (initial): {is_no_bank_accounts}")
    logger.info("=" * 80)

    try:
        downloaded_files = configure_bank_account_and_date_range(
            browser,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
            xero_bank_account,
            window_title,
            download_directory,
            report_file_name,
            is_no_bank_accounts,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(f"COMPLETED: Xero Blue - Download Bank Reconciliation Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Bank Account: {xero_bank_account or 'all accounts'}")
        logger.info(f"Downloaded Files: {downloaded_files}")
        logger.info(f"Download Directory: {download_directory}")
        logger.info("=" * 80)
        return downloaded_files

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(f"FAILED: Xero Blue - Download Bank Reconciliation Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Bank Account: {xero_bank_account or 'all accounts'}")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def configure_bank_account_and_date_range(
    browser: Any,
    xero_end_date: str | None,
    xero_financial_year: str,
    xero_start_date: str | None,
    xero_bank_account: str,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    is_no_bank_accounts: bool,
    extension: list[str],
) -> list[str]:
    """
    Configure bank account selection and date range, then generate and export the report.

    When xero_bank_account is provided, exports once for that account.
    When xero_bank_account is empty, retrieves all available accounts from the dropdown
    and exports a separate report for each, appending the account name to report_file_name.

    Args:
        browser: Browser instance with an active Selenium WebDriver on the Bank Reconciliation page.
        xero_end_date (str): Report end date in 'DD MMM YYYY' format. If empty, defaults to financial year end.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024').
        xero_start_date (str): Report start date in 'DD MMM YYYY' format. If empty, defaults to financial year start.
        xero_bank_account (str): Name of the bank account to select. Empty string to process all accounts.
        window_title (str): Browser window title used to locate the Save As dialog.
        download_directory (str): Target directory path for the exported file.
        report_file_name (str): Output filename without extension.
        is_no_bank_accounts (bool): Initial flag for bank account availability, updated by validation.
        extension (list[str]): File extensions for the exported report (e.g., ['.xlsx']).

    Returns:
        list[str]: Absolute paths of all downloaded files.
    """
    driver = browser.driver
    search_bank_account_xpath = "//input[@aria-haspopup='listbox' and @role='combobox']"

    # STEP 1: Open Bank Account Search Field
    logger.info("Clicking bank account search field to open dropdown...")
    helper.click_element(driver, search_bank_account_xpath)
    logger.info("Bank account search field clicked successfully")

    # STEP 2: Validate Bank Account Availability
    logger.info("Validating bank account availability...")
    is_no_bank_accounts = has_no_bank_accounts(browser)
    logger.info(f"Bank account availability check result — No bank accounts: {is_no_bank_accounts}")

    if is_no_bank_accounts:
        return []

    # STEP 3: Resolve Report Date Range
    logger.info("Resolving report date range...")
    str_start_date, str_end_date = resolve_report_date_range(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )
    logger.info(f"Resolved Start Date: {str_start_date}")
    logger.info(f"Resolved End Date: {str_end_date}")

    # STEP 4: Enter Start Date
    logger.info(f"Entering start date: {str_start_date}")
    helper.type_into_date_element(driver, "report-settings-custom-date-input-from", str_start_date, by=By.ID)
    logger.info(f"Start date entered successfully: {str_start_date}")

    # STEP 5: Enter End Date
    logger.info(f"Entering end date: {str_end_date}")
    helper.type_into_date_element(driver, "report-settings-custom-date-input-to", str_end_date, by=By.ID)
    logger.info(f"End date entered successfully: {str_end_date}")

    # STEP 6: Determine which bank accounts to process
    if not xero_bank_account:
        logger.info("No bank account specified — retrieving all available bank accounts...")
        helper.click_element(driver, search_bank_account_xpath)
        bank_accounts = get_all_bank_accounts(driver)
        logger.info(f"Found {len(bank_accounts)} bank accounts to process: {bank_accounts}")
    else:
        bank_accounts = [xero_bank_account]
        logger.info(f"Processing single bank account: {xero_bank_account}")

    # STEP 7 & 8: Loop — select each account, generate and export report
    downloaded_files: list[str] = []
    for account in bank_accounts:
        logger.info(f"Processing bank account: {account}")

        # Click to exit readonly mode (clears current selection), then type to filter
        helper.click_element(driver, search_bank_account_xpath)
        helper.type_into_element(driver, search_bank_account_xpath, account, timeout=30)

        # Select bank account from dropdown
        safe_label = helper.format_xpath_selector_text(account)
        account_button_xpath = f"//ul[@role='listbox']//li[@aria-label={safe_label}]//button[@type='button']"
        logger.info(f"Selecting bank account from dropdown: {account}")
        helper.click_element(driver, account_button_xpath)
        logger.info(f"Bank account selected: {account}")

        # Append sanitised account name to file name when processing all accounts
        if not xero_bank_account:
            safe_name = re.sub(r'[\\/*?:"<>|]', '_', account).strip()
            file_name = f"{report_file_name}_{safe_name}"
        else:
            file_name = report_file_name

        # Generate and export report
        logger.info(f"Generating and exporting report as '{file_name}'...")
        generate_and_export_report(
            driver,
            window_title,
            download_directory,
            file_name,
            extension,
            take_screenshot_flag=False,
        )
        logger.info(f"Report exported successfully: {file_name}")

        for ext in extension:
            downloaded_files.append(os.path.join(download_directory, file_name + ext))

    return downloaded_files


def get_all_bank_accounts(driver: Any) -> list[str]:
    """Return all bank account names visible in the open dropdown listbox."""
    list_item_xpath = "//ul[@role='listbox']//li[@aria-label]"
    elements = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, list_item_xpath))
    )
    accounts = [el.get_attribute("aria-label") for el in elements if el.get_attribute("aria-label")]
    logger.info(f"Retrieved {len(accounts)} bank accounts from dropdown: {accounts}")
    return accounts


def has_no_bank_accounts(browser: Any) -> bool:
    """
    Verify if the organisation has no bank accounts configured in Xero.

    Args:
        browser: Browser instance containing an active Selenium WebDriver.

    Returns:
        bool: True if no bank accounts are configured, False if bank accounts exist.
    """
    driver = browser.driver
    try:
        no_bank_account_xpath = (
            "//input[@aria-role='combobox' and @aria-label='No Bank Account']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, no_bank_account_xpath)),
        )
        logger.info("Validation result: No bank accounts are configured for this organisation")
        return True

    except Exception:
        logger.info("Validation result: Bank accounts exist for this organisation — proceeding with configuration")
        return False


def resolve_report_date_range(xero_end_date: str | None, xero_financial_year: str, xero_start_date: str | None) -> tuple[str, str]:
    """
    Determine the report date range based on input parameters.

    Returns custom dates if both are provided, otherwise defaults to the full financial year
    (1 Jul previous year to 30 Jun current year).

    Args:
        xero_end_date (str): Custom end date in 'DD MMM YYYY' format, or empty/None for default.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024').
        xero_start_date (str): Custom start date in 'DD MMM YYYY' format, or empty/None for default.

    Returns:
        tuple[str, str]: (str_start_date, str_end_date) in 'DD MMM YYYY' format.
    """
    if not xero_end_date or not xero_start_date:
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"No custom dates provided — using default financial year range: {str_start_date} to {str_end_date}")
    else:
        str_start_date = xero_start_date
        str_end_date = xero_end_date
        logger.info(f"Custom dates provided — using input date range: {str_start_date} to {str_end_date}")

    return str_start_date, str_end_date


