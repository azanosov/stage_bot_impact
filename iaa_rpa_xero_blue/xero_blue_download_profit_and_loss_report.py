from __future__ import annotations

import json
import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from . import selenium_helper as helper
from .download_file import download_file
from .take_screenshot import take_screenshot

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_profit_and_loss_report(
    browser,
    client_name,
    xero_start_date,
    xero_end_date,
    xero_financial_year,
    window_title,
    download_directory_path,
    xero_report_file_name,
    extension,
    account_basis,
    report_setting_chk_options,
    compare_with,
    number_of_periods,
    custom_report_name,
):
    """
    Download Profit and Loss report from Xero Blue with customizable settings.

    This function orchestrates the complete workflow to download a Profit and Loss report
    from Xero, including configuring report settings (accounting basis, date range, comparison
    periods, year-to-date), generating the report, and exporting it as an Excel file to a
    specified directory.

    Args:
        browser: Browser instance containing the Selenium WebDriver with an active Xero session.
        client_name (str): Name of the Xero client/organization for logging purposes.
        xero_start_date (str): Start date for the report in format "DD Mon YYYY" (e.g., "01 Jul 2023").
            If None or empty, defaults to financial year start (1 Jul of xero_financial_year - 1).
        xero_end_date (str): End date for the report in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty, defaults to financial year end (30 Jun of xero_financial_year).
        xero_financial_year (str): Financial year for the report (e.g., "2024").
            Used as fallback when xero_start_date or xero_end_date is not provided.
        window_title (str): Title of the browser window, used to locate the save dialog.
        download_directory_path (str): Absolute path to the directory where the Excel file will be saved.
        xero_report_file_name (str): Desired filename for the downloaded report (without extension).
        extension (list[str]): File formats to export. Accepted values: ".xlsx", ".pdf".
            Defaults to [".xlsx"] if None or empty. Pass [".xlsx", ".pdf"] to export both formats.
        account_basis (str): Accounting basis for the report. Accepted values: "Cash" or "Accrual".
            If None or empty, accounting basis is not changed.
        report_setting_chk_options (list[str]): Report settings checkboxes to enable, identified
            by their button label text (e.g., ["Percentage of Income", "Year to Date"]).
            Each item is located via its checkbox inside the matching button and clicked only if
            not already checked. Pass an empty list or None to skip checkbox configuration.
        compare_with (str): The comparison period type to display alongside the current period.
            Accepted values: "Month", "Quarter", "Year". Pass None or empty string to skip.
        number_of_periods (int): Number of comparison periods to include in the report.
            Only applicable when compare_with is set.
        custom_report_name (str): Custom title to set on the report before exporting.
            If None or empty, the default Xero report title is used.

    Returns:
        None: The function saves the report file to disk and logs the operation status.

    Raises:
        Exception: If any step in the download workflow fails (element not found, timeout,
            no data available, file save error, etc.). All exceptions are logged with
            detailed error information before being re-raised.

    Example:
        >>> xero_blue_download_profit_and_loss_report(
        ...     browser=my_browser,
        ...     client_name="ABC Company",
        ...     xero_start_date="01 Jul 2023",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     window_title="Profit and Loss - Xero",
        ...     download_directory_path="C:/Reports",
        ...     xero_report_file_name="profit_and_loss_2024.xlsx",
        ...     extension=[".xlsx"],
        ...     account_basis="Cash",
        ...     report_setting_chk_options=["Percentage of Income", "Year to Date"],
        ...     compare_with="1 year",
        ...     number_of_periods=1,
        ...     custom_report_name="Profit and Loss [Munro's]"
        ... )
    """
    start_time = datetime.now()

    logger.info("STARTING: xero_blue_download_profit_and_loss_report")
    logger.info(json.dumps({
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "client_name": client_name,
        "xero_start_date": xero_start_date,
        "xero_end_date": xero_end_date,
        "xero_financial_year": xero_financial_year,
        "window_title": window_title,
        "download_directory_path": download_directory_path,
        "xero_report_file_name": xero_report_file_name,
        "extension": extension,
        "account_basis": account_basis,
        "report_setting_chk_options": report_setting_chk_options,
        "compare_with": compare_with,
        "number_of_periods": number_of_periods,
        "custom_report_name": custom_report_name,
    }, indent=2))

    try:
        driver = browser.driver

        # STEP 1: Navigate to Custom Report (if specified)
        # Purpose: If a custom_report_name is provided, click the matching saved report link
        # to load it as the starting point before applying any settings.
        # Function: click_custom_report_link(driver, custom_report_name)
        # - Locates the report link by matching the span text to custom_report_name
        # - Clicks the link to open the saved report
        if custom_report_name:
            logger.info(f"STEP 1: Clicking custom report link: '{custom_report_name}'...")
            click_custom_report_link(driver, custom_report_name)
        else:
            logger.info("STEP 1: No custom report name provided — skipping custom report navigation")

        # STEP 2: Configure Report Settings (accounting basis and checkbox options)
        # Purpose: Open the 'More' settings panel, set the accounting basis, and toggle
        # any additional checkboxes (e.g. Percentage of Income, Year to Date).
        # Function: configure_report_settings(driver, account_basis, report_setting_chk_options)
        # - Clicks 'More' button to expand the settings panel
        # - Selects the accounting basis option if account_basis is provided
        # - For each item in report_setting_chk_options, clicks the checkbox if not already checked
        logger.info("STEP 2: Configuring report settings...")
        configure_report_settings(driver, account_basis, report_setting_chk_options)

        # STEP 3: Set Report Date Range
        logger.info("STEP 3: Configuring report date range...")
        str_start_date, str_end_date = resolve_report_dates(xero_start_date, xero_end_date, xero_financial_year)
        configure_report_dates(
            driver,
            str_start_date,
            str_end_date
        )

        # STEP 4: Configure Comparison Period (if specified)
        # Purpose: Select the comparison period from the Compare With dropdown
        # Function: configure_compare_with(driver, compare_with, number_of_periods)
        # - Clicks the Compare With dropdown button to open the period options
        # - Selects the option matching the compare_with value (e.g., "Month", "Quarter", "Year")
        # - Clicks "Enter a different number" and types number_of_periods, then clicks Select
        if compare_with:
            logger.info(f"STEP 4: Configuring comparison period: '{compare_with}' x {number_of_periods}...")
            configure_compare_with(driver, compare_with, number_of_periods)
        else:
            logger.info("STEP 4: No comparison period specified — skipping compare with configuration")

        # STEP 5: Generate Report and Export
        # Purpose: Trigger report generation, verify data exists, export in requested formats, and save files
        # Function: generate_and_export_report(driver, window_title, download_directory_path, xero_report_file_name, extension)
        # - Clicks Update button to generate the report with configured settings
        # - Waits for report title to confirm rendering is complete
        # - Takes a screenshot of the generated report for audit trail
        # - Verifies Export button is present (confirms report has data)
        # - For each requested extension, clicks Export, selects the format, and saves the file
        logger.info("STEP 5: Generating report and exporting...")
        screenshot_file_path = generate_and_export_report(
            driver,
            window_title,
            download_directory_path,
            xero_report_file_name,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("COMPLETED: Xero Blue Download Profit and Loss Report")
        logger.info(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {client_name}")
        logger.info(f"Report File Name  : {xero_report_file_name}")
        logger.info(f"Screenshot Path   : {screenshot_file_path}")
        logger.info(f"Status            : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error("FAILED: Xero Blue Download Profit and Loss Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {client_name}")
        logger.error(f"Report File Name  : {xero_report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error("xero_blue_download_profit_and_loss_report failed", exc_info=True)
        raise


def resolve_report_dates(xero_start_date, xero_end_date, xero_financial_year):
    """
    Determine and format the start and end dates for the Profit and Loss report.

    Decides which dates to use based on whether custom dates are provided.
    If no custom start date is given, defaults to 1 July of the prior financial year.
    If no custom end date is given, defaults to 30 June of the financial year.

    Args:
        xero_start_date (str): Custom start date in format "DD Mon YYYY" (e.g., "01 Jul 2023").
            If None or empty, the function will use the financial year default.
        xero_end_date (str): Custom end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty, the function will use the financial year default.
        xero_financial_year (str): Financial year (e.g., "2024") used to construct
            default dates when custom dates are not provided.

    Returns:
        tuple[str, str]: Formatted (start_date, end_date) strings in "DD Mon YYYY" format.

    Example:
        >>> resolve_report_dates(None, None, "2024")
        ("01 Jul 2023", "30 Jun 2024")
        >>> resolve_report_dates("01 Jan 2024", "30 Jun 2024", "2024")
        ("01 Jan 2024", "30 Jun 2024")
    """
    prior_year = str(int(xero_financial_year) - 1)

    if not xero_start_date:
        str_start_date = f"01 Jul {prior_year}"
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


def configure_report_dates(
    driver,
    str_start_date,
    str_end_date,
):
    """
    Enter the start and end dates into the Xero Profit and Loss date fields.

    Date resolution (raw input → formatted string) is the caller's responsibility via
    resolve_report_dates().

    Args:
        driver: Selenium WebDriver instance for browser automation.
        str_start_date (str): Resolved start date in format "DD Mon YYYY" (e.g., "01 Jul 2023").
        str_end_date (str): Resolved end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").

    Returns:
        None

    Raises:
        TimeoutException: If the date input fields cannot be located within 10 seconds.
    """
    from_elem = helper.type_into_element(driver, "report-settings-custom-date-input-from", str_start_date, by=By.ID)
    from_elem.send_keys(Keys.TAB)

    to_elem = helper.type_into_element(driver, "report-settings-custom-date-input-to", str_end_date, by=By.ID)
    to_elem.send_keys(Keys.TAB)


def generate_and_export_report(
    driver,
    window_title,
    download_directory_path,
    xero_report_file_name,
    extension,
):
    """
    Generate the Profit and Loss report and export it in one or more formats.

    Triggers report generation by clicking the Update button, verifies that data is
    available for export, then iterates over each requested extension — opening the Export
    menu, selecting the matching format button, and saving the file via the save dialog.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        window_title (str): Title of the browser window used to locate the save dialog.
        download_directory_path (str): Absolute path to the directory where files will be saved.
        xero_report_file_name (str): Base filename for the downloaded report (without extension).
        extension (list[str]): File formats to export — ".xlsx" and/or ".pdf".
            Defaults to [".xlsx"] if None or empty.

    Returns:
        str: File path of the screenshot taken after the report was generated.

    Raises:
        Exception: If the Update button is not clickable, the Export button is not available
            (indicating no data), or any step in the export/save process fails.
    """
    format_button_labels = {
        ".xlsx": "Excel",
        ".pdf": "PDF",
    }

    extensions = extension if extension else [".xlsx"]

    update_xpath = "//button[@type='button' and normalize-space(text())='Update']"
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    report_title_xpath = "//input[@placeholder='Report title']"

    helper.click_element(driver, update_xpath)
    helper.find_element(driver, report_title_xpath)
    logger.info("Report rendered successfully")

    screenshot_file_path = take_screenshot(driver)
    logger.info(f"Screenshot saved: {screenshot_file_path}")

    if not is_export_button_available(driver):
        logger.warning("Export button not found - no Profit and Loss data available for this client")
        raise Exception("No Profit and Loss data available for this client.")

    for ext in extensions:
        format_label = format_button_labels.get(ext, "Excel")
        format_xpath = f"//button[@type='button']//span[normalize-space(text())='{format_label}']"

        logger.info(f"Exporting as {format_label} ({ext})...")
        helper.click_element(driver, export_xpath)
        helper.click_element(driver, format_xpath)

        time.sleep(3)

        logger.info(f"Saving report to: {download_directory_path}")
        download_file(window_title, download_directory_path, xero_report_file_name, ext)
        logger.info(f"Report saved as '{xero_report_file_name}{ext}' in '{download_directory_path}'")

    return screenshot_file_path


def is_export_button_available(driver):
    """
    Check whether the Export button is present on the report page.

    Verifies if the Export button appears after the report is generated. The presence
    of this button indicates that the report contains data and is ready for export.
    If the button is not found within the timeout, it suggests no data is available
    for the current report settings.

    Args:
        driver: Selenium WebDriver instance for browser automation.

    Returns:
        bool: True if the Export button is visible within 5 seconds, False if not found.
    """
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    return helper.element_exists(driver, export_xpath, timeout=5)


def configure_report_settings(driver, account_basis: str, report_setting_chk_options: list) -> None:
    """
    Configure report settings by opening the 'More' panel, setting the accounting basis,
    and enabling any specified checkbox options.

    Opens the settings panel by clicking 'More', then optionally selects the accounting
    basis (Cash or Accrual), then iterates over report_setting_chk_options and clicks each
    checkbox that is not already checked.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        account_basis (str): Accounting basis to select — "Cash" or "Accrual".
            Pass None or empty string to skip.
        report_setting_chk_options (list[str]): Labels of checkbox options to enable
            (e.g., ["Percentage of Income", "Year to Date"]).
            Each item is matched against the button label; the checkbox inside is clicked
            only if it is not already checked. Pass None or empty list to skip.

    Returns:
        None

    Raises:
        TimeoutException: If the 'More' button, accounting basis option, or any checkbox
            button cannot be located within 5 seconds.
    """
    if not account_basis and not report_setting_chk_options:
        logger.info("No account basis or checkbox options specified — skipping report settings configuration")
        return

    more_option_xpath = "//button[normalize-space()='More']"

    helper.click_element(driver, more_option_xpath, timeout=5)

    if account_basis:
        basis_option_xpath = f"//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='{account_basis}']]"
        helper.click_element(driver, basis_option_xpath, timeout=5)

    for item in (report_setting_chk_options or []):
        checkbox_xpath = f"//button[normalize-space()='{item}']//input[@type='checkbox']"
        logger.info(f"Checking option '{item}'...")
        checkbox = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, checkbox_xpath)),
        )
        if not checkbox.is_selected():
            checkbox.click()
            logger.info(f"Option '{item}' checkbox enabled")
        else:
            logger.info(f"Option '{item}' checkbox already checked — skipping")



def click_custom_report_link(driver, custom_report_name: str) -> None:
    """
    Click the saved report link matching custom_report_name.

    Locates a span element whose normalised text matches custom_report_name and clicks it
    to open the saved Profit and Loss report as the starting point for further configuration.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        custom_report_name (str): Exact display text of the saved report link to click
            (e.g., "Profit and Loss [Munro's]").

    Returns:
        None

    Raises:
        TimeoutException: If the link is not found within 10 seconds.
    """
    literal = helper.format_xpath_selector_text(custom_report_name)
    xpath = f"//span[contains(normalize-space(), {literal})]"
    helper.click_element(driver, xpath)


def configure_compare_with(driver, compare_with: str, number_of_periods: int) -> None:
    """
    Select a comparison period from the Compare With dropdown and set the number of periods.

    Clicks the Compare With dropdown button, selects the period type (Month, Quarter, or Year),
    then clicks "Enter a different number" to open the modal, types the desired number of periods,
    and confirms by clicking Select.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        compare_with (str): The comparison period type to select — one of "Month", "Quarter", or "Year".
        number_of_periods (int): The number of comparison periods to enter in the modal input.

    Returns:
        None

    Raises:
        TimeoutException: If any element cannot be located or clicked within 10 seconds.
    """
    dropdown_xpath = "//button[@id='report-settings-comparison-period-button']"
    option_xpath = f"//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='{compare_with}']]"
    enter_different_number_xpath = "//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='Enter a different number']]"
    modal_input_xpath = "//section[@role='dialog']//input[contains(@class,'xui-textinput--input')]"
    select_button_xpath = "//section[@role='dialog']//button[normalize-space()='Select']"

    if not helper.element_exists(driver, dropdown_xpath):
        logger.info("Compare With dropdown not found on page — skipping")
        return

    helper.click_element(driver, dropdown_xpath)
    helper.click_element(driver, option_xpath)
    helper.click_element(driver, enter_different_number_xpath)

    helper.type_into_element(driver, modal_input_xpath, number_of_periods)
    helper.click_element(driver, select_button_xpath)
    logger.info(f"Compare With configured: '{compare_with}' x {number_of_periods} period(s)")
