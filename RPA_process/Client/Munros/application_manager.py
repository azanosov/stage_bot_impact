"""
Application Manager — Munros Client
====================================
Manages the lifecycle of all applications required for the Munros process.

Responsibilities:
    1. Xero Practice Manager  — browser login + MFA
    2. MYOB Web               — browser login (placeholder)
    3. MYOB Desktop/API       — connection initialisation (placeholder)
    4. Config tables          — email templates, manager list, etc.

Main functions:
    initialize_applications()  — called once by RPAStateMachine before processing
    close_applications()       — graceful shutdown at end of run
    kill_applications()        — force shutdown on critical failure
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from iaa_rpa_framework.config import Config
from iaa_rpa_framework import ConfigTable, UserCredential
from iaa_rpa_utils.browser import SeleniumBrowser
from iaa_rpa_xero.xero_login import xero_login

logger = logging.getLogger("IARPA." + __name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_email_templates(sm) -> ConfigTable | None:
    """Load the email-template master config table from the Portal.

    TODO: Set EmailTemplateMasterFile config key to the Portal table name.
    """
    table_name = str(Config.get("EmailTemplateMasterFile", "") or "").strip()
    if not table_name:
        logger.info(
            "EmailTemplateMasterFile not configured; skipping template table load"
        )
        return None
    try:
        raw = sm.get_config_table(table_name)
        if raw is None:
            return None
        import json

        if isinstance(raw, str):
            raw = json.loads(raw)
        templates = ConfigTable(raw)
        logger.info("Loaded %s email template row(s)", len(templates))
        return templates
    except Exception as exc:
        logger.warning("Could not load email template table '%s': %s", table_name, exc)
        return None


def _load_manager_list(sm) -> ConfigTable | None:
    """Load the Partner/Manager mapping table from the Portal.

    TODO: Set ManagerListConfigTableName config key to the Portal table name.
    """
    table_name = str(Config.get("ManagerListConfigTableName", "") or "").strip()
    if not table_name:
        logger.info(
            "ManagerListConfigTableName not configured; skipping manager list load"
        )
        return None
    try:
        raw = sm.get_config_table(table_name)
        if raw is None:
            return None
        import json

        if isinstance(raw, str):
            raw = json.loads(raw)
        manager_list = ConfigTable(raw)
        logger.info("Loaded %s manager list row(s)", len(manager_list))
        return manager_list
    except Exception as exc:
        logger.warning("Could not load manager list table '%s': %s", table_name, exc)
        return None


def _login_to_xero(browser: SeleniumBrowser, sm) -> None:
    """Log in to Xero Practice Manager using the Munros credential asset.

    TODO: Create orchestrator asset 'munros_XeroCredentials' with username,
          password, and mfa_key fields.
    """
    # TODO: replace asset name with the correct Munros Xero credential asset
    creds: UserCredential = sm.get_asset("munros_XeroCredentials", UserCredential)
    logger.info("Logging in to Xero as %s", creds.username)
    success = xero_login(
        browser=browser,
        xero_email=creds.username,
        xero_password=creds.password,
        xero_practice_manager_url=Config.get(
            "Xero_PracticeManagerUrl", "https://practicemanager.xero.com"
        ),
        xero_portal_account_name=Config.get("Xero_PortalAccountName", "Munros"),
        xero_otp_code=creds.mfa_key,
        xero_lastpass_title=Config.get("Xero_LastPassTitle", ""),
        xero_practice_manager_title=Config.get(
            "Xero_PracticeManagerTitle", "Xero Practice Manager"
        ),
    )
    if success is False:
        raise RuntimeError("Xero login failed during initialisation.")
    logger.info("Xero login successful")


def _login_to_myob_web(browser: SeleniumBrowser, sm) -> None:
    """Log in to MYOB Web (browser-based) using the Munros MYOB credential asset.

    TODO: Implement MYOB Web login flow.
          Create orchestrator asset 'munros_MYOBWebCredentials'.
    """
    # TODO: retrieve MYOB Web credentials from orchestrator asset
    # creds = sm.get_asset("munros_MYOBWebCredentials", UserCredential)
    # TODO: navigate browser to MYOB Web URL and authenticate
    logger.info("MYOB Web login — TODO: implement")


def _connect_to_myob(sm) -> Any:
    """Initialise MYOB Desktop / API connection.

    TODO: Implement MYOB connection (API key, company file path, etc.).
          Create orchestrator asset 'munros_MYOBCredentials'.
    Returns the MYOB connection/client object, or None if not yet implemented.
    """
    # TODO: connect to MYOB using appropriate SDK or API
    logger.info("MYOB connection — TODO: implement")
    return None


# ---------------------------------------------------------------------------
# Public lifecycle functions
# ---------------------------------------------------------------------------


def initialize_applications(sm) -> Dict[str, Any]:
    """Initialise all applications for the Munros process.

    Steps:
        1. Load config tables (email templates, manager list)
        2. Initialise Selenium browser
        3. Log in to Xero Practice Manager
        4. Log in to MYOB Web  (TODO)
        5. Connect to MYOB     (TODO)

    Returns:
        dict with keys: mode, email_templates, manager_list,
                        browser, xero_logged_in, myob_connection
    """
    logger.info("=" * 80)
    logger.info("MUNROS APPLICATION MANAGER - INITIALISE APPLICATIONS")
    logger.info("=" * 80)

    apps: Dict[str, Any] = {"mode": "live"}

    try:
        # Step 1 — Config tables
        email_templates = _load_email_templates(sm)
        if email_templates is not None:
            apps["email_templates"] = email_templates

        manager_list = _load_manager_list(sm)
        if manager_list is not None:
            apps["manager_list"] = manager_list

        from RPA_process.Client.Munros import munros_constants as MC

        if str(Config.get(MC.CFG_DISABLE_BROWSER_INIT, "false")).strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            logger.info("Browser init disabled by %s=true", MC.CFG_DISABLE_BROWSER_INIT)
            apps["browser"] = None
            return apps

        # Step 2 — Browser
        browser = SeleniumBrowser(
            download_dir=Config.get("DownloadDir", "downloads"),
            use_existing_profile=True,
        )
        apps["browser"] = browser
        logger.info("Browser initialised")

        # Step 3 — Xero login
        _login_to_xero(browser, sm)
        apps["xero_logged_in"] = "true"

        # Step 4 — MYOB Web login (TODO)
        _login_to_myob_web(browser, sm)

        # Step 5 — MYOB connection (TODO)
        myob_connection = _connect_to_myob(sm)
        apps["myob_connection"] = myob_connection

        logger.info("Initialisation complete")
        return apps

    except Exception as exc:
        logger.exception("Failed to initialise applications: %s", exc)
        raise RuntimeError(f"Failed to initialise applications: {exc}") from exc


def close_applications(initialised_apps: Dict[str, Any] | None = None) -> None:
    """Gracefully close all applications.

    TODO: Add MYOB Web logout and MYOB connection close when implemented.
    """
    logger.info("MUNROS APPLICATION MANAGER - CLOSE APPLICATIONS")
    browser = (initialised_apps or {}).get("browser")
    if browser:
        try:
            browser.close()
            logger.info("Browser closed")
        except Exception as exc:
            logger.warning("Browser close failed: %s", exc)

    # TODO: close MYOB Web session
    # TODO: close MYOB API connection


def kill_applications(initialised_apps: Dict[str, Any] | None = None) -> None:
    """Force-kill all applications."""
    logger.info("MUNROS APPLICATION MANAGER - KILL APPLICATIONS")
    close_applications(initialised_apps)
