from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By

from . import selenium_helper as helper
from .download_file import generate_and_export_report

logger = setup_logger(__name__)


def xero_blue_download_aged_receivables_summary_report(
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
    """Download Aged Receivables Summary report from Xero Blue."""
    start_time = datetime.now()

    logger.info("STARTING: xero_blue_download_aged_receivables_summary_report")
    logger.info(
        json.dumps(
            {
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "client_name": client_name,
                "xero_end_date": xero_end_date,
                "xero_financial_year": xero_financial_year,
                "is_add_gst_column": is_add_gst_column,
                "xero_aging_by": xero_aging_by,
                "window_title": window_title,
                "download_directory": download_directory,
                "report_file_name": report_file_name,
                "extension": extension,
            },
            indent=2,
        )
    )

    try:
        driver = browser.driver

        str_end_date = xero_end_date or f"30 Jun {xero_financial_year}"
        logger.info(f"End date: {str_end_date}")

        helper.type_into_date_element(
            driver, "report-settings-custom-date-input-to", str_end_date, by=By.ID
        )
        configure_aging(driver, xero_aging_by)
        set_ageing_period(driver, ageing_period)
        set_gst_column(driver, is_add_gst_column)

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
        logger.info("COMPLETED: Xero Blue Download Aged Receivables Summary Report")
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
        logger.error("FAILED: Xero Blue Download Aged Receivables Summary Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {client_name}")
        logger.error(f"Report File Name  : {report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error(
            "xero_blue_download_aged_receivables_summary_report failed", exc_info=True
        )
        raise


def configure_aging(driver: Any, xero_aging_by: str) -> None:
    """Open the aging dropdown and select the requested method; warns if the option is absent."""
    ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
    helper.click_element(driver, ageing_button_xpath)

    ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"
    if helper.element_exists(driver, ageing_option_xpath, timeout=5):
        helper.click_element(driver, ageing_option_xpath, timeout=5)
        logger.info(f"Aging method '{xero_aging_by}' selected")
    else:
        logger.warning(f"Aging method '{xero_aging_by}' not found — using default")


def set_ageing_period(driver: Any, ageing_period: str | None) -> None:
    """Parse '{count} periods of {size} {kind}' and apply it via the ageing periods modal."""
    if not ageing_period:
        logger.info("No ageing period specified — skipping")
        return

    match = re.match(
        r"(\d+)\s+periods?\s+of\s+(\d+)\s+(\w+)", ageing_period, re.IGNORECASE
    )
    if not match:
        logger.warning(f"Could not parse ageing period '{ageing_period}' — skipping")
        return

    count, size, kind = match.group(1), match.group(2), match.group(3).capitalize()
    logger.info(f"Setting ageing period: {count} periods of {size} {kind}")

    trigger_xpath = "//button[@id='report-settings-ageing-periods-modal-trigger']"
    count_input_xpath = (
        "(//input[contains(@class,'report-settings-ageing-periods-modal-input')])[1]"
    )
    size_input_xpath = (
        "(//input[contains(@class,'report-settings-ageing-periods-modal-input')])[2]"
    )
    kind_dropdown_xpath = "//section[@role='dialog']//button[@aria-haspopup='listbox']"
    kind_option_xpath = f"//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='{kind}']]"
    apply_button_xpath = (
        "//section[@role='dialog']//button[normalize-space(text())='Apply']"
    )

    helper.click_element(driver, trigger_xpath)
    helper.type_into_element(driver, count_input_xpath, count)
    helper.type_into_element(driver, size_input_xpath, size)
    helper.click_element(driver, kind_dropdown_xpath)
    helper.click_element(driver, kind_option_xpath)
    helper.click_element(driver, apply_button_xpath)

    logger.info(f"Ageing period configured: {count} periods of {size} {kind}")


def set_gst_column(driver: Any, is_add_gst_column: bool) -> None:
    """Open the columns menu, tick 'Tax Amount Due', then close the menu."""
    if not is_add_gst_column:
        logger.info("GST column not requested — skipping")
        return
    helper.click_element(driver, "report-settings-columns-button", by=By.ID)
    helper.click_element(driver, "column-selection-taxamountdue", by=By.ID)
    helper.click_element(driver, "report-settings-columns-button", by=By.ID)
    logger.info("GST column added")
