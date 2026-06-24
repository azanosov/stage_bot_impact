from __future__ import annotations

import html
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_logout(
    browser,
    user_name: str,
    login_page_title: str,
):
    """
    Main entry point to log out the user from Xero Blue application.

    Decodes any HTML entities in the username, then initiates the full logout
    workflow including clicking the logout button and closing the browser window.
    Captures start/end times and logs duration and result for observability.

    Args:
        browser: Browser object containing the Selenium WebDriver instance. Must
                 have a 'driver' attribute with the active WebDriver session.
        user_name (str): The username to log out. HTML entities (e.g. '&amp;')
                         are automatically decoded before use.
        login_page_title (str): Expected title of the Xero login page. Used to
                                determine whether the browser window should be
                                closed after logout completes.

    Returns:
        bool: Returns False if an exception occurs during logout.
              Returns None (implicitly) on success.

    Example:
        >>> xero_blue_logout(browser, "john.doe@example.com", "Xero | Log in")
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Logout - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Username: {user_name}")
    logger.info(f"Login Page Title: {login_page_title}")
    logger.info("=" * 80)

    try:

        # Decode HTML entities in username
        # Purpose: Ensure the username string is clean before using it in XPath selectors
        # Function: html.unescape()
        # - Converts encoded entities such as '&amp;' back to their original characters
        decoded_username = html.unescape(user_name)
        logger.info(f"Username decoded successfully: {decoded_username}")

        # Perform Logout and Close Browser
        # Purpose: Click the user avatar, trigger logout, and close the browser window
        # Function: perform_logout_and_close_browser(browser, decoded_username, login_page_title)
        # - Locates the user button using the decoded username as the aria-label
        # - Clicks the user button to reveal the dropdown menu
        # - Clicks the Log out link in the dropdown
        # - Closes the browser window if the current page is the login page
        perform_logout_and_close_browser(browser, decoded_username, login_page_title)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Logout - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"User: {user_name}")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Logout - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        return False


def perform_logout_and_close_browser(
    browser,
    decoded_username: str,
    login_page_title: str,
):
    """
    Click the user button and logout link, then close the browser window.

    Attempts to log out by locating the user avatar button via aria-label and
    clicking the 'Log out' link in the revealed dropdown menu. If logout elements
    are not found (e.g. already logged out), the function logs a warning and
    proceeds to check whether the browser window should be closed. The window is
    closed only when the current page title matches the expected login page title.

    Args:
        browser: Browser object containing the Selenium WebDriver instance. Must
                 have a 'driver' attribute with the active WebDriver session.
        decoded_username (str): Plain-text username (HTML entities already decoded)
                                used to build the XPath aria-label selector for the
                                user avatar button.
        login_page_title (str): Expected title of the Xero login page. The browser
                                window is closed only if this title is found in the
                                current page title after logout.

    Returns:
        None

    Notes:
        - Uses a 5-second explicit wait for each clickable element.
        - Silently handles the case where the user is already logged out.
        - Always attempts to close the browser window if on the login page,
          regardless of whether the logout click succeeded.
    """
    driver = browser.driver

    try:
        user_button_xpath = f"//button[contains(@aria-label, '{decoded_username}')]"
        logout_button_xpath = "//a[.//span[text()='Log out']]"

        # Click user button to open dropdown menu
        user_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, user_button_xpath)),
        )
        safe_click(driver, user_button, f"User button for {decoded_username}")
        logger.info(f"User avatar button clicked for: {decoded_username}")

        # Click logout link in dropdown
        logout_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, logout_button_xpath)),
        )
        safe_click(driver, logout_button, "Logout button")
        logger.info(f"Logout successful for user: {decoded_username}")

    except Exception:
        logger.warning(
            f"Logout elements not found — user may already be logged out: {decoded_username}",
        )

    # Close browser window if redirected to the login page
    current_title = driver.title
    if login_page_title in current_title:
        try:
            driver.close()
            logger.info("Browser window closed after logout")
        except Exception:
            logger.info("Browser window already closed")
