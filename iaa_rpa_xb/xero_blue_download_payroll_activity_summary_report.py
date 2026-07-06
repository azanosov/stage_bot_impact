from __future__ import annotations

import os
import time
from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from iaa_rpa_xero_blue.download_file import download_file
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_payroll_activity_summary_report(
    browser,
    xero_client_name: str,
    xero_end_date: str,
    xero_financial_year: str,
    xero_start_date: str,
    window_title: str,
    download_directory_path: str,
    xero_report_file_name: str,
    xero_blue_report_name: str,
    xero_blue_module_name: str,
    extension: str,
):
    """
    Download the Payroll Activity Summary report from Xero Blue for a specific client with payroll data.

    This function automates the complete workflow for downloading Payroll Activity Summary reports
    from Xero Blue. It configures the report with custom date ranges (or defaults to financial year
    dates), validates that payroll data exists for the client, updates and exports the report as an
    Excel file, and handles the Windows Save As dialog to save the file with a specified name to a
    designated directory. The function provides comprehensive logging with banners, timestamps,
    module identification, duration tracking, and success/failure status.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be already logged into Xero Blue and navigated to the Payroll Activity Summary report page.
        xero_client_name (str): Name of the Xero client organization for logging purposes.
                               Example: "ABC Company Pty Ltd"
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If not provided or empty, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default date range (1 Jul previous year - 30 Jun this year).
                                   Example: "2024" represents FY 2023-2024
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              If not provided or empty, defaults to "1 Jul {int(xero_financial_year) - 1}".
        window_title (str): Partial window title used to locate the Chrome browser window
                            for Windows Save As dialog automation.
        download_directory_path (str): Absolute path to the directory where the Excel file should be saved.
                                 Example: "C:\\Reports\\Xero\\Payroll"
        xero_report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                               Example: "ABC_Company_Payroll_Activity_Summary_2024"
                               The extension will be appended automatically.
        xero_blue_report_name (str): Display name of the report used for logging.
                                     Example: "Payroll Activity Summary"
        xero_blue_module_name (str): Module name identifier used for structured logging.
                                     Example: "XeroBlue.PayrollReports"
        extension (str): File extension for the downloaded report (e.g., ".xlsx").

    Returns:
        None: The function completes successfully or raises an exception.
              Success is logged with process completion details and timing information.

    Raises:
        Exception: If any step in the download process fails, including:
                  - No payroll data exists for the client (Export button not visible after Update)
                  - Selenium WebDriverWait timeouts (element not found or not clickable)
                  - Windows automation failures (Save As dialog not found or controls unavailable)
                  - File system errors (invalid path, permission issues)
                  All exceptions are logged with full stack traces (exc_info=True) before being re-raised.

    Notes:
        - This function assumes the browser is already positioned on the Payroll Activity Summary report page.
        - Payroll Activity Summary is a payroll report; clients without payroll setup will fail with "no payroll data" error.
        - The report requires both start and end dates to define the reporting period.
        - If xero_start_date or xero_end_date are not provided, defaults to full financial year date range.
        - The function uses explicit waits (5 seconds) for all element interactions.
        - Comprehensive logging captures start/end times, module name, client name, duration, and success/failure status.
        - The Windows Save As dialog is handled using robocorp.windows automation library.
        - File overwrite confirmation is automatically handled if the file already exists.
        - Export button visibility check validates that payroll data exists before attempting download.

    Example:
        >>> from RPA.Browser.Selenium import Selenium
        >>> browser = Selenium()
        >>> browser.open_available_browser("https://go.xero.com")
        >>> # ... login and navigation code ...
        >>> xero_blue_download_payroll_activity_summary_report(
        ...     browser=browser,
        ...     xero_client_name="ABC Company Pty Ltd",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jul 2023",
        ...     window_title="Payroll Activity Summary",
        ...     download_directory_path="C:\\Reports\\Xero",
        ...     xero_report_file_name="ABC_Payroll_Activity_2024",
        ...     xero_blue_report_name="Payroll Activity Summary",
        ...     xero_blue_module_name="XeroBlue.PayrollReports",
        ...     extension=".xlsx"
        ... )
    """

    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Payroll Activity Summary Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Module: {xero_blue_module_name}")
    logger.info(f"Client: {xero_client_name}")
    logger.info(f"Report: {xero_blue_report_name}")
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Start Date: {xero_start_date}")
    logger.info(f"End Date: {xero_end_date}")
    logger.info(f"Download Directory: {download_directory_path}")
    logger.info(f"Output File Name: {xero_report_file_name}{extension}")
    logger.info("=" * 80)

    try:
        # ─────────────────────────────────────────────────────────────────────
        # STEP 1: Extract Selenium WebDriver
        # Purpose: Retrieve the underlying WebDriver from the browser object
        #          for direct element interactions and explicit waits
        # ─────────────────────────────────────────────────────────────────────
        driver = browser.driver
        logger.info("STEP 1: Extracted Selenium WebDriver from browser object")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2: Configure Report Date Range
        # Purpose: Populate the From and To date fields on the Payroll Activity
        #          Summary report page using custom dates or financial year defaults
        # Function: enter_report_date_range(driver, xero_end_date, xero_financial_year, xero_start_date)
        # - Resolves start/end dates (custom provided or FY default)
        # - Clears and types into the From date input field
        # - Clears and types into the To date input field
        # - Presses TAB after each entry to apply the value
        # ─────────────────────────────────────────────────────────────────────
        logger.info("STEP 2: Configuring report date range")
        enter_report_date_range(
            driver,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
        )

        # ─────────────────────────────────────────────────────────────────────
        # STEP 3: Update Report and Export to Excel
        # Purpose: Refresh the report with the configured date range, validate
        #          that payroll data exists, export as Excel, and save the file
        #          via the Windows Save As dialog
        # Function: update_report_and_export_to_excel(driver, window_title, download_directory_path, xero_report_file_name, extension)
        # - Clicks the Update button to refresh the report with the date range
        # - Checks Export button visibility to confirm payroll data exists
        # - Clicks Export then selects Excel format to trigger download
        # - Handles Windows Save As dialog to save the file to the target directory
        # - Automatically confirms file overwrite if the file already exists
        # ─────────────────────────────────────────────────────────────────────
        logger.info("STEP 3: Updating report and exporting to Excel")
        update_report_and_export_to_excel(
            driver,
            window_title,
            download_directory_path,
            xero_report_file_name,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Download Payroll Activity Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Module: {xero_blue_module_name}")
        logger.info(f"Client: {xero_client_name}")
        logger.info(f"Report: {xero_blue_report_name}")
        logger.info(f"Saved As: {xero_report_file_name}{extension}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Payroll Activity Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Module: {xero_blue_module_name}")
        logger.error(f"Client: {xero_client_name}")
        logger.error(f"Report: {xero_blue_report_name}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("=" * 80)
        raise


def resolve_report_date_range(xero_end_date, xero_financial_year, xero_start_date):
    """
    Resolve the start and end dates for the Payroll Activity Summary report period.

    Evaluates whether custom start and end dates have been provided. If either date is
    missing or empty, calculates default dates based on the Australian financial year
    convention — FY 2024 runs from 1 Jul 2023 to 30 Jun 2024.

    Args:
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            Can be empty/None to use the default financial year end date.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Example: "2024" represents FY 2023-2024.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              Can be empty/None to use the default financial year start date.

    Returns:
        tuple: A tuple containing two strings (start_date, end_date):
               - start_date (str): The resolved start date in "d MMM yyyy" format.
               - end_date (str): The resolved end date in "d MMM yyyy" format.

    Notes:
        - If either date is missing, both dates default to the full financial year range.
        - Default financial year dates follow Australian convention: 1 Jul (year-1) to 30 Jun (year).
        - Logs whether the "default financial year range" or "provided date range" is being used.

    Example:
        >>> resolve_report_date_range("", "2024", "")
        ('1 Jul 2023', '30 Jun 2024')
        >>> resolve_report_date_range("31 Dec 2023", "2024", "1 Jan 2023")
        ('1 Jan 2023', '31 Dec 2023')
    """
    if not xero_end_date or not xero_start_date:
        logger.info("Date range not provided — using default financial year range")
        start_date = f"1 Jul {int(xero_financial_year) - 1}"
        end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"Default date range resolved: {start_date} to {end_date}")
    else:
        logger.info("Using provided custom date range")
        start_date = xero_start_date
        end_date = xero_end_date
        logger.info(f"Custom date range: {start_date} to {end_date}")

    return start_date, end_date


def enter_report_date_range(
    driver,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
):
    """
    Populate the From and To date fields on the Payroll Activity Summary report page.

    Resolves the appropriate start and end dates (either provided or default financial year
    dates), locates the From and To date input fields on the Xero report page, and populates
    them using keyboard automation with CTRL+A, DELETE, and TAB key sequences.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must be on the Payroll Activity Summary report page with date input fields visible.
        xero_end_date (str): End date for the report in "d MMM yyyy" format.
                            If not provided or empty, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default dates if custom dates not provided.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format.
                              If not provided or empty, defaults to "1 Jul {int(xero_financial_year) - 1}".

    Returns:
        None: The function completes when both date fields have been populated.

    Raises:
        TimeoutException: If date input fields are not found or not visible within 5 seconds.
        Exception: If any step in date entry fails.

    Notes:
        - Uses WebDriverWait with 5-second timeout for element interactions.
        - From date field ID: "report-settings-custom-date-input-from"
        - To date field ID: "report-settings-custom-date-input-to"
        - Uses Unicode escape sequences: \\ue009 (CTRL), \\ue003 (DELETE), \\ue004 (TAB).
        - Date format must be "d MMM yyyy" (e.g., "1 Jul 2023", not "01/07/2023").
        - TAB key press after each date entry triggers the field to apply the entered value.

    Example:
        >>> enter_report_date_range(driver, "30 Jun 2024", "2024", "1 Jul 2023")
        # Populates From field with "1 Jul 2023" and To field with "30 Jun 2024"
    """

    from_date_id = "report-settings-custom-date-input-from"
    to_date_id = "report-settings-custom-date-input-to"

    # Resolve start and end dates — returns custom dates or FY defaults
    start_date, end_date = resolve_report_date_range(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )

    logger.info(f"Entering From date: {start_date}")

    # Wait for the From date input field to become visible on the report page
    from_date_field = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, from_date_id)),
    )

    # Select all existing text in the From date field and delete it
    from_date_field.send_keys("\ue009" + "a")  # CTRL + A
    from_date_field.send_keys("\ue003")  # DELETE

    # Type the resolved start date and press TAB to apply the value
    from_date_field.send_keys(start_date)
    from_date_field.send_keys("\ue004")  # TAB
    logger.info(f"From date entered: {start_date}")

    logger.info(f"Entering To date: {end_date}")

    # Wait for the To date input field to become visible on the report page
    to_date_field = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, to_date_id)),
    )

    # Select all existing text in the To date field and delete it
    to_date_field.send_keys("\ue009" + "a")  # CTRL + A
    to_date_field.send_keys("\ue003")  # DELETE

    # Type the resolved end date and press TAB to apply the value
    to_date_field.send_keys(end_date)
    to_date_field.send_keys("\ue004")  # TAB
    logger.info(f"To date entered: {end_date}")

    logger.info(f"Report date range configured: {start_date} to {end_date}")


def update_report_and_export_to_excel(
    driver,
    window_title,
    download_directory_path,
    xero_report_file_name,
    extension,
):
    """
    Update the Payroll Activity Summary report, validate payroll data, export to Excel, and save the file.

    Performs the final steps of the Payroll Activity Summary download workflow:
    (1) clicks the Update button to refresh the report with the configured date range,
    (2) validates that payroll data exists by checking if the Export button is visible,
    (3) clicks Export then Excel to initiate the download, and (4) automates the Windows
    Save As dialog to save the file with the specified filename and location. File overwrite
    confirmation is automatically handled if the file already exists.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must have the Payroll Activity Summary report configured with the date range.
        window_title (str): Partial window title used to locate the Chrome browser window
                            for Windows Save As dialog automation.
        download_directory_path (str): Absolute path to the directory where the Excel file will be saved.
                                 Example: "C:\\Reports\\Xero\\Payroll"
        xero_report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                               Example: "ABC_Company_Payroll_Activity_Summary_2024"
        extension (str): File extension to append to the filename (e.g., ".xlsx").

    Returns:
        None: The function completes when the file is saved successfully.

    Raises:
        Exception: If no payroll data is available for the client — raised when the Export
                  button is not visible after clicking Update.
        TimeoutException: If Update, Export, or Excel buttons are not found or not clickable within 5 seconds.
        Exception: If Windows Save As dialog handling fails or the file save operation fails.
                  All exceptions are propagated to the calling function.

    Notes:
        - Uses WebDriverWait with 5-second timeout for button interactions.
        - Update button XPath: "//button[@type='button' and normalize-space(text())='Update']"
        - Export button XPath: "//button[@type='button' and normalize-space(text())='Export']"
        - Excel button XPath: "//button[@type='button']//span[normalize-space(text())='Excel']"
        - Export button visibility is checked via is_export_button_visible() with a 5-second timeout.
        - If Export button not visible, raises Exception: "There is no payroll data for this client."
        - Uses robocorp.windows library for Windows Save As dialog automation.
        - File overwrite confirmation is automatically handled if the file already exists.

    Example:
        >>> update_report_and_export_to_excel(driver, "Payroll Activity Summary", "C:\\Reports", "Payroll_Activity_2024", ".xlsx")
        # Updates report, validates payroll data, exports to Excel, and saves the file
    """

    update_xpath = "//button[@type='button' and normalize-space(text())='Update']"
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    excel_xpath = "//button[@type='button']//span[normalize-space(text())='Excel']"

    # Click the Update button to refresh the report with the configured date range
    logger.info("Clicking Update button to refresh the Payroll Activity Summary report")
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, update_xpath)),
    ).click()
    logger.info("Update button clicked — report is refreshing")

    # Validate payroll data exists by checking if the Export button becomes visible
    # If no payroll data exists for this client, the Export button will not appear
    logger.info("Validating payroll data exists — checking Export button visibility")
    if not is_export_button_visible(driver):
        logger.warning(
            "Export button not visible — no payroll data found for this client",
        )
        raise Exception("There is no payroll data for this client.")
    logger.info("Export button visible — payroll data confirmed")

    # Click the Export button to open the export format options menu
    logger.info("Clicking Export button to open export format options")
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, export_xpath)),
    ).click()
    logger.info("Export button clicked — format menu opened")

    # Click Excel to initiate the file download and trigger the Windows Save As dialog
    logger.info("Clicking Excel option to initiate download")
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, excel_xpath)),
    ).click()
    logger.info("Excel option clicked — waiting for Save As dialog to appear")

    # Wait for the Windows Save As dialog to open before proceeding
    time.sleep(3)
    logger.info("Save As dialog wait complete — proceeding with file save automation")

    # Automate the Windows Save As dialog to set the file path and save the file
    file_path = os.path.join(download_directory_path, xero_report_file_name + extension)
    download_file(
        window_title,
        download_directory_path,
        xero_report_file_name,
        extension,
    )
    logger.info(f"File successfully saved to: {file_path}")


def is_export_button_visible(driver) -> bool:
    """
    Check whether the Export button is visible on the Payroll Activity Summary report page.

    Serves as a validation check to determine whether the report contains payroll data.
    After clicking the Update button, Xero only displays the Export button if payroll data
    is available. If the Export button does not appear within 5 seconds, it indicates the
    client has no payroll setup or no payroll activity for the specified date range.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must have just clicked the Update button on the Payroll Activity Summary report page.

    Returns:
        bool: True if the Export button is visible (payroll data exists).
              False if the Export button does not appear within 5 seconds (no payroll data).

    Notes:
        - Uses WebDriverWait with a 5-second timeout to check for Export button visibility.
        - Export button XPath: "//button[@type='button' and normalize-space(text())='Export']"
        - A TimeoutException (caught internally) indicates no Export button, thus no payroll data.
        - The calling function is responsible for logging the outcome and raising an exception if needed.

    Example:
        >>> if is_export_button_visible(driver):
        ...     # Proceed with export workflow
        ... else:
        ...     raise Exception("There is no payroll data for this client.")
    """
    try:
        export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, export_xpath)),
        )
        return True
    except Exception:
        return False
