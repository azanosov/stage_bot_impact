"""
Xero Practice Protect Login Module

This module handles the complete login workflow for Xero Practice Protect, including:
- Authentication via Practice Protect portal
- Application selection and navigation
- Multi-factor authentication (MFA/OTP) handling
- Portal account switching and verification

Main Function:
    xero_blue_practice_protect_login: Orchestrates the complete login workflow
"""

from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_practiceprotect.login import login
from iaa_rpa_practiceprotect.search import search
from iaa_rpa_utils.browser import safe_click
from iaa_rpa_utils.browser import setup_logger
from RPA.MFA import MFA
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Initialize MFA handler for OTP generation
mfa = MFA()

# Set up logger for this module
logger = setup_logger(__name__)


def xero_blue_practice_protect_login(
    browser,
    xero_application_name,
    practice_protect_user_name,
    practice_protect_password,
    practice_protect_base_url,
    practice_protect_oauth_otp,
    practice_protect_secret_key,
    xero_secret_key,
    max_retries,
    xero_practice_overview_url,
    is_user_logged_in_to_xero,
):
    """
    Orchestrates the complete Xero Practice Protect login workflow.

    This function manages the entire authentication process from portal login
    through MFA verification to final Xero Blue access confirmation, including:
    1. Logging into Practice Protect portal with credentials and optional OTP
    2. Searching for and selecting the Xero application tile
    3. Handling multi-factor authentication with configurable retry logic
    4. Navigating to the correct portal account in Xero
    5. Verifying successful login via Home or Dashboard navigation element

    Args:
        browser: Browser instance containing the Selenium WebDriver
        xero_application_name (str): Name of the Xero application tile to access
        practice_protect_user_name (str): Practice Protect portal username
        practice_protect_password (str): Practice Protect portal password
        practice_protect_base_url (str): Base URL for Practice Protect portal
        practice_protect_oauth_otp (bool): Whether OTP is required for Practice Protect login
        practice_protect_secret_key (str): Secret key for Practice Protect OTP generation
        xero_secret_key (str): Secret key for Xero MFA/OTP generation
        max_retries (int): Maximum number of OTP authentication retry attempts
        xero_practice_overview_url (str): Expected URL fragment for Xero Practice Manager
        is_user_logged_in_to_xero (bool): Current login status flag before workflow starts

    Returns:
        bool: Updated login status — True if successfully logged in, False otherwise

    Raises:
        Exception: If Practice Protect portal login fails
        Exception: If Xero application tile is not found in search results
        Exception: If authenticator page does not load
        Exception: If MFA authentication fails after max_retries attempts
        ValueError: If xero_secret_key is missing when OTP is required
    """

    start_time = datetime.now()
    try:
        logger.info("=" * 80)
        logger.info(
            f"STARTING: Xero Practice Protect Login - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Application Name: {xero_application_name}")
        logger.info(f"Username: {practice_protect_user_name}")
        logger.info(f"Base URL: {practice_protect_base_url}")
        logger.info(f"Max Retries: {max_retries}")
        logger.info(f"Initial Login Status: {is_user_logged_in_to_xero}")
        logger.info("=" * 80)

        # Extract WebDriver from browser instance
        driver = browser.driver
        logger.info("Browser driver extracted from browser instance")

        # STEP 1: Login to Practice Protect Portal
        # Purpose: Authenticate the user into Practice Protect using username, password, and optional OTP
        # Function: login()
        # - Navigates to Practice Protect base URL
        # - Enters username and password credentials
        # - Handles OTP verification if practice_protect_oauth_otp is enabled
        login(
            browser_driver=driver,
            username=practice_protect_user_name,
            password=practice_protect_password,
            base_url=practice_protect_base_url,
            oauth_otp=practice_protect_oauth_otp,
            otp_secret=practice_protect_secret_key,
        )
        logger.info(
            "STEP 1 COMPLETE: Successfully authenticated into Practice Protect portal",
        )

        # STEP 2: Search for Xero Application
        # Purpose: Locate the Xero application tile within the Practice Protect app launcher
        # Function: search()
        # - Types the application name into the search bar
        # - Filters the application tiles by name
        search(driver, xero_application_name)
        logger.info(
            f"STEP 2 COMPLETE: Search executed for application '{xero_application_name}'",
        )

        # STEP 3: Verify Search Results
        # Purpose: Confirm that the Xero application tile exists in the search results
        # Function: verify_search_results_exist()
        # - Checks for 'No matches found. Try again.' message in the empty-results container
        # - Returns True if no results found, raises exception to halt the workflow
        if verify_search_results_exist(driver):
            logger.error(
                f"STEP 3 FAILED: No application tile found matching '{xero_application_name}'",
            )
            raise Exception(f"No applications exist matching: {xero_application_name}")

        logger.info("STEP 3 COMPLETE: Application tile found in search results")

        # STEP 4: Open Xero Application in New Window
        # Purpose: Click the Xero application tile and switch focus to the new browser window
        # Function: switch_to_xero_application_window()
        # - Locates the application tile element by name
        # - Stores the current window handle before clicking
        # - Clicks the application link to open it in a new tab or window
        # - Waits for the new window to open and switches driver focus to it
        switch_to_xero_application_window(driver, xero_application_name)
        logger.info("STEP 4 COMPLETE: Switched to Xero application window successfully")

        # STEP 5: Perform MFA / OTP Authentication
        # Purpose: Complete multi-factor authentication required by Xero after portal SSO
        # Function: perform_mfa_authentication()
        # - Verifies the authenticator code entry page has loaded
        # - Generates a time-based OTP using the provided secret key
        # - Enters the OTP code into the authenticator input field
        # - Handles optional 'Skip for 30 days' and 'Trust this device' checkboxes
        # - Clicks Confirm and retries up to max_retries times on failure
        perform_mfa_authentication(driver, browser, xero_secret_key, max_retries)
        logger.info("STEP 5 COMPLETE: MFA authentication completed successfully")

        # STEP 6: Verify Login and Navigate to Portal Account
        # Purpose: Confirm the user is on the correct Xero Practice Manager tab and is logged in
        # Function: verify_and_navigate_to_portal_account()
        # - Iterates through all open browser tabs
        # - Identifies the Xero Practice Manager tab by URL match
        # - Calls check_user_logged_in() to confirm Home or Dashboard element is visible
        # - Returns updated login status
        is_user_logged_in_to_xero = verify_and_navigate_to_portal_account(
            driver,
            xero_practice_overview_url,
            is_user_logged_in_to_xero,
        )
        logger.info(
            f"STEP 6 COMPLETE: Portal account verified. Login status: {is_user_logged_in_to_xero}",
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Practice Protect Login - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Final Login Status: {is_user_logged_in_to_xero}")
        logger.info("=" * 80)

        return is_user_logged_in_to_xero

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Practice Protect Login - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def verify_search_results_exist(driver) -> bool:
    """
    Check whether the Practice Protect search returned any application results.

    Inspects the DOM for the 'No matches found. Try again.' message inside the
    empty-results container. This message is only rendered when the search query
    does not match any application tiles.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if the 'No matches found' message is visible (no results),
              False if results are present or the message is not found within timeout
    """
    logger.info(
        "Verifying search results are present for the given application name...",
    )

    try:
        no_result_xpath = "//div[contains(@class,'empty-results')]//*[normalize-space(text())='No matches found. Try again.']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, no_result_xpath)),
        )
        logger.warning(
            "Search returned no results — 'No matches found. Try again.' message is visible",
        )
        return True

    except TimeoutException:
        logger.info(
            "Search results are present — empty-results message was not displayed",
        )
        return False
    except Exception as e:
        logger.warning(f"Unexpected error while checking search result state: {str(e)}")
        return False


def switch_to_xero_application_window(driver, xero_application_name):
    """
    Click the Xero application tile and switch WebDriver focus to the new browser window.

    Locates the application tile by name within the Practice Protect app launcher,
    stores the current window handle, performs a safe click to open the application,
    then waits for the new window or tab to appear and switches the driver to it.

    Args:
        driver: Selenium WebDriver instance
        xero_application_name (str): Display name of the Xero application tile to click

    Raises:
        TimeoutException: If the application tile element is not visible within 5 seconds
        Exception: If switching to the new window fails
    """
    logger.info(
        f"Locating application tile for '{xero_application_name}' in the app launcher...",
    )

    # Locate the application tile element by display name
    application_xpath = f"//div[contains(@class,'app-tile-v2-container')]//a[normalize-space()='{xero_application_name}']"
    application_element = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, application_xpath)),
    )
    logger.info(f"Application tile located: '{xero_application_name}'")

    # Store current window handle before clicking to identify the new window later
    original_window = driver.current_window_handle
    logger.info(f"Current window handle stored before click: {original_window}")

    # Click the application tile to trigger the new window or tab
    safe_click(
        driver,
        application_element,
        f"Application tile: {xero_application_name}",
    )
    logger.info(
        f"Clicked application tile: '{xero_application_name}' — waiting for new window to open...",
    )

    # Wait for the new window or tab to appear
    time.sleep(3)

    all_windows = driver.window_handles
    logger.info(f"Total open windows/tabs after click: {len(all_windows)}")

    # Switch to the newly opened window if one was created
    if len(all_windows) > 1:
        new_window = [window for window in all_windows if window != original_window][0]
        driver.switch_to.window(new_window)
        logger.info(f"Switched WebDriver focus to new window: {new_window}")
        logger.info(f"Current URL after window switch: {driver.current_url}")
    else:
        logger.warning(
            "No new window opened after clicking application tile — remaining on current window",
        )
        logger.info(f"Current URL: {driver.current_url}")

    # Allow the application page to fully load before proceeding
    logger.info("Waiting for Xero application page to fully load...")
    time.sleep(10)


def perform_mfa_authentication(driver, browser, xero_secret_key, max_retries):
    """
    Complete Xero MFA authentication by generating and submitting a time-based OTP.

    Verifies the authenticator code entry page has loaded, then enters a generated
    OTP code with configurable retry logic. Also handles optional 'Skip for 30 days'
    and 'Trust this device' checkboxes before submitting the confirmation.

    Args:
        driver: Selenium WebDriver instance
        browser: Browser instance used for checkbox interaction helpers
        xero_secret_key (str): TOTP secret key used to generate the 6-digit OTP code
        max_retries (int): Maximum number of OTP submission attempts before raising

    Raises:
        Exception: If the authenticator code entry page is not visible within 5 seconds
        Exception: If OTP confirmation fails on all max_retries attempts
        ValueError: If xero_secret_key is empty or None
    """
    logger.info(
        "Starting MFA authentication — verifying authenticator page has loaded...",
    )

    # Confirm the authenticator code entry page is displayed before proceeding
    try:
        authenticator_page_xpath = "//h1[normalize-space()='Enter the 6-digit code found in your authenticator app']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, authenticator_page_xpath)),
        )
        logger.info(
            "Authenticator code entry page confirmed — proceeding with OTP submission",
        )
    except TimeoutException:
        logger.error(
            "Authenticator code entry page did not load within the expected timeout",
        )
        raise Exception("Authenticator page does not exist or did not load in time")

    # Retry loop for OTP submission in case of timing or input issues
    authentication_successful = False
    retry_count = 0

    while not authentication_successful and retry_count < max_retries:
        try:
            retry_count += 1
            logger.info(f"OTP submission attempt {retry_count} of {max_retries}")

            # Validate secret key is available before generating OTP
            if not xero_secret_key:
                logger.error(
                    "Xero OTP secret key is missing — cannot generate OTP code",
                )
                raise ValueError(
                    "OTP secret key is required for Xero MFA authentication",
                )

            # Generate a fresh time-based OTP using the secret key
            otp_code = mfa.get_time_based_otp(xero_secret_key)
            logger.info(f"Time-based OTP code generated successfully: {otp_code}")

            # Locate and populate the OTP input field
            logger.info("Locating OTP code input field on the authenticator page...")
            otp_input_locator = (
                By.XPATH,
                "//input[contains(@class, 'xui-textinput--input') and contains(@class, 'medium')]",
            )
            otp_input_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located(otp_input_locator),
            )
            logger.info("OTP input field located — entering generated OTP code")

            otp_input_field.clear()
            otp_input_field.send_keys(otp_code)
            logger.info("OTP code entered into input field")

            # Handle optional 'Skip for 30 days' checkbox if displayed
            handle_remember_device_checkbox(browser)

            # Handle optional 'Trust this device' checkbox if displayed
            handle_trust_device_checkbox(browser)

            # Submit the OTP code via the Confirm button
            logger.info("Locating and clicking the Confirm button to submit OTP...")
            confirm_button_xpath = (
                "//button[@type='submit' and normalize-space()='Confirm']"
            )
            confirm_button = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, confirm_button_xpath)),
            )
            safe_click(driver, confirm_button, "MFA Confirm button")
            logger.info("Confirm button clicked — OTP submitted successfully")

            authentication_successful = True
            logger.info("MFA authentication completed successfully")

        except Exception as e:
            logger.warning(f"OTP submission attempt {retry_count} failed: {str(e)}")

            if retry_count >= max_retries:
                logger.error(
                    f"MFA authentication failed after {max_retries} attempt(s) — raising exception",
                )
                raise Exception(
                    f"OTP authentication failed after {max_retries} attempts",
                ) from e
            else:
                logger.info(
                    f"Waiting 2 seconds before retry attempt {retry_count + 1} of {max_retries}...",
                )
                time.sleep(2)


def handle_remember_device_checkbox(browser):
    """
    Check the 'Skip this step for 30 days' checkbox on the MFA page if it is present.

    Attempts to locate the rememberDevice checkbox. If found and not already selected,
    it is checked to suppress repeated MFA prompts for 30 days. If the checkbox is
    absent or already selected, the function exits silently without raising an error.

    Args:
        browser: Browser instance containing the Selenium WebDriver as browser.driver
    """
    logger.info("Checking for 'Skip this step for 30 days' checkbox on MFA page...")

    try:
        skip_checkbox_locator = (
            By.XPATH,
            "//input[@type='checkbox' and @name='rememberDevice']",
        )
        checkbox_element = WebDriverWait(browser.driver, 3).until(
            EC.presence_of_element_located(skip_checkbox_locator),
        )

        if not checkbox_element.is_selected():
            safe_click(
                browser.driver,
                checkbox_element,
                "'Skip this step for 30 days' checkbox",
            )
            logger.info(
                "'Skip this step for 30 days' checkbox checked — MFA will be skipped for 30 days",
            )
        else:
            logger.info(
                "'Skip this step for 30 days' checkbox is already selected — no action needed",
            )

    except TimeoutException:
        logger.info(
            "'Skip this step for 30 days' checkbox not present on this page — skipping",
        )
    except Exception as e:
        logger.warning(
            f"Unexpected error while handling 'Skip for 30 days' checkbox: {str(e)}",
        )


def handle_trust_device_checkbox(browser):
    """
    Check the 'Trust this device' checkbox on the MFA page if it is present.

    Attempts to locate the trust-device checkbox using its automation ID attribute.
    If found and not already selected, it is checked to mark the device as trusted.
    If the checkbox is absent or already selected, the function exits silently.

    Args:
        browser: Browser instance containing the Selenium WebDriver as browser.driver
    """
    logger.info("Checking for 'Trust this device' checkbox on MFA page...")

    try:
        trust_checkbox_locator = (
            By.XPATH,
            "//input[@type='checkbox' and @data-automationid='auth-remembermecheckbox--input']",
        )
        checkbox_element = WebDriverWait(browser.driver, 3).until(
            EC.presence_of_element_located(trust_checkbox_locator),
        )

        if not checkbox_element.is_selected():
            safe_click(browser.driver, checkbox_element, "'Trust this device' checkbox")
            logger.info(
                "'Trust this device' checkbox checked — device marked as trusted",
            )
        else:
            logger.info(
                "'Trust this device' checkbox is already selected — device already trusted",
            )

    except TimeoutException:
        logger.info("'Trust this device' checkbox not present on this page — skipping")
    except Exception as e:
        logger.warning(
            f"Unexpected error while handling 'Trust this device' checkbox: {str(e)}",
        )


def verify_and_navigate_to_portal_account(
    driver,
    xero_practice_overview_url,
    is_user_logged_in_to_xero,
):
    """
    Iterate through all open browser tabs to find the Xero Practice Manager tab and verify login.

    Switches the WebDriver to each open tab in sequence and checks whether the tab URL
    matches the expected Xero Practice Manager overview URL. Once the matching tab is found,
    calls check_user_logged_in() to confirm the user is authenticated, then returns the
    updated login status.

    Args:
        driver: Selenium WebDriver instance
        xero_practice_overview_url (str): URL fragment expected in the Xero Practice Manager tab
        is_user_logged_in_to_xero (bool): Current login status prior to verification

    Returns:
        bool: Updated login status — True if Home or Dashboard element is found, False otherwise
    """
    logger.info(
        "Scanning all open browser tabs to locate the Xero Practice Manager tab...",
    )

    all_tabs = driver.window_handles
    logger.info(f"Total open browser tabs to check: {len(all_tabs)}")

    # Iterate through each tab and match against the expected Practice Manager URL
    for tab_index, handle in enumerate(all_tabs, 1):
        driver.switch_to.window(handle)
        current_url = driver.current_url
        logger.info(f"Checking tab {tab_index} of {len(all_tabs)}: {current_url}")

        if xero_practice_overview_url in current_url:
            logger.info(
                f"Xero Practice Manager tab identified at tab {tab_index} — verifying login state...",
            )

            # Confirm login by checking for Home or Dashboard navigation element
            is_user_logged_in_to_xero = check_user_logged_in(driver)
            logger.info(
                f"Login verification complete — login status: {is_user_logged_in_to_xero}",
            )
            break

    else:
        logger.warning(
            f"Xero Practice Manager tab not found after checking {len(all_tabs)} tab(s) — "
            f"expected URL fragment: '{xero_practice_overview_url}'",
        )

    return is_user_logged_in_to_xero


def check_user_logged_in(driver) -> bool:
    """
    Verify the current login state by checking for Home or Dashboard navigation elements.

    Inspects the current page DOM for the presence of either the 'Home' or 'Dashboard'
    navigation link that Xero renders for authenticated users. The Home element is checked
    first; if not found within timeout, the function falls back to checking for Dashboard.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if the Home or Dashboard navigation element is visible (user is logged in),
              False if neither element is found within the timeout period

    Note:
        - Uses a 5-second explicit wait for each element check
        - Home element is matched via normalised span text: normalize-space()='Home'
        - Dashboard element is matched via normalised anchor text: normalize-space(.)='Dashboard'
        - Returns False only after both checks have timed out
    """
    logger.info(
        "Verifying login state — checking for Home or Dashboard navigation element...",
    )

    homepage_xpath = "//a[.//span[normalize-space()='Home']]"
    dashboard_xpath = "//a[normalize-space(.)='Dashboard']"

    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, homepage_xpath)),
        )
        logger.info(
            "Home navigation element found — user is confirmed logged in to Xero Blue",
        )
        return True

    except Exception:
        try:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
            )
            logger.info(
                "Dashboard navigation element found — user is confirmed logged in to Xero Blue",
            )
            return True

        except TimeoutException:
            logger.info(
                "Neither Home nor Dashboard element found — user is NOT logged in to Xero Blue",
            )
            return False
