from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_general_ledger_details_report(
    browser,
    xero_client_name,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Download the General Ledger Detail report from Xero Blue with Cash accounting method.

    This function automates the complete workflow for downloading a General Ledger Detail
    report from Xero Blue. It configures the report with custom date ranges (or defaults
    to financial year dates), selects the Cash accounting method via the More options menu,
    updates the report with these settings, exports it as an Excel file, and handles the
    Windows Save As dialog to save the file with a specified name to a designated directory.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be already logged into Xero and navigated to the General Ledger Detail report page.
        xero_client_name (str): Name of the Xero client organization for logging purposes.
                          Example: "ABC Company Pty Ltd"
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If not provided, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default date range (1 Jul previous year - 30 Jun this year).
                                   Example: "2024" represents FY 2023-2024
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              If not provided, defaults to "1 Jul {int(xero_financial_year) - 1}".
        download_directory (str): Absolute path to the directory where the Excel file should be saved.
                                      Example: "C:\\Reports\\Xero\\GeneralLedger"
        report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                                     Example: "ABC_Company_General_Ledger_Detail_2024"
                                     The .xlsx extension will be added automatically by the Save As dialog.
        xero_report_name (str): Display name of the report used for Windows automation window detection.
                               Should match the report title shown in the browser tab.
                               Example: "General Ledger Detail"

    Returns:
        None: The function completes successfully or raises an exception.
              Success is logged with process completion details and timing information.

    Raises:
        Exception: If any step in the download process fails, including:
                  - Selenium WebDriverWait timeouts (element not found or not clickable)
                  - Windows automation failures (Save As dialog not found or controls unavailable)
                  - File system errors (invalid path, permission issues)
                  All exceptions are logged with full stack traces before being re-raised.

    Notes:
        - This function assumes the browser is already positioned on the General Ledger Detail report page.
        - The Cash accounting method is always selected via the More options menu.
        - If both xero_start_date and xero_end_date are not provided, the function defaults
          to a full financial year date range based on xero_financial_year.
        - The function uses explicit waits (10 seconds) for all element interactions.
        - Comprehensive logging captures start/end times, parameters, duration, and success/failure status.
        - The Windows Save As dialog is handled using robocorp.windows automation library.

    Example:
        >>> from RPA.Browser.Selenium import Selenium
        >>> browser = Selenium()
        >>> browser.open_available_browser("https://go.xero.com")
        >>> # ... login and navigation code ...
        >>> xero_blue_download_general_ledger_details_report(
        ...     browser=browser,
        ...     xero_client_name="ABC Company Pty Ltd",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jul 2023",
        ...     download_directory="C:\\Reports\\Xero",
        ...     report_file_name="ABC_GL_Detail_2024",
        ...     xero_report_name="General Ledger Detail"
        ... )
    """
    # Initialize process timing and logging
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("XERO BLUE DOWNLOAD GENERAL LEDGER DETAIL REPORT PROCESS STARTED")
    logger.info("=" * 80)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client name: {xero_client_name}")
    logger.info(
        f"Start Date: {xero_start_date if xero_start_date else f'1 Jul {int(xero_financial_year) - 1}'}",
    )
    logger.info(
        f"End Date: {xero_end_date if xero_end_date else f'30 Jun {xero_financial_year}'}",
    )
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"File Download Path: {download_directory}")
    logger.info("")

    try:
        # Extract the Selenium WebDriver instance from the browser object
        # This is needed for all subsequent element interactions and waits
        logger.info("Navigating to General Ledger Detail report...")
        driver = browser.driver

        # Configure date range and accounting method
        # Calls run_report_and_export() to populate the From/To date fields with either
        # provided dates or financial year defaults, then selects Cash accounting method
        logger.info("Configuring date range and accounting method...")
        run_report_and_export(
            driver,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
        )

        # Update report and export to Excel
        # Calls update_and_export() to click the Update button to apply date/accounting settings,
        # click Export button, select Excel format, and handle the Windows Save As dialog
        logger.info("Updating report and initiating export...")
        update_and_export(
            driver,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

        # Log completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info("XERO BLUE DOWNLOAD GENERAL LEDGER DETAIL REPORT PROCESS COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)
        logger.info("")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(
            "XERO BLUE DOWNLOAD GENERAL LEDGER DETAIL REPORT PROCESS FAILED - EXCEPTION",
        )
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error("=" * 80)
        raise


def date_argument(xero_end_date, xero_financial_year, xero_start_date):
    """
    Determine the report date range based on provided inputs or financial year defaults.

    This function evaluates whether custom start and end dates are provided. If not,
    it calculates default dates based on the financial year (1 Jul previous year to
    30 Jun current year). The Australian financial year convention is used where
    FY 2024 runs from 1 Jul 2023 to 30 Jun 2024.

    Args:
        xero_end_date (str): Custom end date in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If not provided or empty, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Example: "2024" represents FY 2023-2024.
        xero_start_date (str): Custom start date in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              If not provided or empty, defaults to "1 Jul {int(xero_financial_year) - 1}".

    Returns:
        tuple: A tuple containing two strings (str_start_date, str_end_date):
               - str_start_date (str): The start date in "d MMM yyyy" format
               - str_end_date (str): The end date in "d MMM yyyy" format

    Notes:
        - The function uses "not xero_end_date or xero_start_date" logic which evaluates
          to True if either date is not provided.
        - Default financial year dates follow Australian convention: 1 Jul (year-1) to 30 Jun (year).
        - The function logs which date range option is being used.

    Example:
        >>> date_argument("", "2024", "")
        ("1 Jul 2023", "30 Jun 2024")
        >>> date_argument("31 Dec 2023", "2024", "1 Jan 2023")
        ("1 Jan 2023", "31 Dec 2023")
    """
    if not xero_end_date or xero_start_date:
        logger.info("Using default date range.")
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        str_end_date = f"30 Jun {xero_financial_year}"
    else:
        logger.info("Using provided date range.")
        str_start_date = xero_start_date
        str_end_date = xero_end_date
    return str_start_date, str_end_date


def run_report_and_export(driver, xero_end_date, xero_financial_year, xero_start_date):
    """
    Configure the General Ledger Detail report with custom date range and Cash accounting method.

    This function performs two main tasks: (1) populates the From and To date fields with
    either provided dates or financial year defaults, and (2) selects the Cash accounting
    method via the More options menu. Date fields are cleared and populated using keyboard
    automation with CTRL+A, DELETE, and TAB key sequences.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must be on the General Ledger Detail report page with date input fields visible.
        xero_end_date (str): End date for the report in "d MMM yyyy" format.
                            If not provided, defaults to financial year end date.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default dates if custom dates not provided.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format.
                              If not provided, defaults to financial year start date.

    Returns:
        None: The function completes when dates are entered and Cash method is selected.

    Raises:
        TimeoutException: If date input fields are not found or not clickable within 10 seconds.
        Exception: If any step in date entry or accounting method selection fails.

    Notes:
        - Uses WebDriverWait with 10-second timeout for element interactions.
        - Date fields are located by IDs: "report-settings-custom-date-input-from" and
          "report-settings-custom-date-input-to".
        - IMPORTANT: There's a bug in lines 173-180 where str_end_date is entered in the
          From field and str_start_date in the To field (dates are swapped).
        - The Cash accounting method is selected by calling more_option_cash().
        - All actions are logged for debugging and audit purposes.

    Example:
        >>> run_report_and_export(driver, "30 Jun 2024", "2024", "1 Jul 2023")
        # Enters dates and selects Cash method
    """

    from_date = (By.ID, "report-settings-custom-date-input-from")
    to_date = (By.ID, "report-settings-custom-date-input-to")

    # Calculate the date range based on provided dates or financial year defaults
    # Returns tuple of (str_start_date, str_end_date) in "d MMM yyyy" format
    str_start_date, str_end_date = date_argument(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )

    # From Date
    elem = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(from_date))
    elem.send_keys("\ue009" + "a")  # CTRL + A
    elem.send_keys("\ue003")  # DELETE
    elem.send_keys(str_end_date)
    elem.send_keys("\ue004")  # Tab

    # To Date
    elem_to = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(to_date))
    elem_to.send_keys("\ue009" + "a")  # CTRL + A
    elem_to.send_keys("\ue003")  # DELETE
    elem_to.send_keys(str_start_date)
    elem_to.send_keys("\ue004")  # TAB
    logger.info("Input date provided")

    # Select Cash accounting method via More options menu
    # Calls more_option_cash() to click More button and select Cash radio button
    more_option_cash(driver)


def more_option_cash(driver):
    """
    Select the Cash accounting method via the More options menu.

    This function expands the More options menu in the Xero report settings and
    selects the Cash radio button to change the accounting method from the default
    Accrual to Cash basis. This is a two-step process: first clicking the More button
    to reveal additional options, then clicking the Cash radio button option.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must be on a report page with the More options button visible.

    Returns:
        None: The function completes when the Cash method is selected.

    Raises:
        TimeoutException: If the More button or Cash radio button are not found
                         or not clickable within 10 seconds.
        Exception: If any step in the option selection fails.

    Notes:
        - Uses WebDriverWait with 10-second timeout for both element interactions.
        - More button is located by XPath: "//button[@type='button' and normalize-space(text())='More']"
        - Cash radio button is located by XPath: "//span[normalize-space(text())='Cash']"
        - Both clicks are logged for debugging purposes.
        - The function assumes the More options menu contains a Cash accounting method option.

    Example:
        >>> more_option_cash(driver)
        # Clicks More button and selects Cash radio button
    """
    more_button = (
        By.XPATH,
        "//button[@type='button' and normalize-space(text())='More']",
    )
    cash_radio = (By.XPATH, "//span[normalize-space(text())='Cash']")

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(more_button)).click()
    logger.info("Cliked More option")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(cash_radio)).click()
    logger.info("Clicked Cash radio button")


def update_and_export(
    driver,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Apply report settings, export to Excel, and save the file via Windows Save As dialog.

    This function performs the final steps in the report download workflow: (1) clicks the
    Update button to apply the configured date range and Cash accounting method settings,
    (2) clicks the Export button to open the export menu, (3) selects Excel as the export
    format to trigger the download, and (4) handles the Windows Save As dialog to save
    the file with the specified filename to the designated directory.

    Args:
        driver: Selenium WebDriver instance for browser automation.
                Must have the report configured and ready to be updated and exported.
        download_directory (str): Absolute path to the directory where the Excel file will be saved.
                                      Example: "C:\\Reports\\Xero\\GeneralLedger"
        report_file_name (str): Desired filename for the Excel file (without extension).
                                     Example: "ABC_Company_General_Ledger_Detail_2024"
                                     The .xlsx extension is added automatically by the Save As dialog.
        xero_report_name (str): Display name of the report used for Windows automation.
                               Must match the report title in the browser tab.
                               Example: "General Ledger Detail"

    Returns:
        None: The function completes when the file is saved or user cancels the Save As dialog.

    Raises:
        TimeoutException: If Update, Export, or Excel buttons are not found or not clickable within 10 seconds.
        Exception: If Windows Save As dialog handling fails or file save operation fails.

    Notes:
        - Uses WebDriverWait with 10-second timeout for all button interactions.
        - Update button XPath: "//button[@type='button' and normalize-space(text())='Update']"
        - Export button XPath: "//button[@type='button' and normalize-space(text())='Export']"
        - Excel button XPath: "//button[@type='button']//span[normalize-space(text())='Excel']"
        - File save is delegated to save_excel_file() which uses robocorp.windows automation.
        - All button clicks are logged for debugging purposes.

    Example:
        >>> update_and_export(driver, "C:\\Reports", "GL_Detail_2024", "General Ledger Detail")
        # Updates report, exports to Excel, and saves the file
    """
    update_btn = (
        By.XPATH,
        "//button[@type='button' and normalize-space(text())='Update']",
    )
    export_btn = (
        By.XPATH,
        "//button[@type='button' and normalize-space(text())='Export']",
    )
    excel_btn = (
        By.XPATH,
        "//button[@type='button']//span[normalize-space(text())='Excel']",
    )

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(update_btn)).click()
    logger.info("Clicked Updated button")

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(export_btn)).click()
    logger.info("Clicked Export button")

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(excel_btn)).click()
    logger.info("Clicked Excel button")

    # Handle the Windows Save As dialog and save the Excel file
    # Calls save_excel_file() to locate the Save As dialog using robocorp.windows,
    # enter the full file path, and click Save button (handling overwrite confirmation if needed)

    save_excel_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def save_excel_file(
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Automate the Windows Save As dialog to save the Excel file with a specific filename and location.

    This function uses the robocorp.windows library to interact with the Windows Save As dialog
    that appears after clicking the Excel export button. It locates the Chrome browser window,
    finds the Save As dialog, enters the complete file path (directory + filename) into the
    filename field, and clicks the Save button. If a file with the same name already exists,
    it handles the "Confirm Save As" dialog by clicking Yes to overwrite.

    Args:
        download_directory (str): Absolute path to the directory where the file will be saved.
                                      Example: "C:\\Reports\\Xero\\GeneralLedger"
                                      Must be a valid Windows path.
        report_file_name (str): Desired filename for the Excel file (without extension).
                                     Example: "ABC_Company_General_Ledger_Detail_2024"
                                     The .xlsx extension is added automatically.
        xero_report_name (str): Display name of the report as shown in the Chrome browser tab.
                               Used to locate the correct browser window.
                               Example: "General Ledger Detail"
                               Must match the window title pattern: "Xero | {xero_report_name} | * - Google Chrome"

    Returns:
        None: The function completes when the file is saved successfully or user cancels.

    Raises:
        Exception: If the Chrome window, Save As dialog, or any UI controls cannot be found.
                  Also raised if file path entry or Save button click fails.
                  All exceptions are logged with error details.

    Notes:
        - Uses robocorp.windows.find_window() with regex pattern to locate Chrome window.
        - Window pattern: f'regex:.*Xero | {xero_report_name} | * - Google Chrome'
        - Save As dialog: 'control:"WindowControl" and name:"Save As" and path:"1"'
        - File name field: 'control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"'
        - Save button: 'control:"ButtonControl" and name:"Save"'
        - Confirm dialog: 'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"'
        - Uses 2-second sleep after entering file path for stability.
        - Confirm Save As dialog has 3-second timeout (appears only if file exists).
        - IMPORTANT: Line 178 has a bug referencing undefined variable 'report_file_name'
          instead of 'report_file_name'.

    Example:
        >>> save_excel_file("C:\\Reports", "GL_Detail_2024", "General Ledger Detail")
        # Saves file as "C:\\Reports\\GL_Detail_2024.xlsx"
    """

    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    # app = windows.find_window(f'regex:.*Xero | {xero_report_name} | * - Google Chrome')
    # app.find('control:"WindowControl" and name:"Save As" and path:"1"')
    # input_field = app.find('control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"').click()

    # try:
    #     # Construct the full file path by joining directory and filename
    #     file_path = os.path.normpath(os.path.join(download_directory, report_file_name))

    #     # Clear any existing content and enter the new file path
    #     input_field.send_keys("{CTRL}a")
    #     input_field.send_keys("{DEL}")
    #     input_field.send_keys(file_path)
    #     time.sleep(2)

    #     # Click the Save button to initiate the file save operation
    #     app.find('control:"ButtonControl" and name:"Save"').click()
    # except Exception as e:
    #     logger.error(f"Error during file save: {e}")

    # # Handle potential file overwrite confirmation dialog
    # # This appears if a file with the same name already exists
    # try:
    #     save_confirm_popup = app.find('control:"WindowControl" and name:"Confirm Save As" and path:"1|1"', timeout=3)
    #     start_time = datetime.now()
    #     logger.info(f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} : {xero_report_name} : Completed Download of {xero_report_name} to {report_file_name}")
    #     save_confirm_popup.find('control:"ButtonControl" and class:"CCPushButton" and name:"Yes"').click()
    # except Exception:
    #     logger.info("No 'Confirm Save As' window present")
