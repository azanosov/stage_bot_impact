"""
Navigation within Xero Blue.

Caller-invoked navigation helpers for moving between the top-level pages the
report/record modules operate on. Kept separate from the download modules so
navigation is a caller concern (navigate once per batch) and the download
functions do processing only.

Each helper is layered: it tries the current ("new") UI first and falls back to
the legacy path if the new-UI element is absent. Failure is loud - a helper
raises NavigationError only when BOTH the new and legacy paths fail, so a caller
cannot mistake a failed navigation for success.

Note on the legacy paths: the legacy locators cannot be verified against a DOM
capture (no access to the legacy UI), so they are carried as-is and their
success is NOT confirmed after clicking - there is no legacy landing-page
marker to check. The new-UI paths ARE confirmed (via a container/element probe)
before returning.

Locators live in config.py (NAV_ and REPORTS_ sections).
"""

from __future__ import annotations

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils import helpers
from iaa_rpa_utils.exceptions import ElementNotFoundError, NavigationError

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "navigate_to_dashboard_page",
    "navigate_to_all_reports_page",
    "navigate_to_report_page",
]


def navigate_to_dashboard_page(browser) -> None:
    """Navigate to the Xero Blue dashboard/home page.

    Raises:
        NavigationError: neither the new-UI nor the legacy path reached the page.
    """
    # Primary: new UI. A missing element or an unconfirmed landing both fall through.
    try:
        browser.click_element(config.NAV_HOME_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        if browser.does_page_contain_element(config.NAV_HOME_MAIN, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
            logger.info("Navigated to 'Home' page")
            return
        logger.warning("Home page not confirmed - trying legacy Dashboard path")
    except ElementNotFoundError:
        logger.warning("New-UI Home link not found - trying legacy Dashboard path")

    # Fallback: legacy.
    try:
        browser.click_element(config.NAV_DASHBOARD_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        # No legacy landing-page marker available yet, so we can't confirm success.
        logger.info("Clicked the legacy Dashboard link (navigation not verified)")
    except ElementNotFoundError as e:
        raise NavigationError(f"Could not navigate to the dashboard: {e}") from e


def navigate_to_all_reports_page(browser) -> None:
    """Navigate to the report centre ('All reports') page.

    Raises:
        NavigationError: neither the new-UI nor the legacy path reached the page.
    """
    # Primary: new UI.
    try:
        browser.click_element(config.REPORTS_ALL_REPORTS_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        if browser.does_page_contain_element(config.REPORTS_CENTRE_PARENT, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
            logger.info("Navigated to 'All Reports' page")
            return
        logger.warning("All Reports page not confirmed - trying legacy Accounting path")
    except ElementNotFoundError:
        logger.warning("New-UI All reports link not found - trying legacy Accounting path")

    # Fallback: legacy.
    try:
        browser.click_element(config.REPORTS_ACCOUNTING_TAB, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        browser.click_element(config.REPORTS_ACCOUNTING_REPORTS_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        # No legacy landing-page marker available yet, so we can't confirm success.
        logger.info("Clicked the legacy Accounting -> Reports link (navigation not verified)")
    except ElementNotFoundError as e:
        raise NavigationError(f"Could not navigate to 'All Reports': {e}") from e


def navigate_to_report_page(browser, report_name: str) -> None:
    """Open a named report from the report centre.

    Ensures the report centre is showing first (navigating there if not), then
    clicks the report row whose name matches ``report_name`` exactly.

    Raises:
        NavigationError: the report centre could not be reached, or the named
                         report row was not found.
    """
    if not browser.does_page_contain_element(config.REPORTS_CENTRE_PARENT, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        navigate_to_all_reports_page(browser)

    report_link = config.REPORTS_REPORT_LINK_BY_NAME_TPL.format(
        report_literal=helpers.xpath_literal(report_name)
    )
    try:
        browser.click_element(report_link, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        logger.info(f"Opened report: {report_name}")
    except ElementNotFoundError as e:
        raise NavigationError(f"Failed to navigate to {report_name} report: {e}") from e
