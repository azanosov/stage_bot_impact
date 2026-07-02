"""
Shared behaviour for the Xero Blue report modules.

This module holds the functions and helpers that every report needs, so each
report module stays small and composes these rather than re-implementing them:

  - date formatting for Xero's fields
  - shared timeout / bound constants
  - request-validation helpers (used inside each request's __post_init__)
  - pick-list interaction primitives (read state, click, ensure-selected),
    built on config.py's locator templates
  - the clear-and-type input idiom
  - output helpers: build a save path, verify a saved file
  - the best-effort full-page audit screenshot

Validation and file/interaction failures raise the library's TYPED exceptions
from ``iaa_rpa_utils.exceptions`` (DataValidationError for bad inputs / an
unavailable requested option; DownloadError for a file that did not land), so
every report module surfaces the same typed errors.

Locators live in config.py; behaviour lives here. This module imports config;
the report modules import both. Imports are package-relative (`from . import
config`), so config.py, common.py and the report modules must live together in
the same package (e.g. iaa_rpa_xero_blue) with an __init__.py.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.exceptions import DataValidationError, DownloadError
from iaa_rpa_utils.helpers import take_full_page_screenshot

from . import config

logger = setup_logger(__name__)


# ============================================================================
# Shared constants
# ============================================================================
DEFAULT_ELEMENT_TIMEOUT = 5    # seconds; general element waits
EXPORT_TIMEOUT = 10            # seconds; Update/Export/format - Xero builds the file server-side
DETECTION_TIMEOUT = 2          # seconds; fast UI-version / negative-result probes
MIN_FINANCIAL_YEAR = 2000      # earliest financial year we accept

# Locale-independent month abbreviations, matching the labels Xero's date field
# expects (e.g. "30 Jun 2024"). Avoids strftime('%b') locale surprises.
_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# Selenium key codes used by clear_and_type.
_CTRL_A = "\ue009" + "a"   # CTRL + A (select all)
_DELETE = "\ue003"         # DELETE
_TAB = "\ue004"            # TAB (commit / move focus off the field)


# ============================================================================
# Date formatting
# ============================================================================
def format_xero_date(d: date) -> str:
    """Format a date the way Xero's date field expects, e.g. "30 Jun 2024"
    (no leading zero on the day; locale-independent month abbreviation)."""
    return f"{d.day} {_MONTH_ABBR[d.month - 1]} {d.year}"


# ============================================================================
# Request-validation helpers
# (raise the library's typed DataValidationError, so every report surfaces the
#  same class for a bad input; called inside each request's __post_init__)
# ============================================================================
def validate_non_empty_str(value, name: str) -> None:
    """Require a non-empty string (used for download_directory / report_file_name)."""
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{name} is required and must be a non-empty string")


def validate_optional_date(value, name: str) -> None:
    """When given, require a real datetime.date (datetime is accepted - it is a
    date subclass and only the calendar part is used)."""
    if value is not None and not isinstance(value, date):
        raise DataValidationError(f"{name} must be a datetime.date, got {type(value).__name__}")


def validate_financial_year(value) -> None:
    """Require a plausible integer financial year. bool is an int subclass, so
    it is excluded explicitly."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise DataValidationError(f"financial_year must be an int, got {type(value).__name__}")
    max_year = datetime.now().year + 2
    if not MIN_FINANCIAL_YEAR <= value <= max_year:
        raise DataValidationError(
            f"financial_year must be between {MIN_FINANCIAL_YEAR} and {max_year}, got {value}"
        )


def validate_date_order(start: date | None, end: date | None) -> None:
    """When both dates are given explicitly, start must not be after end."""
    if start is not None and end is not None and start > end:
        raise DataValidationError(f"start_date ({start}) must not be after end_date ({end})")


# ============================================================================
# Pick-list interaction primitives
# (the report toolbar / settings menus are XUI pick-lists; these read and drive
#  an option by its stable id, via the templates in config.py)
# ============================================================================
def pickitem_is_selected(browser, opt_id: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> bool:
    """True if the pick-list option is currently selected (aria-selected='true')."""
    return browser.does_page_contain_element(
        config.SH_PICKITEM_SELECTED_TPL.format(opt_id=opt_id), timeout=timeout
    )


def pickitem_is_disabled(browser, opt_id: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> bool:
    """True if the pick-list option is disabled (greyed out)."""
    return browser.does_page_contain_element(
        config.SH_PICKITEM_DISABLED_TPL.format(opt_id=opt_id), timeout=timeout
    )


def click_pickitem_by_id(browser, opt_id: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> None:
    """Click a pick-list option's body, located by its stable id."""
    browser.click_element(config.SH_PICKITEM_BODY_TPL.format(opt_id=opt_id), timeout=timeout)


def ensure_pickitem_selected(browser, opt_id: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> None:
    """Force a pick-list option to be selected: click it only if it isn't already
    (idempotent - safe to call regardless of the page's starting state)."""
    if not pickitem_is_selected(browser, opt_id, timeout):
        click_pickitem_by_id(browser, opt_id, timeout)


def select_accounting_basis_via_more(browser, basis_option_id: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> None:
    """Open the More menu, force the given accounting-basis option selected
    (idempotent), and close the menu so it doesn't overlay the rest of the panel.
    Shared by reports whose basis lives behind More (Trial Balance, General
    Ledger, ...)."""
    browser.click_element(config.SH_MORE_BUTTON, timeout=timeout)
    ensure_pickitem_selected(browser, basis_option_id, timeout)
    browser.click_element(config.SH_MORE_BUTTON, timeout=timeout)   # close the menu


def select_listbox_option(
    browser,
    trigger_locator: str,
    option_locator: str,
    *,
    description: str = "option",
    timeout: int = DEFAULT_ELEMENT_TIMEOUT,
) -> None:
    """Open a single-select dropdown and click one option. Opens the trigger,
    confirms the option is present (raising if it is not - an unavailable option
    would change the output), then clicks it. The dropdown closes on selection."""
    browser.click_element(trigger_locator, timeout=timeout)
    if not browser.does_page_contain_element(option_locator, timeout=timeout):
        raise DataValidationError(f"{description} is not available in the dropdown")
    browser.click_element(option_locator, timeout=timeout)


# ============================================================================
# Input primitive
# ============================================================================
def clear_and_type(browser, locator: str, value: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> None:
    """Focus a (usually pre-filled) field, clear it, type a value, and TAB to
    commit. The trailing TAB is what makes Xero accept the typed value."""
    browser.click_element(locator, timeout=timeout)
    browser.send_keys_to_active_element(_CTRL_A)
    browser.send_keys_to_active_element(_DELETE)
    browser.send_keys_to_active_element(value)
    browser.send_keys_to_active_element(_TAB)


# ============================================================================
# Output helpers
# ============================================================================
def build_dest_path(directory: str, filename: str, ext: str) -> str:
    """Full save path with the extension forced to match the export format's real
    output, not doubled if the filename already ends in it. `ext` includes the
    leading dot (e.g. ".xlsx")."""
    name = filename
    if name.lower().endswith(ext.lower()):
        name = name[: -len(ext)]
    return os.path.join(directory, f"{name}{ext}")


def verify_saved_file(path: str) -> None:
    """Confirm the export actually landed on disk (principle 10). Raises if not."""
    if not os.path.isfile(path):
        raise DownloadError(f"Expected export file was not saved: {path}")


# ============================================================================
# Audit screenshot (best effort - must never abort the run)
# ============================================================================
def capture_report_screenshot(
    browser, directory: str, report_name: str, stage: str, *, enabled: bool
) -> None:
    """Capture a full-page audit screenshot of the report surface.

    Best effort: a screenshot failure is logged as a warning and swallowed - it
    can never affect the report data or abort the run. Does nothing when
    ``enabled`` is False.

    The file lands in ``directory`` with a derived, self-describing name:
        <report_name>_<stage>_<YYYYMMDD_HHMMSS>.png
    (the caller owns the folder; the stage + timestamp keep the shots
    distinguishable and collision-free). Uses the full-page CDP capture so long,
    scrolling SPA reports are captured in full, not just the viewport.

    Args:
        browser:     SeleniumBrowser wrapper (its .driver is passed to the
                     full-page capture helper).
        directory:   Folder the screenshot is written to.
        report_name: Short report slug used as the filename prefix (e.g. "trial_balance").
        stage:       Descriptive stage marker (e.g. "before_update", "after_update").
        enabled:     When False, this is a no-op.
    """
    if not enabled:
        return
    path = os.path.join(directory, f"{report_name}_{stage}_{datetime.now():%Y%m%d_%H%M%S}.png")
    if take_full_page_screenshot(browser.driver, path):
        logger.info(f"Audit screenshot saved: {path}")
    else:
        logger.warning(f"Audit screenshot failed ({report_name}/{stage}) - continuing")
