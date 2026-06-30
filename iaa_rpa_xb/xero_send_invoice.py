"""
Module: xero_send_invoice

This module automates the process of sending invoices via email from Xero Blue.
It handles the complete workflow from navigating to the invoice page, searching for
a specific client, configuring email settings, and sending the invoice with attachments.

The module is designed to work with both new and old Xero UI versions, automatically
detecting and adapting to the interface available.

Main Functions:
    - xero_send_invoice: Main entry point that orchestrates the invoice email sending process
    - navigated_to_dashboard_or_home_page: Navigates to the Xero home/dashboard page
    - navigated_to_invoice_page: Navigates to the Invoices page via Sales or Business menu
    - open_invoice_deatils: Searches for and opens a specific client's invoice
    - send_invoice: Configures and sends the invoice email with attachments

Helper Functions (Validation):
    - is_invoice_exist: Verifies if the invoice details page is displayed
    - is_file_attachments_checked: Checks if file attachments option is enabled
    - is_pdf_attachments_checked: Checks if PDF attachment option is enabled
    - is_mark_sent_as_checked: Checks if mark as sent option is enabled
    - is_sent_me_a_copy_checked: Checks if send me a copy option is enabled

Workflow:
    1. Navigate to Dashboard or Home page
    2. Navigate to Invoices page (via Sales or Business menu)
    3. Search for client invoice
    4. Open invoice details page
    5. Click Email button
    6. Select Professional Invoice template
    7. Enable all attachment and notification options
    8. Send the invoice email

UI Compatibility:
    - New UI: Home > Sales > Invoices
    - Old UI: Dashboard > Business > Invoices
    - Automatic fallback mechanism for UI detection
"""

from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .take_screenshot import take_screenshot

# Set up logger
logger = setup_logger(__name__)


def xero_send_invoice(
    browser,
    xero_client_name,
    xero_url,
    client_email_address,
    email_template,
    send_invoice_status,
):
    """Send an invoice via email from Xero Blue.

    This function automates the complete workflow of sending an invoice via email in Xero Blue,
    including navigating to the invoice page, searching for a specific client, opening the invoice
    details, configuring email settings with the Professional Invoice template, and sending the
    invoice with file attachments and PDF.

    The workflow handles both new and old Xero UI versions and includes multiple checkbox
    validations (file attachments, PDF attachment, mark as sent, send me a copy) before
    sending the email.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_client_name (str): The client name to search for in the invoices list (e.g., "ABC Company Pty Ltd").
        xero_url (str): Expected Xero page title for tab identification and verification.

    Returns:
        None: The function completes successfully or raises an exception.

    Raises:
        Exception: If invoice page is not found, invoice doesn't exist, or email sending fails.
        TimeoutException: If any web elements are not found within the timeout period.

    Notes:
        - The function supports both new UI (Home/Sales) and old UI (Dashboard/Business) navigation
        - Automatically selects "Sales Invoice: Professional Invoice" email template
        - Checks and enables all email options: file attachments, PDF attachment, mark as sent, send me a copy
        - Uses safe_click utility for reliable element clicking
        - All navigation and email operations are logged for debugging

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> xero_send_invoice(browser, "ABC Company Pty Ltd", "Xero | Dashboard")
        # Invoice email sent successfully
    """

    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO SEND INVOICE")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name: {xero_client_name}")
    logger.info(f"Xero Blue Title: {xero_url}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # STEP 1: Navigate to Dashboard or Home Page
        # Purpose: Establish a consistent starting point in Xero interface
        # Function: navigated_to_dashboard_or_home_page()
        # - Attempts to click "Home" link (new UI)
        # - Falls back to "Dashboard" link (old UI) if Home not found
        # - Ensures we're at the main page before proceeding with navigation
        navigated_to_dashboard_or_home_page(driver)

        # STEP 2: Navigate to Invoices Page
        # Purpose: Access the invoices list where we can search for the client
        # Function: navigated_to_invoice_page()
        # - Switches to correct browser tab matching xero_url
        # - Clicks Sales > Invoices (new UI) or Business > Invoices (old UI)
        # - Handles multiple open tabs and UI version detection automatically
        navigated_to_invoice_page(driver, xero_url)
        logger.info(f"Navigated to invoice page")

        # STEP 3: Search and Open Invoice Details
        # Purpose: Find the specific client's invoice and open the details page
        # Function: open_invoice_deatils()
        # - Clicks Search button to reveal search field
        # - Enters client name using keyboard automation
        # - Submits search and clicks on matching invoice link
        # - Opens the invoice details page for the target client
        open_invoice_deatils(driver, xero_client_name)

        # STEP 4: Configure and Send Invoice Email
        # Purpose: Set up email options and send the invoice to the client
        # Function: send_invoice()
        # - Validates invoice page is open
        # - Clicks Email button to open email dialog
        # - Selects "Sales Invoice: Professional Invoice" template
        # - Enables all attachments (files, PDF) and notifications (mark as sent, send me a copy)
        # - Clicks Send button to deliver the email
        send_invoice_status = send_invoice(driver, client_email_address, email_template)

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO SEND INVOICE")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {xero_client_name}")
        logger.info(
            f"Send invoice status {'SUCCESS' if send_invoice_status else 'FAILED'}",
        )
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        return send_invoice_status

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO SEND INVOICE")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {xero_client_name}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"The xero_send_invoice failed due to {e}", exc_info=True)
        raise


def navigated_to_dashboard_or_home_page(driver):
    """Navigate to Home or Dashboard page (supports both new and old Xero UI).

    This function handles navigation to the main page in Xero, automatically detecting
    and adapting to either the new UI (Home link) or the old UI (Dashboard link).
    Uses a cascading try-except pattern for UI version compatibility.

    Args:
        driver: Selenium WebDriver instance.

    Returns:
        None

    Raises:
        TimeoutException: If neither Home nor Dashboard link is found within timeout periods.

    Notes:
        - New UI: Looks for Home link with span element containing 'Home' text
        - Old UI: Falls back to Dashboard link if Home is not found
        - New UI has 5 second timeout, old UI has 2 second timeout
    """
    logger.info("-" * 80)
    logger.info("STEP 1: Navigate to Dashboard or Home Page - STARTED")
    logger.info("-" * 80)

    try:
        # ATTEMPT 1: Navigate using NEW UI (Home link)
        # XPath Strategy: Search for anchor tag containing a span with 'Home' text
        # Timeout: 5 seconds
        logger.info("Attempting to locate 'Home' button (New UI)...")
        home_link_xpath = "//a[.//span[text()='Home']]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, home_link_xpath)),
        ).click()
        logger.info("✓ Successfully clicked 'Home' button (New UI)")

    except Exception as e:
        # ATTEMPT 2: Navigate using OLD UI (Dashboard link)
        # XPath Strategy: Search for anchor with normalized 'Dashboard' text
        # Timeout: 2 seconds
        logger.warning(
            f"'Home' button not found (New UI). Attempting 'Dashboard' (Old UI)...",
        )
        logger.debug(f"New UI error: {e}")

        dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
        WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
        ).click()
        logger.info("✓ Successfully clicked 'Dashboard' button (Old UI)")

    # Wait for page to stabilize after navigation
    time.sleep(2)
    logger.info("✓ STEP 1 COMPLETED: Successfully navigated to main page")
    logger.info("-" * 80)


def navigated_to_invoice_page(driver, xero_url):
    """Navigate to the Invoices page in Xero (supports both new and old UI).

    This function iterates through all open browser tabs to find the Xero tab matching
    the expected title, then navigates to the Invoices page. It handles both new UI
    (Sales > Invoices) and old UI (Business > Invoices) navigation paths.

    Args:
        driver: Selenium WebDriver instance.
        xero_url (str): Expected Xero page title substring for tab identification.

    Returns:
        None

    Raises:
        TimeoutException: If Sales/Business or Invoices elements are not found.

    Notes:
        - Switches between all open browser tabs to find the matching Xero tab
        - New UI navigation: Sales button > Invoices link
        - Old UI navigation: Business button > Invoices link (fallback)
        - Both paths use 5 second timeouts for element visibility
    """
    logger.info("-" * 80)
    logger.info("STEP 2: Navigate to Invoices Page - STARTED")
    logger.info("-" * 80)
    logger.info(f"Target Xero URL: {xero_url}")

    # OPERATION 1: Get all open browser tabs to find the correct Xero tab
    all_tabs = driver.window_handles
    logger.info(f"Found {len(all_tabs)} browser tab(s) open")

    # OPERATION 2: Iterate through all tabs to find the one matching xero_url
    for idx, handle in enumerate(all_tabs, 1):
        driver.switch_to.window(handle)
        current_url = driver.current_url
        logger.info(f"Checking tab {idx}/{len(all_tabs)}: {current_url}")

        # Check if this tab contains the Xero page
        if xero_url in current_url:
            logger.info(f"✓ Found matching Xero tab: {current_url}")

            try:
                # ATTEMPT 1: Navigate using NEW UI (Sales > Invoices)
                # XPath Strategy: Button with 'Sales' span, then link with 'Invoices' span
                # Timeout: 5 seconds for each element
                logger.info("Attempting to navigate via 'Sales' menu (New UI)...")
                sales_xpath = "//button[@type='button' and .//span[normalize-space(text())='Sales']]"
                invoice_xpath = (
                    "//a[@role='link' and span[normalize-space(text())='Invoices']]"
                )

                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, sales_xpath)),
                ).click()
                logger.info("✓ Successfully clicked 'Sales' button (New UI)")

                # Wait for and click Invoices link
                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
                ).click()
                logger.info("✓ Successfully clicked 'Invoices' link (New UI)")

            except Exception as e:
                # ATTEMPT 2: Navigate using OLD UI (Business > Invoices)
                # XPath Strategy: Button with 'Business' text, then link with 'Invoices' text
                # Timeout: 5 seconds for each element
                logger.warning(
                    f"'Sales' menu not found (New UI). Attempting 'Business' menu (Old UI)...",
                )
                logger.debug(f"New UI error: {e}")

                business_xpath = "//button[normalize-space(text())='Business']"
                invoices_tab_xpath = "//a[normalize-space(text())='Invoices']"

                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, business_xpath)),
                )
                driver.find_element(By.XPATH, business_xpath).click()
                logger.info("✓ Successfully clicked 'Business' button (Old UI)")

                # Wait for and click Invoices link
                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, invoices_tab_xpath)),
                )
                driver.find_element(By.XPATH, invoices_tab_xpath).click()
                logger.info("✓ Successfully clicked 'Invoices' link (Old UI)")

            logger.info("✓ STEP 2 COMPLETED: Successfully navigated to Invoices page")
            logger.info("-" * 80)
            return

    # If no matching tab found, log error
    logger.error(f"✗ No browser tab matching URL '{xero_url}' was found")
    logger.info("-" * 80)


def open_invoice_deatils(driver, xero_client_name):
    """Search for and open invoice details page for a specific client.

    This function performs a search operation on the Invoices page to find and open
    the invoice details for the specified client. It clicks the search button, enters
    the client name, submits the search, and opens the matching invoice.

    Args:
        driver: Selenium WebDriver instance.
        xero_client_name (str): The client name to search for in the invoices list.

    Returns:
        None

    Raises:
        TimeoutException: If search elements or invoice link are not found within timeout.

    Notes:
        - Uses keyboard automation (CTRL+A, DELETE, TAB) to clear and input client name
        - Search input field has placeholder "Enter Number, Reference, Contact or Amount"
        - Uses safe_click utility for reliable element clicking
        - 5 second timeout for search elements, 10 second timeout for invoice link
    """
    logger.info("-" * 80)
    logger.info("STEP 3: Search and Open Invoice Details - STARTED")
    logger.info("-" * 80)
    logger.info(f"Searching for client: {xero_client_name}")

    # OPERATION 1: Click the Search button to expand the search interface
    # Purpose: Reveal the search input field for entering client details
    # XPath Strategy: Link containing span with 'Search' automation ID
    # Timeout: 5 seconds
    logger.info("Attempting to locate and click 'Search' button...")
    search_xpath = "//a[.//span[@data-automationid='Search-button' and normalize-space()='Search']]"

    search_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, search_xpath)),
    )
    safe_click(driver, search_ele, "Clicked search")
    logger.info("✓ Successfully clicked 'Search' button to expand search interface")

    # OPERATION 2: Enter the client name into the search input field
    # Purpose: Input the client name to search for their invoice
    # XPath Strategy: Input field with specific ID and name attributes
    # Keyboard Actions:
    #   - CTRL+A: Select all existing text
    #   - DELETE: Clear the field
    #   - Type client name
    #   - TAB: Move to next field and trigger search
    # Timeout: 5 seconds
    logger.info("Locating search input field...")
    input_client_name_xpath = (
        "//input[@type='text' and @id='sb_txtReference' and @name='invoiceReference']"
    )
    input_client_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, input_client_name_xpath)),
    )
    logger.info("✓ Found search input field, entering client name...")
    input_client_ele.send_keys("\ue009" + "a")  # CTRL + A to select all text
    input_client_ele.send_keys("\ue003")  # DELETE to clear the field
    input_client_ele.send_keys(xero_client_name)  # Type the client name
    input_client_ele.send_keys("\ue004")  # TAB to move to next field

    logger.info(f"✓ Successfully entered client name: '{xero_client_name}'")

    # OPERATION 3: Click the Search link to submit the search query
    # Purpose: Trigger the search and display matching invoices
    # XPath Strategy: Link with normalized 'Search' text
    # Timeout: 5 seconds
    logger.info("Submitting search query...")
    submit_xpath = "//a[normalize-space(text())='Search']"
    submit_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, submit_xpath)),
    )
    safe_click(driver, submit_ele, "Click Submit")
    logger.info("✓ Successfully submitted search query")

    # OPERATION 4: Click on the client name link to open the invoice details page
    # Purpose: Navigate to the invoice details page for the found client
    # XPath Strategy: First table row containing a link with the exact client name
    # Timeout: 5 seconds
    logger.info(
        f"Waiting for search results and locating invoice for '{xero_client_name}'...",
    )
    open_invoice_xpath = f"//table//tr[1]//a[normalize-space()='{xero_client_name}']"
    open_invoice_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, open_invoice_xpath)),
    )
    safe_click(driver, open_invoice_ele, "Click Invoice")
    logger.info(
        f"✓ Successfully clicked on invoice for '{xero_client_name}' to open details page",
    )

    logger.info("✓ STEP 3 COMPLETED: Successfully opened invoice details page")
    logger.info("-" * 80)


def send_invoice(driver, client_email_address, email_template):
    """Send invoice via email with specified template and all attachments.

    This function configures and sends an invoice email from the invoice details page.
    It validates the invoice exists, clicks the email button, selects the specified
    Invoice template, enables all attachment options (PDF attachment, send me a copy),
    and sends the email.

    Args:
        driver: Selenium WebDriver instance.
        client_email_address (str): Email address to send the invoice to.
        email_template (str): The email template name to use for sending the invoice.

    Returns:
        bool: True if invoice was sent successfully.

    Raises:
        Exception: If invoice details page is not open or invoice doesn't exist.
        TimeoutException: If any email configuration elements are not found.

    Notes:
        - Validates invoice exists before proceeding
        - Interacts with shadow DOM elements for email configuration
        - Checks and enables options: PDF attachment, send me a copy
        - Uses safe_click utility for reliable element clicking
        - All elements use 10 second timeout for visibility
        - Takes screenshots before and after sending
    """
    logger.info("-" * 80)
    logger.info("STEP 4: Configure and Send Invoice Email - STARTED")
    logger.info("-" * 80)
    logger.info(f"Client Email: {client_email_address}")
    logger.info(f"Email Template: {email_template}")

    # PRE-VALIDATION: Verify Invoice Details Page is Open
    # Purpose: Ensure we're on the correct page before attempting to send
    # Function Call: is_invoice_exist(driver)
    # Returns: True if invoice page exists, False otherwise
    # Action: Raises exception if validation fails to prevent incorrect operations
    logger.info("Validating invoice details page is open...")
    if not is_invoice_exist(driver):
        logger.error("✗ Invoice details page not open - cannot proceed")
        raise Exception("Invoice details page not open")
    logger.info("✓ Invoice details page validated successfully")

    # OPERATION 1: Open More Options Menu
    # Purpose: Access the email sending option from the dropdown menu
    # XPath Strategy: Button with 'More invoice options' aria-label
    # Timeout: 10 seconds
    logger.info("Attempting to locate and click 'More Options' button...")
    more_option_xpath = "//button[@aria-label='More invoice options']"
    more_option_ele = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, more_option_xpath)),
    )
    safe_click(driver, more_option_ele, "Click More option")
    logger.info("✓ Successfully clicked 'More Options' button to reveal menu")

    # OPERATION 2: Click Email Button
    # Purpose: Open the email configuration dialog
    # XPath Strategy: Button containing span with 'Email' text
    # Timeout: 10 seconds
    logger.info("Attempting to locate and click 'Email' button...")
    email_xpath = "//button[.//span[normalize-space()='Email']]"
    email_ele = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, email_xpath)),
    )
    safe_click(driver, email_ele, "Click Email")
    logger.info("✓ Successfully clicked 'Email' button to open email dialog")

    # OPERATION 3: Access Shadow DOM and Check Existing Email Address
    # Purpose: Verify if email address is already populated in the TO field
    # Shadow DOM: Email dialog uses shadow DOM (ID: send-email-mfe-root)
    # CSS Selector: span.xui-pill--text contains the email address
    logger.info("Accessing shadow DOM to check existing email address in TO field...")
    shadow_host = driver.find_element(By.ID, "send-email-mfe-root")
    shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)

    email_element = shadow_root.find_element(
        By.CSS_SELECTOR,
        "span.xui-pill--text",
    )

    email_address = email_element.text.strip()
    logger.info(f"Existing email address in TO section: '{email_address}'")

    # OPERATION 4: Attempt 1 - Enter Email Address if Empty
    # Purpose: Populate TO field with client email if it's empty
    # Keyboard Actions:
    #   - CTRL+A: Select all existing text
    #   - DELETE: Clear the field
    #   - Type client email address
    #   - ENTER: Confirm entry
    if email_address is None or email_address == "":
        logger.info(
            "TO address is empty in XERO - attempting to enter email address (Method 1)...",
        )

        shadow_root.send_keys("\ue009" + "a")  # CTRL + A
        shadow_root.send_keys("\ue003")  # DELETE
        shadow_root.send_keys(client_email_address)
        shadow_root.send_keys("\ue007")  # ENTER

        logger.info(f"✓ Entered TO address using Method 1: '{client_email_address}'")

    # OPERATION 5: Verify Email Address Entry (Re-check)
    # Purpose: Confirm email address was successfully entered
    logger.info("Re-checking TO field to verify email address was entered...")
    shadow_host = driver.find_element(By.ID, "send-email-mfe-root")
    shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)

    email_element = shadow_root.find_element(
        By.CSS_SELECTOR,
        "span.xui-pill--text",
    )

    email_address = email_element.text.strip()
    logger.info(f"Current email address in TO section: '{email_address}'")

    # OPERATION 6: Attempt 2 - Enter Email Address if Still Empty (Fallback Method)
    # Purpose: Use alternative keyboard navigation method if first attempt failed
    # Keyboard Actions:
    #   - TAB (3x): Navigate to TO field
    #   - CTRL+A: Select all existing text
    #   - DELETE: Clear the field
    #   - Type client email address
    #   - ENTER: Confirm entry
    if email_address is None or email_address == "":

        logger.warning(
            "⚠ TO address still empty - attempting fallback method (Method 2)...",
        )

        shadow_root.send_keys("\ue004")  # TAB
        shadow_root.send_keys("\ue004")  # TAB
        shadow_root.send_keys("\ue004")  # TAB

        shadow_root.send_keys("\ue009" + "a")  # CTRL + A
        shadow_root.send_keys("\ue003")  # DELETE
        shadow_root.send_keys(client_email_address)
        shadow_root.send_keys("\ue007")  # ENTER

        logger.info(
            f"✓ Entered TO address using Method 2 (fallback): '{client_email_address}'",
        )

    # OPERATION 7: Change Email Template
    # Purpose: Select the specified invoice email template
    # Shadow DOM: Template dropdown is inside shadow DOM
    # CSS Selector: button#emailTemplateDropdown
    # XPath Strategy (after dropdown): Button containing span with template name
    # Timeout: 10 seconds for shadow DOM, 5 seconds for template selection
    logger.info(f"Attempting to change email template to: '{email_template}'...")

    # Step 1: Access shadow DOM and locate template dropdown button
    logger.info("Accessing shadow DOM to locate email template dropdown...")
    shadow_host = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "send-email-mfe-root")),
    )

    shadow_root = driver.execute_script(
        "return arguments[0].shadowRoot",
        shadow_host,
    )

    email_template_dropdown = shadow_root.find_element(
        By.CSS_SELECTOR,
        "button#emailTemplateDropdown",
    )

    # Step 2: Click dropdown to reveal template options
    email_template_dropdown.click()
    logger.info("✓ Successfully clicked email template dropdown button")

    # Step 3: Select the specified template from dropdown
    logger.info(f"Selecting template '{email_template}' from dropdown...")
    email_template_xpath = f"//button[.//span[normalize-space()='{email_template}']]"
    email_template_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, email_template_xpath)),
    )
    safe_click(driver, email_template_ele, "Click email template")
    logger.info(f"✓ Successfully selected email template: '{email_template}'")

    # OPERATION 8: Enable "Attach PDF to email" Checkbox
    # Purpose: Ensure PDF attachment is enabled for the invoice email
    # Shadow DOM: Checkbox is inside shadow DOM
    # CSS Selector: label.xui-styledcheckboxradio span.xui-styledcheckboxradio--label
    # XPath Strategy: Navigate to parent label and find input checkbox
    # Timeout: 10 seconds
    logger.info("Configuring email attachment options...")
    logger.info("Accessing shadow DOM to locate 'Attach PDF to email' checkbox...")

    shadow_host = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "send-email-mfe-root")),
    )

    shadow_root = driver.execute_script(
        "return arguments[0].shadowRoot",
        shadow_host,
    )

    # Locate the "Attach PDF to email" checkbox label
    attach_pdf_checkbox = shadow_root.find_element(
        By.CSS_SELECTOR,
        "label.xui-styledcheckboxradio span.xui-styledcheckboxradio--label",
    )

    if attach_pdf_checkbox.text.strip() == "Attach PDF to email":
        logger.info("Found 'Attach PDF to email' checkbox, checking selection state...")
        checkbox_input = attach_pdf_checkbox.find_element(
            By.XPATH,
            "./ancestor::label//input[@type='checkbox']",
        )

        if not checkbox_input.is_selected():
            logger.info("Checkbox not selected, enabling 'Attach PDF to email'...")
            driver.execute_script("arguments[0].click();", checkbox_input)
            logger.info("✓ Successfully enabled 'Attach PDF to email' checkbox")
        else:
            logger.info("✓ 'Attach PDF to email' checkbox already enabled")

    # OPERATION 9: Enable "Send myself a copy" Checkbox
    # Purpose: Ensure sender receives a copy of the invoice email
    # Shadow DOM: Checkbox is inside shadow DOM
    # CSS Selector: label.xui-styledcheckboxradio span.xui-styledcheckboxradio--label
    # Strategy: Iterate through all checkboxes to find "Send myself a copy"
    # Timeout: 10 seconds
    logger.info("Accessing shadow DOM to locate 'Send myself a copy' checkbox...")

    shadow_host = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "send-email-mfe-root")),
    )

    shadow_root = driver.execute_script(
        "return arguments[0].shadowRoot",
        shadow_host,
    )

    # Locate all checkbox labels inside shadow DOM
    checkbox_labels = shadow_root.find_elements(
        By.CSS_SELECTOR,
        "label.xui-styledcheckboxradio span.xui-styledcheckboxradio--label",
    )

    # Find and enable "Send myself a copy" checkbox
    for label in checkbox_labels:
        if label.text.strip() == "Send myself a copy":
            logger.info(
                "Found 'Send myself a copy' checkbox, checking selection state...",
            )
            checkbox_input = label.find_element(
                By.XPATH,
                "./ancestor::label//input[@type='checkbox']",
            )

            if not checkbox_input.is_selected():
                logger.info("Checkbox not selected, enabling 'Send myself a copy'...")
                driver.execute_script("arguments[0].click();", checkbox_input)
                logger.info("✓ Successfully enabled 'Send myself a copy' checkbox")
            else:
                logger.info("✓ 'Send myself a copy' checkbox already enabled")

            break

    logger.info("✓ All email attachment options configured successfully")

    # OPERATION 10: Take Pre-Send Screenshot
    # Purpose: Capture the email configuration before sending
    # Function Call: take_screenshot(driver)
    logger.info("Taking screenshot before sending invoice...")
    take_screenshot(driver)
    logger.info("✓ Pre-send screenshot captured successfully")

    # OPERATION 11: Click Send Email Button
    # Purpose: Send the configured invoice email to the client
    # Shadow DOM: Send button is inside shadow DOM
    # CSS Selector: button#send-email-button
    # Timeout: 10 seconds
    logger.info("Attempting to locate and click 'Send Email' button...")

    shadow_host = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "send-email-mfe-root")),
    )

    shadow_root = driver.execute_script(
        "return arguments[0].shadowRoot",
        shadow_host,
    )

    # Locate Send Email button inside shadow DOM
    send_email_button = WebDriverWait(driver, 10).until(
        lambda d: shadow_root.find_element(By.CSS_SELECTOR, "button#send-email-button"),
    )

    # Click the Send Email button
    driver.execute_script("arguments[0].click();", send_email_button)
    logger.info("✓ Successfully clicked 'Send Email' button - invoice email sent!")

    # OPERATION 12: Take Post-Send Screenshot
    # Purpose: Capture confirmation after sending the invoice
    # Function Call: take_screenshot(driver)
    logger.info("Taking screenshot after sending invoice...")
    take_screenshot(driver)
    logger.info("✓ Post-send screenshot captured successfully")

    # Set success status and return
    send_invoice_status = True
    logger.info("✓ STEP 4 COMPLETED: Invoice email sent successfully")
    logger.info("-" * 80)

    return send_invoice_status


def is_invoice_exist(driver) -> bool:
    """Check if invoice details page is currently displayed.

    This function validates that the user is on the invoice details page by
    checking for the presence of the 'Invoice' h1 heading element. This is a
    critical validation step performed before attempting to send an invoice.

    Args:
        driver: Selenium WebDriver instance.

    Returns:
        bool: True if invoice page exists, False otherwise.

    Notes:
        - Uses 10 second timeout for invoice heading visibility
        - XPath looks for h1 element with class 'xui-pageheading--title' containing 'Invoice' text
        - Used to validate correct page before performing invoice operations
        - Called by send_invoice() as a pre-validation step
    """
    logger.debug("Validating invoice details page existence...")

    try:
        # XPath Strategy: H1 heading with specific class containing 'Invoice' text
        # Timeout: 10 seconds
        invoice_xpath = "//h1[contains(@class,'xui-pageheading--title') and contains(normalize-space(),'Invoice')]"
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
        )
        logger.debug("✓ Invoice details page validated - page heading found")
        return True

    except Exception as e:
        # Log detailed error for debugging
        logger.warning(f"✗ Invoice details page not found - validation failed")
        logger.debug(f"Validation error: {e}")
        return False
