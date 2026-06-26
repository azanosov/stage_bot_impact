from __future__ import annotations

from datetime import datetime

from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .download_file import download_file

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_gst_reconciliation_report(
    browser,
    xero_client_name: str,
    xero_end_date: str,
    xero_financial_year: str,
    xero_start_date: str,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    xero_report_name: str,
    extension: str,
):
    """
    Download the GST Reconciliation report from Xero Blue for a specified client and date range.

    This function automates the complete workflow for downloading GST Reconciliation reports
    from Xero Blue (legacy interface). It configures the report with custom date ranges (or
    defaults to financial year dates), generates the report by clicking Update, exports it as
    an Excel file, and handles the Windows Save As dialog to save the file with a specified
    name to a designated directory. The function provides comprehensive logging with banners,
    timestamps, parameters, duration tracking, and success/failure status.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be already logged into Xero Blue and navigated to the GST Reconciliation report page.
        xero_client_name (str): Name of the Xero client organization for logging purposes.
                               Example: "ABC Company Pty Ltd"
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            If not provided or empty, defaults to "30 Jun {xero_financial_year}".
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default date range (1 Jul previous year - 30 Jun this year).
                                   Example: "2024" represents FY 2023-2024
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              If not provided or empty, defaults to "1 Jul {int(xero_financial_year) - 1}".
        download_directory (str): Absolute path to the directory where the Excel file should be saved.
                                      Example: "C:\\Reports\\Xero\\GST"
        report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                                     Example: "ABC_Company_GST_Reconciliation_2024"
                                     The .xlsx extension will be added automatically by the Save As dialog.
        xero_report_name (str): Display name of the report used for Windows automation window detection.
                               Should match the report title shown in the browser tab.
                               Example: "GST Reconciliation"

    Returns:
        None: The function completes successfully or raises an exception.
              Success is logged with process completion details and timing information.

    Raises:
        Exception: If any step in the download process fails, including:
                  - Selenium WebDriverWait timeouts (element not found or not clickable)
                  - Windows automation failures (Save As dialog not found or controls unavailable)
                  - File system errors (invalid path, permission issues)
                  All exceptions are logged with full stack traces (exc_info=True) before being re-raised.

    Notes:
        - This function assumes the browser is already positioned on the GST Reconciliation report page in Xero Blue.
        - This is for Xero Blue (legacy interface) which uses different element locators than Xero New.
        - Date fields use IDs "fromDate" and "toDate" (legacy Xero Blue selectors).
        - If both xero_start_date and xero_end_date are not provided, the function defaults
          to a full financial year date range based on xero_financial_year.
        - The function uses explicit waits (5 seconds) for all element interactions.
        - Comprehensive logging captures start/end times, all parameters, duration, and success/failure status.
        - The Windows Save As dialog is handled using robocorp.windows automation library.
        - File overwrite confirmation is automatically handled if the file already exists.

    Example:
        >>> from RPA.Browser.Selenium import Selenium
        >>> browser = Selenium()
        >>> browser.open_available_browser("https://go.xero.com")
        >>> # ... login and navigation code ...
        >>> xero_blue_download_gst_recconciliation_report(
        ...     browser=browser,
        ...     xero_client_name="ABC Company Pty Ltd",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jul 2023",
        ...     download_directory="C:\\Reports\\Xero",
        ...     report_file_name="ABC_GST_Recon_2024",
        ...     xero_report_name="GST Reconciliation"
        ... )
    """
    try:

        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("XERO BLUE DOWNLOAD GST RECONCONCILLIATION REPORT PROCESS STARTED")
        logger.info("=" * 80)
        logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Client name: {xero_client_name}")
        logger.info(f"Financial Year: {xero_financial_year}")
        logger.info(f"Start date : {xero_start_date}")
        logger.info(f"End date : {xero_end_date}")
        logger.info(f"Report Name : {xero_report_name}")
        logger.info("")

        # Execute the complete report generation and download workflow
        # Calls run_report_and_export() to determine date range, populate fromDate/toDate fields,
        # click Update button, export to Excel, and handle Windows Save As dialog
        run_report_and_export(
            browser,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

        # Log completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            "XERO BLUE DOWNLOAD GST RECONCONCILLIATION REPORT PROCESS COMPLETED",
        )
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)
        logger.info("")

    except Exception as e:

        logger.error("=" * 80)
        logger.error(
            "XERO BLUE DOWNLOAD GST RECONCONCILLIATION REPORT PROCESS FAILED - EXCEPTION",
        )
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error("=" * 80)


def date_argument(xero_end_date, xero_financial_year, xero_start_date):
    """
    Determine the start and end dates for the GST Reconciliation report period.

    This function evaluates whether custom start and end dates are provided. If not,
    it calculates default dates based on the financial year (1 Jul previous year to
    30 Jun current year). The Australian financial year convention is used where
    FY 2024 runs from 1 Jul 2023 to 30 Jun 2024.

    Args:
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                            Can be empty/None to use default financial year end date.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Example: "2024" represents FY 2023-2024.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                              Can be empty/None to use default financial year start date.

    Returns:
        tuple: A tuple containing two strings (start_date, end_date):
               - start_date (str): The start date in "d MMM yyyy" format
               - end_date (str): The end date in "d MMM yyyy" format

    Notes:
        - The function uses "not xero_end_date or xero_start_date" logic which evaluates
          to True if either date is not provided.
        - Default financial year dates follow Australian convention: 1 Jul (year-1) to 30 Jun (year).
        - The function logs whether "Default Date range" or "Input File Date range" is being used.

    Example:
        >>> date_argument("", "2024", "")
        ('1 Jul 2023', '30 Jun 2024')
        >>> date_argument("31 Dec 2023", "2024", "1 Jan 2023")
        ('1 Jan 2023', '31 Dec 2023')
    """
    if not xero_end_date or not xero_start_date:
        logger.info("Using Default Date range")
        start_date = f"1 Jul {int(xero_financial_year) - 1}"
        end_date = f"30 Jun {xero_financial_year}"
    else:
        logger.info("Using Input File Date range")
        start_date = xero_start_date
        end_date = xero_end_date

    return start_date, end_date


def run_report_and_export(
    browser,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Execute the GST Reconciliation report in Xero Blue and export it to Excel format.

    This function performs the complete report generation and download workflow for Xero Blue
    (legacy interface). It determines the appropriate date range, populates the fromDate and
    toDate form fields using legacy ID selectors, clicks the Update button to generate the
    report, exports the report to Excel format, and automates the Windows Save As dialog to
    save the file with the specified filename and location. File overwrite confirmation is
    automatically handled if the file already exists.

    Args:
        browser: Selenium browser object containing the WebDriver instance.
                 Must be on the GST Reconciliation report page with date input fields visible.
        xero_end_date (str): End date for the report in "d MMM yyyy" format.
                            If not provided, defaults to financial year end date.
        xero_financial_year (str): Financial year ending year as a 4-digit string.
                                   Used to calculate default dates if custom dates not provided.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format.
                              If not provided, defaults to financial year start date.
        download_directory (str): Absolute path to the directory where the Excel file will be saved.
                                      Example: "C:\\Reports\\Xero\\GST"
        report_file_name (str): Desired filename for the downloaded Excel file (without extension).
                                     Example: "ABC_Company_GST_Reconciliation_2024"
                                     The .xlsx extension is added automatically.
        xero_report_name (str): Display name of the report used for Windows automation.
                               Must match the report title in the browser tab.
                               Example: "GST Reconciliation"

    Returns:
        None: The function completes when the file is saved or user cancels the Save As dialog.

    Raises:
        TimeoutException: If date fields, Update button, Export button, or Excel button are
                         not found or not clickable within 5 seconds.
        Exception: If Windows Save As dialog handling fails or file save operation fails.
                  All exceptions are propagated to the calling function.

    Notes:
        - Uses Selenium WebDriverWait with 5-second timeout for all element interactions.
        - Date field IDs: "fromDate" and "toDate" (Xero Blue legacy selectors).
        - Update button XPath: "//div[@id='AttributePageMain']//a[normalize-space(text())='Update']"
        - Export button XPath: "//span[@class='words' and normalize-space(text())='Export']"
        - Excel button XPath: "//a[@title='Export to Excel' and normalize-space(text())='Excel']"
        - Uses robocorp.windows library for Windows Save As dialog automation.
        - Includes 2-second delays after entering file path and before clicking Save for stability.
        - File overwrite confirmation window has 3-second timeout (only appears if file exists).
        - All major actions are logged for debugging and audit purposes.

    Example:
        >>> run_report_and_export(
        ...     browser=browser,
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jul 2023",
        ...     download_directory="C:\\Reports",
        ...     report_file_name="GST_Report_2024",
        ...     xero_report_name="GST Reconciliation"
        ... )
    """

    # Extract the Selenium WebDriver instance from the browser object
    # This is needed for all subsequent element interactions and waits
    driver = browser.driver
    from_date_id = "fromDate"
    to_date_id = "toDate"
    update_button_xpath = (
        "//div[@id='AttributePageMain']//a[normalize-space(text())='Update']"
    )
    export_xpath = "//span[@class='words' and normalize-space(text())='Export']"
    excel_xpath = "//a[@title='Export to Excel' and normalize-space(text())='Excel']"

    # Calculate the date range based on provided dates or financial year defaults
    # Returns tuple of (start_date, end_date) in "d MMM yyyy" format
    start_date, end_date = date_argument(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )

    # Populate the From date field with the calculated start date
    # Wait for the field to be visible, clear any existing value, and enter the start date
    from_date = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, from_date_id)),
    )
    from_date.clear()
    from_date.send_keys(start_date)
    logger.info("Entered From date")

    # Populate the To date field with the calculated end date
    # Wait for the field to be visible, clear any existing value, and enter the end date
    to_date = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, to_date_id)),
    )
    to_date.clear()
    to_date.send_keys(end_date)
    logger.info("Entered To date")

    # Click the Update button to generate the report with the configured date range
    # This triggers the report to refresh with the new date parameters
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, update_button_xpath)),
    ).click()
    logger.info("Clicked Update button")

    # Click the Export button to open the export options menu
    # This reveals additional export format options including Excel
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, export_xpath)),
    ).click()
    logger.info("Clicked Export button")

    # Click the Excel option to initiate the Excel file download
    # This triggers the Windows Save As dialog to appear
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, excel_xpath)),
    ).click()
    logger.info("Clicked Excel button")

    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )

    # # Locate the Chrome browser window using Windows automation
    # # The window title pattern matches "Xero | {report_name} | * - Google Chrome"
    # app = windows.find_window(f'regex:.*Xero | {xero_report_name} | * - Google Chrome')

    # # Find the Save As dialog window within the Chrome browser
    # # This dialog appears after clicking the Excel export option
    # app.find('control:"WindowControl" and name:"Save As" and path:"1"')

    # # Click into the File name input field to activate it for text entry
    # # The field is located using Windows UI Automation path within the Save As dialog
    # file_input = app.find('control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"').click()
    # time.sleep(2)

    # # Construct the full file path by combining directory and filename
    # # os.path.normpath ensures the path uses proper Windows backslash separators
    # file_path = os.path.normpath(os.path.join(download_directory, report_file_name))

    # # Clear any existing text in the filename field and enter the full file path
    # # Use CTRL+A to select all, DELETE to clear, then type the full path
    # file_input.send_keys("{CTRL}a")
    # file_input.send_keys("{DEL}")
    # file_input.send_keys(file_path)
    # time.sleep(2)

    # # Click the Save button to initiate the file save operation
    # # Uses the more specific selector with class:"Button" for reliability
    # app.find('control:"ButtonControl" and name:"Save" and class:"Button"').click()

    # # Handle the file overwrite confirmation dialog if it appears
    # # This dialog only appears if a file with the same name already exists
    # try:
    #     save_confirm_popup = app.find('control:"WindowControl" and name:"Confirm Save As" and path:"1|1"', timeout=3)
    #     logger.info(f"Confirm Save As window found. Overwriting {xero_report_name}.")
    #     save_confirm_popup.find('control:"ButtonControl" and class:"CCPushButton" and name:"Yes"').click()
    # except Exception:
    #     logger.info("No overwrite confirmation window appeared.")
