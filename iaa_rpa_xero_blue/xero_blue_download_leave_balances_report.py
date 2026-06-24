from __future__ import annotations

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


def xero_blue_download_leave_balances_report(
    browser,
    xero_client_name: str,
    xero_end_date: str,
    xero_financial_year: str,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: str,
):
    """
    Download the Leave Balances report from Xero Blue for a specific client with payroll data.

    This function automates the complete workflow for downloading Leave Balances reports from
    Xero Blue. It configures the report with a custom end date (or defaults to financial year
    end), validates that payroll data exists for the client, updates and exports the report as
    an Excel file, and handles the Windows Save As dialog to save the file with a specified
    name to a designated directory.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be already logged into Xero Blue and navigated to the Leave Balances report page.
        xero_client_name (str): Name of the Xero client organization for logging purposes.
                               Example: "ABC Company Pty Ltd"
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If not provided or empty, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default end date if not provided.
                                   Example: "2024" represents FY 2023-2024.
        window_title (str): Browser window title fragment used for Windows Save As dialog detection.
                            Example: "Leave Balances"
        download_directory (str): Absolute path to the directory where the Excel file should be saved.
                                 Example: "C:\\Reports\\Xero\\LeaveBalances"
        report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                               Example: "ABC_Company_Leave_Balances_2024"
        extension (str): File extension for the downloaded report.
                        Example: ".xlsx"

    Returns:
        None: The function completes successfully or raises an exception.

    Raises:
        Exception: If any step in the download process fails, including:
                  - No payroll data exists for the client (Export button not visible after Update)
                  - Selenium WebDriverWait timeouts (element not found or not clickable)
                  - Windows automation failures (Save As dialog not found or controls unavailable)
                  - File system errors (invalid path, permission issues)
                  All exceptions are logged with full error details before being re-raised.

    Notes:
        - This function assumes the browser is already positioned on the Leave Balances report page.
        - Leave Balances is a payroll report; clients without payroll setup will raise an exception.
        - The report only uses an end date (no start date required).
        - If xero_end_date is not provided, defaults to "30 Jun {xero_financial_year}".

    Example:
        >>> from RPA.Browser.Selenium import Selenium
        >>> browser = Selenium()
        >>> browser.open_available_browser("https://go.xero.com")
        >>> xero_blue_download_leave_balances_report(
        ...     browser=browser,
        ...     xero_client_name="ABC Company Pty Ltd",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     window_title="Leave Balances",
        ...     download_directory="C:\\Reports\\Xero",
        ...     report_file_name="ABC_Leave_Balances_2024",
        ...     extension=".xlsx"
        ... )
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Leave Balances Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name       : {xero_client_name}")
    logger.info(f"Financial Year    : {xero_financial_year}")
    logger.info(f"End Date          : {xero_end_date}")
    logger.info(f"Window Title      : {window_title}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report File Name  : {report_file_name}")
    logger.info(f"Extension         : {extension}")
    logger.info("=" * 80)

    try:
        # Extract the Selenium WebDriver instance from the browser object
        driver = browser.driver

        # STEP 1: Configure Report Date Range
        # Purpose: Set the "As Of" end date for the Leave Balances report
        # Function: configure_report_date_range(driver, xero_end_date, xero_financial_year)
        # - Resolves the end date (custom date or default financial year end "30 Jun YYYY")
        # - Locates the "To" date input field on the report page
        # - Clears the existing date value and enters the resolved end date
        # - Presses TAB to apply the entered date to the report settings
        logger.info("STEP 1: Configuring report date range...")
        configure_report_date_range(driver, xero_end_date, xero_financial_year)
        logger.info("STEP 1 COMPLETED: Report date range configured successfully.")

        # STEP 2: Update Report and Export to Excel
        # Purpose: Refresh report with configured date, validate payroll data, and export to Excel
        # Function: update_report_and_export_to_excel(driver, window_title, download_directory, report_file_name, extension)
        # - Clicks the Update button to refresh the report with the configured end date
        # - Validates that the Export button is visible (confirms payroll data exists for client)
        # - Clicks Export button to open the export options menu
        # - Clicks Excel option to trigger the Windows Save As dialog
        # - Handles Windows Save As dialog: sets file path, selects file type, saves the file
        # - Handles file overwrite confirmation dialog if the file already exists
        logger.info("STEP 2: Updating report and exporting to Excel...")
        update_report_and_export_to_excel(
            driver,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )
        logger.info("STEP 2 COMPLETED: Report exported and file saved successfully.")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Download Leave Balances Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration          : {duration:.2f} seconds")
        logger.info(f"Client Name       : {xero_client_name}")
        logger.info(f"File Saved        : {report_file_name}{extension}")
        logger.info(f"Download Directory: {download_directory}")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Leave Balances Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration   : {duration:.2f} seconds")
        logger.error(f"Client Name: {xero_client_name}")
        logger.error(f"Error      : {e}")
        logger.error("=" * 80)
        raise


def resolve_report_end_date(xero_end_date: str, xero_financial_year: str) -> str:
    """
    Resolve the appropriate end date for the Leave Balances report.

    Evaluates whether a custom end date is provided. If not, returns the default
    end date of "30 Jun {xero_financial_year}", representing the last day of the
    Australian financial year. Leave Balances reports show employee leave balances
    as of a specific date (no start date required).

    Args:
        xero_end_date (str): End date in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            Can be empty/None to use the default financial year end date.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Example: "2024" represents FY 2023-2024.

    Returns:
        str: Resolved end date string in "d MMM yyyy" format.
             Either the provided custom date or "30 Jun {xero_financial_year}" as default.

    Notes:
        - Logs whether "Default Date range" or "InputFile Date range" is being used.
        - Default end date follows Australian financial year convention: 30 Jun (year).
        - Unlike other reports, Leave Balances only requires an end date (point-in-time snapshot).

    Example:
        >>> resolve_report_end_date("", "2024")
        "30 Jun 2024"
        >>> resolve_report_end_date("31 Dec 2024", "2024")
        "31 Dec 2024"
    """
    if not xero_end_date:
        logger.info(
            "No custom end date provided — using default financial year end date.",
        )
        return f"30 Jun {xero_financial_year}"
    else:
        logger.info(f"Custom end date provided from input file: {xero_end_date}")
        return xero_end_date


def configure_report_date_range(driver, xero_end_date: str, xero_financial_year: str):
    """
    Configure the end date for the Leave Balances report in Xero Blue.

    Determines the appropriate end date (either custom or default financial year end),
    locates the "To" date input field on the Xero report page, and populates it using
    keyboard automation. Leave Balances reports only require an end date field (no start date).

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must be on the Leave Balances report page with the date input field visible.
        xero_end_date (str): End date in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If empty/None, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate the default end date if not provided.

    Returns:
        None: The function completes when the date field is populated and applied.

    Raises:
        TimeoutException: If the date input field is not found or not visible within 10 seconds.
        Exception: If any step in the date entry process fails.

    Notes:
        - Uses WebDriverWait with 10-second timeout for element interaction.
        - Date field ID: "report-settings-custom-date-input-to" (Xero Blue interface selector).
        - Uses Unicode key sequences: \\ue009 (CTRL), \\ue003 (DELETE), \\ue004 (TAB).
        - Date format must be "d MMM yyyy" (e.g., "30 Jun 2024", not "30/06/2024").
        - TAB key press triggers the date field to apply and validate the entered date.

    Example:
        >>> configure_report_date_range(driver, "30 Jun 2024", "2024")
        # Populates "To" date field with "30 Jun 2024"
    """
    date_range_id = "report-settings-custom-date-input-to"

    # Resolve the end date: use custom date from input file or default to financial year end
    xero_end_date = resolve_report_end_date(xero_end_date, xero_financial_year)
    logger.info(f"Resolved end date for report: {xero_end_date}")

    # Wait for the "To" date input field to become visible on the report settings panel
    logger.info(
        f"Waiting for 'To' date input field to become visible (ID: {date_range_id})...",
    )
    date_field = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, date_range_id)),
    )
    logger.info("'To' date input field is visible.")

    # Select all existing text in the date field using CTRL+A
    logger.info("Clearing existing date value from 'To' date field...")
    date_field.send_keys("\ue009" + "a")  # CTRL + A to select all

    # Delete the selected text to fully clear the field
    date_field.send_keys("\ue003")  # DELETE to remove selected text

    # Type the resolved end date into the now-empty field
    logger.info(f"Entering end date: {xero_end_date}")
    date_field.send_keys(xero_end_date)

    # Press TAB to confirm and apply the entered date to the report settings
    date_field.send_keys("\ue004")  # TAB to apply the date
    logger.info(f"End date successfully applied to report: {xero_end_date}")


def update_report_and_export_to_excel(
    driver,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: str,
):
    """
    Update the Leave Balances report, validate payroll data, export to Excel, and save the file.

    Performs the final steps in the Leave Balances report download workflow:
    (1) clicks Update to refresh the report with the configured end date,
    (2) validates payroll data exists by checking Export button visibility,
    (3) clicks Export then Excel to trigger the Windows Save As dialog, and
    (4) automates the Save As dialog to save the file to the specified location.
    File overwrite confirmation is automatically handled if the file already exists.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must have the Leave Balances report configured and ready to update.
        window_title (str): Browser window title fragment for Windows Save As dialog detection.
                           Example: "Leave Balances"
        download_directory (str): Absolute path to the save directory.
                                 Example: "C:\\Reports\\Xero\\LeaveBalances"
        report_file_name (str): Desired filename without extension.
                               Example: "ABC_Company_Leave_Balances_2024"
        extension (str): File extension for the saved report (e.g., ".xlsx").

    Returns:
        None: Completes when the file is saved successfully.

    Raises:
        Exception: If no payroll data is available for the client (Export button not visible
                  after Update, indicating the client has no payroll setup).
        TimeoutException: If Update, Export, or Excel buttons are not found within 10 seconds.
        Exception: If Windows Save As dialog handling or file save operation fails.

    Notes:
        - Uses WebDriverWait with 10-second timeout for all button interactions.
        - Update button XPath: "//button[@type='button' and normalize-space(text())='Update']"
        - Export button XPath: "//button[@type='button' and normalize-space(text())='Export']"
        - Excel button XPath: "//button[@type='button']//span[normalize-space(text())='Excel']"
        - Export button visibility check uses 5-second timeout via check_export_button_visible().
        - Includes 2-second delay after clicking Excel for the Save As dialog to fully appear.

    Example:
        >>> update_report_and_export_to_excel(driver, "Leave Balances", "C:\\Reports", "Leave_Balances_2024", ".xlsx")
        # Updates report, validates data, exports to Excel, and saves the file
    """
    update_xpath = "//button[@type='button' and normalize-space(text())='Update']"
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    excel_xpath = "//button[@type='button']//span[normalize-space(text())='Excel']"

    # Click the Update button to regenerate the Leave Balances report with the configured end date
    logger.info("Clicking 'Update' button to refresh the Leave Balances report data...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, update_xpath)),
    ).click()
    logger.info("'Update' button clicked — report is refreshing.")

    # Validate that the Export button is visible, confirming payroll data exists for this client
    # If Export button does not appear within 5 seconds, the client has no payroll data setup
    logger.info(
        "Checking if Export button is visible to confirm payroll data exists for this client...",
    )
    if not check_export_button_visible(driver):
        logger.warning(
            "Export button not visible after Update — no payroll data found for this client.",
        )
        raise Exception("There is no payroll data for this client.")
    logger.info("Export button is visible — payroll data confirmed for this client.")

    # Click the Export button to open the export format options menu
    logger.info("Clicking 'Export' button to open export format options...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, export_xpath)),
    ).click()
    logger.info("'Export' button clicked — export format menu is open.")

    # Click the Excel option to initiate the file download and trigger the Windows Save As dialog
    logger.info("Clicking 'Excel' option to initiate Excel file download...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, excel_xpath)),
    ).click()
    logger.info(
        "'Excel' option clicked — Windows Save As dialog should appear shortly.",
    )

    # Wait for the Windows Save As dialog to fully load before attempting automation
    logger.info("Waiting 2 seconds for Windows Save As dialog to appear...")
    time.sleep(2)

    # Automate the Windows Save As dialog to save the file to the specified location
    # Sets the file path, selects file type, clicks Save, and handles overwrite confirmation
    logger.info(
        f"Handling Windows Save As dialog — saving file to: {download_directory}\\{report_file_name}{extension}",
    )
    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    logger.info(f"File saved successfully: {report_file_name}{extension}")


def check_export_button_visible(driver) -> bool:
    """
    Check whether the Export button is visible on the Leave Balances report page.

    Serves as a payroll data validation check. After clicking Update, Xero only displays
    the Export button if payroll data is available for the client. If the Export button
    does not appear within 5 seconds, the client has no payroll setup or no employee
    leave data for the configured date.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must have just clicked the Update button on the Leave Balances report page.

    Returns:
        bool: True if the Export button is visible within 5 seconds (payroll data exists).
              False if the Export button is not visible within 5 seconds (no payroll data).

    Notes:
        - Uses WebDriverWait with 5-second timeout for Export button visibility check.
        - Export button XPath: "//button[@type='button' and normalize-space(text())='Export']"
        - A timeout exception catching a False return indicates no payroll data available.
        - Logs the result for debugging and audit trail purposes.

    Example:
        >>> if check_export_button_visible(driver):
        ...     # Proceed with Export → Excel workflow
        ... else:
        ...     # Raise exception: no payroll data for this client
    """
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, export_xpath)),
        )
        logger.info("Export button is visible — payroll data exists for this client.")
        return True
    except Exception:
        logger.warning(
            "Export button did not appear within 5 seconds — no payroll data available.",
        )
        return False
