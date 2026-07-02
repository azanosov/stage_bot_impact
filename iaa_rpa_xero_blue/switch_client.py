"""
====================================================================================
XERO BLUE - SWITCH CLIENT MODULE
====================================================================================

Switch the active Xero organisation/client. Supports both the new Xero UI
(Home-based navigation) and the legacy UI (Dashboard-based navigation),
auto-detecting which is active and using the matching flow.

Refactored to the iaa_rpa_utils house style, with the deliberate exception that
this function takes a plain ``account_name`` argument rather than a request
dataclass: it has a single meaningful input, so a dataclass would add ceremony
without the validation/computed-property payoff that justifies one elsewhere.
(Compare ``list_all_bank_accounts``, the family's other simple operation, which
is likewise a plain function.)

    - Orchestrator owns the sequence; private step helpers each do one thing.
    - ProcessLogger handles timing and success/failure logging.
    - All element interaction is routed through the SeleniumBrowser wrapper API
      (no raw driver access).
    - Locators live in config.py (SWITCH_ section); the Home/Dashboard UI
      indicators reuse the shared NAV_ pair.
    - Timeouts are shared constants in common (off the call surface).

Account-name handling:
    Organisation names are placed into XPath via ``xpath_literal`` (the supported
    quoting helper), which safely handles apostrophes and ampersands. This
    replaces the previous HTML-entity escaping (``&`` -> ``&amp;``, ``'`` ->
    ``&apos;``), which did not match the *decoded* attribute values in the DOM and
    silently failed for any organisation whose name contained ``&`` or ``'``.

Failure behaviour (typed exceptions from iaa_rpa_utils.exceptions):
    - DataValidationError: the account_name argument is empty/not a string, or the
      organisation does not exist in Xero (no search results / not in results).
    - NavigationError: neither UI can be detected, or the switch cannot be
      confirmed (the target org is not active after selecting it).
    - ElementNotFoundError: an expected control (search input, Change organisation,
      search box) is absent.
    Every step raises on failure - there is no path on which the function returns
    normally without having actually switched (or confirmed the client was
    already active). After selecting an organisation the switch is VERIFIED by
    re-checking the active-organisation indicator.

USAGE EXAMPLE:
    from switch_client import switch_client

    switch_client(browser, "ABC Company Pty Ltd")
"""

from __future__ import annotations

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import xpath_literal
from iaa_rpa_utils.exceptions import (
    DataValidationError,
    ElementNotFoundError,
    NavigationError,
)

from . import common
from . import config


logger = setup_logger(__name__)

__all__ = [
    "switch_client",
]


# ====================================================================================
# PUBLIC API
# ====================================================================================

def switch_client(browser, account_name: str) -> None:
    """
    Switch the active Xero organisation to ``account_name``.

    Detects whether the new UI (Home) or legacy UI (Dashboard) is active and runs
    the matching switch flow. If the target organisation is already active, the
    switch is skipped. After switching, the active-organisation indicator is
    re-checked to confirm the switch took effect.

    Args:
        browser: SeleniumBrowser wrapper instance with an active, logged-in Xero
                 session (Practice Manager / multi-organisation environment).
        account_name (str): Exact organisation name to switch to, as shown in Xero.

    Returns:
        None

    Raises:
        DataValidationError: If ``account_name`` is empty/not a string, or the
            organisation does not exist in Xero.
        NavigationError: If neither UI can be detected, or the switch cannot be
            confirmed.
        ElementNotFoundError: If an expected control is absent.
    """
    if not isinstance(account_name, str) or not account_name.strip():
        raise DataValidationError("account_name is required and must be a non-empty string")
    account = account_name.strip()

    with ProcessLogger("Xero Blue Switch Client", logger):
        logger.info(f"Target organisation: '{account}'")

        if _has_home_page(browser, common.DETECTION_TIMEOUT):
            logger.info("New Xero UI detected (Home present)")
            _switch_new_ui(browser, account)
        elif _has_dashboard(browser, common.DETECTION_TIMEOUT):
            logger.info("Legacy Xero UI detected (Dashboard present)")
            _switch_old_ui(browser, account)
        else:
            raise NavigationError(
                "Neither Home nor Dashboard found - cannot determine the Xero UI "
                "version, so the client switch cannot proceed."
            )


# ====================================================================================
# NEW-UI FLOW
# ====================================================================================

def _switch_new_ui(browser, account: str) -> None:
    """Switch organisation using the new (Home-based) UI, verifying the result."""
    # Navigate Home to reach the organisation selector.
    browser.click_element(config.NAV_HOME_LINK, timeout=common.DETECTION_TIMEOUT)

    if _client_selected_new_ui(browser, account, common.DEFAULT_ELEMENT_TIMEOUT):
        logger.info(f"'{account}' is already the active organisation - no switch needed")
        return

    # Open the organisation selector (see SWITCH_NEW_USER_BUTTON note re: fragility).
    browser.click_element(config.SWITCH_NEW_USER_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    logger.info("Opened organisation selector")

    _select_organisation_new_ui(browser, account)

    # VERIFY the switch actually took effect before reporting success.
    if not _client_selected_new_ui(browser, account, common.DEFAULT_ELEMENT_TIMEOUT):
        raise NavigationError(
            f"Switch appeared to complete but '{account}' is not the active "
            f"organisation."
        )
    logger.info(f"Confirmed active organisation: '{account}'")


def _select_organisation_new_ui(browser, account: str) -> None:
    """Search for and click the target organisation in the new UI selector."""
    if not browser.does_page_contain_element(config.SWITCH_NEW_SEARCH, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise ElementNotFoundError("Organisation search input did not appear in the new UI.")

    browser.click_element(config.SWITCH_NEW_SEARCH, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    browser.type_text(config.SWITCH_NEW_SEARCH, account, timeout=common.DEFAULT_ELEMENT_TIMEOUT)  # clears, then types
    logger.info(f"Searched organisations for: '{account}'")

    if browser.does_page_contain_element(config.SWITCH_NEW_NO_RESULTS, timeout=common.DETECTION_TIMEOUT):
        raise DataValidationError(f"Organisation does not exist in Xero: '{account}'")

    account_link = config.SWITCH_NEW_ACCOUNT_LINK_TPL.format(account_literal=xpath_literal(account))
    if not browser.does_page_contain_element(account_link, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise DataValidationError(f"Organisation '{account}' not present in search results.")

    browser.click_element(account_link, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    logger.info(f"Selected organisation: '{account}'")


def _client_selected_new_ui(browser, account: str, timeout: int) -> bool:
    """True if ``account`` is shown as the active organisation in the new UI."""
    locator = config.SWITCH_NEW_ACTIVE_ORG_TPL.format(account_literal=xpath_literal(account))
    return browser.does_page_contain_element(locator, timeout=timeout)


def _has_home_page(browser, timeout: int) -> bool:
    """True if the Home link is present (new UI indicator)."""
    return browser.does_page_contain_element(config.NAV_HOME_LINK, timeout=timeout)


# ====================================================================================
# LEGACY-UI FLOW
# ====================================================================================

def _switch_old_ui(browser, account: str) -> None:
    """Switch organisation using the legacy (Dashboard-based) UI, verifying result."""
    browser.click_element(config.NAV_DASHBOARD_LINK, timeout=common.DETECTION_TIMEOUT)
    logger.info("Navigated to Dashboard")

    if _client_selected_old_ui(browser, account, common.DEFAULT_ELEMENT_TIMEOUT):
        logger.info(f"'{account}' is already the active organisation - no switch needed")
        return

    _select_organisation_old_ui(browser, account)

    if not _client_selected_old_ui(browser, account, common.DEFAULT_ELEMENT_TIMEOUT):
        raise NavigationError(
            f"Switch appeared to complete but '{account}' is not the active "
            f"organisation."
        )
    logger.info(f"Confirmed active organisation: '{account}'")


def _select_organisation_old_ui(browser, account: str) -> None:
    """Open the legacy account selector, search, and click the target organisation."""
    if not browser.does_page_contain_element(config.SWITCH_OLD_CHANGE_ORG, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise ElementNotFoundError("'Change organisation' control not found in the legacy UI.")

    # Open the account selector.
    browser.click_element(config.SWITCH_OLD_ACCOUNT_SELECT, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    logger.info("Opened account selector")

    if not browser.does_page_contain_element(config.SWITCH_OLD_SEARCH_ORG, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise ElementNotFoundError("'Search organisations' control did not appear.")
    browser.click_element(config.SWITCH_OLD_SEARCH_ORG, timeout=common.DEFAULT_ELEMENT_TIMEOUT)

    if not browser.does_page_contain_element(config.SWITCH_OLD_SEARCH_BOX, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise ElementNotFoundError("Organisation search box did not appear.")
    browser.click_element(config.SWITCH_OLD_SEARCH_BOX, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    browser.type_text(config.SWITCH_OLD_SEARCH_BOX, account, timeout=common.DEFAULT_ELEMENT_TIMEOUT)  # clears, then types
    logger.info(f"Searched organisations for: '{account}'")

    if browser.does_page_contain_element(config.SWITCH_OLD_NO_RESULTS, timeout=common.DETECTION_TIMEOUT):
        raise DataValidationError(f"Organisation does not exist in Xero: '{account}'")

    account_link = config.SWITCH_OLD_ACCOUNT_LINK_TPL.format(account_literal=xpath_literal(account))
    if not browser.does_page_contain_element(account_link, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        raise DataValidationError(f"Organisation '{account}' not present in results.")

    browser.click_element(account_link, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
    logger.info(f"Selected organisation: '{account}'")


def _client_selected_old_ui(browser, account: str, timeout: int) -> bool:
    """True if ``account`` is shown as the active organisation in the legacy UI."""
    locator = config.SWITCH_OLD_ACTIVE_ORG_TPL.format(account_literal=xpath_literal(account))
    return browser.does_page_contain_element(locator, timeout=timeout)


def _has_dashboard(browser, timeout: int) -> bool:
    """True if the Dashboard link is present (legacy UI indicator)."""
    return browser.does_page_contain_element(config.NAV_DASHBOARD_LINK, timeout=timeout)
