from iaa_rpa_utils import get_logger, ProcessLogger
from iaa_rpa_xero_blue.xero_blue_navigate_to_reports_dashboard import (
    xero_blue_navigate_to_reports_dashboard,
)
from iaa_rpa_xero_blue.xero_blue_navigate_to_report import xero_blue_navigate_to_report

logger = get_logger(__name__)


def navigate_to_xero_report_wrapper(browser, report_name: str, title: str) -> None:
    """
    Navigate to a specified report page in Xero.
    Navigates to the reports dashboard first, then opens the specified report.

    Args:
        browser: SeleniumBrowser instance
        report_name: The Xero report name, e.g. "Bank Reconciliation"
        title: The Xero page title to match, e.g. "Reports"
    """
    logger.info(f"Navigating to '{report_name}' report")

    try:
        with ProcessLogger("Reports dashboard", logger):
            xero_blue_navigate_to_reports_dashboard(browser)
    except Exception:
        logger.exception("Failed to navigate to reports dashboard")
        raise

    try:
        with ProcessLogger(f"{report_name} report", logger):
            xero_blue_navigate_to_report(
                browser, xero_blue_report_name=report_name, xero_blue_title=title
            )
    except Exception:
        logger.exception(f"Failed to navigate to '{report_name}' report")
        raise

    logger.info(f"Successfully navigated to '{report_name}' report")
