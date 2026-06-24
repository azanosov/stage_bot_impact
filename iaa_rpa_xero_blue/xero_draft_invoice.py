"""
Module for creating and managing draft invoices in Xero.

This module provides comprehensive functionality for automating invoice creation in Xero,
including account verification, client lookup, invoice form population, and approval workflows.
It supports both new and legacy Xero UI versions and handles multiple approval workflows
based on entity configuration.
"""

from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils.browser import safe_click
from iaa_rpa_utils.browser import setup_logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# Set up logger for this module
logger = setup_logger(__name__)


def xero_draft_invoice(
    browser,
    xero_client_name: str,
    due_date: str,
    job_number: str,
    item_1_name: str,
    entity_name: str,
    partner_name: str,
    is_registered_office: bool,
    item_2_name: str,
    account_name: str,
    is_company_exist: bool,
    is_invoice_approve: bool,
    xero_url: str,
):
    """Create and submit a draft invoice in Xero with automated client lookup and approval workflow.

    This function orchestates the complete invoice creation process in Xero, including:
    - Verifying and switching to the correct Xero account
    - Navigating to the invoice creation page
    - Looking up and validating the client exists in Xero
    - Populating invoice details (due date, job number, line items)
    - Adding optional registered office line item if applicable
    - Submitting the invoice for approval or approving it directly

    The function supports both entity-based and standard approval workflows, and handles
    both new and legacy Xero UI versions automatically.

    Args:
        browser: SeleniumBrowser instance with driver attribute
        xero_client_name (str): The client/contact name to search for in Xero. Must match an
            existing contact. Special characters like '&' are automatically escaped.
        due_date (str): Invoice due date in Xero-accepted format (e.g., 'DD/MM/YYYY').
            Optional - if empty or whitespace, this field is skipped.
        job_number (str): Job reference number to associate with the invoice.
            Optional - if empty or whitespace, this field is skipped.
        item_1_name (str): Name of the first invoice line item to select from Xero items.
            Required field.
        entity_name (str): Entity name for tracking dimension on invoice line items.
            Optional - if empty, entity field is skipped. Also determines approval workflow.
        partner_name (str): Partner name for tracking dimension on invoice line items.
            Optional - if empty, partner field is skipped.
        is_registered_office (bool): Flag indicating whether to add a second line item for
            registered office services. If True, adds item_2_name as second line item.
        item_2_name (str): Name of the second invoice line item (for registered office).
            Only used if is_registered_office is True.
        screenshot_path (str): Path for screenshot capture. Currently unused in implementation.
        account_name (str): The Xero account name to verify/switch to before creating invoice.
            Function will switch accounts if current account doesn't match.

    Returns:
        tuple: A tuple containing two boolean values:
            - is_company_exist (bool): True if the client was found in Xero, False otherwise.
            - is_invoice_approve (bool): True if the invoice was successfully approved/submitted,
              False if approval failed or was not completed.

    Raises:
        Exception: Logs error if the invoice creation process fails at any step. The exception
            is caught and logged but not re-raised, allowing graceful failure handling.
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Draft Invoice - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name: {xero_client_name}")
    logger.info(f"Account Name: {account_name}")
    logger.info(f"Due Date: {due_date}")
    logger.info(f"Job Number: {job_number}")
    logger.info(f"Item 1 Name: {item_1_name}")
    logger.info(f"Item 2 Name: {item_2_name}")
    logger.info(f"Entity Name: {entity_name}")
    logger.info(f"Partner Name: {partner_name}")
    logger.info(f"Is Registered Office: {is_registered_office}")
    logger.info(f"Is Company Exist (Initial): {is_company_exist}")
    logger.info(f"Is Invoice Approve (Initial): {is_invoice_approve}")
    logger.info(f"Xero URL: {xero_url}")
    logger.info("=" * 80)

    try:
        # STEP 1: Ensure Correct Xero Account Is Selected
        # Purpose: Verify we are operating in the correct Xero tenant/organisation before
        #          making any changes. Switches account if a mismatch is detected.
        # Function: ensure_correct_account_selected(browser, account_name)
        # - Checks the page heading for the expected account name
        # - Opens the account dropdown and selects the correct account if needed
        # - Waits for the page to reload after switching
        ensure_correct_account_selected(browser, account_name)

        # STEP 2: Navigate to the Invoice Creation Page
        # Purpose: Open the Xero invoices section so a new invoice can be created.
        #          Handles both the new and legacy Xero UI automatically.
        # Function: navigated_to_invoice(browser)
        # - Attempts new UI path: Sales menu → Invoices link
        # - Falls back to old UI path: Dashboard → Business → Invoices if new UI not found
        navigated_to_invoice(browser)

        # STEP 3: Create Draft Invoice with Client Lookup and Field Population
        # Purpose: Perform the full invoice creation workflow — find the client, fill all
        #          required fields, add line items, and submit for approval.
        # Function: create_xero_draft_invoice_with_client_lookup(...)
        # - Locates the Xero browser tab by matching xero_url
        # - Clicks "New Invoice" to open a blank invoice form
        # - Searches for the client by name and selects from dropdown
        # - Populates due date, job number, and invoice line items
        # - Adds registered office line item if is_registered_office is True
        # - Calls approve_and_submit_xero_invoice() to complete the workflow
        is_company_exist, is_invoice_approve = (
            create_xero_draft_invoice_with_client_lookup(
                browser,
                xero_client_name,
                due_date,
                job_number,
                item_1_name,
                entity_name,
                partner_name,
                is_registered_office,
                item_2_name,
                is_company_exist,
                is_invoice_approve,
                xero_url,
            )
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Draft Invoice - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Final Is Company Exist: {is_company_exist}")
        logger.info(f"Final Is Invoice Approve: {is_invoice_approve}")
        logger.info("=" * 80)

        return is_company_exist, is_invoice_approve

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Draft Invoice - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def check_whether_current_account_selected(driver, account_name: str) -> bool:
    """
    Check if the specified Xero account is currently selected.

    This function verifies whether the user is currently viewing the correct Xero
    account/organization by checking for the account name in the page heading.

    Args:
        driver: Selenium WebDriver instance
        account_name (str): Account name to check for in the Xero dashboard

    Returns:
        bool: True if the specified account is currently selected, False otherwise
    """
    # STEP 1: Log the account verification attempt
    logger.info(f"Checking if account '{account_name}' is currently selected")

    try:
        # STEP 2: Wait for account name in page heading
        # Use XPath to find account name in heading element
        # Return True if found within 5 seconds, False if timeout
        account_name_check_xpath = f"//div[@class='xdash-pageHeading__nowrap___jbbkH' and normalize-space() = '{account_name}']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_name_check_xpath)),
        )
        logger.info(f"Account '{account_name}' is currently selected")
        return True
    except TimeoutException:
        # If timeout occurs, the account name was not found in the heading
        logger.info(f"Account '{account_name}' is not currently selected")
        return False


def navigated_to_invoice(browser):
    """
    Navigate to the Invoice page in Xero.

    This function handles navigation to the Invoice page for both new and legacy
    Xero UI versions. It first attempts to use the new UI navigation pattern,
    and falls back to the old UI pattern if the new UI is not detected.

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Returns:
        None
    """
    logger.info("Starting navigation to Invoice page")
    driver = browser.driver

    try:
        # STEP 1: Attempt new UI navigation
        # Click "Sales" menu button
        sales_xpath = "//button[@type='button']//span[normalize-space(text())='Sales']"
        elem = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, sales_xpath)),
        )
        safe_click(driver, elem, "Sales")
        logger.info("Sales button clicked (new UI)")

        # Click "Invoices" link from submenu
        invoice_xpath = "//a[@role='link']//span[normalize-space(text())='Invoices']"
        elem = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, invoice_xpath)),
        )
        safe_click(driver, elem, "Invoices")
        logger.info("Invoices link clicked (new UI)")
        logger.info("Successfully navigated to Invoice page using new UI")

    except TimeoutException:
        # STEP 2: Fallback to old UI navigation if Step 1 fails
        logger.info("New UI not detected, attempting old UI navigation")

        # Click "Dashboard" button
        dashboard_xpath = "//button[normalize-space(text())='Dashboard']"
        dashboard_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
        )
        safe_click(driver, dashboard_ele, "Dashboard button")
        logger.info("Dashboard clicked")

        # Click "Business" menu
        business_xpath = "//button[normalize-space(text())='Business']"
        business_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, business_xpath)),
        )
        safe_click(driver, business_ele, "Business button")
        logger.info("Business clicked")

        # Click "Invoices" link
        invoice_xpath = "//a[normalize-space(text())='Invoices']"
        invoice_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
        )
        safe_click(driver, invoice_ele, "Invoices link")
        logger.info("Invoices clicked")
        logger.info("Successfully navigated to Invoice page using old UI")


def ensure_correct_account_selected(browser, account_name: str):
    """
    Verify the correct Xero account is selected and switch to it if necessary.

    This function checks if the user is currently viewing the correct Xero account/
    organization. If not, it opens the account dropdown menu and switches to the
    specified account.

    Args:
        browser: SeleniumBrowser instance with driver attribute
        account_name (str): Name of the Xero account to verify or switch to

    Returns:
        None

    Note:
        If the current account doesn't match account_name, this function will:
        1. Open the account dropdown menu in the navigation bar
        2. Select the specified account from the list
        3. Wait for the account to load
    """
    # STEP 1: Check if correct account is already selected
    logger.info(f"Ensuring account '{account_name}' is selected")
    driver = browser.driver

    # Call check function to verify current account
    if not check_whether_current_account_selected(driver, account_name):
        # STEP 2: Switch accounts if necessary
        logger.info(f"Current account is not '{account_name}', switching accounts")

        # Open account dropdown menu
        account_dropdown_xpath = "//div[contains(@class,'x-nav--tenant-menu')]//button[@class='x-nav-xui-button x-nav--tenant-menu-button x-nav-xui-button-borderless-inverted x-nav-xui-button-medium x-nav-xui-button-has-icon']"
        account_dropdown_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_dropdown_xpath)),
        )
        safe_click(driver, account_dropdown_ele, "Account dropdown")
        logger.info("Opened account dropdown menu")

        # Click on the correct account name
        # This will reload the page with the selected account
        correct_account_xpath = (
            f"//a[@role='link' and .//span[normalize-space(text())='{account_name}']]"
        )
        correct_account_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, correct_account_xpath)),
        )
        safe_click(driver, correct_account_ele, f"Account {account_name}")
        logger.info(f"Successfully switched to account '{account_name}'")
    else:
        logger.info(f"Account '{account_name}' is already selected")


def create_xero_draft_invoice_with_client_lookup(
    browser,
    xero_client_name: str,
    due_date: str,
    job_number: str,
    item_1_name: str,
    entity_name: str,
    partner_name: str,
    is_registered_office: bool,
    item_2_name: str,
    is_company_exist: bool,
    is_invoice_approve: bool,
    xero_url: str,
):
    """
    Create a new draft invoice in Xero with client validation and field population.

    This function handles the complete invoice creation workflow including:
    - Finding the correct browser tab with Xero
    - Creating a new invoice
    - Searching for and selecting the client
    - Populating invoice fields (due date, job number, line items)
    - Approving or submitting the invoice

    Args:
        browser: SeleniumBrowser instance with driver attribute
        xero_client_name (str): The client/contact name to search for in Xero.
            Special characters like '&' are automatically escaped for XPath.
        due_date (str): Invoice due date (optional - skipped if empty)
        job_number (str): Job reference number (optional - skipped if empty)
        item_1_name (str): First invoice line item name (required)
        entity_name (str): Entity name for tracking dimension (optional)
        partner_name (str): Partner name for tracking dimension (optional)
        is_registered_office (bool): Whether to add a second line item for registered office
        item_2_name (str): Second invoice line item name (used if is_registered_office is True)
        is_company_exist (bool): Input flag for company existence
        is_invoice_approve (bool): Input flag for invoice approval
        xero_url (str): URL pattern to identify the Xero tab

    Returns:
        tuple: (is_company_exist, is_invoice_approve)
            - is_company_exist (bool): True if the client was found in Xero
            - is_invoice_approve (bool): True if the invoice was approved successfully

    Note:
        - Searches through all browser tabs to find the Xero tab
        - Client name matching is case-insensitive
        - If client is not found, navigates back to dashboard
    """
    logger.info("Starting invoice creation with client lookup")
    logger.info(f"Client name: {xero_client_name}")
    driver = browser.driver

    # STEP 1: Find the Xero browser tab
    # Iterate through all open tabs
    all_tabs = driver.window_handles
    logger.info(f"Found {len(all_tabs)} browser tabs - searching for Xero tab")

    for handle in all_tabs:
        # Switch to tab containing xero_url
        driver.switch_to.window(handle)
        current_url = driver.current_url

        # Check if this tab contains the Xero application
        if xero_url in current_url:
            logger.info(f"Found Xero tab with URL: {current_url}")

            # STEP 2: Open new invoice form
            # Click "New Invoice" button
            new_invoice_xpath = (
                "//div[@id='ext-gen30']//a[contains(normalize-space(), 'New Invoice')]"
            )
            new_invoice_ele = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, new_invoice_xpath)),
            )
            safe_click(driver, new_invoice_ele, "New Invoice button")
            logger.info("Clicked New Invoice button - invoice form opened")

            # STEP 3: Search and select client
            # Enter client name in contact field
            contact_xpath = "//input[contains(@class, 'contacts-mfe-textinput--input-medium') and @aria-haspopup='listbox']"
            contact_ele = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, contact_xpath)),
            )
            safe_click(driver, contact_ele, "Contact field")
            contact_ele.clear()
            contact_ele.send_keys(xero_client_name)
            logger.info(f"Entered client name '{xero_client_name}' in contact field")

            # Escape special characters for XPath
            client_name = xero_client_name.replace("&", "&amp;")

            try:
                # Click matching client from dropdown
                # Set is_company_exist flag based on result
                choose_client_name_xpath = (
                    f"//span[translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                    f"'abcdefghijklmnopqrstuvwxyz') = translate('{client_name}', "
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')]"
                )
                choose_client_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, choose_client_name_xpath),
                    ),
                )
                safe_click(driver, choose_client_ele, f"Client {xero_client_name}")
                logger.info(f"Successfully selected client '{xero_client_name}'")
                is_company_exist = True

            except TimeoutException:
                # Client was not found in Xero
                logger.warning(f"Client '{xero_client_name}' not found in Xero")
                is_company_exist = False

            # STEP 4: Populate invoice fields (if client exists)
            if is_company_exist:
                logger.info("Client found - proceeding with invoice field population")

                # Fill due date (optional)
                if due_date and due_date.strip() != "":
                    logger.info(f"Setting due date to: {due_date}")
                    due_date_xpath = "//input[@id='DueDateInput']"
                    due_date_ele = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, due_date_xpath)),
                    )
                    safe_click(driver, due_date_ele, "Due date field")
                    # Clear existing value using keyboard shortcuts
                    due_date_ele.send_keys("\ue009" + "a")  # CTRL + A
                    due_date_ele.send_keys("\ue003")  # DELETE
                    due_date_ele.send_keys(due_date)
                    due_date_ele.send_keys("\ue004")  # Tab to next field
                    logger.info("Successfully entered due date")

                # Fill job number (optional)
                if job_number and job_number.strip() != "":
                    logger.info(f"Setting job number to: {job_number}")
                    job_number_xpath = "//input[@title='Reference' and @data-automationid='reference-input--input' and @type='text']"
                    job_number_ele = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, job_number_xpath)),
                    )
                    safe_click(driver, job_number_ele, "Reference field")
                    job_number_ele.clear()
                    job_number_ele.send_keys(job_number)
                    logger.info("Successfully entered job number")

                # STEP 4: Fill First Invoice Line Item
                # Purpose: Populate the mandatory item field and optional tracking dimensions
                #          (Entity, Partner) for the first line of the invoice.
                # Function: fill_invoice_item_details(browser, item_1_name, entity_name, partner_name)
                # - Locates item combobox in table row 1 and types item_1_name
                # - Presses ENTER to confirm selection from dropdown
                # - Fills Entity tracking field if entity_name is provided
                # - Fills Partner tracking field if partner_name is provided
                logger.info(f"Filling first invoice line item: '{item_1_name}'")
                fill_invoice_item_details(
                    browser,
                    item_1_name,
                    entity_name,
                    partner_name,
                )

                # STEP 5: Add Registered Office Invoice Line (Conditional)
                # Purpose: Add a second line item for registered office services when the
                #          organisation is acting as registered office for this client.
                # Function: add_registered_office_invoice_line(browser, entity_name, partner_name,
                #                                              is_registered_office, item_2_name)
                # - Returns immediately if is_registered_office is False
                # - Locates item combobox in table row 2 and enters item_2_name
                # - Fills Entity and Partner tracking fields for the second line if provided
                logger.info(
                    f"Checking registered office requirement (is_registered_office={is_registered_office})",
                )
                add_registered_office_invoice_line(
                    browser,
                    entity_name,
                    partner_name,
                    is_registered_office,
                    item_2_name,
                )

                # STEP 6: Approve and Submit the Invoice
                # Purpose: Complete the invoice workflow by approving or submitting it
                #          depending on whether an entity name is present.
                # Function: approve_and_submit_xero_invoice(browser, entity_name)
                # - If entity_name provided: opens "More approve options" → clicks "Approve"
                # - If no entity_name: clicks "Submit for approval" (standard workflow)
                # - Verifies approval by checking for confirmation message on screen
                # - Navigates back to dashboard if approval cannot be confirmed
                logger.info("Initiating invoice approval process")
                is_invoice_approve = approve_and_submit_xero_invoice(
                    browser,
                    entity_name,
                )

            else:
                # Client not found — navigate back to dashboard to avoid leaving an
                # incomplete invoice form open in the browser
                logger.warning(
                    f"Client '{xero_client_name}' not found in Xero - navigating back to dashboard",
                )
                navigated_to_dashboard(browser)

            break  # Exit loop after processing Xero tab

    logger.info(
        f"Invoice creation completed - Company exists: {is_company_exist}, Invoice approved: {is_invoice_approve}",
    )
    return is_company_exist, is_invoice_approve


def fill_invoice_item_details(
    browser,
    item_1_name: str,
    entity_name: str,
    partner_name: str,
):
    """
    Fill invoice item details including item name, entity, and partner in Xero.

    This function populates the first invoice line item fields in a Xero draft invoice form.
    It fills the mandatory item name field and optionally fills the entity and partner
    tracking dimension fields if values are provided.

    Args:
        browser: SeleniumBrowser instance with driver attribute
        item_1_name (str): The name of the invoice item to select (required field)
        entity_name (str): Entity name for tracking dimension (optional - skipped if empty)
        partner_name (str): Partner name for tracking dimension (optional - skipped if empty)

    Returns:
        None

    Note:
        - All input fields are cleared before entering new values
        - Uses ENTER key to confirm selection from dropdown menus
        - Waits up to 5 seconds for each element to become visible
    """
    logger.info(f"Filling invoice item details - Item: {item_1_name}")
    driver = browser.driver

    # STEP 1: Select first invoice line item
    # Find item combobox in table row 1
    # Clear and enter item_1_name, press ENTER to confirm
    item_xpath = "//table//tr[1]/td[2]//input[@role='combobox']"
    item_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, item_xpath)),
    )
    safe_click(driver, item_ele, "Item field")
    item_ele.clear()
    item_ele.send_keys(item_1_name)
    item_ele.send_keys(Keys.ENTER)
    logger.info(f"Successfully selected item '{item_1_name}'")

    # STEP 2: Fill Entity tracking dimension (optional)
    # Find Entity field using label
    # Enter entity_name if provided
    if entity_name and entity_name.strip() != "":
        logger.info(f"Setting entity to: {entity_name}")
        entity_xpath = "//label[normalize-space(text())='Entity']/following::input[1]"
        entity_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, entity_xpath)),
        )
        safe_click(driver, entity_ele, "Entity field")
        entity_ele.clear()
        entity_ele.send_keys(entity_name)
        entity_ele.send_keys(Keys.ENTER)
        logger.info(f"Successfully set entity to '{entity_name}'")

    # STEP 3: Fill Partner tracking dimension (optional)
    # Find Partner field using label
    # Enter partner_name if provided
    if partner_name and partner_name.strip() != "":
        logger.info(f"Setting partner to: {partner_name}")
        partner_xpath = "//label[normalize-space(text())='Partner']/following::input[1]"
        partner_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, partner_xpath)),
        )
        safe_click(driver, partner_ele, "Partner field")
        partner_ele.clear()
        partner_ele.send_keys(partner_name)
        partner_ele.send_keys(Keys.ENTER)
        logger.info(f"Successfully set partner to '{partner_name}'")

    logger.info("Completed filling first invoice line item")


def add_registered_office_invoice_line(
    browser,
    entity_name: str,
    partner_name: str,
    is_registered_office: bool,
    item_2_name: str,
):
    """
    Add a second invoice line item for registered office services.

    When the organization serves as the registered office for the client, this function
    adds a second line item to the invoice with the specified item name and optional
    entity/partner tracking dimensions.

    Args:
        browser: SeleniumBrowser instance with driver attribute
        entity_name (str): Entity name for tracking dimension (optional)
        partner_name (str): Partner name for tracking dimension (optional)
        is_registered_office (bool): Flag indicating if WW is the registered office
        item_2_name (str): Name of the second invoice line item to add

    Returns:
        None

    Note:
        - If is_registered_office is False, the function returns immediately
        - Uses the second row in the invoice line items table
        - Entity and partner fields are optional
    """
    # STEP 1: Check if registered office line is needed
    # Return immediately if is_registered_office is False
    if not is_registered_office:
        logger.info("Registered office line not required - skipping")
        return

    logger.info(f"Adding registered office line item - Item: {item_2_name}")
    driver = browser.driver

    # STEP 2: Select second invoice line item
    # Find item combobox in table row 2
    # Clear and enter item_2_name, press ENTER to confirm
    item_xpath = "//table//tr[2]/td[2]//input[@role='combobox']"
    item_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, item_xpath)),
    )
    safe_click(driver, item_ele, "Second item field")
    item_ele.clear()
    item_ele.send_keys(item_2_name)
    item_ele.send_keys(Keys.ENTER)
    logger.info(f"Successfully selected second item '{item_2_name}'")

    # STEP 3: Fill Entity tracking dimension for second line (optional)
    # Find second Entity field
    # Enter entity_name if provided
    if entity_name and entity_name.strip() != "":
        logger.info(f"Setting second line entity to: {entity_name}")
        entity_xpath = "//label[normalize-space(text())='Entity']/following::input[2]"
        entity_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, entity_xpath)),
        )
        safe_click(driver, entity_ele, "Second entity field")
        entity_ele.clear()
        entity_ele.send_keys(entity_name)
        entity_ele.send_keys(Keys.ENTER)
        logger.info(f"Successfully set second line entity to '{entity_name}'")

    # STEP 4: Fill Partner tracking dimension for second line (optional)
    # Find second Partner field
    # Enter partner_name if provided
    if partner_name and partner_name.strip() != "":
        logger.info(f"Setting second line partner to: {partner_name}")
        partner_xpath = "//label[normalize-space(text())='Partner']/following::input[2]"
        partner_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, partner_xpath)),
        )
        safe_click(driver, partner_ele, "Second partner field")
        partner_ele.clear()
        partner_ele.send_keys(partner_name)
        partner_ele.send_keys(Keys.ENTER)
        logger.info(f"Successfully set second line partner to '{partner_name}'")

    logger.info("Completed adding registered office line item")


def approve_and_submit_xero_invoice(browser, entity_name: str) -> bool:
    """
    Approve and submit a Xero invoice using entity-specific or standard approval workflow.

    This function handles two different invoice approval workflows in Xero:
    1. Entity-based approval: When an entity name is provided, uses the "More approve
       options" menu to approve the invoice directly without email notification
    2. Standard approval: When no entity is provided, uses the "Submit for approval"
       button for standard approval workflow with notification

    After attempting approval, the function verifies the invoice was approved by checking
    for the approval confirmation message. If approval fails, it navigates back to the
    dashboard for error recovery.

    Args:
        browser: SeleniumBrowser instance with driver attribute
        entity_name (str): Entity name for tracking dimension. If provided (non-empty),
            triggers entity-based approval workflow. If empty/None,
            triggers standard approval workflow.

    Returns:
        bool: True if invoice was successfully approved (approval confirmation detected),
              False otherwise
    """
    logger.info("Starting invoice approval process")
    driver = browser.driver

    # STEP 1: Determine approval workflow based on entity_name
    if entity_name and entity_name.strip() != "":
        # If entity_name provided: Use "More approve options" → "Approve" (direct approval)
        logger.info("Using entity-based approval workflow (direct approval)")

        # Open the "More approve options" dropdown menu
        more_button_xpath = (
            "//button[@type='button' and @aria-label='More approve options']"
        )
        more_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, more_button_xpath)),
        )
        safe_click(driver, more_button_ele, "More options button")
        logger.info("Opened More approve options menu")

        # Click the "Approve" option from the dropdown
        # This approves the invoice without sending an email
        approve_button_xpath = "//div[@id='ApproveAndEmailButton-approve']//span[normalize-space(text())='Approve']"
        approve_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, approve_button_xpath)),
        )
        safe_click(driver, approve_button_ele, "Approve button")
        logger.info("Clicked Approve button - invoice submitted for approval")
    else:
        # If no entity_name: Use "Submit for approval" button (standard workflow)
        logger.info("Using standard approval workflow (submit for approval)")

        # Click the "Submit for approval" button
        # This submits the invoice through the standard approval process
        submit_and_approve_button_xpath = (
            "//button[@type='button' and normalize-space(text())='Submit for approval']"
        )
        submit_and_approve_button_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located(
                (By.XPATH, submit_and_approve_button_xpath),
            ),
        )
        safe_click(driver, submit_and_approve_button_ele, "Submit for approval button")
        logger.info("Clicked Submit for approval button - invoice submitted")

    # STEP 2: Verify approval success
    # Call is_invoice_approve() to check for confirmation message
    approval_result = is_invoice_approve(driver)

    # Navigate to dashboard if approval failed
    if not approval_result:
        logger.warning("Invoice approval failed or not confirmed")
        # TODO: Invoke COMMON\TakeScreenshot.xaml for debugging
        # Navigate back to dashboard for error recovery
        navigated_to_dashboard(browser)
    else:
        logger.info("Invoice successfully approved")

    logger.info(f"Approval process completed - Result: {approval_result}")
    return approval_result


def is_invoice_approve(driver) -> bool:
    """
    Check if the invoice approval confirmation message is displayed.

    This function waits for and checks the presence of the "Invoice approved"
    confirmation message that appears after successful invoice approval in Xero.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if invoice approval confirmation message is present, False otherwise
    """
    logger.info("Checking for invoice approval confirmation")

    try:
        # STEP 1: Wait for approval confirmation message
        # Look for "Invoice approved" text element
        invoice_approve_xpath = "//p[normalize-space(text())='Invoice approved']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_approve_xpath)),
        )
        logger.info("Invoice approval confirmation message found")
        return True
    except TimeoutException:
        # STEP 2: Return result
        # Return True if message found within 5 seconds
        # Return False if timeout occurs
        logger.warning("Invoice approval confirmation message not found")
        return False


def navigated_to_dashboard(browser):
    """
    Navigate to Dashboard or Home page in Xero.

    This function handles navigation back to the Xero dashboard for both new and
    legacy Xero UI versions. Used for error recovery when operations fail.

    Args:
        browser: SeleniumBrowser instance with driver attribute

    Returns:
        None
    """
    logger.info("Navigating to dashboard")
    driver = browser.driver

    try:
        # STEP 1: Attempt new UI navigation
        # Click "Sales" button
        sales_xpath = "//button[@type='button']//span[normalize-space(text())='Sales']"
        sales_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, sales_xpath)),
        )
        safe_click(driver, sales_ele, "Sales button")
        logger.info("Successfully navigated to dashboard using new UI (Sales button)")

    except TimeoutException:
        # STEP 2: Fallback to old UI navigation if Step 1 fails
        # Click "Dashboard" button
        logger.info("New UI not detected, attempting old UI dashboard navigation")
        dashboard_xpath = "//button[normalize-space(text())='Dashboard']"
        dashboard_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
        )
        safe_click(driver, dashboard_ele, "Dashboard button")
        logger.info(
            "Successfully navigated to dashboard using old UI (Dashboard button)",
        )
