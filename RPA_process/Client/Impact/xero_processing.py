from iaa_rpa_xero_blue.switch_client import switch_client
from iaa_rpa_xero_blue.navigation import navigate_to_report_page, navigate_to_all_reports_page
from iaa_rpa_utils.exceptions import DataValidationError, NavigationError
from iaa_rpa_utils.logger import setup_logger
from iaa_rpa_framework import RPABusinessException, RPASystemException
from typing import TYPE_CHECKING, Any

from xero_report_config import ReportName, _build_report_tasks

if TYPE_CHECKING:
    from iaa_rpa_utils.browser import SeleniumBrowser

logger = setup_logger(__name__)

# ====================================================================================
# STAGE 1 — SELECT CLIENT IN XERO
# ====================================================================================
def _select_xero_client(browser: SeleniumBrowser, vals: dict[str, Any]) -> None:
    """Switch the active Xero organisation to this client.

    Xero switches by the ORGANISATION NAME as shown in Xero — so we pass the
    client name.
    IMPORTANT: the queue's "Client name" must match the Xero org name exactly, or
    switch_client will report the org as not-found.

    Exception translation (switch_client's documented contract):
      - DataValidationError  -> org not found (client_name was already validated
                                non-empty in STAGE 0), so this means the client
                                does not exist in Xero: BUSINESS (warning).
      - NavigationError / ElementNotFoundError -> UI/automation failure: SYSTEM
                                (retry); handled by the caller's translation block.
    """
    try:
        switch_client(browser, vals["client_name"])
    except DataValidationError as exc:
        raise RPABusinessException(
            f"Client '{vals['client_name']}' not found in Xero: {exc}"
        ) from exc
    # NavigationError / ElementNotFoundError propagate to process_client's
    # _SYSTEM_LIBRARY_EXCEPTIONS handler, which classifies them as system/retry.


# ====================================================================================
# STAGE 2 — EXPORT XERO REPORTS
# ====================================================================================

# this automation is built as 9 known reports download template
# since current clinet does not have Payroll reports, we are skipping them
_EXCLUSION_LIST = (
    ReportName.PAYROLL_EMPLOYEE_SUMMARY, 
    ReportName.PAYROLL_ACTIVITY_SUMMARY,
    )

def _export_xero_reports(browser: SeleniumBrowser, vals: dict[str, Any], report_tables:  dict[str, Any]) -> list[str]:
    """Export the required Xero reports for the period into temp_dir.

    Returns the list of downloaded file paths.
    """
    client = vals.get("client_name")
    report_tasks = _build_report_tasks(vals, report_tables)
    report_file_paths = []

    # Establish the report centre ONCE. If this fails, the page/session is broken
    # — a system failure, NOT "reports absent". Fail loud, let the item retry.
    try:
        navigate_to_all_reports_page(browser)
    except NavigationError as exc:
        raise RPASystemException(f"Could not reach the All Reports page: {exc}") from exc

    for report in report_tasks:
        if report.name in _EXCLUSION_LIST:
            continue

        try:
            navigate_to_report_page(browser, report.name)
        except NavigationError as exc:
            # The centre is confirmed up (we reached it above), so a NavigationError
            # here means the specific report row is absent -> genuinely out of scope.
            logger.warning(
                "Report %s not available for client %s — skipping (out of scope): %s",
                report.name, client, exc,
            )
            continue

        try:
            file_path = report.func(browser, report.conf)
            report_file_paths.append(file_path)
        except Exception as exc:
            raise RPASystemException(f"Download of report {report.name} failed: {exc}") from exc

    return report_file_paths