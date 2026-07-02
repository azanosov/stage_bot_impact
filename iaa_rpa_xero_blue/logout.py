"""
Log out of Xero Blue.

Session teardown (auth) - the mirror of login.py. This module logs out and
VERIFIES the result; it does not close the browser window (that is a lifecycle
concern, handled separately in close_browser.py).

Verification is symmetric with login: login confirms success by the dashboard
<main> appearing; logout confirms success by the login form (LOGIN_EMAIL_INPUT)
reappearing. This avoids the locale-dependent page-title match the legacy code
used ("Xero | Log in" varies by brand/locale).

Flow:
    1. If the login form is already present, we're logged out - return.
    2. Click "Log out" (laddered): try the link directly in case the user-menu
       flyout is already open; if it isn't found, open the user-menu button and
       retry the link.
    3. Verify the login form reappears; raise LogoutError if it does not.

There is no username parameter: the "Log out" link and user-menu button are
keyed on stable automation-id / href, so there is no need to build a username
selector (and no html.unescape / xpath-injection surface).

ERROR HANDLING: raises LogoutError (from iaa_rpa_utils.exceptions) when logout
cannot be confirmed - a caller cannot mistake a failed logout for success.
"""

from __future__ import annotations

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.exceptions import ElementNotFoundError, LogoutError

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = ["xero_blue_logout"]


def xero_blue_logout(browser) -> None:
    """Log out of Xero Blue. Returns None on success; raises on failure.

    Args:
        browser: SeleniumBrowser wrapper.

    Raises:
        LogoutError: logout could not be confirmed (login form did not reappear).
    """
    with ProcessLogger("Xero Blue Logout", logger):
        logger.info("STEP 1: Checking for an existing session...")
        if browser.does_page_contain_element(
            config.LOGIN_EMAIL_INPUT, timeout=common.DEFAULT_ELEMENT_TIMEOUT
        ):
            logger.info("Already logged out - login form present")
            return

        logger.info("STEP 2: Clicking 'Log out'...")
        click_logout(browser)

        logger.info("STEP 3: Verifying logged-out state...")
        if not browser.does_page_contain_element(
            config.LOGIN_EMAIL_INPUT, timeout=common.EXPORT_TIMEOUT
        ):
            raise LogoutError("Logout not confirmed - login form did not reappear")
        logger.info("Logout confirmed")


def click_logout(browser) -> None:
    """Click the 'Log out' link, opening the user-menu flyout first if needed.

    Laddered: the Log out link lives inside a flyout that is hidden until the
    user-avatar button is clicked. We try the link directly first (in case the
    flyout is already open), and only open the user menu and retry if the link
    isn't found.
    """
    try:
        browser.click_element(config.LOGOUT_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        logger.info("Clicked 'Log out'")
        return
    except ElementNotFoundError:
        logger.info("'Log out' not directly available - opening the user menu")

    # Open the user-menu flyout, then the Log out link must be present.
    try:
        browser.click_element(config.LOGOUT_USER_MENU_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        browser.click_element(config.LOGOUT_LINK, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        logger.info("Opened user menu and clicked 'Log out'")
    except ElementNotFoundError as e:
        raise LogoutError(f"Could not click 'Log out': {e}") from e
