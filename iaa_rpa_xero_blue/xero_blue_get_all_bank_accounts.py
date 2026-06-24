from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# Set up logger
logger = setup_logger(__name__)


def xero_blue_get_all_bank_accounts(
    browser,
    xero_url,
):
    """
    Extract all bank account data from a Xero Blue data table.

    This function automates the process of extracting bank account information from Xero's
    data table interface. It navigates to the correct browser tab containing the Xero page,
    locates the data table, and extracts all rows of bank account data. The function handles
    paginated tables by automatically clicking through multiple pages until all data is retrieved.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.
        xero_url (str): URL substring to identify the correct Xero tab/page containing the
                       bank accounts table.

    Returns:
        list: List of lists containing bank account data, where each inner list represents
              one row from the table with cells as list elements. Returns empty list if
              no data is found or extraction fails.

    Raises:
        Exception: If the Xero page cannot be found or extraction fails.

    Notes:
        - UiPath selector: <webctrl tag='MAIN' /> translates to //main//table
        - Pagination handled automatically with "Next" button detection
        - All operations include comprehensive logging

    Example:
        >>> data = xero_blue_get_all_bank_accounts(browser, "xero.com/banking")
        >>> print(f"Extracted {len(data)} bank accounts")
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE GET ALL BANK ACCOUNTS")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Target URL Pattern: {xero_url}")
    logger.info("=" * 80)

    driver = browser.driver
    all_data = []

    try:
        # Get all open browser tabs to find the Xero page
        all_tabs = driver.window_handles
        logger.info(f"Found {len(all_tabs)} browser tab(s)")

        # Flag to track if we found the correct tab
        tab_found = False

        # Iterate through all tabs to find the one matching xero_url
        for handle in all_tabs:
            driver.switch_to.window(handle)
            current_url = driver.current_url
            logger.info(f"Checking tab: {current_url}")

            # Check if this tab contains the Xero page
            if xero_url in current_url:
                logger.info(f"Found matching Xero tab: {current_url}")
                tab_found = True

                # Extract data from the table on this page
                all_data = extract_data_table(driver)
                break

        # If no matching tab was found, log error and raise exception
        if not tab_found:
            error_msg = f"No browser tab found containing URL pattern: {xero_url}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE GET ALL BANK ACCOUNTS")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Total Rows Extracted: {len(all_data)}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        return all_data

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE GET ALL BANK ACCOUNTS")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Target URL Pattern: {xero_url}")
        logger.error(f"Rows Extracted Before Error: {len(all_data)}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(
            f"xero_blue_get_all_bank_accounts failed due to {e}",
            exc_info=True,
        )
        return []


def extract_data_table(driver):
    """
    Extract all data rows from a multi-page Xero data table using structured data extraction.

    This function handles the complete extraction process for paginated data in Xero using
    UiPath-style column-based extraction with nested div elements. It extracts data from
    structured div containers and automatically navigates through pagination.

    The extraction uses the following UiPath selector pattern:
    <extract>
        <column exact='1' name='Column0' attr='fulltext'>
            <webctrl tag='div' idx='4' />
            <webctrl tag='div' idx='1' />
            <webctrl tag='div' />
            <webctrl tag='div' idx='1' />
            ... (multiple nested divs)
        </column>
    </extract>

    Args:
        driver: Selenium WebDriver instance with the page containing the data table loaded

    Returns:
        list: List of lists containing all extracted data across all pages.
              Returns empty list if no data found or on error.

    Notes:
        - UiPath column selector translates to nested div XPath
        - Next button XPath: "//span[@id='button-1035-btnInnerEl' and normalize-space(text())='Next']"
        - Uses 5-second timeout for data container visibility on each page
        - Adds 2-second delay after each page navigation for stability
    """
    all_data = []

    # UiPath extract column selector translates to this XPath pattern
    # Starts with <main> tag, then navigates through nested divs
    # <webctrl tag='div' idx='4' /> means 4th div child of main
    # <webctrl tag='div' idx='1' /> means 1st div child
    # <webctrl tag='div' /> without idx means any/all div children at that level
    column_xpath = (
        "//main/div[4]/div[1]/div//div[1]/div[1]/div[1]/div[1]/div[1]/div[1]/div[1]"
    )

    next_button_xpath = (
        "//span[@id='button-1035-btnInnerEl' and normalize-space(text())='Next']"
    )
    page_count = 1

    try:
        # Wait for the data container to appear on the first page
        logger.info("Waiting for data container to load...")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, column_xpath)),
        )
        logger.info("Data container loaded successfully")

        # Process all pages until no more "Next" button or it's disabled
        while True:
            logger.info(f"Processing page {page_count}...")

            # Locate all column elements matching the pattern
            # The UiPath column selector extracts all matching elements as a list
            try:
                column_elements = driver.find_elements(By.XPATH, column_xpath)

                if not column_elements:
                    logger.warning(f"No data elements found on page {page_count}")
                    break

                rows_extracted = 0

                # Extract text from each column element
                for element in column_elements:
                    # Get the full text content (attr='fulltext' in UiPath)
                    text_content = element.get_attribute("textContent")

                    if text_content:
                        # Clean and strip whitespace
                        text_content = text_content.strip()

                        # Skip empty content
                        if not text_content:
                            continue

                        # Split the account data into account name and account number
                        # Format: "NAB Wages Acc #1329086-006-922161329"
                        # Should become: ["NAB Wages Acc #1329", "086-006-922161329"]
                        account_name, account_number = split_account_data(text_content)

                        # Add as a two-item list [account_name, account_number]
                        all_data.append([account_name, account_number])
                        rows_extracted += 1

                logger.info(f"Extracted {rows_extracted} items from page {page_count}")

            except Exception as e:
                logger.warning(f"Error extracting data on page {page_count}: {e}")
                break

            # Check if there's a next page available
            if not has_next_page(driver, next_button_xpath):
                logger.info(f"No more pages available. Stopping at page {page_count}")
                break

            # Navigate to the next page
            try:
                next_button = driver.find_element(By.XPATH, next_button_xpath)
                safe_click(driver, next_button, f"Next button (page {page_count})")
                logger.info(f"Clicked Next button to navigate to page {page_count + 1}")

                # Wait for the data container to reload with new data
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, column_xpath)),
                )

                # Add delay for page stability
                time.sleep(2)
                page_count += 1

            except Exception as e:
                logger.warning(f"Failed to navigate to next page: {e}")
                break

        # Log final extraction summary
        logger.info(
            f"Data extraction completed. Total: {len(all_data)} rows from {page_count} page(s)",
        )
        return all_data

    except TimeoutException:
        logger.error("Timeout waiting for data table to load")
        return all_data

    except Exception as e:
        logger.error(f"Error during table extraction: {e}", exc_info=True)
        return all_data


def split_account_data(text_content):
    """
    Split bank account text into account name and account number.

    This function parses the extracted text which contains both the account name
    and account number, and splits them into two separate fields based on a pattern.

    Expected format: "Account Name #XXXXnnn-nnn-nnnnnnnnn"
    Where the last 4 digits before the hyphen are part of both name and number.

    Args:
        text_content (str): Full text extracted from the bank account element
                           Example: "NAB Wages Acc #1329086-006-922161329"

    Returns:
        tuple: (account_name, account_number)
               Example: ("NAB Wages Acc #1329", "086-006-922161329")

    Notes:
        - Looks for the pattern where account number starts after the last 4 digits
          following a # symbol
        - The last 4 digits before the first hyphen appear in both name and number
        - If the pattern doesn't match, returns original text and empty string
    """
    import re

    try:
        # Pattern: Capture everything up to and including #XXXX
        # Then capture the remaining part starting with 3 digits before hyphen
        # Example: "NAB Wages Acc #1329" + "086-006-922161329"

        # Look for pattern: text ending with #XXXX, followed by XXX-XXX-XXXXXX
        # The account number is the last part after the last 4 digits following #
        match = re.search(r"^(.*#\d{4})(\d{3}-.+)$", text_content)

        if match:
            account_name = match.group(1)  # Everything up to and including #XXXX
            account_number = match.group(2)  # Remaining part with hyphens
            return account_name, account_number
        else:
            # If pattern doesn't match, try alternative: split at first occurrence of digit-hyphen-digit
            match = re.search(r"^(.+?)(\d+-\d+-.+)$", text_content)
            if match:
                account_name = match.group(1).strip()
                account_number = match.group(2).strip()
                return account_name, account_number
            else:
                # Fallback: return original text as name, empty number
                logger.warning(f"Could not parse account format: {text_content}")
                return text_content, ""

    except Exception as e:
        logger.warning(f"Error splitting account data '{text_content}': {e}")
        return text_content, ""


def has_next_page(driver, next_button_xpath):
    """
    Check if pagination "Next" button is available and enabled.

    This function determines whether there are more pages to process by checking
    for the presence and state of the "Next" button in the pagination controls.

    Args:
        driver: Selenium WebDriver instance
        next_button_xpath (str): XPath to locate the "Next" button element

    Returns:
        bool: True if Next button exists, is visible, and is not disabled.
              False if button doesn't exist, is hidden, or is disabled.
    """
    try:
        # Check if Next button element exists
        next_buttons = driver.find_elements(By.XPATH, next_button_xpath)
        if not next_buttons:
            logger.info("Next button not found - likely last page")
            return False

        next_button = next_buttons[0]

        # Check if Next button is visible
        if not next_button.is_displayed():
            logger.info("Next button exists but is not visible")
            return False

        # Check if Next button is disabled
        class_attr = next_button.get_attribute("class") or ""
        if "disabled" in class_attr.lower():
            logger.info("Next button is disabled - reached last page")
            return False

        # Button exists, is visible, and is enabled
        logger.info("Next button is available and enabled")
        return True

    except Exception as e:
        logger.warning(f"Error checking Next button availability: {e}")
        return False
