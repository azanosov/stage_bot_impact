from __future__ import annotations

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

logger = setup_logger(__name__)


def format_xpath_selector_text(value: str) -> str:
    """Return an XPath string literal that safely handles embedded single quotes."""
    if "'" not in value:
        return f"'{value}'"
    parts = value.split("'")
    concat_args = ', "\'", '.join(f"'{p}'" for p in parts)
    return f"concat({concat_args})"


def click_element(
    driver: WebDriver, selector: str, by: str = By.XPATH, timeout: int = 10
):
    """Wait for an element to be clickable and click it, with before/after logging."""
    logger.info(f"Clicking: {selector}")
    element = (
        WebDriverWait(driver, timeout)
        .until(EC.element_to_be_clickable((by, selector)))
        .click()
    )
    logger.info(f"Clicked: {selector}")
    return element


def find_element(
    driver: WebDriver, selector: str, by: str = By.XPATH, timeout: int = 10
):
    """Wait for an element to be visible and return it."""
    logger.info(f"Waiting for visible: {selector}")
    element = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, selector))
    )
    logger.info(f"Visible: {selector}")
    return element


def element_exists(
    driver: WebDriver, selector: str, by: str = By.XPATH, timeout: int = 10
) -> bool:
    """Wait up to timeout seconds for an element to be present; return True if found, False if not."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        logger.info(f"Exists: {selector}")
        return True
    except Exception:
        logger.info(f"Not exists: {selector}")
        return False


def type_into_element(
    driver: WebDriver, selector: str, value, by: str = By.XPATH, timeout: int = 10
):
    """Wait for an element to be clickable, clear it, and type a value into it."""
    logger.info(f"Typing '{value}' into: {selector}")
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )

    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.DELETE)
    element.send_keys(str(value))
    logger.info(f"Typed '{value}' into: {selector}")
    return element


def find_elements(
    driver: WebDriver, selector: str, by: str = By.XPATH, timeout: int = 10
) -> list:
    """Wait for at least one element to be present, then return all matching elements."""
    logger.info(f"Finding elements: {selector}")
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    elements = driver.find_elements(by, selector)
    logger.info(f"Found {len(elements)} element(s): {selector}")
    return elements


def type_into_date_element(
    driver: WebDriver, selector: str, value, by: str = By.XPATH, timeout: int = 10
):
    """Wait for an element to be clickable, clear it, and type a value into it."""
    element = type_into_element(driver, selector, value, by, timeout)
    element.send_keys(Keys.TAB)  # TAB
    return element
