"""
This module has not been refactored.

If you need the functionality provided by this module,
please first contact Praveen Lobo and/or Alexander Zanosov.
"""


from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_check_payroll_module_present(
    browser,
    client_name,
    is_payroll_exist,
):
    """
    Check whether the Payroll module is present and enabled for a Xero client.

    This function verifies if the Payroll tab is visible in the Xero Blue navigation menu,
    which indicates whether the client has the Payroll module enabled. The function supports
    both Xero's legacy UI and new UI interface versions by attempting to locate the Payroll
    tab using different XPath selectors. This check is essential before attempting to download
    payroll-related reports, as clients without the Payroll module will not have payroll data
    available.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.
                The browser must be logged in and positioned on any Xero page where the main
                navigation menu is visible.
        client_name (str): Name of the Xero client organization being checked.
                          Used for logging and audit trail purposes.
        is_payroll_exist: Initial/default value for payroll existence flag (typically None or False).
                         This parameter is overwritten by the function's actual detection result.

    Returns:
        bool: True if the Payroll tab is found in the navigation menu (module is enabled).
              False if the Payroll tab is not found (module is not enabled or not available).
              Returns the value even on exceptions to ensure calling code can handle the result.

    Raises:
        Exception: Any exception during payroll tab detection is caught, logged with full
                  stack trace, and the function returns the is_payroll_exist value (likely False).
                  Exceptions are not re-raised to allow graceful degradation.

    Notes:
        - The function checks for both new UI and old UI Payroll tab selectors for compatibility.
        - Uses Selenium WebDriverWait with 5-second timeout for element visibility checks.
        - New UI XPath: "//button[.//span[normalize-space(text())='Payroll']]"
        - Old UI XPath: "//button[@type='button' and normalize-space(text())='Payroll']"
        - Comprehensive logging includes start/end timestamps, duration, and success/failure status.
        - All operations are logged with INFO level for success and ERROR level for failures.
        - The function includes banner separators (80 "=" characters) for clear log visibility.
        - Duration is calculated and logged in seconds with 2 decimal precision.

    Example:
        >>> browser = SeleniumBrowser()
        >>> xero_blue_login(browser, email, password, url, service_key)
        >>> has_payroll = xero_blue_check_payroll_module_present(
        ...     browser=browser,
        ...     client_name="ABC Company Pty Ltd",
        ...     is_payroll_exist=None
        ... )
        >>> if has_payroll:
        ...     xero_blue_download_payroll_employee_summary_report(...)
        ... else:
        ...     logger.info("Skipping payroll reports - module not enabled")
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE CHECK PAYROLL MODULE PRESENT")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name: {client_name}")
    logger.info("=" * 80)

    try:

        # Check if the payroll tab exists in the navigation menu
        is_payroll_exist = does_have_payroll_tab(browser)

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(
            f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE CHECK PAYROLL MODULE PRESENT",
        )
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Payroll Module Present: {is_payroll_exist}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        return is_payroll_exist

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE CHECK PAYROLL MODULE PRESENT")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Payroll Module Present: {is_payroll_exist}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(
            f"xero_blue_check_payroll_module_present failed due to {e}",
            exc_info=True,
        )
        return is_payroll_exist


def does_have_payroll_tab(browser) -> bool:
    """
    Detect the presence of the Payroll tab in Xero's navigation menu.

    This function attempts to locate the Payroll tab in the Xero interface using two different
    XPath selectors to support both the new UI and legacy UI versions of Xero. It first tries
    to find the Payroll tab using the new UI selector, and if that fails (TimeoutException),
    it falls back to the old UI selector. If neither selector finds the Payroll tab, the
    function concludes that the Payroll module is not enabled for this client.

    The function uses Selenium WebDriverWait with explicit waits to check for element visibility,
    ensuring that the page has fully loaded before determining whether the tab exists.

    Args:
        browser: SeleniumBrowser instance containing the WebDriver with an active Xero session.
                Must be positioned on a page where the main navigation menu is visible (e.g.,
                Dashboard, Reports, or any main Xero page).

    Returns:
        bool: True if the Payroll tab is found in either the new UI or old UI navigation menu,
              indicating that the Payroll module is enabled for this client.
              False if the Payroll tab is not found after checking both UI versions,
              indicating that the Payroll module is not enabled or not available.

    Raises:
        None: This function catches all exceptions internally and returns False if the Payroll
              tab cannot be found. No exceptions are propagated to the caller.

    Notes:
        - New UI XPath: "//button[.//span[normalize-space(text())='Payroll']]"
          This selector targets a button element with a nested span containing "Payroll" text.
        - Old UI XPath: "//button[@type='button' and normalize-space(text())='Payroll']"
          This selector targets a button element with type="button" and direct "Payroll" text.
        - Uses Selenium WebDriverWait with 5-second timeout for each UI version check.
        - The function uses a cascading try-except pattern: tries new UI first, then old UI.
        - All detection attempts are logged at INFO level for debugging and audit purposes.
        - The 5-second timeout is sufficient for page loads but avoids excessive waiting.

    Example:
        >>> browser = SeleniumBrowser()
        >>> xero_blue_login(browser, email, password, url, service_key)
        >>> has_payroll = does_have_payroll_tab(browser)
        >>> if has_payroll:
        ...     logger.info("Payroll module detected - can download payroll reports")
        ... else:
        ...     logger.info("Payroll module not detected - skipping payroll reports")
    """
    try:
        # Attempt to locate Payroll tab using New UI selector
        # New UI uses a nested button structure with span elements
        payroll_new_ui_xpath = "//button[.//span[normalize-space(text())='Payroll']]"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, payroll_new_ui_xpath)),
        )
        logger.info("Payroll tab is exist")
        is_payroll_exist = True
        return is_payroll_exist

    except Exception:
        # New UI selector failed - try Old UI selector as fallback
        try:
            # Attempt to locate Payroll tab using Old UI (legacy) selector
            # Old UI uses a simpler button structure with direct text content
            payroll_tab = (
                "//button[@type='button' and normalize-space(text())='Payroll']"
            )
            WebDriverWait(browser.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, payroll_tab)),
            )
            logger.info("Payroll tab is exist")
            is_payroll_exist = True
            return is_payroll_exist

        except Exception:
            # Both UI selectors failed - Payroll tab does not exist
            logger.info("Payroll tab does not exist")
            is_payroll_exist = False
            return is_payroll_exist
