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
    - Timeouts are module constants (tunable in one place, off the call surface).

Account-name handling:
    Organisation names are placed into XPath via ``xpath_literal`` (the supported
    quoting helper), which safely handles apostrophes and ampersands. This
    replaces the previous HTML-entity escaping (``&`` -> ``&amp;``, ``'`` ->
    ``&apos;``), which did not match the *decoded* attribute values in the DOM and
    silently failed for any organisation whose name contained ``&`` or ``'``.

Failure behaviour:
    Every step raises on failure - there is no path on which the function returns
    normally without having actually switched (or confirmed the client was
    already active). After selecting an organisation the switch is VERIFIED by
    re-checking the active-organisation indicator; a switch that does not take
    effect raises rather than reporting success.

USAGE EXAMPLE:
    from switch_client import switch_client

    switch_client(browser, "ABC Company Pty Ltd")
"""

from __future__ import annotations

# ====================================================================================
# INTERNAL IMPORTS
# ====================================================================================
from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import xpath_literal
from iaa_rpa_utils.exceptions import WebAutomationError, DataValidationError


# ====================================================================================
# MODULE SETUP
# ====================================================================================
logger = setup_logger(__name__)

__all__ = [
    "switch_client",
]

# ====================================================================================
# MODULE CONSTANTS
# ====================================================================================
_DETECTION_TIMEOUT = 2   # seconds; fast UI-version / negative-result probes
_ELEMENT_TIMEOUT = 5     # seconds; normal element interactions and verification

# --- Shared / new-UI locators ------------------------------------------------------
_HOME_LINK = "xpath://a[@role='link' and span[normalize-space(text())='Home']]"
_NEW_UI_SEARCH = "xpath://input[@placeholder='Search organizations']"
_NEW_UI_NO_RESULTS = "xpath://p[starts-with(normalize-space(.), 'No results found for')]"
# NOTE: fragile locator carried over from the original - "the first button on the
# page" is not a robust anchor for the organisation selector. Replace with a real
# data-automationid / aria-label when the page HTML is available.
_NEW_UI_USER_BUTTON = "xpath://button[@type='button']"

# --- Legacy-UI locators (verbatim from the original) -------------------------------
_DASHBOARD_LINK = "xpath://a[normalize-space(.)='Dashboard']"
_OLD_UI_CHANGE_ORG = (
    "xpath://button[@type='button']//span[normalize-space(text())='Change organisation']"
)
_OLD_UI_ACCOUNT_SELECT = "xpath://div[@class='xnav-appbutton--body']"
_OLD_UI_SEARCH_ORG = (
    "xpath://input[@role='searchbox' and @aria-label='Search organisations']"
)
_OLD_UI_SEARCH_BOX = "xpath://input[normalize-space(@placeholder)='Search organisations']"
_OLD_UI_NO_RESULTS = "xpath://div[starts-with(normalize-space(.), 'No results found for')]"


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
        ValueError: If ``account_name`` is empty or not a string.
        WebAutomationError: If neither UI can be detected, an expected control is
            absent, or the switch cannot be confirmed.
        DataValidationError: If the organisation does not exist in Xero.
    """
    if not isinstance(account_name, str) or not account_name.strip():
        raise ValueError("account_name is required and must be a non-empty string")
    account = account_name.strip()

    with ProcessLogger("Xero Blue Switch Client", logger):
        logger.info(f"Target organisation: '{account}'")

        if _has_home_page(browser, _DETECTION_TIMEOUT):
            logger.info("New Xero UI detected (Home present)")
            _switch_new_ui(browser, account)
        elif _has_dashboard(browser, _DETECTION_TIMEOUT):
            logger.info("Legacy Xero UI detected (Dashboard present)")
            _switch_old_ui(browser, account)
        else:
            raise WebAutomationError(
                "Neither Home nor Dashboard found - cannot determine the Xero UI "
                "version, so the client switch cannot proceed."
            )


# ====================================================================================
# NEW-UI FLOW
# ====================================================================================

def _switch_new_ui(browser, account: str) -> None:
    """Switch organisation using the new (Home-based) UI, verifying the result."""
    # Navigate Home to reach the organisation selector.
    browser.click_element(_HOME_LINK, timeout=_DETECTION_TIMEOUT)

    if _client_selected_new_ui(browser, account, _ELEMENT_TIMEOUT):
        logger.info(f"'{account}' is already the active organisation - no switch needed")
        return

    # Open the organisation selector (see _NEW_UI_USER_BUTTON note re: fragility).
    browser.click_element(_NEW_UI_USER_BUTTON, timeout=_ELEMENT_TIMEOUT)
    logger.info("Opened organisation selector")

    _select_organisation_new_ui(browser, account)

    # VERIFY the switch actually took effect before reporting success.
    if not _client_selected_new_ui(browser, account, _ELEMENT_TIMEOUT):
        raise WebAutomationError(
            f"Switch appeared to complete but '{account}' is not the active "
            f"organisation."
        )
    logger.info(f"Confirmed active organisation: '{account}'")


def _select_organisation_new_ui(browser, account: str) -> None:
    """Search for and click the target organisation in the new UI selector."""
    if not browser.does_page_contain_element(_NEW_UI_SEARCH, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError("Organisation search input did not appear in the new UI.")

    browser.click_element(_NEW_UI_SEARCH, timeout=_ELEMENT_TIMEOUT)
    browser.type_text(_NEW_UI_SEARCH, account, timeout=_ELEMENT_TIMEOUT)  # clears, then types
    logger.info(f"Searched organisations for: '{account}'")

    if browser.does_page_contain_element(_NEW_UI_NO_RESULTS, timeout=_DETECTION_TIMEOUT):
        raise DataValidationError(f"Organisation does not exist in Xero: '{account}'")

    account_link = (
        f"xpath://a[@role='link' and .//span[normalize-space(.)={xpath_literal(account)}]]"
    )
    if not browser.does_page_contain_element(account_link, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError(f"Organisation '{account}' not present in search results.")

    browser.click_element(account_link, timeout=_ELEMENT_TIMEOUT)
    logger.info(f"Selected organisation: '{account}'")


def _client_selected_new_ui(browser, account: str, timeout: int) -> bool:
    """True if ``account`` is shown as the active organisation in the new UI."""
    locator = (
        f"xpath://div[@class='header-and-quick-actions-mfe-Header--organisation-name-text' "
        f"and text()={xpath_literal(account)}]"
    )
    return browser.does_page_contain_element(locator, timeout=timeout)


def _has_home_page(browser, timeout: int) -> bool:
    """True if the Home link is present (new UI indicator)."""
    return browser.does_page_contain_element(_HOME_LINK, timeout=timeout)


# ====================================================================================
# LEGACY-UI FLOW
# ====================================================================================

def _switch_old_ui(browser, account: str) -> None:
    """Switch organisation using the legacy (Dashboard-based) UI, verifying result."""
    browser.click_element(_DASHBOARD_LINK, timeout=_DETECTION_TIMEOUT)
    logger.info("Navigated to Dashboard")

    if _client_selected_old_ui(browser, account, _ELEMENT_TIMEOUT):
        logger.info(f"'{account}' is already the active organisation - no switch needed")
        return

    _select_organisation_old_ui(browser, account)

    if not _client_selected_old_ui(browser, account, _ELEMENT_TIMEOUT):
        raise WebAutomationError(
            f"Switch appeared to complete but '{account}' is not the active "
            f"organisation."
        )
    logger.info(f"Confirmed active organisation: '{account}'")


def _select_organisation_old_ui(browser, account: str) -> None:
    """Open the legacy account selector, search, and click the target organisation."""
    if not browser.does_page_contain_element(_OLD_UI_CHANGE_ORG, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError("'Change organisation' control not found in the legacy UI.")

    # Open the account selector.
    browser.click_element(_OLD_UI_ACCOUNT_SELECT, timeout=_ELEMENT_TIMEOUT)
    logger.info("Opened account selector")

    if not browser.does_page_contain_element(_OLD_UI_SEARCH_ORG, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError("'Search organisations' control did not appear.")
    browser.click_element(_OLD_UI_SEARCH_ORG, timeout=_ELEMENT_TIMEOUT)

    if not browser.does_page_contain_element(_OLD_UI_SEARCH_BOX, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError("Organisation search box did not appear.")
    browser.click_element(_OLD_UI_SEARCH_BOX, timeout=_ELEMENT_TIMEOUT)
    browser.type_text(_OLD_UI_SEARCH_BOX, account, timeout=_ELEMENT_TIMEOUT)  # clears, then types
    logger.info(f"Searched organisations for: '{account}'")

    if browser.does_page_contain_element(_OLD_UI_NO_RESULTS, timeout=_DETECTION_TIMEOUT):
        raise DataValidationError(f"Organisation does not exist in Xero: '{account}'")

    account_link = (
        f"xpath://a[@class='xnav-verticalmenuitem--body xnav-menuitem-orgpractice']"
        f"//span[normalize-space(.)={xpath_literal(account)}]"
    )
    if not browser.does_page_contain_element(account_link, timeout=_ELEMENT_TIMEOUT):
        raise WebAutomationError(f"Organisation '{account}' not present in results.")

    browser.click_element(account_link, timeout=_ELEMENT_TIMEOUT)
    logger.info(f"Selected organisation: '{account}'")


def _client_selected_old_ui(browser, account: str, timeout: int) -> bool:
    """True if ``account`` is shown as the active organisation in the legacy UI."""
    locator = (
        f"xpath://div[@class='xnav-appbutton--body']"
        f"//span[@class='xnav-appbutton--text' and normalize-space(text())={xpath_literal(account)}]"
    )
    return browser.does_page_contain_element(locator, timeout=timeout)


def _has_dashboard(browser, timeout: int) -> bool:
    """True if the Dashboard link is present (legacy UI indicator)."""
    return browser.does_page_contain_element(_DASHBOARD_LINK, timeout=timeout)