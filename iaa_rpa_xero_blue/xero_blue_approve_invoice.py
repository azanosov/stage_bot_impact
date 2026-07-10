"""
This module has not been refactored.

If you need the functionality provided by this module,
please first contact Praveen Lobo and/or Alexander Zanosov.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from bs4 import BeautifulSoup
from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_approve_invoice(
    browser,
    xero_invoice_number: str,
    file_path_to_save_invoice: str,
    max_rows: int,
    xero_blue_title: str,
    invoice_file_name: str | None,
    invoice_approved: bool,
):
    """
    Approve a draft invoice in Xero Blue and download it as a PDF file.

    This function automates the complete workflow of approving a draft invoice in Xero Blue,
    including navigating to the invoice page, searching for the specific invoice, clicking
    the approve button, handling confirmation dialogs, and downloading the approved invoice
    as a PDF file to the specified directory.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_invoice_number (str): The invoice number to search for and approve (e.g., "INV-001").
        file_path_to_save_invoice (str): Absolute path to the directory where the invoice PDF will be saved.
        max_rows (int): Maximum number of table rows to search before stopping (prevents infinite loops).
        xero_blue_title (str): Expected Xero page title for verification before navigation.

    Returns:
        tuple: A tuple containing two elements:
            - invoice_approved (bool): True if the invoice was successfully approved, False otherwise.
            - invoice_file_name (str or None): The filename of the downloaded invoice PDF,
                                              or None if approval failed.

    Raises:
        Exception: Any exceptions that occur during navigation, approval, or file download.
                  All exceptions are logged with full stack traces and re-raised.

    Notes:
        - The function supports both new and old Xero Blue UI versions.
        - Uses cascading try-except to detect UI version (new UI → old UI).
        - Waits 3 seconds after navigating to dashboard/home for page stabilization.
        - Waits 1 second after navigating to invoice page for table loading.
        - If invoice is not found, the function returns (False, None).
        - Uses Windows automation (robocorp.windows) to handle Save As dialogs.
        - The function logs comprehensive start and end information with timestamps and duration.

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> approved, filename = xero_blue_approve_invoice(
        ...     browser=browser,
        ...     xero_invoice_number="INV-12345",
        ...     file_path_to_save_invoice="C:\\Invoices",
        ...     max_rows=100,
        ...     xero_blue_title="Xero"
        ... )
        >>> print(f"Approved: {approved}, File: {filename}")
        Approved: True, File: Invoice_INV-12345.pdf
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE APPROVE INVOICE")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Invoice Number: {xero_invoice_number}")
    logger.info(f"File Save Path: {file_path_to_save_invoice}")
    logger.info(f"Max Rows: {max_rows}")
    logger.info("=" * 80)

    # invoice_file_name = None
    # invoice_approved = False

    try:
        # Navigate to Dashboard (old UI) or Home page (new UI)
        # This function detects the UI version and clicks the appropriate navigation link
        # Ensures we start from a known state before navigating to invoices
        navigated_to_dashboard_or_home_page(browser)
        time.sleep(3)

        # Navigate to the Draft Invoices page
        # This function verifies the page title, then navigates via Sales→Invoices→Draft (new UI)
        # or Business→Invoices→Draft (old UI), and waits for the invoice table to load
        navigated_to_invoice_page(browser, xero_blue_title)
        time.sleep(1)

        # Extract invoice data from the table and find the row number matching the invoice number
        # This function parses the HTML table, searches through paginated results up to max_rows,
        # and returns the row number (1-indexed) where the invoice is located, or 0 if not found
        row_number = extract_data_table(browser, xero_invoice_number, max_rows)
        logger.info("Done")

        if row_number == 0:
            logger.error(f"{xero_invoice_number} not found the table")
            raise Exception(f"{xero_invoice_number} not found the table")

        # Click the invoice, approve it, handle confirmation dialogs, and download the PDF
        # This function clicks the invoice row, clicks Approve button, clicks OK/Confirm if needed,
        # verifies approval success, navigates to Awaiting Payment, and downloads the invoice
        invoice_approved, invoice_file_name = invoice_modification(
            browser,
            row_number,
            file_path_to_save_invoice,
            max_rows,
        )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE APPROVE INVOICE")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Invoice Number: {xero_invoice_number}")
        logger.info(f"Invoice Approved: {invoice_approved}")
        logger.info(f"Invoice File Name: {invoice_file_name}")
        logger.info(f"File Save Path: {file_path_to_save_invoice}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE APPROVE INVOICE")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Invoice Number: {xero_invoice_number}")
        logger.error(f"File Save Path: {file_path_to_save_invoice}")
        logger.error(f"Invoice Approved: {invoice_approved}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"xero_blue_approve_invoice failed due to {e}", exc_info=True)
        raise

    return invoice_approved, invoice_file_name


def invoice_modification(browser, row_number, file_path_to_save_invoice, max_rows):
    """
    Approve the selected invoice and download it if approval is successful.

    This function clicks the invoice row to open it, clicks the Approve button, handles
    any confirmation dialogs (Confirm and OK buttons), verifies that the approval was
    successful, and if so, proceeds to download the invoice PDF file.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        row_number (int): The table row number (1-indexed) where the invoice is located.
        file_path_to_save_invoice (str): Absolute path to the directory where the invoice PDF will be saved.

    Returns:
        tuple: A tuple containing two elements:
            - invoice_approved (bool): True if the invoice was successfully approved, False otherwise.
            - invoice_file_name (str or None): The filename of the downloaded invoice PDF,
                                              or None if approval failed.

    Raises:
        TimeoutException: If web elements cannot be located within the specified wait times.
        NoSuchElementException: If required elements are not found on the page.

    Notes:
        - Clicks the second cell (td[2]) in the specified row to open the invoice.
        - Waits up to 5 seconds for each element to become visible before interacting.
        - The Confirm button is optional and only clicked if present.
        - The OK button is only clicked if the Confirm button was present.
        - Verifies approval by checking for "1 item was approved" message.
        - Only proceeds to download if approval was successful.

    Example:
        >>> invoice_approved, filename = invoice_modification(browser, 5, "C:\\Invoices")
        >>> print(f"Approved: {invoice_approved}, File: {filename}")
        Approved: True, File: Invoice_INV-12345.pdf
    """
    invoice_xpath = f"//table//tbody//tr[{row_number}]//td[2]"
    approve_xpath = "//span[normalize-space(text())='Approve']"

    # Click the invoice row to open the invoice detail page
    # Wait up to 5 seconds for the table row to be visible, then click the second cell
    # This opens the invoice in edit/view mode
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
    ).click()
    logger.info("Click invoice")

    # Click the Approve button to initiate the approval process
    # Wait up to 5 seconds for the Approve button to be visible, then click it
    # This triggers the approval workflow and may show confirmation dialogs
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, approve_xpath)),
    ).click()
    logger.info("Click approve")

    # Check if a Confirm button appears and click it if present
    # The has_confirm_button function waits for the Confirm button (5 seconds timeout)
    # and clicks it if found, returning True; returns False if not found
    if has_confirm_button(browser):
        # If Confirm button was present and clicked, now click the OK button
        # Wait up to 5 seconds for the OK button to appear, then click it
        # This completes the confirmation dialog sequence
        ok_button_xpath = "//span[normalize-space(text())='OK']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ok_button_xpath)),
        )
        browser.driver.find_element(By.XPATH, ok_button_xpath).click()
        logger.info("Click Ok")

    # Verify that the invoice was successfully approved
    # The is_invoice_approvied function checks for "1 item was approved" message
    # Returns True if approval was successful, False otherwise
    invoice_approved = is_invoice_approvied(browser)

    # If approval was successful, proceed to download the invoice
    # Navigate to Awaiting Payment tab, find the invoice, print it, and save the PDF
    # Returns the filename of the downloaded invoice
    invoice_file_name = None
    if invoice_approved:
        invoice_file_name = awaiting_for_invoice_approve(
            browser,
            row_number,
            file_path_to_save_invoice,
            max_rows,
        )
    return invoice_approved, invoice_file_name


def awaiting_for_invoice_approve(
    browser,
    xero_invoice_number,
    file_path_to_save_invoice,
    max_rows,
):
    """
    Navigate to Awaiting Payment tab, locate the approved invoice, and download it as PDF.

    After an invoice has been approved, it moves to the "Awaiting Payment" status. This function
    navigates to the Awaiting Payment tab, searches for the invoice in the table, opens it,
    clicks the Print button to trigger PDF generation, handles the "Mark as sent" dialog if it
    appears, and saves the PDF file using Windows automation.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_invoice_number: The invoice number or row number to search for (parameter name is misleading).
        file_path_to_save_invoice (str): Absolute path to the directory where the invoice PDF will be saved.
        max_rows (int): Maximum number of table rows to search before stopping.

    Returns:
        str: The filename of the downloaded invoice PDF.

    Raises:
        TimeoutException: If web elements cannot be located within the specified wait times.
        NoSuchElementException: If required elements are not found on the page.

    Notes:
        - Clicks the "Awaiting Payment" tab to view newly approved invoices.
        - Re-extracts the data table to find the invoice in its new location.
        - The "Mark as sent" button is optional and only clicked if present.
        - Uses Windows automation to handle the browser's Save As dialog.

    Example:
        >>> filename = awaiting_for_invoice_approve(browser, "INV-12345", "C:\\Invoices", 100)
        >>> print(f"Downloaded: {filename}")
        Downloaded: Invoice_INV-12345.pdf
    """
    # Click the Awaiting Payment tab to view approved invoices
    # Wait up to 5 seconds for the tab to be visible, then click it
    # Approved invoices automatically move to this status after approval
    awaiting_payment_xpath = "//a[normalize-space((.))='Awaiting Payment']"
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, awaiting_payment_xpath)),
    )
    browser.driver.find_element(By.XPATH, awaiting_payment_xpath).click()
    logger.info("Click awaiting payment")

    # Extract the Awaiting Payment invoice data table and find the invoice row number
    # This searches through the table (with pagination) to locate the specific invoice
    # Returns the row number (1-indexed) where the invoice is found
    row_number = extract_data_table(browser, xero_invoice_number, max_rows)

    # Click the invoice to open it
    # Wait up to 5 seconds for the first cell in the matching row to be visible, then click it
    # This opens the invoice detail page
    invoice_num_xpath = f"//table//tr[{row_number}]//td[1]"
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, invoice_num_xpath)),
    )
    browser.driver.find_element(By.XPATH, invoice_num_xpath).click()
    logger.info("Click Invoice")

    # Click the Print button to initiate PDF generation
    # Wait up to 5 seconds for the Print button to be visible, then click it
    # This triggers the browser's print/save dialog
    print_button_xpath = "//span[normalize-space(text()))='Print']"
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, print_button_xpath)),
    )
    browser.driver.find_element(By.XPATH, print_button_xpath).click()
    logger.info("Click print button")

    # Check if a Confirm button appears and click it if present
    # Some Xero configurations may show a confirmation dialog before printing
    if has_confirm_button(browser):
        # If Confirm button was present, Xero may show "Mark as sent" button
        # Wait up to 5 seconds for the button to appear, then click it
        # This marks the invoice as sent to the customer
        mark_as_sent_xpath = "//span[normalize-space(text()))='Mark as sent']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, mark_as_sent_xpath)),
        )
        browser.driver.find_element(By.XPATH, mark_as_sent_xpath).click()
        logger.info("Click Mark as sent")

    # Handle the Windows Save As dialog and save the PDF file
    # Uses robocorp.windows library to interact with the native dialog
    # Returns the filename of the saved PDF
    invoice_file_name = save_file(file_path_to_save_invoice)
    return invoice_file_name


def has_confirm_button(browser) -> bool:
    """
    Check if the Confirm button is present and click it if found.

    This function waits up to 5 seconds for a Confirm button to appear on the page.
    If the button is found, it clicks it automatically. This is used to handle
    optional confirmation dialogs that may appear during the invoice approval process.

    Args:
        browser: Selenium WebDriver browser instance for web automation.

    Returns:
        bool: True if the Confirm button was found and clicked, False if not found within timeout.

    Notes:
        - Uses a 5-second explicit wait for the Confirm button.
        - The button is automatically clicked if found.
        - Returns False silently if the button is not found (normal flow, not an error).
        - This is a non-blocking check - execution continues regardless of result.

    Example:
        >>> if has_confirm_button(browser):
        ...     print("Confirm button was found and clicked")
        ... else:
        ...     print("No confirm button present")
    """
    try:
        confirm_xpath = "//span[normalize-space(text())='Confirm']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, confirm_xpath)),
        )
        browser.driver.find_element(By.XPATH, confirm_xpath).click()
        logger.info("Click confirm button")
        return True
    except Exception:
        return False


def is_invoice_approvied(browser) -> bool:
    """
    Verify that the invoice approval was successful by checking for confirmation message.

    This function waits up to 5 seconds for the "1 item was approved" success message
    to appear on the page after clicking the Approve button. This message confirms that
    the invoice approval operation completed successfully.

    Args:
        browser: Selenium WebDriver browser instance for web automation.

    Returns:
        bool: True if the "1 item was approved" message is found (approval successful),
             False if the message is not found within 5 seconds (approval failed).

    Notes:
        - Uses a 5-second explicit wait for the success message.
        - The presence of this message is the definitive indicator of approval success.
        - Returns False silently if the message is not found (indicates approval failure).
        - This check should be performed immediately after the approval workflow.

    Example:
        >>> if is_invoice_approvied(browser):
        ...     print("Invoice approved successfully")
        ... else:
        ...     print("Invoice approval failed")
    """
    invoice_approved = False
    try:
        approve_xpath = "//span[normalize-space(text())='1 item was approved']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, approve_xpath)),
        )
        logger.info("1 item was approved found")
        invoice_approved = True
        return invoice_approved
    except Exception:
        invoice_approved = False
        return invoice_approved


def navigated_to_dashboard_or_home_page(browser):
    """
    Navigate to the Dashboard (old UI) or Home page (new UI) to establish a known starting point.

    This function detects which version of Xero Blue UI is active and navigates to the appropriate
    starting page. It first tries to click the Home link (new UI), and if that fails, falls back
    to clicking the Dashboard link (old UI). This ensures a consistent starting point before
    navigating to specific sections like Invoices.

    Args:
        browser: Selenium WebDriver browser instance for web automation.

    Returns:
        None

    Raises:
        TimeoutException: If neither Home nor Dashboard links can be located.

    Notes:
        - Uses cascading try-except for UI version detection (new UI → old UI).
        - New UI: Waits up to 5 seconds for Home link, uses safe_click for reliability.
        - Old UI: Waits up to 2 seconds for Dashboard link.
        - safe_click is preferred as it handles potential click interception issues.

    Example:
        >>> navigated_to_dashboard_or_home_page(browser)
        # Navigates to either Home (new UI) or Dashboard (old UI)
    """
    driver = browser.driver

    try:
        # NEW UI: Try to click the Home button
        # Wait up to 5 seconds for the Home link to be visible
        # Uses safe_click to handle potential element interception issues
        home_link_xpath = "//a[.//span[text()='Home']]"
        home_link_ele = WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, home_link_xpath)),
        )
        safe_click(driver, home_link_ele, "Clicked Home button")
        logger.info("Home Button clicked")

    except Exception:
        # OLD UI: If Home link not found, fall back to Dashboard link
        # Wait up to 2 seconds for the Dashboard link to be visible, then click it
        # This indicates we're using the legacy Xero Blue interface
        dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
        WebDriverWait(browser.driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
        ).click()
        logger.info("Dashboard page clicked")


def navigated_to_invoice_page(browser, xero_blue_title):
    """
    Navigate to the Draft Invoices page in Xero Blue.

    This function verifies that the browser is on a Xero page (by checking the page title),
    then navigates through the menu structure to reach the Draft Invoices page. It supports
    both new UI (Sales→Invoices→Draft) and old UI (Business→Invoices→Draft) navigation paths.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_blue_title (str): Expected substring in the page title to verify we're on Xero (e.g., "Xero").

    Returns:
        None

    Raises:
        TimeoutException: If navigation elements cannot be located within specified wait times.

    Notes:
        - Verifies page title contains xero_blue_title before attempting navigation.
        - Uses cascading try-except for UI version detection (new UI → old UI).
        - New UI path: Sales button → Invoices link → Draft link.
        - Old UI path: Business button → Invoices link → Draft link.
        - Uses safe_click for new UI to handle element interception.
        - Waits 1 second before starting navigation for page stabilization.

    Example:
        >>> navigated_to_invoice_page(browser, "Xero")
        # Navigates to Draft Invoices page
    """
    # Verify that the current page title contains the expected Xero title
    # This ensures we're on the correct website before attempting navigation
    current_title = browser.driver.title
    if xero_blue_title in current_title:

        try:
            time.sleep(1)

            """For New ui"""
            sales_xpath = (
                "//button[@type='button' and .//span[normalize-space(text())='Sales']]"
            )
            invoice_xpath = (
                "//a[@role='link' and span[normalize-space(text())='Invoices']]"
            )
            draft_xpath = "//a[normalize-space(text())='Draft']"

            # Click sales
            sales_ele = WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, sales_xpath)),
            )
            safe_click(browser.driver, sales_ele, "Clicked sales")
            logger.info("Sales Button clicked")

            # Click invoice
            invoice_ele = WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
            )
            safe_click(browser.driver, invoice_ele, "Clicked Invoice")
            logger.info("Invoice tab clicked")

            # Click Draft
            draft_ele = WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, draft_xpath)),
            )
            safe_click(browser.driver, draft_ele, "Clicked Draft")
            logger.info("Click - Draft")

        except Exception:

            """For old ui"""
            business_xpath = "//button[normalize-space(text())='Business']"
            invoices_tab_xpath = "//a[normalize-space(text())='Invoices']"
            draft_xpath = "//a[normalize-space(.)='Draft']"

            # Click  Business
            WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, business_xpath)),
            ).click()
            logger.info("Business button clicked")

            # Click Invoice
            WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, invoices_tab_xpath)),
            ).click()
            logger.info("Invoice tab clicked")

            # Click Draft
            WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, draft_xpath)),
            ).click()
            logger.info("Click - Draft")


def extract_data_table(
    browser,
    xero_invoice_number,
    max_rows,
):
    """
    Extract invoice data from the table and find the row number matching the invoice number.

    This function parses the HTML table on the current page using BeautifulSoup, extracts all
    invoice rows, and searches for a row where the invoice number (second column) matches the
    provided xero_invoice_number. It supports pagination by automatically clicking the "Next"
    button to search through multiple pages.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_invoice_number (str): The invoice number to search for (compared case-insensitively).
        max_rows (int): Maximum number of table rows to search before stopping (prevents infinite loops).

    Returns:
        int: The row number (1-indexed) where the matching invoice is found.
            Returns 0 if the invoice is not found or no table exists.

    Raises:
        NoSuchElementException: If the table element cannot be found on the page.

    Notes:
        - Uses BeautifulSoup to parse the HTML table structure.
        - Compares invoice numbers case-insensitively with strip() to handle whitespace.
        - The invoice number is expected in the second column (index 1) of each row.
        - Skips the header row (first tr element) when extracting data.
        - Automatically navigates to the next page if the "Next" button is enabled.
        - Stops searching if the "Next" button is disabled or max_rows is reached.
        - Row numbers start at 1 (not 0) to match XPath indexing.

    Example:
        >>> row_num = extract_data_table(browser, "INV-12345", 100)
        >>> if row_num > 0:
        ...     print(f"Invoice found at row {row_num}")
        ... else:
        ...     print("Invoice not found")
    """
    table_xpath = "//table"
    all_data = []

    row_number = 1

    while True:
        element = browser.driver.find_element(By.XPATH, table_xpath)
        html = element.get_attribute("outerHTML")
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if not table:
            logger.info("No table found")
            break

        # Extract rows
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            row_data = [cell.text.strip() for cell in cells]
            all_data.append(row_data)

            if len(all_data) > 0:
                if xero_invoice_number and len(row_data) > 0:
                    if (
                        row_data[1].strip().lower()
                        == xero_invoice_number.strip().lower()
                    ):
                        logger.info(f"Invoice number matches: {xero_invoice_number}")
                        logger.info(f"Row number : {row_number}")

                        return row_number
                    else:
                        row_number += 1
            else:
                row_number = 0

            # Stop if reached max rows
            if len(all_data) >= max_rows:
                logger.info(f"Reached max row limit: {max_rows}")
                return 0

        # Try to click "Next »" if available
        try:
            next_button_xpath = "//a[contains(normalize-space(.), 'Next')]"
            next_button = browser.driver.find_element(By.XPATH, next_button_xpath)
            if "disabled" in next_button.get_attribute("class"):
                break  # Stop if no next button

            next_button.click()
            WebDriverWait(browser.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, table_xpath)),
            )
        except Exception:
            logger.info("No more pages found")
            break

    return 0


def save_file(file_path_to_save_invoice):
    """
    Handle the Windows Save As dialog to save the invoice PDF file.

    This function uses Windows automation (robocorp.windows library) to interact with Chrome's
    native Save As dialog. It retrieves the default filename suggested by the browser, constructs
    the full file path by combining it with the target directory, enters the path into the file
    name field, and clicks the Save button. It also handles the overwrite confirmation dialog
    if the file already exists.

    Args:
        file_path_to_save_invoice (str): Absolute path to the directory where the PDF should be saved.

    Returns:
        str: The default filename that was suggested by the browser (before adding the directory path).

    Raises:
        Exception: If the Chrome window or Save As dialog cannot be found.
        Exception: If UI automation controls cannot be located.

    Notes:
        - Uses regex to find the Chrome window: 'regex:.*Xero | * - Google Chrome'.
        - Retrieves the default filename from the "File name:" edit control.
        - Combines the default filename with the target directory using os.path.normpath.
        - Clears the existing filename using CTRL+A and DEL keys before entering the new path.
        - Waits 2 seconds after entering the path for UI stabilization.
        - Automatically handles "Confirm Save As" overwrite dialog if it appears.
        - Uses a 3-second timeout when checking for the overwrite confirmation.

    Example:
        >>> filename = save_file("C:\\Invoices")
        >>> print(f"Saved as: {filename}")
        Saved as: Invoice_INV-12345.pdf
    """
    # Find the Chrome window using regex pattern
    # This locates the active Chrome window showing Xero
    app = windows.find_window(f"regex:.*Xero | * - Google Chrome")

    # Find the Save As dialog window
    # This locates the native Windows Save As dialog
    app.find('control:"WindowControl" and name:"Save As" and path:"1"')

    # Find and click the File name input field
    # This activates the edit control so we can manipulate the filename
    find_input = app.find(
        'control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"',
    ).click()

    # Get the default filename suggested by the browser
    # This is typically in the format "Invoice_INV-12345.pdf" or similar
    actual_file_name = find_input.get_value() or ""
    invoice_file_name = actual_file_name

    # Construct the full file path by combining the directory with the default filename
    # os.path.normpath ensures proper path formatting for Windows
    file_path = os.path.normpath(
        os.path.join(file_path_to_save_invoice, actual_file_name),
    )

    # Select all text in the filename field (CTRL+A)
    # This prepares to replace the entire filename with our custom path
    find_input.send_keys("{CTRL}a")

    # Delete the selected text (DEL key)
    # This clears the field completely
    find_input.send_keys("{DEL}")

    # Enter the full file path including directory and filename
    # This specifies exactly where the file should be saved
    find_input.send_keys(file_path)

    # Wait 2 seconds for the UI to process the input
    # This ensures the path is fully entered before clicking Save
    time.sleep(2)

    # Click the Save button to initiate the file save
    # This triggers the actual file write operation
    app.find('control:"ButtonControl" and name:"Save"').click()

    # Check if an overwrite confirmation dialog appears
    # This happens if a file with the same name already exists
    try:
        # Wait up to 3 seconds for the "Confirm Save As" dialog to appear
        save_confirm_popup = app.find(
            'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"',
            timeout=3,
        )

        # Click the "Yes" button to confirm overwriting the existing file
        save_confirm_popup.find(
            'control:"ButtonControl" and class:"CCPushButton" and name:"Yes"',
        ).click()
    except Exception:
        # No overwrite confirmation appeared (file doesn't exist) - this is normal
        logger.info("No window present")

    # Return the original default filename (without the directory path)
    return invoice_file_name
