from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


change_organisation_xpath = (
    "//button[@type='button']//span[normalize-space(text())='Change organisation']"
)
home_link_xpath = "//a[@role='link' and span[normalize-space(text())='Home']]"
new_ui_search_xpath = "//input[@placeholder='Search organizations']"


def xero_blue_switch_client(
    browser,
    xero_account_name: str,
):
    """
    Switch the active Xero client/organization account to a specified account.

    This function automates the process of switching between different Xero client organizations
    within a Xero Practice Manager or multi-organization environment. It intelligently detects
    which version of Xero UI is active (new UI with Home page or legacy UI with Dashboard),
    navigates to the appropriate account selector interface, searches for the target organization,
    and switches to it. If the target client is already selected, the function skips the switch
    operation to optimize performance.

    The function supports both Xero Blue's new interface (Home-based navigation) and legacy
    interface (Dashboard-based navigation), automatically determining which approach to use
    based on the presence of UI elements.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.
                Must be logged in to a Xero Practice Manager account or multi-org environment.
        xero_account_name (str): Name of the target Xero client/organization to switch to.
                                Example: "ABC Company Pty Ltd", "XYZ Services Ltd"
                                The name must exactly match the organization name in Xero.

    Returns:
        None: The function completes when the client is switched successfully or was already
              selected. All operations are logged for audit purposes.

    Raises:
        Exception: If neither Home page nor Dashboard is found (unable to determine UI version).
                  If the target client/organization cannot be found in the account list.
                  If any step in the switch process fails (element not found, timeout, etc.).
                  All exceptions are logged with detailed error information before being re-raised.

    Notes:
        - HTML special characters in account names are escaped (&→&amp;, '→&apos;) for XPath.
        - The function checks if the target client is already selected before attempting switch.
        - Uses WebDriverWait with 2-5 second timeouts for element interactions.
        - New UI XPath (Home): "//a[@role='link' and span[normalize-space(text())='Home']]"
        - Old UI XPath (Dashboard): "//a[normalize-space(.)='Dashboard']"
        - All operations include comprehensive logging with banners, timestamps, and durations.
        - Duration tracking provides performance metrics for switch operations.

    Example:
        >>> browser = SeleniumBrowser()
        >>> xero_blue_login(browser, email, password, url, service_key)
        >>> xero_blue_switch_client(browser, "ABC Company Pty Ltd")
        # Successfully switches to ABC Company Pty Ltd
        >>> xero_blue_switch_client(browser, "ABC Company Pty Ltd")
        # Logs: Client already selected, no switch needed
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE SWITCH CLIENT")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Target Account Name: {xero_account_name}")
    logger.info("=" * 80)

    driver = browser.driver

    try:
        # Detect which Xero UI version is active by checking for Home page (new UI)
        # The has_home_page function checks for the presence of the Home link in the navigation
        # Returns True if new UI is active, False if legacy UI or Home link not found
        if has_home_page(browser):
            # NEW UI WORKFLOW: Navigate via Home page to access account selector
            # Wait for Home link element to become visible and clickable in the navigation
            home_link_ele = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.XPATH, home_link_xpath)),
            )
            # Click the Home link using safe_click utility to handle potential click interceptions
            safe_click(driver, home_link_ele, "Home link")

            logger.info(
                f"Attempting to switch Xero Blue Account to '{xero_account_name}'",
            )

            # Escape HTML special characters in account name for safe XPath usage
            # & becomes &amp; and ' becomes &apos; to prevent XPath syntax errors
            html_account_name = xero_account_name.replace("&", "&amp;").replace(
                "'",
                "&apos;",
            )

            # Check if the target client is already selected in the new UI
            # This optimization skips unnecessary navigation if we're already on the correct account
            client_is_already_selected = check_client_selected_new_ui(
                browser,
                html_account_name,
            )

            if not client_is_already_selected:
                # Target client is not currently selected - proceed with account switch
                # Find the user/account button (first button element) to open organization selector
                user_button_xpath = "//button[@type='button']"
                user_buttons = driver.find_elements(By.XPATH, user_button_xpath)
                if user_buttons:
                    # Click the first button to open the organization selection dropdown menu
                    safe_click(driver, user_buttons[0], "User button")
                    logger.info(f"Switch to client: {xero_account_name}")

                    # Search for and select the target organization from the new UI dropdown
                    # This function handles searching, validation, and clicking the target account
                    select_organisation_new_ui(browser, xero_account_name)
            else:
                # Target client is already selected - no action needed, log and continue
                logger.info(
                    f"Client '{xero_account_name}' is already selected. No switch needed.",
                )

        # OLD UI WORKFLOW: Navigate via Dashboard to access account selector
        elif has_dashboard(browser):
            # Legacy UI detected - use Dashboard-based navigation approach
            # Wait for Dashboard link element to become visible in the old UI navigation
            dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
            dashboard = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
            )
            # Click the Dashboard link to navigate to the dashboard page
            safe_click(driver, dashboard, "Clicked dashboard")
            logger.info("Clicked dashboard")

            # Locate the Chrome browser window with Xero Dashboard using Windows automation
            # This is needed for potential Windows-level interactions in the old UI
            dashboard_page = windows.find_window(
                "regex:.*Dashboard – Xero - Google Chrome",
            )
            logger.info(
                f"Attempting to switch Xero Blue Account to '{xero_account_name}'",
            )

            # Escape HTML special characters in account name for safe XPath usage in old UI
            html_account_name = xero_account_name.replace("&", "&amp;").replace(
                "'",
                "&apos;",
            )

            # Check if the target client is already selected in the old UI
            # This optimization prevents unnecessary navigation if already on the correct account
            client_is_already_selected = check_client_selected_old_ui(
                browser,
                html_account_name,
            )

            if not client_is_already_selected:
                # Target client is not currently selected - proceed with account switch
                logger.info(f"Switch to client: {xero_account_name}")

                # Search for and select the target organization using old UI workflow
                # This function handles the legacy account selector interface and search process
                search_organisation(browser, html_account_name)
            else:
                # Target client is already selected - no action needed, log and continue
                logger.info(
                    f"Client '{xero_account_name}' is already selected. No switch needed.",
                )

        # Neither home page nor dashboard found
        else:
            error_msg = (
                "Neither Home page nor Dashboard found. Unable to switch client."
            )
            logger.error(error_msg)
            raise Exception(error_msg)

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE SWITCH CLIENT")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Target Account Name: {xero_account_name}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE SWITCH CLIENT")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Target Account Name: {xero_account_name}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(f"xero_blue_switch_client failed due to {e}", exc_info=True)
        raise


def has_dashboard(browser) -> bool:
    """
    Check if the Dashboard link is present in the Xero navigation menu (old/legacy UI indicator).

    This function detects whether the Xero interface is using the legacy UI by checking for
    the presence of the Dashboard link in the navigation menu. The Dashboard link is specific
    to Xero's older interface version and is not present in the new UI.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.

    Returns:
        bool: True if Dashboard link is visible within 2 seconds (legacy UI detected).
              False if Dashboard link is not found (new UI or timeout).

    Raises:
        None: TimeoutException is caught internally and returns False.

    Notes:
        - Uses WebDriverWait with 2-second timeout for quick UI version detection.
        - Dashboard XPath: "//a[normalize-space(.)='Dashboard']"
        - Logs INFO level for success, ERROR level for absence.
    """
    try:
        driver = browser.driver
        dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
        WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
        )
        logger.info("Dashboard exist")
        return True
    except TimeoutException:
        logger.error("Dashboard does not exist")
        return False


def has_home_page(browser) -> bool:
    """
    Check if the Home link is present in the Xero navigation menu (new UI indicator).

    This function detects whether the Xero interface is using the new UI by checking for
    the presence of the Home link in the navigation menu. The Home link is specific to
    Xero's newer interface version and is not present in the legacy UI.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.

    Returns:
        bool: True if Home link is visible within 2 seconds (new UI detected).
              False if Home link is not found (legacy UI or timeout).

    Raises:
        None: TimeoutException and other exceptions are caught internally and return False.

    Notes:
        - Uses WebDriverWait with 2-second timeout for quick UI version detection.
        - Home link XPath: "//a[@role='link' and span[normalize-space(text())='Home']]"
        - Logs INFO level for success, ERROR level for absence.
    """
    try:
        driver = browser.driver
        WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, home_link_xpath)),
        )
        logger.info("Home button exist")
        return True
    except (TimeoutException, Exception):
        logger.error("Home button does not exist")
        return False


def check_client_selected_new_ui(browser, html_account_name) -> bool:
    """
    Verify if the target client is already selected in the new Xero UI.

    This function checks the new UI's account selector button to determine if the specified
    client/organization is currently active. It looks for an abbreviation element with the
    client name as its aria-label attribute, which indicates the currently selected account.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver.
        html_account_name (str): HTML-escaped account name to check (with &amp; and &apos;).

    Returns:
        bool: True if the specified client is currently selected (abbr element with matching
              aria-label found within 5 seconds).
              False if the client is not selected or element not found.

    Raises:
        None: TimeoutException and exceptions are caught internally and return False.

    Notes:
        - New UI XPath pattern: "//button[@type='button']//span//abbr[@aria-label='{name}']"
        - Uses WebDriverWait with 5-second timeout for element visibility check.
        - Logs "Logged in same user" if match found, "Logged in different user" otherwise.
    """
    try:
        driver = browser.driver
        new_account_client_xpath = (
            f"//button[@type='button']//span//abbr[@aria-label='{html_account_name}']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, new_account_client_xpath)),
        )
        logger.info("Logged in same user")
        return True
    except (TimeoutException, Exception):
        logger.info("Logged in diffrenet user")
        return False


def select_organisation_new_ui(browser, xero_account_name):
    """
    Search for and select the target organization in the new Xero UI account selector.

    This function handles the complete workflow for switching to a target organization in
    the new UI: it opens the search input, types the account name, validates the account
    exists in the search results, and clicks on the matching account link to perform the switch.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver.
        xero_account_name (str): Original account name to search for and select.

    Returns:
        None: Completes when the target account is selected successfully.

    Raises:
        Exception: If search input is not available, account does not exist in Xero,
                  or account link cannot be found/clicked after search.

    Notes:
        - Searches using placeholder "Search organizations" input field.
        - HTML-escapes account name for XPath matching (& → &amp;).
        - Validates account exists by checking for "No results found for" message.
        - Account link XPath: "//a[@role='link' and .//span[normalize-space(.)='{name}']]"
        - All steps are logged for debugging and audit purposes.
    """
    driver = browser.driver

    # Check if the organization search input field is available in the new UI
    # This validates that the account selector dropdown has opened successfully
    if has_search_input_new_ui(browser):
        # Locate the search input field and click to activate it for text entry
        search_input = driver.find_element(By.XPATH, new_ui_search_xpath)
        safe_click(driver, search_input, "Search organization input")
        logger.info("Clicked search option")

        # Clear any existing text and type the target account name for searching
        search_input.clear()
        search_input.send_keys(xero_account_name)
        logger.info(f"Typed into client name : {xero_account_name}")

        # Check if Xero displays "No results found" message indicating account doesn't exist
        # This validation prevents attempting to click on a non-existent account
        if not_account_listed(browser, xero_account_name):
            logger.error(f"Client does not exist in XERO : {xero_account_name}")
            raise Exception(f"Client does not exist in XERO : {xero_account_name}")

        # Prepare the account name for XPath by escaping special characters and trimming whitespace
        val_selector_name = xero_account_name.replace("&", "&amp;").strip()
        account_name_xpath = (
            f"//a[@role='link' and .//span[normalize-space(.)='{val_selector_name}']]"
        )

        # Verify that the account appears in the search results before attempting to click
        # This ensures the account link is present and visible in the dropdown
        if is_account_present(browser, val_selector_name):
            # Locate the account link element and click it to switch to the target organization
            account_link = driver.find_element(By.XPATH, account_name_xpath)
            safe_click(driver, account_link, f"Account: {val_selector_name}")
            logger.info(f"{val_selector_name} is selected")
        else:
            # Account was not found in search results even though "No results" wasn't shown
            raise Exception(f"Could Not Switch Client to : {xero_account_name}")


def has_search_input_new_ui(browser) -> bool:
    """Check if search organizations input element is present in new UI"""
    try:
        driver = browser.driver
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, new_ui_search_xpath)),
        )
        logger.info("Search option exist")
        return True
    except (TimeoutException, Exception):
        logger.info("Search option does not exist")
        return False


def not_account_listed(browser, xero_account_name) -> bool:
    """Check not account listed"""
    try:
        driver = browser.driver
        no_account_xpath = (
            "//p[starts-with(normalize-space(.), 'No results found for')]"
        )
        WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.XPATH, no_account_xpath)),
        )
        logger.info("No client found")
        return True
    except (TimeoutException, Exception):
        logger.info(f"Client {xero_account_name} found")
        return False


def is_account_present(browser, val_selector_name) -> bool:
    """Check the account present"""
    try:
        driver = browser.driver
        account_name_xpath = (
            f"//a[@role='link']//span[normalize-space(.)='{val_selector_name}']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_name_xpath)),
        )
        logger.info(f"Account : {val_selector_name} found")
        return True
    except (TimeoutException, Exception):
        logger.info(f"Account : {val_selector_name} does not exist")
        return False


def check_client_selected_old_ui(browser, html_account_name) -> bool:
    """Check client already selected or not"""
    try:
        driver = browser.driver
        old_ui_client_xpath = f"//div[@class='xnav-appbutton--body']//span[@class='xnav-appbutton--text' and normalize-space(text())='{html_account_name}']"
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, old_ui_client_xpath)),
        )
        return True
    except (TimeoutException, Exception):
        return False


def search_organisation(browser, html_account_name):
    """Change the user or organisation in old UI account"""
    driver = browser.driver
    old_ui_account_select_xpath = "//div[@class='xnav-appbutton--body']"

    if has_old_ui_change_organisation(browser):
        search_organisation_xpath = (
            "//input[@role='searchbox' and @aria-label='Search organisations']"
        )
        logger.info(f"Click - Change Organisation")

        search_element = driver.find_element(By.XPATH, search_organisation_xpath)
        relative_visibility = search_element.get_attribute("relativeVisibility")

        account_select = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, old_ui_account_select_xpath)),
        )
        safe_click(driver, account_select, "Account selector")

        if not relative_visibility:
            logger.info("Click - Account (relative visibility false)")
        else:
            logger.info("Click - Account")

        # Click account and wait for search organisation box
        if has_old_ui_search_organisation(browser):
            search_org = driver.find_element(By.XPATH, search_organisation_xpath)
            safe_click(driver, search_org, "Search organisation")
            logger.info("Click - Change organisation")

            if has_old_ui_search_box(browser):
                search_box_xpath = (
                    "//input[normalize-space(@placeholder)='Search organisations']"
                )
                search_box = driver.find_element(By.XPATH, search_box_xpath)
                safe_click(driver, search_box, "Search box")

                search_box.clear()
                search_box.send_keys(html_account_name)

                # check no account found
                if is_old_ui_no_account_found(browser):
                    raise Exception(
                        f"Client does not exist in XERO : {html_account_name}",
                    )

                # check corresponding name present
                if is_old_ui_account_present(browser, html_account_name):
                    account_name_xpath = f"//a[@class='xnav-verticalmenuitem--body xnav-menuitem-orgpractice']//span[normalize-space(.)='{html_account_name}']"
                    account_link = driver.find_element(By.XPATH, account_name_xpath)
                    safe_click(driver, account_link, f"Account: {html_account_name}")
                    logger.info(f"{html_account_name} clicked")
                else:
                    raise Exception(f"Could Not Switch Client to : {html_account_name}")


def is_old_ui_account_present(browser, html_account_name) -> bool:
    """Check the account present"""
    try:
        driver = browser.driver
        account_name_xpath = f"//a[@class='xnav-verticalmenuitem--body xnav-menuitem-orgpractice']//span[normalize-space(.)='{html_account_name}']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_name_xpath)),
        )
        logger.info(f"{html_account_name} is present")
        return True
    except (TimeoutException, Exception):
        logger.info(f"{html_account_name} not found")
        return False


def is_old_ui_no_account_found(browser) -> bool:
    """Check no account found"""
    try:
        driver = browser.driver
        no_account_found_xpath = (
            "//div[starts-with(normalize-space(.), 'No results found for')]"
        )
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, no_account_found_xpath)),
        )
        logger.info("No account found")
        return True
    except (TimeoutException, Exception):
        logger.info("User account found")
        return False


def has_old_ui_search_organisation(browser) -> bool:
    """Check the search organisation element"""
    try:
        driver = browser.driver
        search_organisation_xpath = (
            "//input[@role='searchbox' and @aria-label='Search organisations']"
        )
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, search_organisation_xpath)),
        )
        logger.info(f"Search organisation element found")
        return True
    except (TimeoutException, Exception):
        logger.info("Search organisation element is not found")
        return False


def has_old_ui_search_box(browser) -> bool:
    """Check the search box"""
    try:
        driver = browser.driver
        search_box_xpath = (
            "//input[normalize-space(@placeholder)='Search organisations']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, search_box_xpath)),
        )
        logger.info("Search box present")
        return True
    except (TimeoutException, Exception):
        logger.error("Search box not present")
        return False


def has_old_ui_change_organisation(browser) -> bool:
    """Check 'Change organisation' element"""
    try:
        driver = browser.driver
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, change_organisation_xpath)),
        )
        logger.info("Change organisation is present")
        return True
    except (TimeoutException, Exception):
        logger.info("Change organisation is not present")
        return False
