"""
This module has not been refactored.

If you need the functionality provided by this module,
please first contact Praveen Lobo and/or Alexander Zanosov.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from RPA.PDF import PDF
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

pdf = PDF()


# Set up logger
logger = setup_logger(__name__)


def xero_approval_and_email_invoice(
    browser,
    xero_url: str,
    client_name: str,
    download_directory_path: str,
    invoice_number: str,
    invoice_dir: str,
    preset_client_name: str,
):
    """Approve and email invoice in Xero.

    This function automates the complete invoice approval and email process in Xero:
    - Navigates to the invoice page
    - Searches for the invoice by reference number
    - Validates invoice details
    - Prints invoice PDF
    - Sends approval email

    Args:
        browser: SeleniumBrowser instance with driver attribute
        xero_url: URL of the Xero instance
        client_name: Name of the client for validation
        download_directory_path: Directory path for downloading invoice PDF
        invoice_number: Invoice reference number to search for
        invoice_dir: Directory for storing invoice files
        in_InvoiceCreatedDate: Invoice creation date
        preset_client_name: Current client name for comparison

    Raises:
        Exception: If invoice approval or email process fails
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE APPROVE AND EMAIL INVOICE")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Xero URL: {xero_url}")
    logger.info(f"Client Name: {client_name}")
    logger.info(f"Invoice Number: {invoice_number}")
    logger.info(f"Download Directory: {download_directory_path}")
    logger.info(f"Invoice Directory: {invoice_dir}")
    logger.info(f"Current Client: {preset_client_name}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # ========================================================================
        # STEP 1: Switch to Correct Browser Tab
        # ========================================================================
        # Purpose: Find and activate the browser tab containing Xero
        # Iterates through all open tabs to locate the one matching xero_url
        all_tabs = driver.window_handles
        logger.info(
            f"STEP 1: Searching through {len(all_tabs)} browser tab(s) for Xero",
        )

        xero_tab_found = False
        for tab_index, handle in enumerate(all_tabs, 1):
            driver.switch_to.window(handle)
            current_url = driver.current_url
            logger.info(f"  Checking tab {tab_index}: {current_url[:50]}...")

            if xero_url in current_url.lower():
                xero_tab_found = True
                logger.info(f"  ✓ Found Xero tab (tab {tab_index})")
                logger.info(f"STEP 1 COMPLETED: Switched to Xero tab")

                # ========================================================================
                # STEP 2: Navigate to Home/Dashboard Page
                # ========================================================================
                # Purpose: Ensure we're on the main page before navigating to invoices
                # Function: navigated_to_home(browser)
                # - Clicks "Home" button (new UI) or "Dashboard" button (old UI)
                # - Serves as a stable starting point for navigation
                logger.info("=" * 80)
                logger.info("STEP 2: Navigating to Home/Dashboard page")
                navigated_to_home(browser)
                logger.info(
                    "STEP 2 COMPLETED: Successfully navigated to Home/Dashboard",
                )

                # ========================================================================
                # STEP 3: Navigate to Invoices Page
                # ========================================================================
                # Purpose: Access the invoices list page via Sales/Business menu
                # Function: navigated_to_invoice(browser)
                # - NEW UI: Clicks Sales > Invoices
                # - OLD UI: Clicks Business > Invoices
                logger.info("=" * 80)
                logger.info("STEP 3: Navigating to Invoices page")
                navigated_to_invoice(browser)
                logger.info("STEP 3 COMPLETED: Successfully navigated to Invoices page")

                # ========================================================================
                # STEP 4: Search for Invoice by Reference Number
                # ========================================================================
                # Purpose: Find and open the specific invoice using its reference number
                # Sub-steps:
                # 4.1 - Open search interface
                # 4.2 - Enter invoice reference number
                # 4.3 - Submit search
                # 4.4 - Open matching invoice
                logger.info("=" * 80)
                logger.info(f"STEP 4: Searching for invoice: {invoice_number}")

                # STEP 4.1: Open Search Interface
                logger.info("  Step 4.1: Opening search interface")
                search_xpath = (
                    "//span[@class='text' and normalize-space(text())='Search']"
                )
                search_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, search_xpath)),
                )
                safe_click(driver, search_ele, "Search button")
                logger.info("  ✓ Search interface opened")

                # STEP 4.2: Enter Invoice Reference Number
                logger.info(f"  Step 4.2: Entering invoice reference: {invoice_number}")
                reference_xpath = (
                    "//input[@type='text' and contains(@name, 'Reference')]"
                )
                reference_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, reference_xpath)),
                )
                safe_click(driver, reference_ele, "Reference field")
                reference_ele.clear()
                reference_ele.send_keys(invoice_number)
                logger.info(f"  ✓ Invoice reference entered: {invoice_number}")

                # STEP 4.3: Submit Search Query
                logger.info("  Step 4.3: Submitting search query")
                search_invoice_xpath = "//a[normalize-space(text())='Search']"
                search_invoice_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, search_invoice_xpath)),
                )
                safe_click(driver, search_invoice_ele, "Search link")
                logger.info("  ✓ Search submitted")

                # STEP 4.4: Open Matching Invoice
                logger.info("  Step 4.4: Opening matching invoice from search results")
                invoice_xpath = f"//table[@class='standard']//tbody//td[normalize-space()='{invoice_number}']"
                invoice_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
                )
                safe_click(driver, invoice_ele, f"Invoice {invoice_number}")
                logger.info(f"  ✓ Invoice {invoice_number} opened")
                logger.info("STEP 4 COMPLETED: Invoice found and opened")

                # ========================================================================
                # STEP 5: Print Invoice to PDF (Conditional - Client Specific)
                # ========================================================================
                # Purpose: Generate PDF copy of invoice for validation
                # Condition: Only if 'Approve & Email' button exists AND client matches
                # Function: print_invoice(browser, download_directory_path, invoice_dir)
                # - Clicks More > Print PDF
                # - Saves PDF to specified directory
                # - Validates PDF contains email and BPAY reference
                logger.info("=" * 80)
                logger.info("STEP 5: Checking if invoice PDF printing is required")
                if (
                    has_approve_and_email_exist(browser)
                    and preset_client_name == client_name
                ):
                    logger.info(
                        f"  ✓ 'Approve & Email' button exists and client matches ({client_name})",
                    )
                    logger.info("  Printing invoice to PDF...")
                    print_invoice(browser, download_directory_path, invoice_dir)
                    logger.info("STEP 5 COMPLETED: Invoice PDF printed and validated")
                else:
                    logger.info("  ✗ PDF printing skipped (conditions not met)")
                    logger.info("STEP 5 SKIPPED")

                # ========================================================================
                # STEP 6: Remove Invoice Section (Conditional - Client Specific)
                # ========================================================================
                # Purpose: Remove specific invoice line items (Stannards client only)
                # Condition: Only if preset_client_name matches client_name
                # Function: remove_section_from_invoice(browser)
                # - Looks for specific line item text
                # - Clicks Remove button if found
                # TODO: Client-specific manipulation - test only in production
                logger.info("=" * 80)
                logger.info("STEP 6: Checking if invoice section removal is required")
                if preset_client_name == client_name:
                    logger.info(
                        f"  ✓ Client matches ({client_name}) - checking for removable sections",
                    )
                    remove_section_from_invoice(browser)
                    logger.info("STEP 6 COMPLETED: Invoice section removal processed")
                else:
                    logger.info("  ✗ Client does not match - skipping section removal")
                    logger.info("STEP 6 SKIPPED")

                # ========================================================================
                # STEP 7: Update Invoice and Prepare for Email
                # ========================================================================
                # Purpose: Save invoice changes and open email dialog
                # Function: update_invoice(browser)
                # - PATH A: If Update button exists: Update > More > Email
                # - PATH B: If no Update button: Approve & Email
                logger.info("=" * 80)
                logger.info("STEP 7: Updating invoice and preparing email")
                update_invoice(browser)
                logger.info("STEP 7 COMPLETED: Invoice updated, email dialog opened")

                # ========================================================================
                # STEP 8: Validate Email Address
                # ========================================================================
                # Purpose: Ensure invoice has valid email recipient
                # Function: validate_email(browser)
                # - Checks for email address containing '@' and '.'
                # - Throws exception if no valid email found
                logger.info("=" * 80)
                logger.info("STEP 8: Validating email address")
                validate_email(browser)
                logger.info("STEP 8 COMPLETED: Email address validated")

                # ========================================================================
                # STEP 9: Validate Email Body Salutation (Conditional - Client Specific)
                # ========================================================================
                # Purpose: Check email body has proper salutation (Stannards client only)
                # Condition: Only if preset_client_name matches client_name
                # Function: get_email_body(browser)
                # - Reads email body text
                # - Validates character at position 5 (after "Dear ")
                # - Throws exception if salutation is missing or malformed
                logger.info("=" * 80)
                logger.info(
                    "STEP 9: Checking if email salutation validation is required",
                )
                if preset_client_name == client_name:
                    logger.info(
                        f"  ✓ Client matches ({client_name}) - validating salutation",
                    )
                    get_email_body(browser)
                    logger.info("STEP 9 COMPLETED: Email salutation validated")
                else:
                    logger.info(
                        "  ✗ Client does not match - skipping salutation validation",
                    )
                    logger.info("STEP 9 SKIPPED")

                # ========================================================================
                # STEP 10: Send Email
                # ========================================================================
                # Purpose: Send the invoice email to the client
                # Function: send_email_button(browser)
                # - Clicks "Send email" button
                # - Retries up to 3 times if needed
                # - Validates success by checking for Sales/Business button
                logger.info("=" * 80)
                logger.info("STEP 10: Sending invoice email")
                send_email_button(browser)
                logger.info("STEP 10 COMPLETED: Invoice email sent successfully")

                break  # Exit loop after processing the correct tab

        # Check if Xero tab was found
        if not xero_tab_found:
            raise Exception(
                f"No browser tab found containing Xero URL pattern: {xero_url}",
            )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(
            f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE APPROVE AND EMAIL INVOICE",
        )
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Invoice Number: {invoice_number}")
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Download Directory: {download_directory_path}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE APPROVE AND EMAIL INVOICE")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Invoice Number: {invoice_number}")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Download Directory: {download_directory_path}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(
            f"Xero blue approve and email invoice failed due to {e}",
            exc_info=True,
        )
        raise


def send_email_button(browser):
    """
    Click send email button with validation.

    This function handles the final step of sending the invoice email.
    It validates that the Send Email button is present, then attempts
    to click it with retry logic.

    Process:
    1. Check if Send Email button exists
    2. If exists: Click with retry logic (up to 3 attempts)
    3. If not exists: Raise exception

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        Exception: If send email button is not found or clicking fails

    Note:
        - Uses 5-second timeout for element waits
        - Delegates to retry_select_send_button() for actual clicking
        - Validates success by checking for home page elements
    """
    send_email_button_xpath = "//div[@id='send-email-mfe-root']//button[@id='send-email-button' and @type='submit' and normalize-space(text())='Send email']"

    logger.info("  Checking for Send Email button")

    # Check send email button is present
    if has_email_button(browser, send_email_button_xpath):
        logger.info("  ✓ Send Email button found")
        logger.info("  Attempting to send email (with retry logic)")
        # Click send button using retry scope
        retry_select_send_button(browser, send_email_button_xpath)
    else:
        logger.error("  ✗ Send Email button not found")
        raise Exception("Invoice approved, but couldn't email.")


def retry_select_send_button(browser, send_email_button_xpath: str):
    """
    Retry clicking send button with validation of successful navigation.

    This function implements retry logic for clicking the Send Email button.
    After clicking, it validates success by checking for the presence of
    home page elements (Sales or Business button).

    Retry Strategy:
    - Maximum 3 attempts
    - 2-second wait between retries
    - Validates success by checking for home page navigation

    Success Validation:
    - NEW UI: Looks for Sales button
    - OLD UI: Looks for Business button
    - If either found, email was sent successfully

    Args:
        browser: SeleniumBrowser instance with driver attribute
        send_email_button_xpath: XPath of the send email button

    Returns:
        bool: True if successfully sent, False otherwise

    Note:
        - Uses 5-second timeout for element waits
        - Waits 1 second after clicking before validation
        - Automatically retries on failure
    """
    driver = browser.driver
    attempt = 1
    max_retries = 3
    wait_time = 2

    while attempt <= max_retries:
        try:
            # ACTION 1: Click Send Email Button
            # Purpose: Submit the email to be sent
            logger.info(
                f"    Attempt {attempt}/{max_retries}: Clicking Send Email button",
            )
            send_email_ele = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, send_email_button_xpath)),
            )
            safe_click(driver, send_email_ele, "Send email button")
            logger.info(f"      ✓ Send Email button clicked")

            # ACTION 2: Wait for Page Transition
            # Purpose: Allow time for email to be sent and page to navigate
            time.sleep(1)

            # ACTION 3: Validate Success - Check for Home Page Elements
            # Purpose: Confirm email was sent by verifying navigation to home page
            logger.info(f"      Validating email sent successfully...")

            try:
                # NEW UI VALIDATION: Look for Sales button
                sales_xpath = "//button[@type='button' and .//span[normalize-space(text())='Sales']]"
                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, sales_xpath)),
                )
                logger.info(
                    f"      ✓ Sales button found (New UI) - email sent successfully",
                )
                logger.info(f"  ✓ Email sent successfully on attempt {attempt}")
                return True

            except TimeoutException:
                try:
                    # OLD UI VALIDATION: Look for Business button
                    business_xpath = "//button[normalize-space(text())='Business']"
                    WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, business_xpath)),
                    )
                    logger.info(
                        f"      ✓ Business button found (Old UI) - email sent successfully",
                    )
                    logger.info(f"  ✓ Email sent successfully on attempt {attempt}")
                    return True

                except TimeoutException:
                    # Neither button found - send may have failed
                    logger.warning(f"      ✗ Neither Sales nor Business button found")
                    logger.warning(
                        f"      Email send validation failed on attempt {attempt}",
                    )
                    return False

        except Exception as e:
            # Unexpected error occurred
            logger.error(f"      ✗ Error on attempt {attempt}: {str(e)}")

        # Retry logic
        if attempt < max_retries:
            logger.info(f"      Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

        attempt += 1

    # All retries exhausted
    logger.error(f"  ✗ Failed to send email after {max_retries} attempts")
    return False


def has_email_button(browser, send_email_button_xpath: str) -> bool:
    """Check if email button is present.

    Args:
        browser: SeleniumBrowser instance
        send_email_button_xpath: XPath of the send email button

    Returns:
        bool: True if button is present, False otherwise
    """
    try:
        driver = browser.driver
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, send_email_button_xpath)),
        )
        logger.info("Send email button found")
        return True
    except TimeoutException:
        logger.info("Send email button not found")
        return False


def get_email_body(browser):
    """
    Validate email body salutation (Stannards-specific validation).

    This function performs client-specific validation of the email body text
    to ensure a proper salutation is present. Expected format: "Dear [Name]"

    Validation Logic:
    - Checks character at position 5 (after "Dear ")
    - Valid: Any letter character (e.g., "Dear John")
    - Invalid: Empty string, space, or comma (e.g., "Dear " or "Dear ,")

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        Exception: If no valid salutation found in email body
        TimeoutException: If email body or Cancel button not found within 5 seconds

    Note:
        - Uses 5-second timeout for element waits
        - Client-specific validation (Stannards only)
        - Automatically cancels email dialog on validation failure
    """
    driver = browser.driver

    # ACTION 1: Read Email Body Text
    # Purpose: Extract email message content for validation
    logger.info("    Action 1: Reading email body text")
    email_body_xpath = (
        "//div[@id='send-email-mfe-root']//textarea[@id='messageTextEditor']"
    )
    email_body_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, email_body_xpath)),
    )
    email_body = email_body_ele.get_attribute("value") or email_body_ele.text
    logger.info(f"      Email body length: {len(email_body)} characters")

    # ACTION 2: Validate Salutation
    # Purpose: Check that position 5 contains a valid name character
    # Expected format: "Dear [Name]" where position 5 is first letter of name
    salutation_first_letter = email_body[5:6] if len(email_body) > 5 else ""
    logger.info(f"      Character at position 5: '{salutation_first_letter}'")

    # Check if salutation is valid
    if (
        salutation_first_letter == ""
        or salutation_first_letter == " "
        or salutation_first_letter == ","
    ):
        # Invalid salutation - cancel and raise exception
        logger.warning("      ✗ Invalid salutation detected")
        logger.warning(f"         Expected: Letter at position 5")
        logger.warning(f"         Found: '{salutation_first_letter}'")

        # ACTION 3: Click Cancel Button
        # Purpose: Close email dialog since validation failed
        cancel_button_xpath = (
            "//div[@id='send-email-mfe-root']//button[normalize-space(text())='Cancel']"
        )
        cancel_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, cancel_button_xpath)),
        )
        safe_click(driver, cancel_button_ele, "Cancel button")
        logger.info("      ✓ Cancel button clicked - email dialog closed")
        raise Exception("No salutation found in Xero Invoice")

    logger.info(
        f"      ✓ Valid salutation found (starts with '{salutation_first_letter}')",
    )


def validate_email(browser):
    """
    Validate that email address is present in the invoice email dialog.

    This function checks that the invoice has a valid recipient email address
    before attempting to send. If no email is found, it cancels the email
    dialog and raises an exception.

    Process:
    1. Check for email address in email dialog (must contain '@' and '.')
    2. If not found: Click Cancel button and raise exception
    3. If found: Validation passes

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        Exception: If no valid email address found in the email dialog
        TimeoutException: If Cancel button not found within 5 seconds

    Note:
        - Uses 5-second timeout for element waits
        - Delegates to has_email_address() for actual validation
        - Automatically cancels email dialog on validation failure
    """
    logger.info("  Checking for valid email address in email dialog")

    # Check if email address is present
    if not has_email_address(browser):
        # No email address found - cancel and raise exception
        logger.warning("  ✗ No email address found - canceling email dialog")
        driver = browser.driver

        # ACTION: Click Cancel Button
        # Purpose: Close email dialog since validation failed
        cancel_button_present = (
            "//div[@id='send-email-mfe-root']//button[normalize-space(text())='Cancel']"
        )
        cancel_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, cancel_button_present)),
        )
        safe_click(driver, cancel_button_ele, "Cancel button")
        logger.info("  ✓ Cancel button clicked - email dialog closed")
        raise Exception("No email address found in Xero Invoice")

    logger.info("  ✓ Valid email address found")


def has_email_address(browser) -> bool:
    """Check if email address is present.

    Args:
        browser: SeleniumBrowser instance

    Returns:
        bool: True if email address found, False otherwise
    """
    try:
        driver = browser.driver
        email_address_xpath = "//div[@id='send-email-mfe-root']//span[contains(text(), '@') and contains(text(), '.')]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, email_address_xpath)),
        )
        logger.info("Email address found")
        return True
    except TimeoutException:
        logger.info("Email address not found")
        return False


def update_invoice(browser):
    """
    Update invoice and prepare for email sending.

    This function handles two different scenarios based on invoice status:

    PATH A (Invoice Requires Update):
    - If 'Update' button exists: Click Update > More > Email
    - Used when invoice has been modified and needs saving first

    PATH B (Invoice Ready to Approve):
    - If no 'Update' button: Click 'Approve & Email' directly
    - Used when invoice is ready for approval without modifications

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        TimeoutException: If required buttons are not found within 5 seconds

    Note:
        - Uses 5-second timeout for all element waits
        - Automatically determines correct path based on button availability
        - Opens email dialog regardless of path taken
    """
    driver = browser.driver
    update_button_xpath = (
        "//button[@type='button' and normalize-space(text())='Update']"
    )
    update_more_option_xpath = (
        "//button[@aria-label='More invoice options' and @type='button']/div"
    )
    email_option_xpath = (
        "//span[@class='xui-pickitem--text' and normalize-space(text())='Email']"
    )
    approval_and_email_xpath = (
        "//button[@type='button' and normalize-space(text())='Approve &amp; email']"
    )

    # Check which path to take based on button availability
    if has_update_button(browser, update_button_xpath):
        # ===== PATH A: UPDATE FLOW =====
        # Invoice has modifications that need to be saved first
        logger.info("  Path A: Invoice requires update before emailing")

        # ACTION 1: Click Update Button
        # Purpose: Save invoice modifications
        update_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, update_button_xpath)),
        )
        safe_click(driver, update_button_ele, "Update button")
        logger.info("    ✓ Update button clicked - invoice saved")

        # ACTION 2: Click More Options Menu
        # Purpose: Open dropdown menu with additional invoice actions
        more_option_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, update_more_option_xpath)),
        )
        safe_click(driver, more_option_ele, "More option button")
        logger.info("    ✓ More options menu opened")

        # ACTION 3: Click Email Option
        # Purpose: Open email dialog from the More options menu
        email_option_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, email_option_xpath)),
        )
        safe_click(driver, email_option_ele, "Email option")
        logger.info("    ✓ Email option selected - email dialog opened")

    else:
        # ===== PATH B: DIRECT APPROVE & EMAIL =====
        # Invoice is ready for approval without modifications
        logger.info("  Path B: Invoice ready for direct approval and email")

        # ACTION: Click Approve & Email Button
        # Purpose: Approve invoice and open email dialog in one action
        approval_and_email_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, approval_and_email_xpath)),
        )
        safe_click(driver, approval_and_email_ele, "Approve and email button")
        logger.info("    ✓ Approve & Email button clicked - email dialog opened")


def has_update_button(browser, update_button_xpath: str) -> bool:
    """Check if update button is present.

    Args:
        browser: SeleniumBrowser instance
        update_button_xpath: XPath of the update button

    Returns:
        bool: True if button is present, False otherwise
    """
    try:
        driver = browser.driver
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, update_button_xpath)),
        )
        logger.info("Update button found")
        return True
    except TimeoutException:
        logger.info("Update button not found")
        return False


def print_invoice(browser, download_directory_path: str, invoice_dir: str):
    """
    Print invoice to PDF and validate contents.

    This function performs the complete PDF printing and validation workflow:
    1. Opens More options menu
    2. Clicks Print PDF
    3. Saves PDF to specified directory
    4. Validates PDF contains required information (email, BPAY reference)

    Args:
        browser: SeleniumBrowser instance with driver attribute
        download_directory_path: Directory path for downloading invoice PDF
        invoice_dir: Directory for storing invoice files

    Raises:
        TimeoutException: If UI elements are not found within 5 seconds
        Exception: If PDF validation fails (missing email or BPAY reference)

    Note:
        - Uses Windows automation (robocorp.windows) for file save dialog
        - Creates invoice directory if it doesn't exist
        - Validates PDF content using regex patterns
    """
    driver = browser.driver

    # ACTION 1: Open More Options Menu
    # Purpose: Access additional invoice actions including Print PDF
    logger.info("    Action 1: Opening More options menu")
    more_xpath = "//button[@type='button' and @aria-label='More invoice options']/div"
    more_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, more_xpath)),
    )
    safe_click(driver, more_ele, "More button")
    logger.info("      ✓ More options menu opened")

    # ACTION 2: Click Print PDF Option
    # Purpose: Trigger PDF generation and download
    logger.info("    Action 2: Clicking Print PDF option")
    print_button_xpath = (
        "//span[@class='xui-pickitem--text' and normalize-space(text())='Print PDF']"
    )
    print_button_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, print_button_xpath)),
    )
    safe_click(driver, print_button_ele, "Print PDF button")
    logger.info("      ✓ Print PDF clicked - save dialog opening")

    # ACTION 3: Ensure Directory Exists
    # Purpose: Create invoice storage directory if not present
    logger.info("    Action 3: Checking invoice directory")
    if not os.path.exists(invoice_dir):
        os.makedirs(invoice_dir)
        logger.info(f"      ✓ Created invoice directory: {invoice_dir}")
    else:
        logger.info(f"      ✓ Invoice directory exists: {invoice_dir}")

    # ACTION 4: Save PDF File
    # Purpose: Handle file save dialog and save PDF to specified path
    # Function: save_file(download_directory_path)
    # - Uses Windows automation to interact with save dialog
    # - Returns full path to saved PDF file
    logger.info("    Action 4: Saving PDF file via Windows dialog")
    out_invoice_file_name = save_file(download_directory_path)
    logger.info(f"      ✓ PDF saved to: {out_invoice_file_name}")

    # ACTION 5: Validate PDF Contents
    # Purpose: Ensure PDF contains required information
    # Function: validate_invoice_pdf(out_invoice_file_name)
    # - Reads PDF text content
    # - Validates email address exists (using regex)
    # - Validates BPAY reference exists (using regex)
    # - Throws exception if either validation fails
    logger.info("    Action 5: Validating PDF contents")
    validate_invoice_pdf(out_invoice_file_name)
    logger.info("      ✓ PDF validation passed (email and BPAY found)")


def remove_section_from_invoice(browser):
    """Remove specific section from invoice (Stannards specific).

    Args:
        browser: SeleniumBrowser instance
    """
    # Check the delete button
    if has_delete_button(browser):
        driver = browser.driver
        delete_button_xpath = "//table//tr[contains(normalize-space(.), 'Inventory itemDescriptionProvision of accounting services including the following:')]//button[@type='button' and @aria-label='Remove' and normalize-space(@aaname)='Remove']"
        delete_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, delete_button_xpath)),
        )
        safe_click(driver, delete_button_ele, "Delete button")
        logger.info("Clicked delete button")


def has_delete_button(browser) -> bool:
    """Check if delete button is present.

    Args:
        browser: SeleniumBrowser instance

    Returns:
        bool: True if button is present, False otherwise
    """
    try:
        driver = browser.driver
        delete_button_xpath = "//table//tr[contains(normalize-space(.), 'Inventory itemDescriptionProvision of accounting services including the following:')]//button[@type='button' and @aria-label='Remove' and normalize-space(@aaname)='Remove']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, delete_button_xpath)),
        )
        logger.info("Delete button found")
        return True
    except TimeoutException:
        logger.info("Delete button not found")
        return False


def no_invoice_date_present(browser):
    """Handle case when invoice date field is not present.

    Args:
        browser: SeleniumBrowser instance
    """
    # Check invoice date
    if not has_invoice_date_input(browser):
        driver = browser.driver

        # Click more options
        more_option_xpath = (
            "//button[@type='button' and @aria-label='More invoice options']/div"
        )
        more_option_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, more_option_xpath)),
        )
        safe_click(driver, more_option_ele, "More button")
        logger.info("Clicked More button")

        # Click edit button
        edit_option_xpath = (
            "//span[@class='xui-pickitem--text' and normalize-space(text())='Edit']"
        )
        edit_option_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, edit_option_xpath)),
        )
        safe_click(driver, edit_option_ele, "Edit button")
        logger.info("Clicked Edit button")


def has_invoice_date_input(browser) -> bool:
    """Check if invoice date input box is present.

    Args:
        browser: SeleniumBrowser instance

    Returns:
        bool: True if input is present, False otherwise
    """
    try:
        driver = browser.driver
        invoice_date_xpath = "//input[@id='InvoiceDateInput' and @aaname='Issue date']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_date_xpath)),
        )
        logger.info("Invoice date found")
        return True
    except TimeoutException:
        logger.info("Invoice date not found")
        return False


def read_invoice_pdf(pdf_path: str) -> str:
    """Read PDF text using RPA.PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        str: Extracted text from PDF
    """
    try:
        text = pdf.get_text_from_pdf(pdf_path, pages="ALL")
        full_text = "\n".join(text.values())
        return full_text
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}")
        return ""


def validate_invoice_pdf(pdf_path: str):
    """Validate invoice PDF for Email and BPAY Ref patterns.

    Args:
        pdf_path: Path to the PDF file

    Raises:
        Exception: If PDF is empty, unreadable, or missing required patterns
    """
    text = read_invoice_pdf(pdf_path)
    if not text:
        raise Exception("Empty or unreadable PDF file")

    # --- 1. Email Regex ---
    EMAIL_REGEX = r"""((?>[a-zA-Z\d!#$%&'*+\-\/=?^_`{|}~]+\x20*|"((?=[\x01-\x7f])[^"\\]|\\[\x01-\x7f])*"\x20*)*
    (?<angle><))?((?!\.)(?>\.?[a-zA-Z\d!#$%&'*+\-\/=?^_`{|}~]+)+|"((?=[\x01-\x7f])[^"\\]|\\[\x01-\x7f])*")@
    (((?!-)[a-zA-Z\d\-]+(?<!-)\.)+[a-zA-Z]{2,}|\[(((?(?<!\[)\.)(25[0-5]|2[0-4]\d|[01]?\d?\d)){4}|
    [a-zA-Z\d\-]*[a-zA-Z\d]:((?=[\x01-\x7f])[^\\\[\]]|\\[\x01-\x7f])+)\])(?(angle)>)+"""

    emails = re.findall(EMAIL_REGEX, text, flags=re.IGNORECASE | re.VERBOSE)
    if not emails:
        raise Exception("No email address found in Xero Invoice")
    logger.info("Email found in invoice PDF")

    # --- 2. BPAY Ref Regex ---
    BPAY_REGEX = r"(?s)By\s+BPAY.*\s*Ref:\s*\d+"
    bpay_ref = re.search(BPAY_REGEX, text, flags=re.IGNORECASE)
    if not bpay_ref:
        raise Exception("No BPAY Ref found in Xero Invoice")
    logger.info("BPAY Ref found in invoice PDF")


def save_file(download_directory_path: str) -> str:
    """Save invoice PDF using Windows automation.

    Args:
        download_directory_path: Directory path for downloading file

    Returns:
        str: Full path to the saved file
    """
    app = windows.find_window(f"regex:.*Xero | * - Google Chrome")
    app.find('control:"WindowControl" and name:"Save As" and path:"1"')
    find_input = app.find(
        'control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"',
    ).click()

    # Get the actual name
    actual_file_name = find_input.get_value() or ""
    file_path = os.path.normpath(
        os.path.join(download_directory_path, actual_file_name),
    )
    find_input.send_keys("{CTRL}a")
    find_input.send_keys("{DEL}")
    find_input.send_keys(file_path)
    time.sleep(2)
    app.find('control:"ButtonControl" and name:"Save"').click()

    try:
        save_confirm_popup = app.find(
            'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"',
            timeout=3,
        )
        save_confirm_popup.find(
            'control:"ButtonControl" and class:"CCPushButton" and name:"Yes"',
        ).click()
    except Exception:
        logger.info("No confirmation window present")

    return file_path


def has_approve_and_email_exist(browser) -> bool:
    """Check if approve and email button exists.

    Args:
        browser: SeleniumBrowser instance

    Returns:
        bool: True if button exists, False otherwise
    """
    try:
        driver = browser.driver
        approval_and_email_xpath = (
            "//button[@type='button' and normalize-space(text())='Approve & email']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, approval_and_email_xpath)),
        )
        logger.info("Approve & email button found")
        return True
    except TimeoutException:
        logger.info("Approve & email button not found")
        return False


def navigated_to_invoice(browser):
    """
    Navigate to the Invoices page (handles both new and old Xero UI).

    This function navigates to the Invoices list page by attempting to use
    the new Xero UI first, and falling back to the old UI if needed.

    Process Flow:
    - NEW UI: Sales button > Invoices link
    - OLD UI: Business button > Invoices link

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        TimeoutException: If navigation elements are not found in either UI version

    Note:
        - Uses 5-second timeout for all element waits
        - Automatically detects UI version and adjusts navigation accordingly
    """
    driver = browser.driver

    try:
        # ===== NEW XERO UI NAVIGATION =====
        logger.info("  Attempting to navigate using NEW Xero UI")

        # ACTION 1: Click Sales Button (New UI)
        # Purpose: Expand the Sales menu to reveal invoices, quotes, and other options
        sales_xpath = (
            "//button[@type='button' and .//span[normalize-space(text())='Sales']]"
        )
        sales_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, sales_xpath)),
        )
        safe_click(driver, sales_ele, "Sales button")
        logger.info("    ✓ Sales button clicked (New UI)")

        # ACTION 2: Click Invoices Link (New UI)
        # Purpose: Open the Invoices page showing all invoices for the organization
        invoice_xpath = (
            "//a[@role='link' and .//span[normalize-space(text())='Invoices']]"
        )
        invoice_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
        )
        safe_click(driver, invoice_ele, "Invoices link")
        logger.info("    ✓ Invoices link clicked (New UI)")
        logger.info("  Successfully navigated to Invoices page using NEW UI")

    except TimeoutException:
        # ===== OLD XERO UI NAVIGATION (FALLBACK) =====
        logger.info("  New UI elements not found - attempting OLD Xero UI navigation")

        # ACTION 1: Click Business Button (Old UI)
        # Purpose: Expand the Business menu to reveal accounting options
        business_xpath = "//button[normalize-space(text())='Business']"
        business_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, business_xpath)),
        )
        safe_click(driver, business_ele, "Business button")
        logger.info("    ✓ Business button clicked (Old UI)")

        # ACTION 2: Click Invoices Link (Old UI)
        # Purpose: Open the Invoices page showing all invoices
        invoices_tab_xpath = "//a[normalize-space(text())='Invoices']"
        invoices_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoices_tab_xpath)),
        )
        safe_click(driver, invoices_ele, "Invoices link")
        logger.info("    ✓ Invoices link clicked (Old UI)")
        logger.info("  Successfully navigated to Invoices page using OLD UI")


def navigated_to_home(browser):
    """
    Navigate to the Home/Dashboard page (handles both new and old Xero UI).

    This function navigates to the main landing page by attempting to use
    the new Xero UI first, and falling back to the old UI if needed.
    Provides a stable starting point before navigating to specific sections.

    Process Flow:
    - NEW UI: Home link
    - OLD UI: Dashboard button

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Raises:
        TimeoutException: If navigation elements are not found in either UI version

    Note:
        - Uses 5-second timeout for all element waits
        - Automatically detects UI version and adjusts navigation accordingly
    """
    driver = browser.driver

    try:
        # ===== NEW XERO UI NAVIGATION =====
        logger.info("  Attempting to navigate using NEW Xero UI")

        # ACTION: Click Home Link (New UI)
        # Purpose: Navigate to the main dashboard/home page
        home_xpath = "//a[.//span[normalize-space()='Home']]"
        home_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, home_xpath)),
        )
        safe_click(driver, home_ele, "Home button")
        logger.info("    ✓ Home button clicked (New UI)")
        logger.info("  Successfully navigated to Home page using NEW UI")

    except TimeoutException:
        # ===== OLD XERO UI NAVIGATION (FALLBACK) =====
        logger.info("  New UI elements not found - attempting OLD Xero UI navigation")

        # ACTION: Click Dashboard Button (Old UI)
        # Purpose: Navigate to the main dashboard page
        business_xpath = "//button[normalize-space(text())='Dashboard']"
        business_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, business_xpath)),
        )
        safe_click(driver, business_ele, "Dashboard button")
        logger.info("    ✓ Dashboard button clicked (Old UI)")
        logger.info("  Successfully navigated to Dashboard page using OLD UI")
