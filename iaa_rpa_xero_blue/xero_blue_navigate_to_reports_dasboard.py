from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


# ------------------ Main Function ------------------
def xero_blue_navigate_to_reports_dashboard(browser):
    """
    Navigate to the Reports Dashboard in Xero Blue UI.

    Main entry point that orchestrates navigation to the Reports Dashboard.
    Handles both old and new Xero Blue UI layouts by detecting available
    UI elements and using the appropriate navigation path.

    Steps:
        1. Navigate to the Dashboard/Home page to start from a known state.
        2. Navigate to the Reports page using the appropriate UI path.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Raises:
        Exception: If required UI elements (Accounting or Reporting menus) are not found,
                   or if navigation fails to reach the Reports page.
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Navigate to Reports Dashboard - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info("=" * 80)

    try:
        # STEP 1: Navigate to Dashboard/Home Page
        # Purpose: Start from a known state before navigating to reports
        # Function: go_to_dashboard(browser)
        # - Clicks Home link (newer UI) or falls back to Dashboard link (older UI)
        go_to_dashboard(browser)

        # STEP 2: Navigate to Reports Using Appropriate UI Path
        # Purpose: Detect the active UI layout and navigate to the Reports dashboard
        # Function: navigate_to_reports_or_account(browser)
        # - Checks for Reporting button (newer UI) or Accounting menu (older UI)
        # - Navigates using the correct path based on detected UI layout
        # - Verifies successful navigation by checking for the Reports heading
        navigate_to_reports_or_account(browser)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Navigate to Reports Dashboard - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Navigate to Reports Dashboard - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def is_report_button_visible(browser) -> bool:
    """
    Check if the Reporting button exists on the current page.

    Verifies whether the Xero Blue UI displays the 'Reporting' button,
    which indicates the newer UI layout where reports are accessible directly.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Returns:
        bool: True if the Reporting button is visible within 5 seconds, False otherwise.
    """
    try:
        report_button_xpath = (
            "//button[@type='button' and span[normalize-space(text())='Reporting']]"
        )
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, report_button_xpath)),
        )
        logger.info("Reporting button found on the page.")
        return True
    except Exception:
        logger.info("Reporting button not found on the page.")
        return False


def is_accounting_button_visible(browser) -> bool:
    """
    Check if the Accounting button exists on the current page.

    Verifies whether the Xero Blue UI displays the 'Accounting' button,
    which indicates the older UI layout where reports are accessible via the Accounting menu.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Returns:
        bool: True if the Accounting button is visible within 5 seconds, False otherwise.
    """
    try:
        account_tab_xpath = (
            "//button[@type='button' and normalize-space(text())='Accounting']"
        )
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_tab_xpath)),
        )
        logger.info("Accounting button found on the page.")
        return True
    except Exception:
        logger.info("Accounting button not found on the page.")
        return False


def is_account_reports_link_visible(browser) -> bool:
    """
    Check if the Reports link exists under the Accounting dropdown menu.

    Verifies whether the 'Reports' link is available within the Accounting
    dropdown menu after the Accounting button has been clicked.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Returns:
        bool: True if the Reports link is visible within 5 seconds, False otherwise.
    """
    try:
        account_report_xpath = "//a[normalize-space(text())='Reports']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_report_xpath)),
        )
        logger.info("Reports link found under Accounting dropdown.")
        return True
    except Exception:
        logger.info("Reports link not found under Accounting dropdown.")
        return False


def is_reports_heading_visible(browser) -> bool:
    """
    Check if the Reports page heading exists on the current page.

    Verifies whether the H1 heading 'Reports' is displayed on the page,
    confirming successful navigation to the Reports dashboard.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Returns:
        bool: True if the Reports heading is visible within 5 seconds, False otherwise.
    """
    try:
        report_heading_xpath = "//h1[normalize-space(text())='Reports']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, report_heading_xpath)),
        )
        logger.info("Reports page heading confirmed - navigation successful.")
        return True
    except Exception:
        logger.info("Reports page heading not found - navigation may have failed.")
        return False


# ------------------ Dashboard Navigation ------------------
def go_to_dashboard(browser):
    """
    Navigate to the Dashboard or Home page based on the UI version.

    Attempts to click the 'Home' link (newer UI). If not found, falls back
    to clicking the 'Dashboard' link (older UI) to ensure navigation starts
    from a consistent, known page state.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Raises:
        TimeoutException: If neither Home nor Dashboard elements are found and clickable.
    """
    driver = browser.driver

    try:
        home_xpath = "//a[@role='link' and span[normalize-space(text())='Home']]"
        home_ele = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, home_xpath)),
        )
        home_ele.click()
        logger.info("Clicked Home link - navigated to Home page.")

    except Exception:
        logger.info("Home link not found, falling back to Dashboard link.")
        dashboard_xpath = "//a[normalize-space(.)='Dashboard']"
        element = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, dashboard_xpath)),
        )
        element.click()
        logger.info("Clicked Dashboard link - navigated to Dashboard page.")


# ------------------ Report or Account Tab Logic ------------------
def navigate_to_reports_or_account(browser):
    """
    Navigate to the Reports page using the appropriate UI path.

    Determines which navigation path to use based on the available UI elements:
    1. Newer UI: Navigates via the direct 'Reporting' button.
    2. Older UI: Navigates via 'Accounting' menu → 'Reports' link.

    After navigation, verifies that the Reports page loaded successfully
    by checking for the Reports heading.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Raises:
        Exception: If neither the Reporting button nor Accounting menu are available,
                   or if the Reports page fails to load after navigation.
    """
    if is_report_button_visible(browser):
        logger.info("Newer UI detected - navigating via Reporting button.")
        open_report_tab(browser)

    else:
        if is_accounting_button_visible(browser):
            logger.info("Older UI detected - navigating via Accounting menu.")
            open_account_tab(browser)

        else:
            logger.error(
                "Neither Reporting button nor Accounting menu found for this client.",
            )
            raise Exception("Accounting menu does not exist for this client.")

    if not is_reports_heading_visible(browser):
        logger.error(
            "Reports page heading not found after navigation - navigation may have failed.",
        )
        raise Exception("Failed to navigate to the Reports dashboard.")

    logger.info("Successfully navigated to the Reports Dashboard.")


# ------------------ Reporting Tab ------------------
def open_report_tab(browser):
    """
    Navigate to the Reports page via the Reporting button (newer UI).

    Performs the following actions:
    1. Clicks the 'Reporting' button to open the reporting dropdown menu.
    2. Clicks the 'All reports' link to navigate to the Reports dashboard.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Raises:
        TimeoutException: If the Reporting button or All Reports link are not found within 5 seconds.
    """
    logger.info("Clicking Reporting button to open dropdown menu...")
    report_button_xpath = (
        "//button[@type='button' and span[normalize-space(text())='Reporting']]"
    )
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, report_button_xpath)),
    ).click()
    logger.info("Reporting button clicked - dropdown menu opened.")

    logger.info("Clicking All Reports link...")
    all_report_link_xpath = (
        "//a[@role='link' and span[normalize-space(text())='All reports']]"
    )
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, all_report_link_xpath)),
    ).click()
    logger.info("All Reports link clicked - navigating to Reports page.")


# ------------------ Accounting Tab ------------------
def open_account_tab(browser):
    """
    Navigate to the Reports page via the Accounting menu (older UI).

    Performs the following actions:
    1. Clicks the 'Accounting' button to open the accounting dropdown menu.
    2. Waits briefly for the dropdown to fully expand.
    3. Verifies the 'Reports' link exists in the dropdown.
    4. Clicks the 'Reports' link to navigate to the Reports dashboard.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.

    Raises:
        Exception: If the Reports link is not found under the Accounting dropdown menu.
        TimeoutException: If the Accounting button is not found within 5 seconds.
    """
    logger.info("Clicking Accounting button to open dropdown menu...")
    account_tab_xpath = (
        "//button[@type='button' and normalize-space(text())='Accounting']"
    )
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, account_tab_xpath)),
    ).click()
    logger.info("Accounting button clicked - waiting for dropdown to expand.")
    time.sleep(1)

    if is_account_reports_link_visible(browser):
        logger.info("Reports link found - clicking to navigate to Reports page...")
        account_report_xpath = "//a[normalize-space(text())='Reports']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, account_report_xpath)),
        ).click()
        logger.info("Reports link clicked - navigating to Reports page.")

    else:
        logger.error("Reports link not found under the Accounting dropdown menu.")
        raise Exception("Report tab menu does not found for this client.")
