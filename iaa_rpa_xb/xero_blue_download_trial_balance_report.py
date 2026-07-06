from __future__ import annotations

import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file
from .take_screenshot import take_screenshot

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_trial_balance_report(
    browser,
    xero_client_name,
    xero_end_date,
    xero_financial_year,
    is_add_gst_column,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Download Trial Balance report from Xero Blue with customizable settings.

    This function orchestrates the complete workflow to download a Trial Balance report
    from Xero, including configuring report settings (accounting basis, date range, GST columns),
    generating the report, and exporting it as an Excel file to a specified directory.

    Args:
        browser: Browser instance containing the Selenium WebDriver with an active Xero session.
        xero_client_name (str): Name of the Xero client/organization for logging purposes.
        xero_end_date (str): End date for the report in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty, defaults to financial year end (30 Jun of xero_financial_year).
        xero_financial_year (str): Financial year for the report (e.g., "2024").
            Used as fallback when xero_end_date is not provided.
        is_add_gst_column (bool): Flag to include GST/Tax column in the report.
            True adds "Outstanding GST" column, False excludes it.
        window_title (str): Title of the browser window, used to locate the save dialog.
        download_directory (str): Absolute path to the directory where the Excel file will be saved.
        report_file_name (str): Desired filename for the downloaded report including .xlsx extension.
        extension (str): File extension used when saving the downloaded report (e.g., ".xlsx").

    Returns:
        None: The function saves the report file to disk and logs the operation status.

    Raises:
        Exception: If any step in the download workflow fails (element not found, timeout,
            no data available, file save error, etc.). All exceptions are logged with
            detailed error information before being re-raised.

    Example:
        >>> xero_blue_download_trial_balance_report(
        ...     browser=my_browser,
        ...     xero_client_name="ABC Company",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     is_add_gst_column=True,
        ...     window_title="Trial Balance - Xero",
        ...     download_directory="C:/Reports",
        ...     report_file_name="trial_balance_2024.xlsx",
        ...     extension=".xlsx"
        ... )
    """
    start_time = datetime.now()

    logger.info("=" * 80)
    logger.info("STARTING: Xero Blue Download Trial Balance Report")
    logger.info(f"Start Time        : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name       : {xero_client_name}")
    logger.info(
        f"End Date          : {xero_end_date if xero_end_date else 'Using Financial Year Default'}",
    )
    logger.info(f"Financial Year    : {xero_financial_year}")
    logger.info(f"GST Column        : {'Enabled' if is_add_gst_column else 'Disabled'}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report File Name  : {report_file_name}")
    logger.info("=" * 80)

    try:
        driver = browser.driver

        # STEP 1: Configure Cash Accounting Basis
        # Purpose: Set the report to use Cash accounting method before applying date filters
        # Function: configure_cash_accounting_basis(driver)
        # - Clicks 'More' button to expand accounting basis options
        # - Selects 'Cash' option from the dropdown menu
        logger.info("STEP 1: Configuring Cash accounting basis...")
        configure_cash_accounting_basis(driver)

        # STEP 2: Set Report Date Range and GST Column Settings
        # Purpose: Enter the report end date and optionally add the Outstanding GST column
        # Function: configure_report_date_and_gst_settings(driver, xero_end_date, xero_financial_year, is_add_gst_column)
        # - Resolves end date (custom date or financial year default)
        # - Clears existing date and enters the resolved end date
        # - Conditionally opens columns menu and enables Outstanding GST column
        logger.info("STEP 2: Configuring report date range and GST column settings...")
        configure_report_date_and_gst_settings(
            driver,
            xero_end_date,
            xero_financial_year,
            is_add_gst_column,
        )

        # STEP 3: Generate Report and Export to Excel
        # Purpose: Trigger report generation, verify data exists, export as Excel, and save the file
        # Function: generate_and_export_report(driver, window_title, download_directory, report_file_name, extension)
        # - Clicks Update button to generate the report with configured settings
        # - Waits for report title to confirm rendering is complete
        # - Takes a screenshot of the generated report for audit trail
        # - Verifies Export button is present (confirms report has data)
        # - Clicks Export and selects Excel format
        # - Handles the file save dialog to save the report to the specified directory
        logger.info("STEP 3: Generating report and exporting to Excel...")
        screenshot_file_path = generate_and_export_report(
            driver,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("COMPLETED: Xero Blue Download Trial Balance Report")
        logger.info(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {xero_client_name}")
        logger.info(f"Report File Name  : {report_file_name}")
        logger.info(f"Screenshot Path   : {screenshot_file_path}")
        logger.info(f"Status            : SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error("FAILED: Xero Blue Download Trial Balance Report")
        logger.error(f"End Time          : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration          : {duration:.2f} seconds")
        logger.error(f"Client Name       : {xero_client_name}")
        logger.error(f"Report File Name  : {report_file_name}")
        logger.error(f"Error             : {e}")
        logger.error(f"Status            : FAILED")
        logger.error("=" * 80)
        logger.error("xero_blue_download_trial_balance_report failed", exc_info=True)
        raise


def resolve_report_end_date(xero_end_date, xero_financial_year):
    """
    Determine and format the end date for the Trial Balance report.

    Decides which date to use based on whether a custom end date is provided.
    If no custom date is given, defaults to the financial year end date (30 June).

    Args:
        xero_end_date (str): Custom end date in format "DD Mon YYYY" (e.g., "30 Jun 2024").
            If None or empty string, the function will use the financial year default.
        xero_financial_year (str): Financial year (e.g., "2024") used to construct
            the default end date when xero_end_date is not provided.

    Returns:
        str: Formatted end date string in "DD Mon YYYY" format (e.g., "30 Jun 2024").

    Example:
        >>> resolve_report_end_date(None, "2024")
        "30 Jun 2024"
        >>> resolve_report_end_date("15 Mar 2024", "2024")
        "15 Mar 2024"
    """
    if not xero_end_date:
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(
            f"No custom end date provided. Using financial year default: {str_end_date}",
        )
    else:
        str_end_date = xero_end_date
        logger.info(f"Using provided end date: {str_end_date}")

    return str_end_date


def configure_report_date_and_gst_settings(
    driver,
    xero_end_date,
    xero_financial_year,
    is_add_gst_column,
):
    """
    Configure the report date range and GST column visibility settings.

    Sets the end date for the Trial Balance report by interacting with the date input
    field on the Xero report settings page, then conditionally configures the
    Outstanding GST column based on user preference.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        xero_end_date (str): Custom end date in format "DD Mon YYYY", or None to use default.
        xero_financial_year (str): Financial year used as fallback for the default end date.
        is_add_gst_column (bool): Whether to add the Outstanding GST column to the report.

    Returns:
        None: Modifies report date and column settings in the Xero UI.

    Raises:
        TimeoutException: If the date input field cannot be located within 10 seconds.
    """
    to_date = (By.ID, "report-settings-custom-date-input-to")

    # Resolve the appropriate end date (custom or financial year default)
    str_end_date = resolve_report_end_date(xero_end_date, xero_financial_year)

    logger.info(f"Entering end date '{str_end_date}' into the report date field...")

    # Clear existing date value and enter the resolved end date
    elem = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(to_date))
    elem.send_keys("\ue009" + "a")  # CTRL + A to select all
    elem.send_keys("\ue003")  # DELETE to clear the field
    elem.send_keys(str_end_date)
    elem.send_keys("\ue004")  # TAB to confirm the entry
    logger.info(f"End date '{str_end_date}' entered and confirmed in the date field")

    # Configure GST column visibility based on user preference
    configure_gst_column_visibility(driver, is_add_gst_column)


def configure_gst_column_visibility(driver, is_add_gst_column):
    """
    Configure the Outstanding GST column visibility in the Trial Balance report.

    Conditionally adds the 'Outstanding GST' column to the Trial Balance report based
    on the is_add_gst_column flag. If enabled, opens the columns settings dropdown,
    selects the 'Outstanding GST' checkbox option, and closes the menu to apply changes.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        is_add_gst_column (bool): Flag controlling GST column inclusion.
            If True, opens the columns menu and selects 'Outstanding GST'.
            If False, skips GST configuration entirely.

    Returns:
        None: Modifies the report column settings in the Xero UI.

    Raises:
        TimeoutException: If the columns button or 'Outstanding GST' option cannot be
            located within 5 seconds when is_add_gst_column is True.
    """
    gst_button_xpath = "//*[@id='report-settings-columns-button']"
    outstanding_gst_xpath = "//span[contains(@class,'xui-pickitem-multiselect--label')][.//span[normalize-space()='Outstanding GST']]"

    if is_add_gst_column:
        logger.info("GST column addition requested - opening columns menu...")

        # Open the columns dropdown menu to access column options
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button_xpath)),
        ).click()
        logger.info("Columns dropdown menu opened successfully")

        # Select the 'Outstanding GST' checkbox option from the menu
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, outstanding_gst_xpath)),
        ).click()
        logger.info("'Outstanding GST' option selected from columns menu")

        # Close the columns dropdown to apply the selection
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button_xpath)),
        ).click()
        logger.info("Columns menu closed - Outstanding GST column added successfully")
    else:
        logger.info("GST column not requested - skipping GST column configuration")


def generate_and_export_report(
    driver,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Generate the Trial Balance report and export it to Excel format.

    Triggers report generation by clicking the Update button, verifies that data is
    available for export, initiates the export process, selects Excel as the export
    format, and handles the file save dialog to save the report to the specified location.

    Args:
        driver: Selenium WebDriver instance for browser automation.
        window_title (str): Title of the browser window used to locate the save dialog.
        download_directory (str): Absolute path to the directory where the file will be saved.
        report_file_name (str): Filename for the downloaded report including .xlsx extension.
        extension (str): File extension used when saving the downloaded report (e.g., ".xlsx").

    Returns:
        str: File path of the screenshot taken after the report was generated.

    Raises:
        Exception: If the Update button is not clickable, the Export button is not available
            (indicating no data), or any step in the export/save process fails.
    """
    update_xpath = (
        By.XPATH,
        "//button[@type='button' and normalize-space(text())='Update']",
    )
    export_xpath = (
        By.XPATH,
        "//button[@type='button' and normalize-space(text())='Export']",
    )
    excel_xpath = (
        By.XPATH,
        "//button[@type='button']//span[normalize-space(text())='Excel']",
    )
    report_title_xpath = "//input[@placeholder='Report title']"

    # Click Update button to generate the report with current settings
    logger.info("Clicking Update button to generate the Trial Balance report...")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(update_xpath)).click()
    logger.info("Update button clicked - waiting for report to finish rendering...")

    # Wait for the report title input to appear, confirming the report has loaded
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, report_title_xpath)),
    )
    logger.info("Report rendered successfully - report title is visible")

    # Capture a screenshot of the generated report for audit trail
    logger.info("Taking screenshot of the generated report...")
    screenshot_file_path = take_screenshot(driver)
    logger.info(f"Screenshot saved: {screenshot_file_path}")

    # Verify Export button is present to confirm the report contains data
    logger.info("Checking if Export button is available (confirms report has data)...")
    if not is_export_button_available(driver):
        logger.warning(
            "Export button not found - no Trial Balance data available for this client",
        )
        raise Exception("No Trial Balance data available for this client.")

    # Click Export button to open the export format options
    logger.info("Clicking Export button to open export format options...")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(export_xpath)).click()
    logger.info("Export options menu opened")

    # Select Excel format from the export options
    logger.info("Selecting Excel format from export options...")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(excel_xpath)).click()
    logger.info("Excel format selected - file download initiated")

    # Wait briefly for the save dialog to appear before interacting with it
    time.sleep(3)

    # Handle the file save dialog and save the report to the specified directory
    logger.info(
        f"Handling file save dialog - saving report to: {download_directory}",
    )
    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    logger.info(
        f"Report saved successfully as '{report_file_name}' in '{download_directory}'",
    )

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

    Raises:
        None: TimeoutException is caught internally and returns False.
    """
    try:
        export_xpath = (
            By.XPATH,
            "//button[@type='button' and normalize-space(text())='Export']",
        )
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located(export_xpath))
        logger.info(
            "Export button found - report contains data and is ready for export",
        )
        return True

    except TimeoutException:
        logger.warning(
            "Export button not found within timeout - report may contain no data",
        )
        return False


def configure_cash_accounting_basis(driver):
    """
    Set the Trial Balance report to use Cash accounting basis.

    Opens the accounting basis dropdown by clicking the 'More' options button,
    then selects 'Cash' from the available accounting methods. This must be done
    before setting the date range or generating the report.

    Args:
        driver: Selenium WebDriver instance for browser automation.

    Returns:
        None: Modifies the accounting basis setting in the Xero report UI.

    Raises:
        TimeoutException: If the 'More' button or 'Cash' option cannot be located
            within 5 seconds.
    """
    more_option_xpath = "//button[normalize-space()='More']"
    cash_option_xpath = "//button[contains(@class,'xui-pickitem--body')][.//span[normalize-space()='Cash']]"

    # Click 'More' button to expand the accounting basis options dropdown
    logger.info("Clicking 'More' button to expand accounting basis options...")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, more_option_xpath)),
    ).click()
    logger.info("Accounting basis options expanded")

    # Select 'Cash' accounting basis from the dropdown menu
    logger.info("Selecting 'Cash' accounting basis...")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, cash_option_xpath)),
    ).click()
    logger.info("Cash accounting basis selected successfully")
