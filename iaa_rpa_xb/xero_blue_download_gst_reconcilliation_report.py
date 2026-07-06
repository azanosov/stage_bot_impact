from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By

from . import selenium_helper as helper
from .download_file import generate_and_export_report

logger = setup_logger(__name__)


def xero_blue_download_gst_recconciliation_report(
    browser: Any,
    xero_client_name: str,
    xero_end_date: str | None,
    xero_financial_year: str,
    xero_start_date: str | None,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    xero_report_name: str,
    extension: list[str],
) -> None:
    """
    Download the GST Reconciliation report from Xero Blue (legacy interface).

    Resolves the reporting period dates, enters them into the legacy Xero UI,
    clicks Update, then iterates over each requested extension — opening the Export
    menu, selecting the matching format link, and saving the file via the save dialog.

    Args:
        browser: Browser instance containing the Selenium WebDriver with an active Xero session.
        xero_client_name (str): Name of the Xero client/organization for logging purposes.
        xero_end_date (str | None): Report end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty, defaults to 30 Jun of xero_financial_year.
        xero_financial_year (str): Financial year for the report (e.g., "2024").
            Used as fallback when xero_start_date or xero_end_date is not provided.
        xero_start_date (str | None): Report start date in format "DD Mon YYYY" (e.g., "1 Jul 2023").
            If None or empty, defaults to 1 Jul of the prior financial year.
        window_title (str): Title of the browser window, used to locate the save dialog.
        download_directory (str): Absolute path to the directory where files will be saved.
        report_file_name (str): Desired filename for the downloaded report (without extension).
        xero_report_name (str): Display name of the report shown in the Xero UI, used for logging.
        extension (list[str]): File formats to export. Accepted values: ".xlsx", ".pdf".
            Defaults to [".xlsx"] if None or empty.

    Returns:
        None: The function saves the report file(s) to disk and logs the operation status.

    Raises:
        Exception: If any step in the download workflow fails (element not found, timeout,
            file save error, etc.). All exceptions are logged before being re-raised.
    """
    start_time = datetime.now()

    logger.info("STARTING: xero_blue_download_gst_recconciliation_report")
    logger.info(json.dumps({
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "xero_client_name": xero_client_name,
        "xero_end_date": xero_end_date,
        "xero_financial_year": xero_financial_year,
        "xero_start_date": xero_start_date,
        "window_title": window_title,
        "download_directory": download_directory,
        "report_file_name": report_file_name,
        "xero_report_name": xero_report_name,
        "extension": extension,
    }, indent=2))

    try:
        driver = browser.driver
        from_date_id = "fromDate"
        to_date_id = "toDate"

        start_date, end_date = resolve_report_dates(
            xero_start_date,
            xero_end_date,
            xero_financial_year,
        )

        helper.type_into_date_element(driver, from_date_id, start_date, by=By.ID)
        logger.info("Entered From date")

        helper.type_into_date_element(driver, to_date_id, end_date, by=By.ID)
        logger.info("Entered To date")

        generate_and_export_report(
            driver,
            window_title,
            download_directory,
            report_file_name,
            extension,
            take_screenshot_flag=False,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("COMPLETED: Xero Blue Download GST Reconciliation Report")
        logger.info(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {xero_client_name}")
        logger.info(f"Report File Name  : {report_file_name}")
        logger.info(f"Status            : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error("FAILED: Xero Blue Download GST Reconciliation Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {xero_client_name}")
        logger.error(f"Report File Name  : {report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error("xero_blue_download_gst_recconciliation_report failed", exc_info=True)
        raise


def resolve_report_dates(
    xero_start_date: str | None,
    xero_end_date: str | None,
    xero_financial_year: str,
) -> tuple[str, str]:
    """Return (start_date, end_date), defaulting to the full financial year if not provided."""
    if not xero_start_date:
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        logger.info(f"No custom start date provided. Using financial year default: {str_start_date}")
    else:
        str_start_date = xero_start_date
        logger.info(f"Using provided start date: {str_start_date}")

    if not xero_end_date:
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"No custom end date provided. Using financial year default: {str_end_date}")
    else:
        str_end_date = xero_end_date
        logger.info(f"Using provided end date: {str_end_date}")

    return str_start_date, str_end_date


