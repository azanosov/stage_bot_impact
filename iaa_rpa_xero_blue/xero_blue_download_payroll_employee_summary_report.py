from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_payroll_employee_summary_report(
    browser,
    client_name: str,
    xero_end_date: str,
    xero_financial_year: str,
    xero_start_date: str,
    window_title: str,
    download_directory_path: str,
    xero_report_file_name: str,
    xero_report_name: str,
    extension: str,
):
    """
    Download the Payroll Employee Summary report from Xero Blue for a specific client.

    This function automates the complete workflow for downloading Payroll Employee Summary
    reports from Xero Blue. It configures the report with custom date ranges (or defaults
    to financial year dates), validates that payroll data exists for the client, updates
    and exports the report as an Excel file, and handles the Windows Save As dialog to
    save the file with a specified name to a designated directory.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be already logged into Xero Blue and navigated to the
                 Payroll Employee Summary report page.
        client_name (str): Name of the Xero client organisation for logging purposes.
                           Example: "ABC Company Pty Ltd"
        xero_end_date (str): End date for the report in "d MMM yyyy" format.
                             Example: "30 Jun 2024". Defaults to financial year end
                             if not provided.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Example: "2024" represents FY 2023-2024.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format.
                               Example: "1 Jul 2023". Defaults to financial year start
                               if not provided.
        window_title (str): Browser window title used by Windows automation to locate
                            the Save As dialog.
        download_directory_path (str): Absolute path to the directory where the Excel
                                       file should be saved.
                                       Example: "C:\\Reports\\Xero\\Payroll"
        xero_report_file_name (str): Desired filename for the downloaded Excel file
                                     (without extension).
                                     Example: "ABC_Company_Payroll_Employee_Summary_2024"
        xero_report_name (str): Display name of the report used for logging.
                                Example: "Payroll Employee Summary"
        extension (str): File extension for the downloaded file. Example: ".xlsx"

    Returns:
        None: The function completes successfully or raises an exception.

    Raises:
        Exception: If any step in the download process fails, including:
                   - No payroll data exists for the client
                   - Selenium WebDriverWait timeouts
                   - Windows Save As dialog failures
                   - File system errors
                   All exceptions are logged before being re-raised.

    Notes:
        - The browser must already be positioned on the Payroll Employee Summary report page.
        - Clients without payroll setup will raise a "no payroll data" exception.
        - If xero_start_date or xero_end_date are empty, defaults to full financial year range.
        - The Windows Save As dialog is handled using robocorp.windows.
        - File overwrite confirmation is automatically handled if the file already exists.
    """

    # -------------------------------------------------------------------------
    # START: Initialise process timing and log all input parameters
    # -------------------------------------------------------------------------
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Payroll Employee Summary Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name: {client_name}")
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Start Date: {xero_start_date}")
    logger.info(f"End Date: {xero_end_date}")
    logger.info(f"Report Name: {xero_report_name}")
    logger.info(f"Report File Name: {xero_report_file_name}")
    logger.info(f"File Extension: {extension}")
    logger.info(f"Download Path: {download_directory_path}")
    logger.info(f"Window Title: {window_title}")
    logger.info("=" * 80)

    try:

        # STEP 1: Extract WebDriver Instance
        # Purpose: Obtain the raw Selenium WebDriver from the browser wrapper so that
        #          all subsequent waits and element interactions can be performed directly.
        # - Reads browser.driver attribute provided by the RPA framework
        logger.info(
            "STEP 1: Extracting Selenium WebDriver instance from browser object.",
        )
        driver = browser.driver
        logger.info("WebDriver instance extracted successfully.")

        # STEP 2: Configure Report Date Range
        # Purpose: Populate the From and To date input fields on the report page with
        #          the correct reporting period before generating the report.
        # Function: configure_date_range_fields(driver, xero_end_date, xero_financial_year, xero_start_date)
        # - Resolves the date range from provided inputs or financial year defaults
        # - Clears any existing value in the From date field and enters the start date
        # - Clears any existing value in the To date field and enters the end date
        # - Presses TAB after each entry to trigger Xero's date validation
        logger.info("STEP 2: Configuring report date range fields.")
        configure_date_range_fields(
            driver,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
        )
        logger.info("Date range fields configured successfully.")

        # STEP 3: Update Report and Export to Excel
        # Purpose: Refresh the report with the configured dates, confirm payroll data
        #          exists, trigger the Excel export, and save the file via the Windows
        #          Save As dialog.
        # Function: update_report_and_export_to_excel(driver, window_title, download_directory_path, xero_report_file_name, extension)
        # - Clicks the Update button to generate the report for the selected date range
        # - Checks Export button visibility to confirm payroll data exists for this client
        # - Raises an exception immediately if no payroll data is found
        # - Clicks Export then Excel to initiate the file download
        # - Handles the Windows Save As dialog to save the file to the target directory
        # - Confirms any overwrite prompt if the file already exists
        logger.info("STEP 3: Updating report and exporting to Excel.")
        update_report_and_export_to_excel(
            driver,
            window_title,
            download_directory_path,
            xero_report_file_name,
            extension,
        )
        logger.info("Report updated and exported to Excel successfully.")

        # -------------------------------------------------------------------------
        # END (SUCCESS): Log completion details and duration
        # -------------------------------------------------------------------------
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue Download Payroll Employee Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Report Name: {xero_report_name}")
        logger.info(f"File Name: {xero_report_file_name}{extension}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        # -------------------------------------------------------------------------
        # END (FAILURE): Log error details and duration before re-raising
        # -------------------------------------------------------------------------
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Payroll Employee Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Report Name: {xero_report_name}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("=" * 80)
        raise


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def resolve_report_dates(
    xero_end_date: str,
    xero_financial_year: str,
    xero_start_date: str,
) -> tuple:
    """
    Resolve the start and end dates for the Payroll Employee Summary report period.

    Evaluates whether custom start and end dates are provided. If either is missing
    or empty, both dates are calculated from the financial year using the Australian
    convention (1 Jul previous year to 30 Jun current year). Returns both dates as
    strings in the format expected by Xero's date input fields.

    Args:
        xero_end_date (str): End date in "d MMM yyyy" format (e.g., "30 Jun 2024").
                             Can be empty or None to trigger financial year default.
        xero_financial_year (str): 4-digit financial year ending year.
                                   Example: "2024" represents FY 2023-2024.
        xero_start_date (str): Start date in "d MMM yyyy" format (e.g., "1 Jul 2023").
                               Can be empty or None to trigger financial year default.

    Returns:
        tuple[str, str]: A tuple of (str_start_date, str_end_date) in "d MMM yyyy" format.
                         - str_start_date: The resolved start date.
                         - str_end_date: The resolved end date.

    Notes:
        - If either date is missing, both default to the full financial year range.
        - Default dates follow the Australian FY convention:
          start = "1 Jul {year - 1}", end = "30 Jun {year}".
        - The resolved source (default or input) is logged for audit purposes.

    Example:
        >>> resolve_report_dates("", "2024", "")
        ('1 Jul 2023', '30 Jun 2024')
        >>> resolve_report_dates("31 Dec 2023", "2024", "1 Jan 2023")
        ('1 Jan 2023', '31 Dec 2023')
    """
    if not xero_end_date or not xero_start_date:
        logger.info(
            "No custom dates provided — using default financial year date range.",
        )
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"Default date range resolved: {str_start_date} to {str_end_date}")
    else:
        logger.info("Custom dates provided — using input file date range.")
        str_start_date = xero_start_date
        str_end_date = xero_end_date
        logger.info(f"Custom date range resolved: {str_start_date} to {str_end_date}")
    return str_start_date, str_end_date


def configure_date_range_fields(
    driver,
    xero_end_date: str,
    xero_financial_year: str,
    xero_start_date: str,
) -> None:
    """
    Populate the From and To date input fields on the Payroll Employee Summary report page.

    Resolves the reporting period dates and enters them into the Xero Blue report date
    fields using keyboard automation. Each field is cleared with CTRL+A then DELETE before
    the new date is typed. TAB is pressed after each entry to trigger Xero's date
    validation and formatting. This function only configures the date fields — it does not
    click Update or Export.

    Args:
        driver: Selenium WebDriver instance positioned on the Payroll Employee Summary
                report page with the date input fields visible.
        xero_end_date (str): End date in "d MMM yyyy" format, or empty to use default.
        xero_financial_year (str): 4-digit financial year ending year used for defaults.
        xero_start_date (str): Start date in "d MMM yyyy" format, or empty to use default.

    Returns:
        None: Completes when both date fields have been populated and validated.

    Raises:
        TimeoutException: If either date input field is not visible within 10 seconds.
        WebDriverException: If keyboard automation fails on the date fields.

    Notes:
        - Date field IDs:
            From: "report-settings-custom-date-input-from"
            To:   "report-settings-custom-date-input-to"
        - Unicode keyboard codes used:
            \\ue009 = CTRL, \\ue003 = DELETE, \\ue004 = TAB
        - CTRL+A followed by DELETE clears any existing date before typing the new one.
        - TAB triggers Xero's internal date parsing and field validation.
        - Date resolution is delegated to resolve_report_dates().
    """
    logger.info("Resolving report date range.")

    # Define element locators for the From and To date input fields
    from_date_id = (By.ID, "report-settings-custom-date-input-from")
    to_date_id = (By.ID, "report-settings-custom-date-input-to")

    # Resolve the date range — uses provided dates or falls back to financial year defaults
    str_start_date, str_end_date = resolve_report_dates(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )

    # --- Populate the From date field ---
    logger.info(f"Entering From date: {str_start_date}")
    from_date = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(from_date_id),
    )
    from_date.send_keys("\ue009" + "a")  # CTRL + A — select all existing text
    from_date.send_keys("\ue003")  # DELETE — clear the selected text
    from_date.send_keys(str_start_date)  # Type the new start date
    from_date.send_keys("\ue004")  # TAB — trigger Xero date validation
    logger.info(f"From date entered: {str_start_date}")

    # --- Populate the To date field ---
    logger.info(f"Entering To date: {str_end_date}")
    to_date = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(to_date_id),
    )
    to_date.send_keys("\ue009" + "a")  # CTRL + A — select all existing text
    to_date.send_keys("\ue003")  # DELETE — clear the selected text
    to_date.send_keys(str_end_date)  # Type the new end date
    to_date.send_keys("\ue004")  # TAB — trigger Xero date validation
    logger.info(f"To date entered: {str_end_date}")

    logger.info(
        f"Date range configured successfully: {str_start_date} to {str_end_date}",
    )


def update_report_and_export_to_excel(
    driver,
    window_title: str,
    download_directory_path: str,
    xero_report_file_name: str,
    extension: str,
) -> None:
    """
    Update the report, validate payroll data, export to Excel, and save the file.

    Executes the complete report generation and download workflow after date configuration.
    Clicks Update to refresh the report, validates that payroll data exists by checking
    Export button visibility, triggers the Excel export, and automates the Windows Save As
    dialog to save the file to the specified location. Overwrite confirmation is handled
    automatically if the target file already exists.

    Args:
        driver: Selenium WebDriver instance on the Payroll Employee Summary report page
                with dates already configured via configure_date_range_fields().
        window_title (str): Browser window title fragment used by Windows automation to
                            locate the Save As dialog.
        download_directory_path (str): Absolute path to the target download directory.
                                       Example: "C:\\Reports\\Xero\\Payroll"
        xero_report_file_name (str): Target filename without extension.
                                     Example: "ABC_Company_Payroll_Employee_Summary_2024"
        extension (str): File extension to append to the filename. Example: ".xlsx"

    Returns:
        None: Completes when the file has been saved to disk.

    Raises:
        Exception: If no payroll data exists for the client — Export button is not visible
                   after Update. Message: "There is no payroll data for this client."
        TimeoutException: If Update, Export, or Excel buttons are not found or not
                         clickable within 10 seconds.
        Exception: If the Windows Save As dialog cannot be located or the file save fails.

    Notes:
        - Update button XPath: //button[@type='button' and normalize-space(text())='Update']
        - Export button XPath: //button[@type='button' and normalize-space(text())='Export']
        - Excel button XPath:  //button[@type='button']//span[normalize-space(text())='Excel']
        - Export button visibility (5-second timeout) is used to confirm payroll data exists.
        - The Windows Save As dialog is handled by download_file() using robocorp.windows.
        - All actions and errors are logged for audit and debugging purposes.
    """
    # Define XPath locators for the report action buttons
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

    try:
        # Click the Update button to generate the report for the configured date range
        logger.info("Clicking Update button to refresh the report.")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(update_xpath),
        ).click()
        logger.info("Update button clicked — report generation initiated.")

        # Validate that payroll data exists for this client before attempting export
        # The Export button only appears when payroll data is available for the selected period
        logger.info(
            "Checking whether payroll data exists for this client (Export button visibility).",
        )
        if not is_export_button_visible(driver):
            logger.warning(
                "Export button not visible after Update — no payroll data found for this client.",
            )
            raise Exception("There is no payroll data for this client.")
        logger.info(
            "Export button is visible — payroll data confirmed for this client.",
        )

        # Click the Export button to reveal the export format options menu
        logger.info("Clicking Export button to open export format menu.")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(export_xpath),
        ).click()
        logger.info("Export button clicked — export format menu opened.")

        # Click the Excel option to initiate the file download and trigger the Save As dialog
        logger.info("Clicking Excel option to initiate Excel file download.")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(excel_xpath)).click()
        logger.info("Excel export triggered — Windows Save As dialog expected.")

        # Handle the Windows Save As dialog to save the file to the specified location
        # download_file() locates the dialog, enters the file path, selects file type,
        # clicks Save, and handles any overwrite confirmation prompt automatically
        logger.info(
            f"Handling Windows Save As dialog — saving file to: {download_directory_path}\\{xero_report_file_name}{extension}",
        )
        download_file(
            window_title,
            download_directory_path,
            xero_report_file_name,
            extension,
        )
        logger.info("File saved successfully via Windows Save As dialog.")

    except Exception as e:
        logger.error(f"Failed during report update and export: {e}")
        raise


def is_export_button_visible(driver) -> bool:
    """
    Check whether the Export button is visible on the report page after clicking Update.

    For payroll reports in Xero Blue, the Export button only appears when payroll data
    exists for the selected client and date range. This check prevents an export attempt
    when no data is available. A shorter timeout (5 seconds) is used intentionally since
    the button should appear quickly if data exists.

    Args:
        driver: Selenium WebDriver instance on the Payroll Employee Summary report page,
                immediately after the Update button has been clicked.

    Returns:
        bool: True if the Export button becomes visible within 5 seconds (payroll data
              exists and the report can be exported). False otherwise (no payroll data).

    Raises:
        None: All exceptions are caught internally and treated as a False result.
              Any timeout or element-not-found error means the button is not visible.

    Notes:
        - Export button XPath: //button[@type='button' and normalize-space(text())='Export']
        - Timeout is intentionally set to 5 seconds (shorter than the standard 10 seconds)
          because a missing button means no data, not a slow page load.
        - Returns False for any exception including TimeoutException, StaleElementException, etc.
        - The calling function is responsible for raising an appropriate exception when False
          is returned.

    Example:
        >>> if is_export_button_visible(driver):
        ...     # Proceed with export
        ... else:
        ...     raise Exception("No payroll data available for this client.")
    """
    try:
        export_xpath = (
            By.XPATH,
            "//button[@type='button' and normalize-space(text())='Export']",
        )
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located(export_xpath))
        logger.info("Export button is visible.")
        return True
    except Exception:
        logger.warning(
            "Export button not visible within 5 seconds — no payroll data available.",
        )
        return False
