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


def xero_blue_download_aged_payables_summary_reports(
    browser,
    client_name,
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
    Download Xero Aged Payables Summary report with specified parameters.

    This function orchestrates the complete process of downloading an Aged Payables Summary
    report from Xero Blue. It configures report parameters including date range, aging method,
    GST column inclusion, and handles the file download to the specified directory.

    Args:
        browser: Browser instance with active Selenium WebDriver
        client_name (str): Name of the Xero client for logging purposes
        xero_end_date (str): Report end date (format: 'DD MMM YYYY'). If empty, defaults to financial year end
        xero_financial_year (str): Financial year (e.g., '2024') used when xero_end_date is not provided
        is_add_gst_column (bool): Whether to include Outstanding GST column in the report
        xero_aging_by (str): Aging method - 'Due date' or 'Invoice date'
        download_directory (str): Directory path where the report will be saved
        report_file_name (str): Name for the downloaded report file (without extension)
        xero_report_name (str): Display name of the report for logging and UI identification

    Returns:
        None

    Raises:
        Exception: If any step in the download process fails
    """
    # Initialize process timing and logging
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("XERO BLUE DOWNLOAD AGED PAYABLES SUMMARY REPORT PROCESS STARTED")
    logger.info("=" * 80)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client name: {client_name}")
    logger.info(
        f"End Date: {xero_end_date if xero_end_date else f'30 Jun {xero_financial_year}'}",
    )
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Add GST Column: {is_add_gst_column}")
    logger.info(f"Aging By: {xero_aging_by}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"File Download Path: {download_directory}")
    logger.info("")

    try:
        # Configure report parameters (date, aging method, GST column) and initiate download
        # This function handles setting the end date, selecting aging method, adding GST column if needed,
        # and triggering the export process
        logger.info("Configuring report date parameters and filters...")
        set_date_parameters(
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
        logger.info("XERO BLUE DOWNLOAD AGED PAYABLES SUMMARY REPORT PROCESS COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)
        logger.info("")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(
            "XERO BLUE DOWNLOAD AGED PAYABLES SUMMARY REPORT PROCESS FAILED - EXCEPTION",
        )
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error("=" * 80)
        raise


def set_date_parameters(
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
    Configure report date parameters and aging method for Aged Payables Summary.

    This function sets up the report's end date and aging method (Due date or Invoice date).
    If no end date is provided, it defaults to the financial year end date (30 Jun YYYY).
    After setting these parameters, it proceeds to configure the GST column option.

    Args:
        browser: Browser instance with active Selenium WebDriver
        xero_end_date (str): Report end date (format: 'DD MMM YYYY'). If empty, defaults to '30 Jun {xero_financial_year}'
        xero_financial_year (str): Financial year used for default end date calculation
        is_add_gst_column (bool): Whether to include Outstanding GST column in the report
        xero_aging_by (str): Aging method - 'Due date' or 'Invoice date'
        download_directory (str): Directory path where the report will be saved
        report_file_name (str): Name for the downloaded report file
        xero_report_name (str): Display name of the report for logging

    Returns:
        None
    """
    driver = browser.driver
    logger.info("Setting date parameters and aging method...")

    # If no end date provided, default to the financial year end date
    if not xero_end_date:
        xero_end_date = f"30 Jun {xero_financial_year}"
        logger.info(f"No end date provided. Using financial year end: {xero_end_date}")

    # Locate and populate the report end date field
    # This field determines the cut-off date for the aged payables calculation
    logger.info(f"Setting report end date to: {xero_end_date}")
    custom_date_id = "report-settings-custom-date-input-to"
    date_input = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, custom_date_id)),
    )
    date_input.click()
    date_input.send_keys("\ue009a")  # CTRL+A
    date_input.send_keys("\ue003")  # BACKSPACE
    date_input.send_keys(xero_end_date)
    date_input.send_keys("\ue004")  # TAB
    logger.info(f"Successfully entered end date: {xero_end_date}")

    # Configure the aging method (Due date or Invoice date)
    # This determines how overdue amounts are calculated
    logger.info(f"Configuring aging method: {xero_aging_by}")

    # Click the aging method dropdown button to reveal options
    ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, ageing_button_xpath)),
    ).click()
    logger.info("Opened aging method dropdown")

    # Prepare XPath for the desired aging option (Due date or Invoice date)
    ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"

    # Verify the aging option exists in the dropdown before attempting to select it
    # This prevents errors if the requested option is not available in the UI
    if is_due_date_or_invoice_exist(driver, ageing_option_xpath, xero_aging_by):
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        ).click()
        logger.info(f"Successfully selected aging method: {xero_aging_by}")
    else:
        logger.warning(
            f"Aging method '{xero_aging_by}' not found in dropdown. Proceeding with default selection.",
        )

    # Proceed to configure GST column settings and initiate export
    # This function will add the Outstanding GST column if requested, then export the report
    logger.info("Proceeding to GST column configuration...")
    set_gst_column(
        browser,
        is_add_gst_column,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def set_gst_column(
    browser,
    is_add_gst_column,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Configure Outstanding GST column visibility and proceed to export.

    This function optionally adds the Outstanding GST column to the report based on user preference.
    It opens the columns menu, selects the GST option if requested, then proceeds to export the report.

    Args:
        browser: Browser instance with active Selenium WebDriver
        is_add_gst_column (bool): Whether to include Outstanding GST column in the report
        download_directory (str): Directory path where the report will be saved
        report_file_name (str): Name for the downloaded report file
        xero_report_name (str): Display name of the report for logging

    Returns:
        None
    """
    driver = browser.driver
    gst_button = "//*[@id='report-settings-columns-button']"
    ouststanding_gst_xpath = "//span[contains(@class,'xui-pickitem-multiselect--label')][.//span[normalize-space()='Outstanding GST']]"

    if is_add_gst_column:
        logger.info("GST column addition requested. Opening columns menu...")

        # Open the columns dropdown menu to access column options
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()
        logger.info("Opened columns dropdown menu")

        # Select the 'Outstanding GST' checkbox option from the menu
        # This adds a column showing GST amounts for each payable
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ouststanding_gst_xpath)),
        ).click()
        logger.info("Selected 'Outstanding GST' option")

        # Close the columns dropdown menu to apply the selection
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()
        logger.info("GST column added successfully. Closing columns menu.")
    else:
        logger.info("GST column not requested. Skipping GST configuration.")

    # Proceed to export the configured report to Excel format
    # This function will update the report, trigger export, and handle the file download
    logger.info("Proceeding to report export...")
    export_to_excel(
        browser,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def export_to_excel(
    browser,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Update the report and export it to Excel format.

    This function finalizes the report by clicking the Update button to apply all configured
    parameters, then initiates the export process by selecting Excel as the output format.
    After triggering the download, it handles the Windows Save As dialog.

    Args:
        browser: Browser instance with active Selenium WebDriver
        download_directory (str): Directory path where the report will be saved
        report_file_name (str): Name for the downloaded report file
        xero_report_name (str): Display name of the report for logging

    Returns:
        None
    """
    driver = browser.driver
    update_btn = "//button[@type='button' and normalize-space(text())='Update']"
    export_btn = "//button[@type='button' and normalize-space(text())='Export']"
    excel_btn = "//button[@type='button']//span[normalize-space(text())='Excel']"

    logger.info("Updating report with configured parameters...")

    # Click 'Update' button to refresh the report with all configured parameters
    # This applies the date range, aging method, and column selections before export
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, update_btn)),
    ).click()
    logger.info("Successfully clicked Update button. Report is being refreshed...")

    # Click 'Export' button to reveal export format options
    # This opens a menu with different export formats (Excel, PDF, etc.)
    logger.info("Opening export options menu...")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, export_btn)),
    ).click()
    logger.info("Export menu opened successfully")

    # Select 'Excel' format from the export options menu
    # This triggers the browser download and opens the Windows Save As dialog
    logger.info("Selecting Excel export format...")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, excel_btn)),
    ).click()
    logger.info("Excel export initiated. Waiting for Save As dialog...")

    # Handle the Windows Save As dialog to specify the download location and filename
    # This function will interact with the native Windows dialog to save the file
    handle_save_as_popup(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )

    logger.info(f"Report export completed successfully: {report_file_name}")


def handle_save_as_popup(
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Handle the Windows Save As dialog to save the downloaded report.

    This function interacts with the native Windows Save As dialog that appears after
    initiating an Excel export from Xero. It locates the Chrome browser window, enters
    the full file path including directory and filename, saves the file, and handles
    potential file overwrite confirmations.

    Args:
        in_str_DownloadDirectory (str): Directory path where the report will be saved
        in_str_ReportFileName (str): Name for the downloaded report file (without path)
        xero_report_name (str): Display name of the report used to identify the Chrome window

    Returns:
        None

    Raises:
        Exception: If the Save As dialog cannot be found or file save operation fails
    """
    logger.info("Handling Windows Save As dialog...")

    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )

    # # Locate the Chrome browser window containing the Xero report
    # # Uses regex pattern to find the window with the specific report name in the title
    # logger.info(f"Searching for Chrome window with report: {xero_report_name}")
    # app = windows.find_window(f'regex:.*Xero | {xero_report_name} | * - Google Chrome')
    # logger.info("Chrome window located successfully")

    # # Find the Save As dialog within the Chrome window
    # app.find('control:"WindowControl" and name:"Save As"')
    # logger.info("Save As dialog found")

    # # Locate the file name input field in the Save As dialog
    # input_field = app.find('control:"EditControl" and class:"Edit" and name:"File name:"')
    # input_field.click()
    # logger.info("File name input field located and clicked")

    # # Construct the full file path by joining directory and filename
    # # Normalize the path to handle different path separators and formats
    # file_path = os.path.normpath(os.path.join(in_str_DownloadDirectory, in_str_ReportFileName))
    # logger.info(f"Constructed file path: {file_path}")

    # # Clear any existing content in the file name field and enter the new path
    # input_field.send_keys("{CTRL}a")
    # input_field.send_keys("{DEL}")
    # input_field.send_keys(file_path)
    # logger.info("File path entered into Save As dialog")
    # time.sleep(1)

    # # Click the Save button to initiate the file save operation
    # app.find('control:"ButtonControl" and name:"Save"').click()
    # logger.info(f"Clicked 'Save' button for file: {file_path}")

    # # Handle potential file overwrite confirmation dialog
    # # This appears if a file with the same name already exists
    # try:
    #     logger.info("Checking for file overwrite confirmation...")
    #     popup = app.find('control:"WindowControl" and name:"Confirm Save As"', timeout=3)
    #     popup.find('control:"ButtonControl" and name:"Yes"').click()
    #     logger.info("File already exists. Confirmed overwrite by clicking 'Yes'.")
    # except Exception:
    #     logger.info("No overwrite confirmation detected. File saved without conflicts.")

    # logger.info(f"Report successfully saved to: {file_path}")


def is_due_date_or_invoice_exist(
    driver,
    ageing_option_xpath,
    xero_str_aging_by,
) -> bool:
    """
    Verify if the specified aging option exists in the dropdown menu.

    This function checks whether the requested aging method (Due date or Invoice date)
    is available in the aging dropdown before attempting to select it. This prevents
    errors when the option is not present in the UI.

    Args:
        driver: Selenium WebDriver instance
        ageing_option_xpath (str): XPath selector for the aging option element
        xero_str_aging_by (str): The aging method being validated ('Due date' or 'Invoice date')

    Returns:
        bool: True if the aging option exists in the dropdown, False otherwise
    """
    try:
        # Wait for the aging option to be visible in the dropdown
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        )
        logger.info(f"{xero_str_aging_by} is exist in the drop down")
        return True

    except Exception:
        # Option not found in dropdown within timeout period
        logger.info(f"{xero_str_aging_by} does not exist in the drop down")
        return False
