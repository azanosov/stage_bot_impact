from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_aged_payables_details_report(
    browser,
    xero_client_name,
    xero_end_date,
    xero_financial_year,
    is_add_gst_column,
    xero_aging_by,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Download aged payables detail report from Xero Blue.

    This function orchestrates the complete process of downloading an aged payables
    detail report, including setting date parameters, configuring aging options,
    optionally adding GST columns, and exporting to Excel format.

    Args:
        browser: Selenium browser instance with active Xero session
        xero_client_name (str): Name of the Xero client
        xero_end_date (str): End date for the report (format: 'DD MMM YYYY').
                                 If empty, defaults to '30 Jun {financial_year}'
        xero_financial_year (str): Financial year (e.g., '2024')
        is_add_gst_column (bool): Whether to include GST column in the report
        xero_aging_by (str): Aging method - either 'Due date' or 'Invoice date'
        download_directory (str): Local directory path for saving the report
        report_file_name (str): Desired filename for the downloaded report
        xero_report_name (str): Display name of the report in Xero

    Returns:
        None. Logs success or failure information.

    Raises:
        Exception: Any errors during report download are caught, logged, and function returns
    """
    # Initialize process timing and logging
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("XERO BLUE DOWNLOAD AGED PAYABLES DETAIL REPORT PROCESS STARTED")
    logger.info("=" * 80)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client name: {xero_client_name}")
    logger.info(
        f"End Date: {xero_end_date if xero_end_date else f'30 Jun {xero_financial_year}'}",
    )
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Add GST Column: {is_add_gst_column}")
    logger.info(f"Aging By: {xero_aging_by}")
    logger.info(f"Xero report name: {report_file_name}")
    logger.info(f"File Download path: {download_directory}")
    logger.info("")

    try:
        # Prepare and set report dates, then configure report parameters
        # This function determines the appropriate end date (either provided or default financial year end)
        # and passes all configuration to the parameter setup process
        end_date_argument(
            browser,
            xero_end_date,
            xero_financial_year,
            is_add_gst_column,
            xero_aging_by,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

        # Log completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info("XERO BLUE DOWNLOAD AGED PAYABLES DETAIL REPORT PROCESS COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)
        logger.info("")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(
            "XERO BLUE DOWNLOAD AGED PAYABLES DETAIL REPORT PROCESS FAILED - EXCEPTION",
        )
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error("=" * 80)
        return


# --------------------------------------------------------------------
# Set Date and Parameters
# --------------------------------------------------------------------
def end_date_argument(
    browser,
    xero_end_date,
    xero_financial_year,
    is_add_gst_column,
    xero_aging_by,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Determine the appropriate end date for the report.

    This function checks if a custom end date is provided. If not, it defaults to
    the financial year end date (30 June of the specified year). The determined date
    is then passed to set_dates_and_parameters for report configuration.

    Args:
        browser: Selenium browser instance
        xero_end_date (str): User-provided end date or empty string
        xero_financial_year (str): Financial year for default date calculation
        is_add_gst_column (bool): GST column inclusion flag
        xero_aging_by (str): Aging calculation method
        download_directory (str): Download location
        report_file_name (str): Report filename
        xero_report_name (str): Report display name

    Returns:
        None
    """
    if not xero_end_date:
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"Using default End Date: {str_end_date}")
    else:
        str_end_date = xero_end_date
        logger.info(f"Using provided End Date: {str_end_date}")

    time.sleep(2)

    # Configure all report parameters including date, aging method, and GST column
    # This function interacts with Xero UI to set the end date, select aging calculation
    # method (Due date/Invoice date), and optionally add GST columns
    set_dates_and_parameters(
        browser,
        str_end_date,
        is_add_gst_column,
        xero_aging_by,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def set_dates_and_parameters(
    browser,
    str_end_date,
    is_add_gst_column,
    xero_aging_by,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Configure report date and aging parameters on the Xero report page.

    This function performs the following operations:
    1. Locates and clears the end date input field
    2. Enters the specified end date
    3. Opens the aging method dropdown
    4. Selects the aging calculation method (Due date or Invoice date)
    5. Proceeds to add GST column configuration

    Args:
        browser: Selenium browser instance
        str_end_date (str): Formatted end date string (e.g., '30 Jun 2024')
        is_add_gst_column (bool): Whether to add GST column
        xero_aging_by (str): 'Due date' or 'Invoice date'
        download_directory (str): Download destination path
        report_file_name (str): Report filename
        xero_report_name (str): Report display name

    Returns:
        None
    """
    driver = browser.driver
    custom_date_xpath = "//*[@id='report-settings-custom-date-input-to']"

    date_input = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, custom_date_xpath)),
    )

    date_input.send_keys("\ue009" + "a")  # CTRL + A
    date_input.send_keys("\ue003")  # DELETE
    date_input.send_keys(str_end_date)
    date_input.send_keys("\ue004")  # Tab

    logger.info("Entered End Date successfully.")

    # Click the aging method dropdown button to reveal options
    ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, ageing_button_xpath)),
    ).click()

    # Prepare XPath for the desired aging option (Due date or Invoice date)
    ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"

    # Verify the aging option exists in the dropdown before attempting to click
    # This prevents errors if the option is not available in the UI
    if is_due_date_or_invoice_exist(driver, ageing_option_xpath, xero_aging_by):

        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        ).click()

    # Proceed to GST column configuration and report export
    # This function will conditionally add the GST column if requested, then trigger the export process
    add_gst_column(
        browser,
        is_add_gst_column,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


# --------------------------------------------------------------------
# GST Column Selection
# --------------------------------------------------------------------
def add_gst_column(
    browser,
    is_add_gst_column,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Conditionally add the GST (Outstanding GST) column to the report.

    If is_add_gst_column is True, this function opens the columns menu,
    selects the 'Outstanding GST' option, and closes the menu. Regardless
    of the GST column setting, it then proceeds to export the report.

    Args:
        browser: Selenium browser instance
        is_add_gst_column (bool): Flag to determine if GST column should be added
        download_directory (str): Download destination path
        report_file_name (str): Report filename
        xero_report_name (str): Report display name

    Returns:
        None
    """
    driver = browser.driver
    gst_button = "//*[@id='report-settings-columns-button']"
    ouststanding_gst_xpath = "//span[contains(@class,'xui-pickitem-multiselect--label')][.//span[normalize-space()='Outstanding GST']]"

    if is_add_gst_column:
        # Open the columns dropdown menu
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()

        logger.info("Clicked column")

        # Select the 'Outstanding GST' checkbox option from the menu
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ouststanding_gst_xpath)),
        ).click()
        logger.info("Select outstanding GST")

        # Close the columns dropdown menu
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()

        logger.info("GST column added successfully.")

    # Trigger the report export process
    # This function updates the report with current settings, initiates the export,
    # and handles the Windows save dialog to download the file
    export_to_report(
        browser,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


# --------------------------------------------------------------------
# Export Report
# --------------------------------------------------------------------
def export_to_report(
    browser,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Export the configured Aged Payables Detail report to Excel format.

    This function performs the following steps:
    1. Clicks the 'Update' button to apply all report settings
    2. Clicks the 'Export' button to open export options
    3. Selects 'Excel' as the export format
    4. Triggers the Windows Save As dialog handler

    Args:
        browser: Selenium browser instance
        download_directory (str): Local directory path for saving the report
        report_file_name (str): Desired filename for the downloaded Excel file
        xero_report_name (str): Display name of the report in Xero (used for window identification)

    Returns:
        None
    """
    driver = browser.driver
    update_btn = "//button[@type='button' and normalize-space(text())='Update']"
    export_btn = "//button[@type='button' and normalize-space(text())='Export']"
    excel_btn = "//button[@type='button']//span[normalize-space(text())='Excel']"

    # Click 'Update' button to refresh the report with all configured parameters
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, update_btn)),
    ).click()

    logger.info("Clicked Update button")

    # Click 'Export' button to reveal export format options
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, export_btn)),
    ).click()
    logger.info("Clicked Export button")

    # Select 'Excel' format from the export options menu
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, excel_btn)),
    ).click()
    logger.info("Clicked Excel button")

    time.sleep(2)

    # Handle the Windows Save As dialog using robocorp windows automation
    # This function locates the save dialog, enters the full file path, and clicks Save

    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


# --------------------------------------------------------------------
# Aging Option Validation
# --------------------------------------------------------------------
def is_due_date_or_invoice_exist(
    driver,
    ageing_option_xpath,
    xero_aging_by,
) -> bool:
    """
    Verify if the specified aging option exists in the dropdown menu.

    This function checks whether the requested aging method (Due date or Invoice date)
    is available in the aging dropdown before attempting to select it. This prevents
    errors when the option is not present in the UI.

    Args:
        driver: Selenium WebDriver instance
        ageing_option_xpath (str): XPath selector for the aging option element
        xero_aging_by (str): The aging method being validated ('Due date' or 'Invoice date')

    Returns:
        bool: True if the aging option exists in the dropdown, False otherwise
    """
    try:
        # Wait for the aging option to be visible in the dropdown
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        )
        logger.info(f"{xero_aging_by} is exist in the drop down")
        return True

    except Exception:
        # Option not found in dropdown within timeout period
        logger.info(f"{xero_aging_by} does not exist in the drop down")
        return False
