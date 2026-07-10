from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# Set up logger
logger = setup_logger(__name__)

# ----------------- Main Function -----------------
"""
    "xero_blue_report_name: "Activity Statements",
    "xero_blue_title" : "Xero"
    """


def xero_blue_navigate_to_report(
    browser,
    xero_blue_report_name: str,
    xero_blue_title: str = "",
):
    """
    Navigate to a specific Xero Blue report page by verifying the page title and clicking the report button.

    This function acts as the main entry point for navigating to a Xero report within the
    report centre. It verifies the current browser page is the expected Xero reports dashboard,
    then locates and clicks the target report button. Comprehensive start/end logging with
    duration tracking is included.

    Args:
        browser: Browser object containing the Selenium WebDriver instance.
                 Must have a 'driver' attribute providing access to the WebDriver.
        xero_blue_report_name (str): The exact display name of the report to navigate to.
                                     Used to locate the report button in the report centre.
        xero_blue_title (str): The expected page title substring to verify before navigation.
                               Confirms the user is on the correct Xero reports page.

    Returns:
        None: If report navigation completes successfully.
        False: If page title verification fails, report button is not found,
               or an unexpected exception occurs.

    Raises:
        Does not explicitly raise exceptions. All exceptions are caught, logged, and
        False is returned.
    """

    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Navigate to Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Report Name: {xero_blue_report_name}")
    logger.info(f"Expected Page Title: {xero_blue_title}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # STEP 1: Verify Current Page Title
        # Purpose: Confirm the browser is on the correct Xero reports dashboard before proceeding
        # Function: verify_page_title(driver, expected_title)
        # - Retrieves the current browser page title
        # - Checks if the expected title string is present within it
        # - Returns True if matched, False if not
        logger.info("Verifying current page title matches expected Xero reports page")
        is_correct_page = verify_page_title(driver, xero_blue_title)

        if not is_correct_page:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error("=" * 80)
            logger.error(
                f"FAILED: Xero Blue Navigate to Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error(
                f"Reason: Page title does not match expected title '{xero_blue_title}'",
            )
            logger.error("=" * 80)
            return False

        # STEP 2: Locate and Click Report Button
        # Purpose: Find the target report in the report centre and click it to open the report page
        # Function: locate_and_click_report_button(driver, report_name)
        # - Constructs XPath targeting the report span by exact text match within report-centre-parent
        # - Waits up to 5 seconds for the button element to be present in the DOM
        # - Clicks the first matching report button element
        logger.info(
            f"Locating and clicking report button for '{xero_blue_report_name}'",
        )
        is_report_clicked = locate_and_click_report_button(
            driver,
            xero_blue_report_name,
        )

        if not is_report_clicked:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error("=" * 80)
            logger.error(
                f"FAILED: Xero Blue Navigate to Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error(
                f"Reason: Report button for '{xero_blue_report_name}' was not found in report centre",
            )
            logger.error("=" * 80)
            return False

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Navigate to Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Report Navigated: {xero_blue_report_name}")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Navigate to Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


# ----------------- Helper Functions -----------------


def verify_page_title(driver, expected_title: str) -> bool:
    """
    Verify that the current browser page title contains the expected title string.

    Args:
        driver: Selenium WebDriver instance used to retrieve the current page title.
        expected_title (str): The expected title string to search for within the current page title.

    Returns:
        bool: True if the expected title is found within the current page title, False otherwise.
    """
    current_title = driver.title
    logger.info(f"Current page title: '{current_title}'")
    logger.info(f"Expected title contains: '{expected_title}'")

    if expected_title in current_title:
        logger.info(
            f"Page title verified successfully - '{expected_title}' found in '{current_title}'",
        )
        return True

    logger.error(
        f"Page title mismatch - Expected to contain '{expected_title}', but got '{current_title}'",
    )
    return False


def locate_and_click_report_button(driver, report_name: str) -> bool:
    """
    Locate the specified report button within the Xero report centre and click it.

    Constructs an XPath targeting the report span element by exact text match within
    the report-centre-parent container, waits for its presence, and clicks the first match.

    Args:
        driver: Selenium WebDriver instance used to locate and interact with the report button.
        report_name (str): The exact display name of the report button to locate and click.

    Returns:
        bool: True if the report button was found and clicked successfully, False otherwise.
    """
    report_button_xpath = (
        # f"//div[@id='report-centre-parent']"
        # f"//span[normalize-space(text())='{report_name}']"
        f"//div[@id='report-centre-parent']"
        f"//a[.//span[@data-automationid='report-name'][normalize-space(text())='{report_name}']]"
    )
    logger.info(f"Locating report button for report: '{report_name}'")
    logger.info(f"Using XPath: {report_button_xpath}")

    try:
        report_button_elements = driver.find_elements(By.XPATH, report_button_xpath)
        # report_button_elements = WebDriverWait(driver, 5).until(
        #     EC.presence_of_all_elements_located((By.XPATH, report_button_xpath)),
        # )

        element_count = len(report_button_elements)
        logger.info(
            f"Found {element_count} element(s) for report button: '{report_name}'",
        )
        if element_count > 1:
            logger.info(f"Multiple elements found, clicking the first one")

        report_button_elements[0].click()
        logger.info(f"Successfully clicked report button: '{report_name}'")
        return True

    except Exception:

        logger.error(f"Report button not found for report: '{report_name}'")
        return False
