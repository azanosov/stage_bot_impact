from __future__ import annotations

import logging
import time
from datetime import datetime

from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Logger setup
logger = logging.getLogger("IARPA." + __name__)
logging.basicConfig(level=logging.INFO)


module_name = "IA_Libraries_Legacy_Apps_Xero.XEROBlueGetbankRecBankAccounts"
search_bank_account_xpath = "//input[@data-automationid='Bank Account-selector-autocompleter--input' and @aria-label='Search for bank account']"


def xero_blue_download_get_bank_reconciliation_account_report(
    browser,
    client_name,
    bank_account,
    download_directory,
    report_file_name,
    max_retries,
):
    """Xero blue download bank reconciliation account reports"""
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE GET BANK RECONCILIATION ACCOUNTS")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name: {client_name}")
    logger.info(f"Bank Account: {bank_account if bank_account else 'All Accounts'}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info("=" * 80)

    try:
        bank_account_details(
            browser,
            client_name,
            bank_account,
            download_directory,
            report_file_name,
            max_retries,
        )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(
            f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE GET BANK RECONCILIATION ACCOUNTS",
        )
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {client_name}")
        # logger.info(f"Bank Accounts Retrieved: {len(out_lst_BankAccounts) if out_lst_BankAccounts else 0}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        # return out_lst_BankAccounts

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE GET BANK RECONCILIATION ACCOUNTS")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(
            f"xero_blue_download_get_bank_reconciliation_account_report failed due to {e}",
            exc_info=True,
        )
        return None


def bank_account_details(
    browser,
    client_name,
    bank_account,
    download_directory,
    report_file_name,
    max_retries,
):
    """Provide bank account details and dates"""
    driver = browser.driver

    try:
        # Wait for and click search bank account input
        search_input = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, search_bank_account_xpath)),
        )
        safe_click(driver, search_input, "Search bank account input")
        logger.info("Clicked Search bank account input")

        # Check if there are no bank accounts

        if not has_no_bank_accounts(browser):
            select_bank_account(browser, max_retries)
            accounts = get_bank_account(browser)
            return accounts
        else:
            logger.info(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} : {module_name} : Found No Bank Accounts for {client_name} to Download",
            )
            logger.warning("No bank accounts available")
            return []

    except Exception as e:
        logger.error(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {module_name}: "
            f"Error while Getting Bank Reconciliation Bank Accounts\n{str(e)}",
        )
        raise


def select_bank_account(browser, max_retries):
    """Retry to open bank account dropdown with multiple attempts"""
    driver = browser.driver

    dropdown_panel_xpath = "//div[@class='xui-dropdown--panel' and @data-automationid='Bank Account-selector-autocompleter--list']"
    listbox_xpath = "//ul[@role='listbox' and @class='xui-picklist xui-picklist-layout xui-picklist-medium']"

    attempt = 1
    wait = 2

    while attempt <= max_retries:
        try:
            logger.info(
                f"Attempt {attempt} of {max_retries} to open bank account dropdown",
            )

            # Wait for and click search input
            search_input = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, search_bank_account_xpath)),
            )
            safe_click(driver, search_input, "Search bank account input")
            logger.info("Clicked Search bank account input")

            time.sleep(1)

            # Check if dropdown opened
            try:
                dropdown_present = (
                    len(driver.find_elements(By.XPATH, dropdown_panel_xpath)) > 0
                    or len(driver.find_elements(By.XPATH, listbox_xpath)) > 0
                )

                if dropdown_present:
                    logger.info(
                        f"Bank account dropdown opened successfully on attempt {attempt}",
                    )
                    return True
                else:
                    logger.warning(f"Dropdown not found on attempt {attempt}")

            except Exception:
                logger.warning(f"Dropdown not found on attempt {attempt}")

        except Exception as e:
            logger.error(f"Error on attempt {attempt}: {str(e)}")

        # Retry logic
        if attempt < max_retries:
            logger.info(f"Waiting {wait} seconds before retry...")
            time.sleep(wait)

            # Try to close any open dialogs by pressing ESCAPE
            try:

                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.5)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Could not send ESCAPE key to close dialog: {e}")

        attempt += 1

    logger.error(f"Failed to open bank account dropdown after {max_retries} attempts")
    return False


def get_bank_account(browser):
    """
    Get all available bank accounts from the dropdown list.
    Returns a list of account names
    """
    driver = browser.driver
    accounts = []

    try:
        # XPath for all list items in the bank account dropdown
        account_items_xpath = "//ul[@role='listbox']//li"

        # Find all elements
        elements = driver.find_elements(By.XPATH, account_items_xpath)

        for el in elements:
            # Pick text from aria-label or innerText
            name = el.get_attribute("aria-label") or el.text
            if name:
                accounts.append(name.strip())

        logger.info(f"Found {len(accounts)} Bank Accounts to Download")

    except Exception as e:
        logger.error(f"Failed to get bank accounts: {e}")

    return accounts


def has_no_bank_accounts(browser) -> bool:
    """Check if there are no bank accounts available"""
    driver = browser.driver

    try:
        # Check for "No Bank Account" indicator
        no_bank_account_xpath = (
            "//input[@aria-role='combobox' and @aria-label='No Bank Account']"
        )
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, no_bank_account_xpath)),
        )
        logger.info("No bank accounts detected")
        return True

    except (TimeoutException, Exception):
        logger.info("Bank accounts are exist")
        return False
