from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By

from . import selenium_helper as helper
from .download_file import generate_and_export_report

logger = setup_logger(__name__)


def xero_blue_download_aged_payables_summary_reports(
    browser: Any,
    client_name: str,
    xero_end_date: str | None,
    xero_financial_year: str,
    is_add_gst_column: bool,
    xero_aging_by: str,
    ageing_period: str | None,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: list[str],
) -> None:
    """
    Download the Xero Aged Payables Summary report.

    Sets the report end date, selects the aging method, optionally adds the Outstanding GST
    column, then clicks Update and exports in each requested format via the save dialog.

    Args:
        browser: Browser instance containing the Selenium WebDriver with an active Xero session.
        client_name (str): Name of the Xero client/organization for logging purposes.
        xero_end_date (str | None): Report end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty, defaults to 30 Jun of xero_financial_year.
        xero_financial_year (str): Financial year for the report (e.g., "2024").
            Used as fallback when xero_end_date is not provided.
        is_add_gst_column (bool): Whether to include the Outstanding GST column in the report.
        xero_aging_by (str): Aging method — "Due date" or "Invoice date".
        window_title (str): Title of the browser window, used to locate the save dialog.
        download_directory (str): Absolute path to the directory where files will be saved.
        report_file_name (str): Desired filename for the downloaded report (without extension).
        extension (list[str]): File formats to export. Accepted values: ".xlsx", ".pdf".
            Defaults to [".xlsx"] if None or empty. Pass [".xlsx", ".pdf"] to export both.

    Returns:
        None: The function saves the report file(s) to disk and logs the operation status.

    Raises:
        Exception: If any step in the download workflow fails (element not found, timeout,
            file save error, etc.). All exceptions are logged before being re-raised.
    """
    start_time = datetime.now()

    logger.info("STARTING: xero_blue_download_aged_payables_summary_reports")
    logger.info(json.dumps({
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "client_name": client_name,
        "xero_end_date": xero_end_date,
        "xero_financial_year": xero_financial_year,
        "is_add_gst_column": is_add_gst_column,
        "xero_aging_by": xero_aging_by,
        "ageing_period": ageing_period,
        "window_title": window_title,
        "download_directory": download_directory,
        "report_file_name": report_file_name,
        "extension": extension,
    }, indent=2))

    try:
        driver = browser.driver

        if not xero_end_date:
            xero_end_date = f"30 Jun {xero_financial_year}"
            logger.info(f"No end date provided. Using financial year end: {xero_end_date}")
        
        # Select End Date
        helper.type_into_date_element(driver, "report-settings-custom-date-input-to", xero_end_date, by=By.ID)

        select_aging_by(xero_aging_by, driver)
        set_ageing_period(driver, ageing_period)

        set_gst_column(
            browser,
            is_add_gst_column,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

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
        logger.info("COMPLETED: Xero Blue Download Aged Payables Summary Report")
        logger.info(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {client_name}")
        logger.info(f"Report File Name  : {report_file_name}")
        logger.info(f"Status            : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error("FAILED: Xero Blue Download Aged Payables Summary Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {client_name}")
        logger.error(f"Report File Name  : {report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error("xero_blue_download_aged_payables_summary_reports failed", exc_info=True)
        raise

def select_aging_by(xero_aging_by, driver):
    logger.info(f"Configuring aging method: {xero_aging_by}")
    ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
    helper.click_element(driver, ageing_button_xpath)
    logger.info("Opened aging method dropdown")

    ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"
    if helper.element_exists(driver, ageing_option_xpath, timeout=5):
        helper.click_element(driver, ageing_option_xpath)
        logger.info(f"Successfully selected aging method: {xero_aging_by}")
    else:
        logger.warning(f"Aging method '{xero_aging_by}' not found in dropdown. Proceeding with default.")

def set_ageing_period(driver: Any, ageing_period: str | None) -> None:
    """
    Configure the ageing period modal on the Aged Payables report.

    Parses ageing_period (e.g. "4 periods of 3 Month") into count, size, and kind,
    then opens the modal, sets each value, and selects the period kind from the dropdown.

    Args:
        driver: Selenium WebDriver instance.
        ageing_period (str | None): Period string in the format "{count} periods of {size} {kind}".
            If None or empty, the step is skipped.
    """
    if not ageing_period:
        logger.info("No ageing period specified — skipping ageing period configuration")
        return

    match = re.match(r'(\d+)\s+periods?\s+of\s+(\d+)\s+(\w+)', ageing_period, re.IGNORECASE)
    if not match:
        logger.warning(f"Could not parse ageing period '{ageing_period}' — skipping")
        return

    count, size, kind = match.group(1), match.group(2), match.group(3).capitalize()
    logger.info(f"Setting ageing period: {count} periods of {size} {kind}")

    trigger_xpath = "//button[@id='report-settings-ageing-periods-modal-trigger']"
    count_input_xpath = "(//input[contains(@class,'report-settings-ageing-periods-modal-input')])[1]"
    size_input_xpath = "(//input[contains(@class,'report-settings-ageing-periods-modal-input')])[2]"
    kind_dropdown_xpath = "//section[@role='dialog']//button[@aria-haspopup='listbox']"
    kind_option_xpath = f"//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='{kind}']]"
    apply_button_xpath = "//section[@role='dialog']//button[normalize-space(text())='Apply']"

    helper.click_element(driver, trigger_xpath)
    helper.type_into_element(driver, count_input_xpath, count)
    helper.type_into_element(driver, size_input_xpath, size)
    helper.click_element(driver, kind_dropdown_xpath)
    helper.click_element(driver, kind_option_xpath)
    helper.click_element(driver, apply_button_xpath)

    logger.info(f"Ageing period configured: {count} periods of {size} {kind}")


def set_gst_column(
    browser: Any,
    is_add_gst_column: bool,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: list[str],
) -> None:
    """Optionally add Outstanding GST column, then export the report."""
    driver = browser.driver
    gst_button_xpath = "//*[@id='report-settings-columns-button']"
    outstanding_gst_xpath = "//span[contains(@class,'xui-pickitem-multiselect--label')][.//span[normalize-space()='Outstanding GST']]"

    if is_add_gst_column:
        logger.info("Adding GST column...")
        helper.click_element(driver, gst_button_xpath)
        helper.click_element(driver, outstanding_gst_xpath)
        helper.click_element(driver, gst_button_xpath)
        logger.info("GST column added successfully.")
    else:
        logger.info("GST column not requested. Skipping.")

   
