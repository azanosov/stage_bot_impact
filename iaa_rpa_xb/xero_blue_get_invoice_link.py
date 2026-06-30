# """
# Module: xero_blue_get_invoice_link
# This module automates the process of retrieving invoice URLs from Xero Blue
# and optionally updating partner information on the invoice.
# The module handles the complete workflow of:
# 1. Navigating to the Invoices page in Xero
# 2. Searching for a specific invoice by number
# 3. Retrieving the invoice URL
# 4. Optionally adding/updating partner information
# Main Functions:
#     - xero_blue_get_invoice_link: Main entry point that orchestrates the process
#     - navigated_to_invoice_page: Navigates to the Invoices page via Sales menu
#     - navigated_to_invoice: Searches for and opens a specific invoice, retrieves URL
#     - navigated_to_partner: Adds or updates partner information on the invoice (optional)
# Workflow:
#     1. Switch to the correct browser tab containing Xero
#     2. Navigate to Sales > Invoices page
#     3. Search for invoice by invoice number
#     4. Open invoice details page
#     5. Retrieve invoice URL from the page
#     6. (Optional) Add partner information if partner_name is provided
#     7. Save and close if partner was added
# UI Compatibility:
#     - Designed for Xero's new UI (Sales > Invoices)
#     - Uses 5-second timeouts for all element waits
# """
from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_get_invoice_link(
    browser,
    invoice_number,
    invoice_url,
    partner_name,
    xero_url,
):
    """
    Retrieve invoice URL from Xero Blue and optionally update partner information.

    This function automates the complete workflow of:
    1. Switching to the correct Xero browser tab
    2. Navigating to the Invoices page
    3. Searching for the specified invoice
    4. Retrieving the invoice URL
    5. Optionally adding partner information if partner_name is provided

    Args:
        browser: Browser instance containing the Selenium WebDriver
        invoice_number (str): The invoice number to search for (e.g., "INV-001")
        retrieved_invoice_url (str): Variable to store the retrieved invoice URL (passed by reference in original UiPath)
        partner_name (str): Optional partner name to add to the invoice. If empty or None, skipped.
        xero_url (str): URL substring to identify the correct Xero browser tab

    Returns:
        str: The retrieved invoice URL from the invoice details page

    Raises:
        Exception: If navigation fails, invoice not found, or partner update fails
        TimeoutException: If any web elements are not found within timeout period

    Example:
        >>> retrieved_invoice_url = xero_blue_get_invoice_link(
        ...     browser=my_browser,
        ...     invoice_number="INV-001",
        ...     retrieved_invoice_url="",
        ...     partner_name="ABC Partners Ltd",
        ...     xero_url="xero.com"
        ... )
        >>> print(f"Invoice URL: {retrieved_invoice_url}")

    Note:
        - Uses 5-second timeouts for all element waits
        - Partner information is only updated if partner_name is not empty/None
        - Switches between browser tabs to find the one containing xero_url
    """

    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE GET INVOICE LINK")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Invoice Number: {invoice_number}")
    logger.info(
        f"Partner Name: {partner_name if partner_name else 'None (will be skipped)'}",
    )
    logger.info(f"Xero URL Pattern: {xero_url}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # STEP 1: Switch to Correct Browser Tab
        # Purpose: Find and activate the browser tab containing Xero
        # Iterates through all open tabs and switches to the one matching xero_url
        all_tabs = driver.window_handles
        logger.info(f"Found {len(all_tabs)} browser tab(s)")

        xero_tab_found = False
        for handle in all_tabs:
            driver.switch_to.window(handle)
            current_url = driver.current_url

            # Check if this tab contains the Xero page
            if xero_url in current_url:
                xero_tab_found = True
                logger.info(f"Switched to Xero tab with URL: {current_url}")

                # STEP 2: Navigate to Invoices Page
                # Purpose: Access the invoices list page via Sales menu
                # Function: navigated_to_invoice_page()
                # - Clicks Sales button to expand menu
                # - Clicks Invoices link to open invoices page
                navigated_to_invoice_page(driver)

                # STEP 3: Search for and Open Invoice
                # Purpose: Find the specific invoice and retrieve its URL
                # Function: navigated_to_invoice(driver, invoice_number, retrieved_invoice_url)
                # - Opens search interface
                # - Enters invoice number and submits search
                # - Opens invoice details page
                # - Retrieves and returns invoice URL
                invoice_url = navigated_to_invoice(driver, invoice_number, invoice_url)

                # STEP 4: Update Partner Information (Optional)
                # Purpose: Add or update partner information if partner_name is provided
                # Function: navigated_to_partner()
                # - Skipped if partner_name is None or empty string
                # - Clicks partner field, enters partner name, selects from dropdown
                # - Saves and closes the invoice
                add_partner_to_invoice(driver, partner_name)

                # Calculate duration and log successful completion
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                logger.info("=" * 80)
                logger.info(
                    f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE GET INVOICE LINK",
                )
                logger.info("=" * 80)
                logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"Duration: {duration:.2f} seconds")
                logger.info(f"Invoice Number: {invoice_number}")
                logger.info(f"Invoice URL Retrieved: {invoice_url}")
                logger.info(f"Partner Updated: {'Yes' if partner_name else 'No'}")
                logger.info(f"Status: SUCCESS")
                logger.info("=" * 80)

                return invoice_url

        # If no matching tab was found
        if not xero_tab_found:
            raise Exception(f"No browser tab found containing URL pattern: {xero_url}")

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE GET INVOICE LINK")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Invoice Number: {invoice_number}")
        logger.error(f"Partner Name: {partner_name}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"The xero_blue_get_invoice_link failed due to {e}", exc_info=True)
        raise


def navigated_to_invoice_page(driver):
    """
    Navigate to the Invoices page in Xero via Sales menu.

    This function navigates from the current Xero page to the Invoices list page
    by clicking through the Sales menu. Designed for Xero's new UI.

    Args:
        driver: Selenium WebDriver instance for browser control

    Raises:
        TimeoutException: If Sales button or Invoices link are not found within 5 seconds

    Note:
        - Uses 5-second timeout for element waits
        - Designed for new Xero UI (Sales > Invoices)
    """

    # ACTION 1: Click Sales Button
    # Purpose: Expand the Sales menu to reveal sub-menu options
    # This button opens the dropdown containing Invoices, Quotes, etc.
    sales_xpath = "//button[@type='button']//span[normalize-space(text())='Sales']"
    elem = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, sales_xpath)),
    )
    safe_click(driver, elem, "Sales")
    logger.info("Sales button clicked")

    # ACTION 2: Click Invoices Link
    # Purpose: Open the Invoices page with the list of all invoices
    # This displays the searchable list of invoices for the current organization
    invoice_xpath = "//a[@role='link']//span[normalize-space(text())='Invoices']"
    elem = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, invoice_xpath)),
    )
    safe_click(driver, elem, "Invoices")
    logger.info("Invoices link clicked (new UI)")


def navigated_to_invoice(driver, invoice_number, retrieved_invoice_url) -> str:
    """
    Search for a specific invoice and retrieve its URL.

    This function performs invoice search, opens the invoice details page,
    and retrieves the invoice URL. It follows these steps:
    1. Opens the search interface
    2. Enters the invoice number
    3. Submits the search
    4. Clicks on the matching invoice
    5. Retrieves the invoice URL from the page

    Args:
        driver: Selenium WebDriver instance for browser control
        invoice_number (str): The invoice number to search for
        retrieved_invoice_url (str): Placeholder parameter (for compatibility with original UiPath workflow)

    Returns:
        str: The retrieved invoice URL from the invoice details page

    Raises:
        TimeoutException: If search elements or invoice link are not found within 5 seconds

    Note:
        - Uses 5-second timeout for all element waits
        - Invoice URL is retrieved from Business button attributes or falls back to current URL
    """

    # ACTION 1: Open Search Interface
    # Purpose: Reveal the search input field for entering invoice details
    # Clicking this expands the search functionality on the Invoices page
    search_xpath = "//span[@class='text' and normalize-space(text())='Search']"

    search_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, search_xpath)),
    )
    safe_click(driver, search_ele, "Clicked search")
    logger.info("Clicked search")

    # ACTION 2: Enter Invoice Number
    # Purpose: Input the invoice number into the search field
    # Uses keyboard shortcuts to ensure clean input (clear existing text first)
    input_client_name_xpath = "//input[@type='text' and @id='sb_txtReference']"
    input_client_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, input_client_name_xpath)),
    )
    input_client_ele.send_keys("\ue009" + "a")  # CTRL + A to select all text
    input_client_ele.send_keys("\ue003")  # DELETE to clear the field
    input_client_ele.send_keys(invoice_number)  # Type the invoice number
    input_client_ele.send_keys("\ue004")  # TAB to move to next field

    logger.info(f"Typed invoice number: {invoice_number}")

    # ACTION 3: Submit Search Query
    # Purpose: Execute the search to display matching invoices
    # Clicking this triggers the search and updates the invoice list
    submit_xpath = "//a[normalize-space(text())='Search']"
    submit_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, submit_xpath)),
    )
    safe_click(driver, submit_ele, "Click Submit")
    logger.info("Clicked Submit")

    # ACTION 4: Open Invoice Details Page
    # Purpose: Click on the matching invoice to open its details page
    # The invoice link contains the invoice number as its text
    # invoice_xpath = f"//table//a[normalize-space(text())='{invoice_number}']"
    invoice_xpath = f"//table[@class='standard']//tbody//td[@class='ref' and normalize-space(.)='{invoice_number}']"
    invoice_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
    )
    safe_click(driver, invoice_ele, "Click Invoice")
    logger.info("Clicked Invoice")

    invoice_url = driver.current_url
    logger.info(f"Invoice URL retrieved: {invoice_url}")

    return invoice_url


def add_partner_to_invoice(driver, partner_name):
    """
    Add or update partner information on the invoice (optional operation).

    This function adds partner information to the invoice if partner_name is provided.
    If partner_name is None or empty string, the function does nothing and returns.

    The function performs these steps:
    1. Clicks on the partner field in the invoice
    2. Enters the partner name
    3. Selects the partner from the dropdown
    4. Saves and closes the invoice

    Args:
        driver: Selenium WebDriver instance for browser control
        partner_name (str): Partner name to add to the invoice. If None or empty, skipped.

    Raises:
        TimeoutException: If partner field or dropdown elements are not found within 5 seconds

    Note:
        - Uses 5-second timeout for all element waits
        - This is an optional operation - only executes if partner_name has a value
        - Automatically saves the invoice after adding partner information
    """

    # Check if partner_name is provided
    # If None or empty string, skip the entire partner update operation

    # TODO: Not all user client specific (Not tested) -> click partner name and select the partner name
    if partner_name is not None and partner_name != "":
        logger.info(
            f"Partner name provided: {partner_name}. Proceeding to update partner information.",
        )

        # ACTION 1: Click Partner Field
        # Purpose: Activate the partner autocomplete field in the invoice table
        # This field allows entering and selecting partner information
        partner_xpath = "//tr[contains(@class,'editabletablerow')]//td[contains(@class,'editabletablecell') and contains(@class,'autocompleter') and @colname='Partner']"
        partner_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, partner_xpath)),
        )
        safe_click(driver, partner_ele, "Click Partner")
        logger.info("Clicked Partner field")

        # ACTION 2: Enter Partner Name
        # Purpose: Type the partner name into the autocomplete field
        # Uses keyboard shortcuts to clear existing text and input new value
        partner_ele.send_keys("\ue009" + "a")  # CTRL + A to select all text
        partner_ele.send_keys("\ue003")  # DELETE to clear the field
        partner_ele.send_keys(partner_name)  # Type the partner name
        partner_ele.send_keys("\ue004")  # TAB to trigger autocomplete dropdown

        logger.info(f"Typed partner name: {partner_name}")

        # ACTION 3: Select Partner from Dropdown
        # Purpose: Click on the matching partner from the autocomplete dropdown
        # The dropdown appears after typing, showing matching partners

        partner_name_xpath = f"//span[contains(@class,'xui-pickitem--text') and ancestor::*[@id='{partner_name}']]"
        partner_name_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, partner_name_xpath)),
        )
        safe_click(driver, partner_name_ele, "Click Partner name")
        logger.info(f"Selected partner from dropdown: {partner_name}")

        # ACTION 4: Save and Close Invoice
        # Purpose: Save the invoice with the updated partner information
        # This commits the changes and closes the invoice details page
        save_xpath = "//button[normalize-space(.)='Save & close']"
        save_ele = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, save_xpath)),
        )
        safe_click(driver, save_ele, "Click save and close")
        logger.info("Clicked 'Save & close' - Partner information saved")

    else:
        logger.info("Partner name not provided or empty. Skipping partner update.")
