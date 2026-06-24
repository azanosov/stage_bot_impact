from __future__ import annotations

import logging
import time
from datetime import datetime


from RPA.MFA import MFA
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

mfa = MFA()

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click


# Set up logger
logger = setup_logger(__name__)


def xero_blue_login(
    browser,
    xero_email: str,
    xero_password: str,
    xero_blue_url: str,
    payroll_url: str,
    xero_blue_authenticator_secret_key: str,
    max_retry: int,
    is_authentication_code_is_entered: bool,
    is_user_logged_in_to_xero: bool
):
    """
    Orchestrate the complete Xero Blue login automation process.

    This is the main entry point for Xero Blue authentication. It manages the full
    login workflow — navigating to the login page, entering credentials, handling
    MFA authentication, and verifying the final login state. Comprehensive start/end
    logging with timestamps and duration is included for audit and debugging purposes.

    Args:
        browser: Browser instance with driver attribute (Selenium WebDriver wrapper)
        xero_email (str): Email address for Xero account login
        xero_password (str): Password for Xero account login
        xero_blue_url (str): URL for Xero Blue login page
        payroll_url (str): URL for Xero Payroll page (used to detect an existing session)
        xero_blue_authenticator_secret_key (str): Secret key for generating TOTP codes for MFA
        max_retry (int): Maximum number of MFA submission attempts before giving up

    Returns:
        bool: True if login is successful and user is confirmed logged in, False otherwise

    Raises:
        Exception: Re-raises any unexpected exception after logging failure details
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"STARTING: Xero Blue Login Automation - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Xero Blue URL: {xero_blue_url}")
    logger.info(f"Payroll URL: {payroll_url}")
    logger.info(f"Email: {xero_email}")
    logger.info(f"Max Retries: {max_retry}")
    logger.info(f"Authentication code is entered: {is_authentication_code_is_entered}")
    logger.info(f"User logged in to xero: {is_user_logged_in_to_xero}")
    logger.info("=" * 80)

    

    try:

        # STEP 1: Navigate to Xero Blue Login Page
        # Purpose: Ensure the browser is on the Xero Blue or Payroll login page before proceeding
        # Function: open_xero_blue_login_page(browser, xero_blue_url, payroll_url)
        # - Reads the current browser URL
        # - If already on Xero Blue or Payroll URL, skips navigation
        # - Otherwise, opens the Xero Blue login URL in the browser
        open_xero_blue_login_page(browser, xero_blue_url, payroll_url)

        # STEP 2: Verify Login State and Perform Login if Required
        # Purpose: Check whether the user is already authenticated; if not, complete the full login flow
        # Function: ensure_user_logged_in(browser, is_authentication_code_is_entered, xero_email, xero_password, ...)
        # - Checks current page for Home or Dashboard navigation elements
        # - If not logged in, navigates through email/password entry and MFA challenge
        # - Returns True if the user is confirmed logged in after all steps
        is_user_logged_in_to_xero = ensure_user_logged_in(
            browser,
            is_authentication_code_is_entered,
            xero_email,
            xero_password,
            xero_blue_authenticator_secret_key,
            max_retry,
        )

        # STEP 3: Final Login Verification
        # Purpose: Perform a definitive check on the current page to confirm the login state
        # Function: is_user_logged_in(browser)
        # - Looks for Home or Dashboard navigation elements on the current page
        # - Updates the final login status flag based on the result
        if is_user_logged_in(browser):
            logger.info("Final verification passed — user is logged in to Xero Blue")
            is_user_logged_in_to_xero = True
        else:
            logger.warning("Final verification failed — user is NOT logged in to Xero Blue")
            is_user_logged_in_to_xero = False

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(f"COMPLETED: Xero Blue Login Automation - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Final Login Status: {'SUCCESS' if is_user_logged_in_to_xero else 'FAILED'}")
        logger.info("=" * 80)

        return is_user_logged_in_to_xero

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(f"FAILED: Xero Blue Login Automation - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def open_xero_blue_login_page(browser, xero_blue_url: str, payroll_url: str) -> None:
    """
    Navigate to the Xero Blue login page if the browser is not already on a valid Xero page.

    Reads the current browser URL and compares it against the expected Xero Blue and
    Payroll URLs. If neither matches, the function navigates to the Xero Blue login URL.
    This prevents unnecessary page reloads and preserves any existing authenticated sessions.

    Args:
        browser: Browser instance with driver attribute (Selenium WebDriver wrapper)
        xero_blue_url (str): Target URL for the Xero Blue login page
        payroll_url (str): URL for the Xero Payroll page (treated as an already-valid Xero session)

    Returns:
        None
    """
    driver = browser.driver
    current_url = driver.current_url
    logger.info(f"Current browser URL: {current_url}")

    if xero_blue_url in current_url:
        logger.info("Browser is already on the Xero Blue login page — no navigation required")

    elif payroll_url in current_url:
        logger.info("Browser is already on the Xero Payroll page — no navigation required")

    else:
        logger.info("Xero Blue or Payroll URL not detected — navigating to Xero Blue login page")
        driver.get(xero_blue_url)
        logger.info(f"Xero Blue login page loaded successfully: {xero_blue_url}")


def ensure_user_logged_in(
    browser,
    is_authentication_code_is_entered: bool,
    xero_email: str,
    xero_password: str,
    xero_blue_authenticator_secret_key: str,
    max_retry: int,
) -> bool:
    """
    Check the current login state and initiate the login process only if the user is not authenticated.

    Inspects the current page for Home or Dashboard navigation elements to determine whether
    the user already has an active Xero session. If an active session is detected, the function
    returns True immediately without re-authenticating. If no active session is found, it delegates
    to the login page handler to complete credential entry and MFA.

    Args:
        browser: Browser instance with driver attribute (Selenium WebDriver wrapper)
        is_authentication_code_is_entered (bool): Legacy flag for MFA code entry state (currently unused)
        xero_email (str): Email address for Xero account login
        xero_password (str): Password for Xero account login
        xero_blue_authenticator_secret_key (str): Secret key for generating TOTP codes for MFA
        max_retry (int): Maximum number of MFA submission attempts before giving up

    Returns:
        bool: True if the user is already logged in or login completes successfully, False otherwise
    """
    logger.info("Checking current login state for Xero Blue")

    if not is_user_logged_in(browser):
        logger.info("User is not logged in — proceeding with login page authentication")
        return perform_xero_login(
            browser,
            is_authentication_code_is_entered,
            xero_email,
            xero_password,
            xero_blue_authenticator_secret_key,
            max_retry,
        )

    logger.info("Active Xero session detected — skipping login")
    return True


def perform_xero_login(
    browser,
    is_authentication_code_is_entered: bool,
    xero_email: str,
    xero_password: str,
    xero_blue_authenticator_secret_key: str,
    max_retry: int,
) -> bool:
    """
    Enter credentials on the Xero login page and handle MFA if required.

    Locates and fills the email and password input fields, submits the login form,
    then checks whether an MFA challenge is presented. If MFA is required, the function
    retries OTP generation and submission up to `max_retry` times with a 1-second delay
    between attempts.

    Args:
        browser: Browser instance with driver attribute (Selenium WebDriver wrapper)
        is_authentication_code_is_entered (bool): Legacy flag for MFA code entry state (currently unused)
        xero_email (str): Email address for Xero account login
        xero_password (str): Password for Xero account login
        xero_blue_authenticator_secret_key (str): Secret key for generating TOTP codes for MFA
        max_retry (int): Maximum number of MFA submission attempts before giving up

    Returns:
        bool: True if login succeeds (with or without MFA), False if email field is not
              found or MFA authentication exhausts all retry attempts

    Note:
        - Waits up to 5 seconds for each element to become visible before interacting
        - Uses safe_click utility for robust submit button interaction
        - MFA is retried up to `max_retry` times before the function returns False
    """
    logger.info("Xero Blue login page — beginning credential entry")
    driver = browser.driver

    try:
        xero_email_box_xpath = "//input[@id='xl-form-email']"
        xero_email_field = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, xero_email_box_xpath)),
        )
        logger.info("Email input field located successfully")

    except Exception:
        logger.error("Email input field not found on the page — login cannot proceed")
        return False

    xero_email_field.send_keys(xero_email)
    logger.info(f"Email address entered: {xero_email}")

    xero_password_box_xpath = "//input[@id='xl-form-password']"  # nosec B105
    xero_password_box_element = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, xero_password_box_xpath)),
    )
    logger.info("Password input field located successfully")
    xero_password_box_element.send_keys(xero_password)
    logger.info("Password entered successfully")

    submit_button_xpath = "//button[@id='xl-form-submit']"
    submit_button_ele = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, submit_button_xpath)),
    )
    logger.info("Submit button located successfully")
    safe_click(driver, submit_button_ele, "Submit login form")
    logger.info("Login form submitted — waiting for page response")

    if is_2fa_required(driver):
        logger.info("MFA challenge detected — beginning OTP authentication")
        for attempt in range(1, max_retry + 1):
            try:
                logger.info(f"MFA attempt {attempt} of {max_retry}")
                is_authentication_code_is_entered = submit_mfa_code(
                    driver, xero_blue_authenticator_secret_key
                )
                if is_authentication_code_is_entered:
                    logger.info(f"MFA authentication succeeded on attempt {attempt}")
                    return True
            except Exception as e:
                logger.warning(f"MFA attempt {attempt} failed with error: {e}")
            time.sleep(1)

        logger.error(f"MFA authentication failed after {max_retry} attempt(s) — login aborted")
        return False

    logger.info("No MFA challenge detected — login completed without MFA")
    return True


def is_2fa_required(driver) -> bool:
    """
    Detect whether a two-factor authentication (MFA) challenge is present on the current page.

    Waits up to 5 seconds for the Xero OTP input field to appear. This function is called
    immediately after submitting login credentials to determine whether the MFA step is
    required before the session is granted.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if the MFA OTP input field is visible within the timeout, False otherwise

    Note:
        Targets Xero's authenticator input via the combined CSS class selector
        'xui-textinput--input medium'.
    """
    try:
        authenticator_box_xpath = "//input[contains(@class, 'xui-textinput--input') and contains(@class, 'medium')]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, authenticator_box_xpath)),
        )
        logger.info("MFA OTP input field detected — 2FA is required")
        return True

    except TimeoutException:
        logger.info("MFA OTP input field not detected — 2FA is not required")
        return False


def submit_mfa_code(driver, xero_blue_authenticator_secret_key: str) -> bool:
    """
    Generate a TOTP code and submit it to complete the MFA authentication challenge.

    Uses the RPA.MFA library to generate a time-based one-time password (TOTP) from the
    provided secret key, enters the code into the OTP input field, optionally checks the
    "Trust this device" checkbox to suppress future MFA prompts, and clicks the confirm button
    to finalise the MFA step.

    Args:
        driver: Selenium WebDriver instance
        xero_blue_authenticator_secret_key (str): Base32-encoded secret key for TOTP generation

    Returns:
        bool: True if the OTP was entered and the confirm button was clicked successfully,
              False if any step raises an unexpected exception

    Note:
        - Waits up to 5 seconds for the OTP input field and confirm button to be interactable
        - The trust-device checkbox click is attempted but failure does not abort the process
    """
    try:
        authenticator_box_xpath = "//input[contains(@class, 'xui-textinput--input') and contains(@class, 'medium')]"
        login_confirm_button_xpath = "//button[@class='xui-button xui-button-main xui-button-medium xui-button-fullwidth']"

        otp_code = mfa.get_time_based_otp(xero_blue_authenticator_secret_key)
        logger.info(f"TOTP code generated successfully: {otp_code}")

        otp_element = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, authenticator_box_xpath)),
        )
        otp_element.send_keys(otp_code)
        logger.info("OTP code entered into the authenticator input field")

        click_trust_device_checkbox(driver)

        confirm_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, login_confirm_button_xpath)),
        )
        confirm_btn.click()
        logger.info("MFA confirm button clicked — awaiting session confirmation")
        return True

    except Exception as e:
        logger.error(f"MFA submission failed for secret key '{xero_blue_authenticator_secret_key}': {e}")
        return False


def click_trust_device_checkbox(driver) -> None:
    """
    Attempt to check the "Trust this device" checkbox during the MFA challenge step.

    Uses JavaScript to click the checkbox element to avoid interaction issues with
    non-standard Xero UI components. Checking this box can reduce or eliminate future
    MFA prompts on the same device. Failure is handled silently because this step is
    optional and should not block the overall login flow.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        None

    Note:
        - Logs a success message when the checkbox is found and clicked
        - Logs an informational message if the checkbox is absent (e.g. already selected,
          not rendered for this session, or removed by a Xero UI update)
        - Does not raise exceptions under any circumstance
    """
    try:
        checkbox = driver.find_element(
            "xpath",
            "//input[@type='checkbox' and @data-automationid='auth-remembermecheckbox--input']",
        )
        driver.execute_script("arguments[0].click();", checkbox)
        logger.info("'Trust this device' checkbox clicked successfully")
    except Exception:
        logger.info("'Trust this device' checkbox not found — possibly already selected or not displayed")


def is_user_logged_in(browser) -> bool:
    """
    Verify the current login state by checking for Home or Dashboard navigation elements.

    Inspects the current page DOM for the presence of either the "Home" or "Dashboard"
    navigation link that Xero renders for authenticated users. The Home element is checked
    first; if not found, the function falls back to checking for the Dashboard element.

    Args:
        browser: Browser instance with driver attribute (Selenium WebDriver wrapper)

    Returns:
        bool: True if the Home or Dashboard navigation element is visible (user is logged in),
              False if neither element is found within the timeout period

    Note:
        - Uses a 5-second explicit wait for each element check
        - Home element is matched via normalised span text: normalize-space()='Home'
        - Dashboard element is matched via normalised anchor text: normalize-space(.)='Dashboard'
        - Returns False only after both checks have timed out
    """
    logger.info("Verifying login state — checking for Home or Dashboard navigation element")
    driver = browser.driver
    dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
    homepage_xpath = "//a[.//span[normalize-space()='Home']]"

    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, homepage_xpath)),
        )
        logger.info("Home navigation element found — user is confirmed logged in to Xero Blue")
        return True

    except Exception:
        try:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, dashboard_xpath)),
            )
            logger.info("Dashboard navigation element found — user is confirmed logged in to Xero Blue")
            return True

        except TimeoutException:
            logger.info("Neither Home nor Dashboard element found — user is NOT logged in to Xero Blue")
            return False
