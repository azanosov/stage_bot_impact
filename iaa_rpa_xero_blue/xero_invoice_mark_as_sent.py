"""
This module has not been refactored.

If you need the functionality provided by this module,
please first contact Praveen Lobo and/or Alexander Zanosov.
"""

from datetime import datetime

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click

# Set up logger
logger = setup_logger(__name__)


def xero_invoice_mark_as_sent(browser, xero_invoice_number, xero_url):
    """Mark an invoice as sent in Xero.

    This function automates the process of marking an invoice as sent in Xero Blue.
    It navigates to the Invoices page, filters for "Awaiting Payment" invoices, searches
    for the specific invoice by number, selects it, and clicks the "Mark as Sent" button.

    The workflow handles both new and old Xero UI versions through cascading try-except
    patterns. It searches through all open browser tabs to find the correct Xero tab
    using the provided URL.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_invoice_number (str): The invoice number to search for and mark as sent (e.g., "INV-12345").
        xero_url (str): The Xero URL to identify the correct browser tab (e.g., "xero.com").

    Returns:
        None: The function completes successfully or raises an exception.

    Raises:
        Exception: If navigation fails or invoice cannot be found and marked.
        TimeoutException: If any web elements are not found within the timeout period.

    Notes:
        - Supports both new UI (Sales > Invoices) and old UI (Business > Invoices) navigation
        - Uses keyboard automation (CTRL+A, DELETE, TAB) to search for invoice
        - Filters invoices by "Awaiting Payment" status before searching
        - Uses safe_click utility for reliable element clicking
        - Grid view ID 'gridview-1056' is used to locate invoice checkbox
        - All navigation and actions are logged for debugging

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> xero_invoice_mark_as_sent(browser, "INV-12345", "xero.com")
        # Invoice INV-12345 marked as sent successfully
    """

    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO INVOICE MARK AS SENT")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Invoice Number: {xero_invoice_number}")
    logger.info(f"Xero URL: {xero_url}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # Get all open browser tabs to find the correct Xero tab
        all_tabs = driver.window_handles
        logger.info(f"Found {len(all_tabs)} browser tab(s)")

        # Iterate through all tabs to find the one matching xero_url
        for handle in all_tabs:
            driver.switch_to.window(handle)
            current_url = driver.current_url

            # Check if this tab contains the Xero URL
            if xero_url in current_url:
                logger.info(f"Found Xero tab with URL: {current_url}")

                # Navigate to Invoices page using new UI (Sales > Invoices) or old UI (Business > Invoices)
                # Uses cascading try-except to support both UI versions
                try:
                    # For new UI: Click Sales button
                    # This expands the Sales menu to reveal the Invoices link
                    sales_xpath = "//button[@type='button']//span[normalize-space(text())='Sales']"
                    elem = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, sales_xpath))
                    )
                    safe_click(driver, elem, "Sales")
                    logger.info("Sales button clicked (new UI)")

                    # For new UI: Click Invoices link
                    # Opens the Invoices page with all invoice lists
                    invoice_xpath = (
                        "//a[@role='link']//span[normalize-space(text())='Invoices']"
                    )
                    elem = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, invoice_xpath))
                    )
                    safe_click(driver, elem, "Invoices")
                    logger.info("Invoices link clicked (new UI)")

                except Exception:
                    # For old UI: Fallback navigation path
                    logger.info("New UI not found, attempting old UI navigation")
                    try:
                        # For old UI: Click Business button
                        # Opens the Business dropdown menu
                        business_xpath = "//button[normalize-space(text())='Business']"
                        elem = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, business_xpath))
                        )
                        safe_click(driver, elem, "Business")
                        logger.info("Business button clicked (old UI)")

                        # For old UI: Click Invoices link
                        # Navigates to the Invoices page
                        invoice_xpath = "//a[normalize-space(text())='Invoices']"
                        elem = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, invoice_xpath))
                        )
                        safe_click(driver, elem, "Invoices")
                        logger.info("Invoices link clicked (old UI)")
                    except Exception as e:
                        logger.error(f"Could not navigate to Invoices page: {e}")
                        raise

                # Click the "Awaiting Payment" filter to show only unpaid invoices
                # This narrows down the list to invoices that need to be marked as sent
                awaiting_payments = (
                    "//a[contains(normalize-space(), 'Awaiting Payment')]"
                )
                awaiting_ele = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, awaiting_payments))
                )
                safe_click(driver, awaiting_ele, "Awaiting Payment")
                logger.info("Clicked 'Awaiting Payment' filter")

                # Search for the specific invoice using the search input field
                # Uses keyboard automation to clear field and enter invoice number
                input_xpath = "//input[contains(@id, 'inputEl')]"
                input_client_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, input_xpath))
                )
                input_client_ele.send_keys(
                    "\ue009" + "a"
                )  # CTRL + A to select all text
                input_client_ele.send_keys("\ue003")  # DELETE to clear the field
                input_client_ele.send_keys(
                    xero_invoice_number
                )  # Type the invoice number
                input_client_ele.send_keys("\ue004")  # TAB to trigger search
                logger.info(
                    f"Entered invoice number in search field: {xero_invoice_number}"
                )

                # Select the invoice checkbox in the grid view
                # Clicks the first row checkbox to select the matching invoice
                checker_xpath = "//*[@id='gridview-1056']//table//div[@class='x-grid-row-checker'][1]"
                checker_ele = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, checker_xpath))
                )
                safe_click(driver, checker_ele, "Invoice checkbox")
                logger.info(f"Selected invoice checkbox for: {xero_invoice_number}")

                # Click the "Mark as Sent" button to update invoice status
                # This marks the invoice as sent in Xero's system
                mark_as_sent_button_xpath = (
                    "//a[@aria-role='button']//span[normalize-space()='Mark as Sent']"
                )
                mark_as_sent_button_ele = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, mark_as_sent_button_xpath)
                    )
                )
                safe_click(driver, mark_as_sent_button_ele, "Mark as Sent")
                logger.info(
                    f"Clicked 'Mark as Sent' button for invoice: {xero_invoice_number}"
                )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO INVOICE MARK AS SENT")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Invoice Number: {xero_invoice_number}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO INVOICE MARK AS SENT")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Invoice Number: {xero_invoice_number}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"The xero_invoice_mark_as_sent failed due to {e}", exc_info=True)
        raise
