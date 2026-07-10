"""
====================================================================================
APPLICATION MANAGER — XERO REPORT CONSOLIDATION ROBOT
====================================================================================

Manages the lifecycle of the long-lived applications this robot needs. For the
Xero-only phase that is a single resource: a Selenium browser logged in to Xero
Practice Manager with the firm's credentials. One login serves every client in the
run (200–300/day at peak), so the browser is created ONCE in init and reused for
every queue item.

WHAT LIVES WHERE (important):
    - The Xero BROWSER is long-lived: created here in init, held on
      ``agent.initialised_apps``, reused across all items, torn down in close.
    - EXCEL is NOT managed here. The consolidation module (consolidate_workbook)
      opens its own dedicated Excel instance via DispatchEx and quits it in a
      finally block, per consolidation. Excel is therefore a per-item resource
      owned by that module, not a run-long one owned here.
    - Even so, KILL force-sweeps orphaned EXCEL.EXE by name: a hard crash mid-
      consolidation can leave Excel orphaned despite the module's own cleanup, and
      kill runs on the retry-recovery path precisely to clear such orphans before a
      fresh init.

REPORT CONFIG TABLES (fetched once, here):
    Report-table config keys follow the convention ``ReportTable_<ReportName>`` and
    each holds the NAME of a portal config table for that report. Init enumerates
    those keys generically (it hardcodes no report roster), fetches each whole table
    once, and returns them under ``initialised_apps["report_tables"]`` keyed by the
    clean report name (prefix stripped) — e.g. "BankReconciliation". A blank key
    value means that report is not in scope and is skipped.

HOOKS PROVIDED (wired via config.json):
    - initialize_applications(agent)          -> InitApplicationsFunction
    - close_applications(initialised_apps=..) -> CloseAllProcessFunction
    - kill_applications(initialised_apps=..)  -> KillAllProcessFunction

ALSO EXPORTED (for the consumer to call at the top of each item):
    - ensure_browser_session(agent)  -> a live, logged-in browser, healed if the
      shared session died on an earlier item.

NOTE: The Xero browser API and the xero_login signature below are marked with
``TODO`` where your real iaa_rpa_utils / iaa_rpa_xero calls plug in. The lifecycle
structure around them is complete.
"""

# ====================================================================================
# STANDARD LIBRARY IMPORTS
# ====================================================================================
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict

# ====================================================================================
# IAA FRAMEWORK IMPORTS
# ====================================================================================
from iaa_rpa_framework.config import Config
from iaa_rpa_framework import UserCredential

# ====================================================================================
# BROWSER + XERO INTEGRATION IMPORTS
# ====================================================================================
# TODO: point these at your real helpers.
from iaa_rpa_utils.browser import SeleniumBrowser
from iaa_rpa_utils.logger import setup_logger, ProcessLogger
from iaa_rpa_utils.strfunctions import str_to_bool
from iaa_rpa_utils.exceptions import InitialisationError
from iaa_rpa_xero_blue.auth import xero_blue_login

# ====================================================================================
# MODULE SETUP
# ====================================================================================
logger = setup_logger(__name__)

# Processes that can be left orphaned by a crashed run and must be swept before a
# fresh start. chromedriver/chrome from Selenium; EXCEL from the consolidation module.
_ORPHAN_PROCESS_NAMES = ("chromedriver.exe", "chrome.exe", "EXCEL.EXE")

# Config-key convention for report tables. A key named "ReportTable_<ReportName>"
# holds the portal config-table name for that report. The prefix is load-bearing:
# do NOT use it for any config key that is not a report table.
_REPORT_TABLE_KEY_PREFIX = "ReportTable_"


# ====================================================================================
# INTERNAL: BROWSER + XERO LOGIN
# ====================================================================================
def _create_browser() -> SeleniumBrowser:
    """Create a fresh Selenium browser instance (not yet logged in).

    Uses the iaa_rpa_utils SeleniumBrowser. ``use_existing_profile=True`` clones
    the named Chrome profile into a temp dir (avoiding profile locks), which is the
    right choice on an unattended runner where a logged-in Chrome profile carries
    session cookies. Set ``ChromeProfileDirectory`` in config if you use a named
    profile other than "Default".
    """
    logger.info("  Creating browser instance")
    browser = SeleniumBrowser(
        use_existing_profile=str_to_bool(
            Config.get("UseExistingChromeProfile", "true")
        ),
        profile_directory=Config.get("ChromeProfileDirectory", "Default"),
        headless=str_to_bool(Config.get("BrowserHeadless", "false")),
    )
    return browser


def _login_to_xero(browser: SeleniumBrowser, agent) -> None:
    """Log the given browser in to Xero Practice Manager using the firm's asset.

    ONE firm-wide login serves every client in the run; individual clients are
    selected per item during processing, not logged into separately.
    """
    asset_name = Config.get("XeroCredentialAsset", "xero_FirmCredentials")
    logger.info("  Retrieving Xero credentials from asset: %s", asset_name)
    creds: UserCredential = agent.get_asset(asset_name, UserCredential)

    logger.info("  Logging in to Xero Practice Manager as %s", creds.username)
    # TODO: match your xero_login signature.
    login_ok = xero_blue_login(
        browser=browser,
        email=creds.username,
        password=creds.password,
        otp=creds.mfa_key,
        xero_blue_url=Config.get("XeroLoginUrl"),
        payroll_url=Config.get("XeroPayrollUrl"),
    )
    if login_ok is False:
        raise RuntimeError("Xero login failed during initialisation.")
    logger.info("  Xero login successful")


def _browser_is_alive(browser: Any) -> bool:
    """Best-effort probe: is this browser/session still usable?

    Reads a cheap driver property; any raise means the session is dead or the
    browser has quit ("invalid session id", "no such window", disconnected, or a
    WebDriverException because the driver is gone entirely). Returns False on any
    problem so a dead or wedged session is always treated as dead.
    """
    if browser is None or getattr(browser, "driver", None) is None:
        return False
    try:
        # Reading window_handles is cheap and raises on a dead/closed session.
        # (current_url would also work; window_handles avoids a network round-trip.)
        _ = browser.driver.window_handles
        return True
    except Exception as exc:
        logger.warning("  Browser liveness probe failed (treating as dead): %s", exc)
        return False


# ====================================================================================
# INTERNAL: REPORT CONFIG TABLES
# ====================================================================================
def _fetch_report_tables(agent) -> Dict[str, Any]:
    """Fetch every in-scope report config table, once, at init time.

    Generic by design: enumerates config keys matching the ``ReportTable_`` prefix
    (knowing NO specific report), and for each non-blank value fetches the whole
    portal config table it names. Returns a dict keyed by the CLEAN report name
    (prefix stripped), e.g. {"BankReconciliation": <ConfigTable>, ...}.

    A blank key value = that report is not in scope (skipped). A key that names a
    table the portal does not have is a configuration error -> fail the whole run
    (better than failing identically on every item).
    """
    all_config = Config.list_all_keys_and_values() or {}
    report_tables: Dict[str, Any] = {}

    for config_key, raw_value in all_config.items():
        if not config_key.startswith(_REPORT_TABLE_KEY_PREFIX):
            continue

        table_name = str(raw_value or "").strip()
        report_name = config_key[len(_REPORT_TABLE_KEY_PREFIX):]

        if not table_name:
            logger.info("Report '%s' has no table configured — not in scope", report_name)
            continue

        logger.info("Fetching config table '%s' for report '%s'", table_name, report_name)
        table = agent.get_config_table(table_name)
        if table is None:
            raise InitialisationError(
                f"Config key '{config_key}' points at config table '{table_name}', "
                f"which was not found on the portal."
            )
        report_tables[report_name] = table

    logger.info("Report tables in scope: %s", sorted(report_tables.keys()))
    return report_tables


# ====================================================================================
# PUBLIC HOOK: INITIALISE
# ====================================================================================
def initialize_applications(agent) -> Dict[str, Any]:
    """InitApplicationsFunction. Runs once at startup (only if the queue has work).

    Creates the long-lived Xero browser, logs it in, and fetches the in-scope report
    config tables once. Returns the dict that becomes ``agent.initialised_apps``.
    """
    with ProcessLogger("Application Manager — Initialise", logger):
        apps: Dict[str, Any] = {}

        try:
            browser = _create_browser()
            apps["browser"] = browser
            _login_to_xero(browser, agent)

            # Fetch all in-scope report config tables once (network calls live here,
            # not in the per-item consumer). Keyed by clean report name.
            apps["report_tables"] = _fetch_report_tables(agent)

            logger.info("Initialisation complete")
            return apps
        except Exception as exc:
            # Make sure a half-created browser from a failed init does not leak.
            logger.exception("Initialisation failed: %s", exc)
            try:
                browser = apps.get("browser")
                if browser:
                    browser.close()
            except Exception:
                pass
            # Re-raise so the framework records the initialisation failure.
            raise RuntimeError(f"Failed to initialise applications: {exc}") from exc


# ====================================================================================
# PUBLIC HELPER: PER-ITEM SESSION HEALTH CHECK
# ====================================================================================
def ensure_browser_session(agent) -> Any:
    """Return a live, logged-in Xero browser, healing the shared one if it died.

    Call this at the TOP of the consumer's per-item processing. Init runs once, so
    the single firm-wide browser is shared across every client in the run; over
    200–300 clients a session can go stale or crash. When that happens this rebuilds
    the browser, re-logs-in, and updates ``agent.initialised_apps`` in place so the
    repair carries forward to later items too (one item pays the reconnect cost).

    Raises:
        RuntimeError: If a live session cannot be established (a system-level
                      failure — the caller should raise RPASystemException).
    """
    apps = getattr(agent, "initialised_apps", None) or {}
    browser = apps.get("browser")

    if _browser_is_alive(browser):
        return browser

    logger.warning("  Xero browser session is dead — rebuilding and re-logging in")
    # Best-effort teardown of the dead browser before replacing it.
    try:
        if browser:
            browser.close()
    except Exception as exc:
        logger.warning("  Could not close dead browser: %s", exc)

    browser = _create_browser()
    _login_to_xero(browser, agent)

    # Heal in place so every later item benefits from the fresh session.
    apps["browser"] = browser
    agent.initialised_apps = apps
    logger.info("  Xero browser session rebuilt")
    return browser


# ====================================================================================
# PUBLIC HOOK: CLOSE (graceful)
# ====================================================================================
def close_applications(initialised_apps: Dict[str, Any] | None = None) -> None:
    """CloseAllProcessFunction. Graceful shutdown at the end of a normal run.

    Only the browser is managed here (Excel is owned by the consolidation module).
    Catches everything so cleanup never raises.
    """
    with ProcessLogger("Application Manager — Close", logger):
        browser = (initialised_apps or {}).get("browser")
        if not browser:
            logger.info("No browser to close")
            return

        try:
            browser.close()
            logger.info("Browser closed")
        except Exception as exc:
            logger.warning("Browser close failed: %s", exc)


# ====================================================================================
# PUBLIC HOOK: KILL (forceful)
# ====================================================================================
def kill_applications(initialised_apps: Dict[str, Any] | None = None) -> None:
    """KillAllProcessFunction. Force cleanup, run at the START of each init cycle
    — including the retry-recovery re-init after a system exception.

    Two parts:
      1. Graceful close of anything we were handed (reuses close_applications).
      2. Force-kill ORPHANED processes by name — chromedriver/chrome from a crashed
         browser, and EXCEL.EXE that the consolidation module may have orphaned on a
         crash despite its own finally-block cleanup. This is the part close() can't
         do, and the reason kill exists for this robot.

    The force-kill is gated behind ``EnableProcessKill`` (default true) so it can be
    turned OFF for local development, where blindly killing EXCEL.EXE would close the
    developer's own open spreadsheets.
    """
    with ProcessLogger("Application Manager — Kill", logger):
        # 1) Graceful attempt first.
        close_applications(initialised_apps)

        # 2) Force-sweep orphans (guarded for dev safety).
        if not str_to_bool(Config.get("EnableProcessKill", "true")):
            logger.info(
                "EnableProcessKill=false — skipping force-kill of orphaned processes"
            )
            return

        for proc_name in _ORPHAN_PROCESS_NAMES:
            _force_kill_process(proc_name)


def _force_kill_process(process_name: str) -> None:
    """Force-terminate all instances of a process by image name (Windows).

    Best-effort and independent per process — a failure to kill one never stops the
    others or raises. Uses taskkill on Windows; logs and skips elsewhere.
    """
    try:
        # /F force, /IM image name, /T also child processes.
        result = subprocess.run(
            ["taskkill", "/F", "/IM", process_name, "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        # taskkill: 0 = killed something, 128 = no such process (both fine).
        if result.returncode == 0:
            logger.info("  Killed orphaned process: %s", process_name)
        else:
            logger.debug("  No orphaned %s to kill (or kill skipped)", process_name)
    except Exception as exc:
        logger.warning("  Could not force-kill %s: %s", process_name, exc)