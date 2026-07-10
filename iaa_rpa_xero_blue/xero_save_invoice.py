"""
This module has not been refactored.

If you need the functionality provided by this module,
please first contact Praveen Lobo and/or Alexander Zanosov.
"""

"""
Module: xero_save_invoice

This module automates the process of saving invoices from Xero as PDF files.
It navigates through the Xero interface, locates specific invoices, and downloads
them to a specified local directory using browser automation and Windows UI automation.

Main Functions:
    - xero_save_invoice: Main entry point that orchestrates the invoice saving process
    - navigate_to_dashboard_or_home: Navigates to the Xero home/dashboard page
    - navigate_to_correct_account: Switches to the specified Xero account
    - navigated_to_client: Locates and opens the specific invoice
    - send_invoice: Downloads the invoice PDF using Windows automation

Helper Functions:
    - is_correct_account: Verifies if the current account matches the target
    - is_invoice_exist: Checks if an invoice exists in the list
    - is_invoice_page_exist: Verifies if the invoice page has loaded
    - is_print_pdf_exist: Checks if the Print PDF button is available
"""

import os
import time
from datetime import datetime
from robocorp import windows

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click

# Set up logger
logger = setup_logger(__name__)


def xero_save_invoice(
    browser,
    xero_account_name,
    xero_invoice_number,
    xero_url,
    invoice_save_path,
    is_invoice_saved_successfully,
):
    """
    Main function to save a Xero invoice as a PDF file.

    This function orchestrates the entire process of:
    1. Navigating to the Xero dashboard/home page
    2. Switching to the correct Xero account
    3. Searching for the specific invoice by number
    4. Opening the invoice page
    5. Downloading the invoice as a PDF to the specified path

    Args:
        browser: Browser instance containing the Selenium WebDriver
        xero_account_name (str): Name of the Xero account to navigate to
        xero_invoice_number (str): Invoice number to search for and save
        xero_url (str): Expected browser tab title for Xero Blue interface
        invoice_save_path (str): Local directory path where the PDF should be saved
        is_invoice_saved_successfully (bool): Initial save status flag (typically False)

    Returns:
        tuple[bool, str]: A tuple containing:
            - bool: True if invoice was saved successfully, False otherwise
            - str: Full file path of the saved invoice PDF, or empty string if failed

    Raises:
        Exception: If any step in the process fails (navigation, search, or download)

    Example:
        >>> success, file_path = xero_save_invoice(
        ...     browser=my_browser,
        ...     xero_account_name="ABC Company Ltd",
        ...     xero_invoice_number="INV-001",
        ...     xero_url="Xero",
        ...     invoice_save_path="C:\\Invoices",
        ...     is_invoice_saved_successfully=False
        ... )
        >>> print(f"Saved: {success}, Path: {file_path}")
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO SAVE INVOICE")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Account Name: {xero_account_name}")
    logger.info(f"Invoice Number: {xero_invoice_number}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # Step 1: Navigate to Dashboard or Home page
        # This ensures we start from a consistent state in the Xero interface
        navigate_to_dashboard_or_home(driver)

        # Step 2: Switch to the correct Xero account
        # Verifies if we're on the right account and switches if necessary
        navigate_to_correct_account(driver, xero_account_name)

        # Step 3: Navigate back to dashboard after account switch
        # Required to refresh the page and ensure proper account context
        navigate_to_dashboard_or_home(driver)

        # Step 4: Navigate to the invoice page
        # Searches for and opens the specific invoice using the invoice number
        navigated_to_client(driver, xero_invoice_number, xero_url)

        # Step 5: Save the invoice as PDF
        # Uses Windows automation to download the invoice to the specified path
        is_invoice_saved_successfully, res_invoice_path = send_invoice(
            driver, invoice_save_path
        )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO SAVE INVOICE")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Account Name: {xero_account_name}")
        logger.info(f"Invoice Number: {xero_invoice_number}")
        logger.info(f"Invoice Saved Successfully: {is_invoice_saved_successfully}")
        logger.info(f"Invoice Path: {res_invoice_path}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        return is_invoice_saved_successfully, res_invoice_path

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO SAVE INVOICE")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Account Name: {xero_account_name}")
        logger.error(f"Invoice Number: {xero_invoice_number}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"The xero_save_invoice failed due to {e}", exc_info=True)
        raise


def navigate_to_dashboard_or_home(driver):
    """
    Navigate to the Xero Dashboard or Home page.

    This function attempts to navigate to a consistent starting point in Xero.
    It first tries to click the "Dashboard" link, and if that fails (e.g., in a
    different Xero interface version), it falls back to clicking the "Home" link.

    Args:
        driver: Selenium WebDriver instance for browser control

    Raises:
        Exception: If neither Dashboard nor Home links can be found or clicked

    Note:
        Uses a 10-second wait time for element visibility
    """
    try:
        # Attempt to click Home link (primary option)
        home_xpath = "//a[.//span[normalize-space()='Home']]"
        home_ele = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, home_xpath))
        )
        safe_click(driver, home_ele, "Clicked Home")
        logger.info("Clicked Home")

    except Exception:
        # Attempt to click Dashboard link
        dashboard_xpath = "//a[normalize-space(text())='Dashboard']"
        dashboard_ele = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath))
        )
        safe_click(driver, dashboard_ele, "Clicked Dashboard")
        logger.info("Clicked Dashboard")


def is_correct_account(driver, xero_account_name) -> bool:
    """
    Verify if the current Xero account matches the target account name.

    This helper function checks if the displayed account name in the page header
    matches the expected account name. Used to determine if account switching is needed.

    Args:
        driver: Selenium WebDriver instance for browser control
        xero_account_name (str): The expected account name to verify

    Returns:
        bool: True if the current account matches the target, False otherwise

    Note:
        Uses a 10-second timeout to wait for the account name element
    """
    try:
        # Search for the account name in the page header (H1 element)
        account_xpath = f"//h1//div[normalize-space(.)='{xero_account_name}']"
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, account_xpath))
        )
        logger.info("This is correct account")
        return True
    except Exception:
        logger.info("This is not correct account")
        return False


def is_invoice_exist(driver, invoice_num_xpath, xero_invoice_number) -> bool:
    """
    Check if an invoice exists in the invoice list table.

    Searches the invoice list grid for a cell containing the specified invoice number.
    Used to verify that the search results contain the target invoice.

    Args:
        driver: Selenium WebDriver instance for browser control
        xero_invoice_number (str): The invoice number to search for

    Returns:
        bool: True if the invoice is found in the list, False otherwise

    Note:
        Uses a 10-second timeout to wait for the invoice element
    """
    try:
        # Look for invoice number in the table cell with role='cell'
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, invoice_num_xpath))
        )
        logger.info(f"{xero_invoice_number} Invoice exist")
        return True
    except Exception:
        logger.info(f"{xero_invoice_number} Invoice is not exist")
        return False


def is_invoice_page_exist(driver, xero_invoice_number) -> bool:
    """
    Verify that the invoice detail page has loaded correctly.

    Checks for the presence of the invoice page header with the specific invoice number.
    Used to confirm successful navigation to the invoice detail page.

    Args:
        driver: Selenium WebDriver instance for browser control
        xero_invoice_number (str): The invoice number to verify in the page header

    Returns:
        bool: True if the invoice page has loaded, False otherwise

    Note:
        Uses a 10-second timeout to wait for the header element
    """
    try:
        # Check for the H1 header containing "Invoice {number}"
        invoice_page_confirm_xpath = (
            f"//h1[normalize-space(text())='Invoice {xero_invoice_number}']"
        )
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, invoice_page_confirm_xpath))
        )
        logger.info("Invoice page exist")
        return True
    except Exception:
        logger.info("Invoice page is not exist")
        return False


def is_print_pdf_exist(driver) -> bool:
    """
    Check if the Print PDF button is available on the invoice page.

    Verifies that the Print PDF button is present and visible, which indicates
    the invoice is ready to be downloaded. This is a prerequisite for the save operation.

    Args:
        driver: Selenium WebDriver instance for browser control

    Returns:
        bool: True if the Print PDF button exists, False otherwise

    Note:
        Uses a 10-second timeout to wait for the button element
    """
    try:
        # Search for the Print PDF button by its ID and text content
        print_pdf_xpath = f"//button[@id='PrintDropdown-print' and normalize-space(text())='Print PDF']"
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, print_pdf_xpath))
        )
        logger.info("Print PDF exist")
        return True
    except Exception:
        logger.info("Print PDF is not exist")
        return False


def navigate_to_correct_account(driver, xero_account_name):
    """
    Switch to the specified Xero account if not already on it.

    This function checks if the current account matches the target account name.
    If not, it opens the account dropdown menu and selects the correct account.
    Handles different Xero interface versions with fallback XPath selectors.

    Args:
        driver: Selenium WebDriver instance for browser control
        xero_account_name (str): The target account name to switch to

    Raises:
        Exception: If the account dropdown or account name cannot be found

    Note:
        Uses multiple XPath strategies to handle different Xero UI versions
    """
    # Check if we're already on the correct account
    if not is_correct_account(driver, xero_account_name):
        logger.info("Current Account is not " + xero_account_name)

        # Click on Account dropdown
        try:
            # New ui
            account_drop_down_xpath = "//div[@id='main-menu']//button[@type='button']"
            elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, account_drop_down_xpath))
            )
            safe_click(driver, elem, "Account dropdown")
            logger.info(f"Clicked {xero_account_name} from the dropdown")

        except Exception:
            try:
                # Old ui
                account_drop_down_xpath = "//div[@class='xnav-appbutton--body']"
                elem = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, account_drop_down_xpath))
                )
                safe_click(driver, elem, "Account dropdown")
                logger.info(f"Clicked {xero_account_name} from the dropdown")
            except Exception as e:
                logger.error(f"Could not open account dropdown: {e}")
                raise

        # Click account name
        try:
            # New ui
            account_name_xpath = f"//a[@role='link']//span[normalize-space(text())='{xero_account_name}']"
            elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, account_name_xpath))
            )
            safe_click(driver, elem, f"Account: {xero_account_name}")
            logger.info(f"Clicked {xero_account_name}")

        except Exception:
            try:
                # Old ui
                account_name_xpath = f"//div[@id='main-menu']//a[normalize-space(text())='{xero_account_name}']"
                elem = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, account_name_xpath))
                )
                safe_click(driver, elem, f"Account: {xero_account_name}")
                logger.info(f"Clicked {xero_account_name}")
            except Exception as e:
                logger.error(f"Could not select account {xero_account_name}: {e}")
                raise


def navigated_to_client(driver, xero_invoice_number, xero_url):
    """
    Navigate to a specific invoice by searching for its invoice number.

    This function performs the following steps:
    1. Switches to the correct browser tab containing Xero
    2. Navigates to the Business/Sales section
    3. Opens the Invoices page
    4. Searches for the specific invoice by number
    5. Opens the invoice detail page

    Args:
        driver: Selenium WebDriver instance for browser control
        xero_invoice_number (str): The invoice number to search for and open
        xero_url (str): Expected substring in the browser tab title to identify Xero

    Raises:
        Exception: If the invoice doesn't exist or the invoice page fails to load

    Note:
        Handles multiple browser tabs and searches for the Xero tab by title
    """
    # Switch to the correct browser tab containing Xero
    all_tabs = driver.window_handles
    logger.info(f"Found {len(all_tabs)} browser tab(s)")

    for handle in all_tabs:
        driver.switch_to.window(handle)
        current_url = driver.current_url

        # Check if this tab contains Xero based on the current_url
        if xero_url in current_url:

            try:
                # For new UI: Click Sales button
                # This expands the Sales menu to reveal the Invoices link
                sales_xpath = (
                    "//button[@type='button']//span[normalize-space(text())='Sales']"
                )
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

            # Search for the specific invoice using the search input field
            # Uses keyboard automation to clear field and enter invoice number
            search_xpath = "//a[.//span[normalize-space()='Search']]"
            search_ele = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, search_xpath))
            )
            safe_click(driver, search_ele, "Clicked search button")
            logger.info("Clicked search button")

            # Click searchbar
            input_xpath = "//input[@id='sb_txtReference']"
            input_client_ele = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, input_xpath))
            )
            safe_click(driver, input_client_ele, "Clicked search bar")
            logger.info("Clicked search bar")

            input_client_ele.send_keys("\ue009" + "a")  # CTRL + A to select all text
            input_client_ele.send_keys("\ue003")  # DELETE to clear the field
            input_client_ele.send_keys(xero_invoice_number)  # Type the invoice number
            input_client_ele.send_keys("\ue004")  # TAB to trigger search
            logger.info(
                f"Entered invoice number in search field: {xero_invoice_number}"
            )

            # Step 5: Click the Search button to execute the search
            search_user_xpath = "//a[normalize-space(text())='Search']"
            search_user_ele = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, search_user_xpath))
            )
            safe_click(driver, search_user_ele, "Clicked Search")
            logger.info("Clicked on Search")

            invoice_num_xpath = f"//table[@id='ext-gen45']//tbody//tr//td[normalize-space(text())='{xero_invoice_number}']"

            # Step 6: Verify invoice exists and open it
            if is_invoice_exist(driver, invoice_num_xpath, xero_invoice_number):

                logger.info(
                    f"Invoice exist: ", {"True" if is_invoice_exist else "False"}
                )

                # Click on the invoice number to open the detail page
                invoice_num_ele = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, invoice_num_xpath))
                )
                safe_click(driver, invoice_num_ele, "Clicked Invoice Number")
                logger.info("Clicked on Invoice Number")

                # Step 7: Verify the invoice page has loaded
                if not is_invoice_page_exist(driver, xero_invoice_number):
                    # Invoice page failed to load
                    logger.error("Bot failed to open invoice page")
                    raise Exception("Bot failed to open invoice page")

            else:
                # Invoice not found in search results
                logger.error("Created invoice not exist in Xero")
                raise Exception("Created invoice not exist in Xero")


def send_invoice(driver, invoice_save_path) -> tuple[bool, str]:
    """
    Download the invoice as a PDF file using Windows UI automation.

    This function performs the following steps:
    1. Verifies the Print PDF button is available
    2. Uses Windows automation to interact with the Save As dialog
    3. Retrieves the default filename from Xero
    4. Saves the file to the specified directory
    5. Verifies the file was saved successfully

    Args:
        driver: Selenium WebDriver instance (used for validation)
        invoice_save_path (str): Directory path where the PDF should be saved

    Returns:
        tuple[bool, str]: A tuple containing:
            - bool: True if the file was saved successfully, False otherwise
            - str: Full path to the saved file, or empty string if failed

    Raises:
        Exception: If the Print PDF button is missing or Windows automation fails

    Note:
        This function assumes:
        - The invoice page is already open
        - The Print PDF button has been clicked (triggering the Save As dialog)
        - Google Chrome is being used as the browser
        - Windows UI Automation is available (robocorp.windows library)
    """
    # Step 1: Verify the Print PDF button is available
    if not is_print_pdf_exist(driver):
        logger.error("Print PDF button not exist after sending the email from Xero")
        raise Exception("Print PDF button not exist after sending the email from Xero")

    # Step 2: Use Windows automation to handle the Save As dialog
    try:
        # Find the Chrome window containing Xero
        app = windows.find_window(f"regex:.*Xero | * | * - Google Chrome")

        # Locate the Save As dialog window
        app.find('control:"WindowControl" and name:"Save As" and path:"1"')

        # Find the filename input field in the Save As dialog
        file_input = app.find(
            'control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"'
        )

        # Step 3: Get the default filename from Xero (e.g., "INV-001.pdf")
        default_invoice_name = file_input.get_value()
        logger.info(f"Default filename from Save As dialog: {default_invoice_name}")

        # Step 4: Set the full file path (directory + filename)
        file_input.click()  # Activate the input field
        file_path = os.path.normpath(
            os.path.join(invoice_save_path, default_invoice_name)
        )
        file_input.set_value(file_path)

        # Wait for the path to be set
        time.sleep(2)

        # Click the Save button to download the file
        app.find('control:"ButtonControl" and name:"Save"').click()

        # Step 5: Wait for the file to be saved and verify it exists
        time.sleep(2)

        if os.path.exists(file_path):
            logger.info(f"Invoice saved successfully at: {file_path}")
            is_invoice_saved_successfully = True
            res_invoice_path = file_path
        else:
            logger.error(f"Invoice file not found at: {file_path}")
            is_invoice_saved_successfully = False
            res_invoice_path = ""

        return is_invoice_saved_successfully, res_invoice_path

    except Exception as e:
        logger.error(f"Failed during export: {e}")
        raise
