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


def xero_blue_download_aged_receivables_detail_report(
    browser,
    xero_client_name: str,
    end_date: str,
    financial_year: str,
    is_add_gst_column: bool,
    xero_aging_by: str,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: str,
):
    """
    Download aged receivables detail report from Xero Blue.

    Orchestrates the complete workflow for downloading an aged receivables detail report
    from Xero Blue. This includes determining the appropriate date range, configuring
    report parameters (aging method, GST column), updating the report, and exporting
    it to Excel format via the Windows Save As dialog.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for interacting
            with the Xero web application.
        xero_client_name (str): Name of the client organization for logging and audit purposes.
        end_date (str): Report end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty string, defaults to '30 Jun {financial_year}'.
        financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            calculate default date range when end_date is not provided.
        is_add_gst_column (bool): Flag indicating whether to include the 'Outstanding GST'
            column in the exported report.
        xero_aging_by (str): Aging calculation method. Valid values are:
            - 'Due Date': Age invoices based on their due date.
            - 'Invoice Date': Age invoices based on their invoice date.
            - 'Transaction Date': Age invoices based on transaction date.
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Absolute or relative directory path where the
            Excel report file will be saved.
        report_file_name (str): Filename for the saved report, including .xlsx extension
            (e.g., 'Aged_Receivables_Detail_2024.xlsx').
        extension (str): File extension for the exported report (e.g., '.xlsx').

    Returns:
        None: This function performs actions and saves files but does not return a value.

    Raises:
        Exception: If any step fails including:
            - Date field population errors.
            - Aging method selection failures.
            - GST column configuration issues.
            - Export button interaction failures.
            - Windows Save As dialog handling errors.
            - File save operation failures.

    Example:
        >>> xero_blue_download_aged_receivablesdetailreport(
        ...     browser=my_browser,
        ...     xero_client_name="ACME Corp",
        ...     end_date="31 Dec 2024",
        ...     financial_year="2024",
        ...     is_add_gst_column=True,
        ...     xero_aging_by="Due Date",
        ...     window_title="Aged Receivables Detail",
        ...     download_directory="C:\\Reports",
        ...     report_file_name="ACME_Receivables_2024.xlsx",
        ...     extension=".xlsx"
        ... )
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue - Download Aged Receivables Detail Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name: {xero_client_name}")
    logger.info(
        f"End Date: {end_date if end_date else f'30 Jun {financial_year} (default)'}",
    )
    logger.info(f"Financial Year: {financial_year}")
    logger.info(f"Add GST Column: {is_add_gst_column}")
    logger.info(f"Aging By: {xero_aging_by}")
    logger.info(f"Window Title: {window_title}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"Extension: {extension}")
    logger.info("=" * 80)

    try:
        # STEP 1: Resolve Report End Date
        # Purpose: Determine the correct end date — either from user input or defaulting
        #          to the financial year end date (30 Jun {financial_year})
        # Function: resolve_report_end_date()
        # - Checks if a custom end_date was provided
        # - Falls back to '30 Jun {financial_year}' if end_date is empty
        # - Proceeds to configure report parameters with the resolved date
        resolve_report_end_date(
            browser,
            end_date,
            financial_year,
            is_add_gst_column,
            xero_aging_by,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue - Download Aged Receivables Detail Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Report Saved To: {download_directory}\\{report_file_name}")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue - Download Aged Receivables Detail Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def resolve_report_end_date(
    browser,
    end_date,
    financial_year,
    is_add_gst_column,
    xero_aging_by,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Resolve the report end date and delegate to report parameter configuration.

    Evaluates the provided end_date parameter and determines whether to use it directly
    or calculate the default financial year end date (30 Jun {financial_year}). For
    Australian financial years, the default period is 1 Jul (previous year) to 30 Jun
    (current year). After resolving the date, delegates to configure_report_dates_and_aging()
    for UI configuration.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for web interactions.
        end_date (str): Custom end date in 'DD MMM YYYY' format. If empty or None, the
            function automatically calculates '30 Jun {financial_year}' as the default.
        financial_year (str): Financial year as a 4-digit string (e.g., '2024'). Used to
            calculate the default start date (1 Jul previous year) and end date (30 Jun current year).
        is_add_gst_column (bool): Flag indicating whether to include the 'Outstanding GST'
            column in the report output.
        xero_aging_by (str): Aging calculation method - 'Due Date', 'Invoice Date', or
            'Transaction Date'.
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Target directory path for saving the Excel report file.
        report_file_name (str): Output filename including .xlsx extension.
        extension (str): File extension for the exported report.

    Returns:
        None: This function orchestrates the workflow but does not return a value.

    Note:
        The financial year calculation assumes Australian financial year convention where
        FY 2024 runs from 1 Jul 2023 to 30 Jun 2024.
    """
    logger.info("Resolving report end date...")

    if not end_date:
        str_start_date = f"1 Jul {int(financial_year) - 1}"
        str_end_date = f"30 Jun {financial_year}"
        logger.info(
            f"No custom end date provided. Using default financial year date range:",
        )
        logger.info(f"  Start Date: {str_start_date}")
        logger.info(f"  End Date  : {str_end_date}")
    else:
        str_end_date = end_date
        logger.info(f"Custom end date provided: {str_end_date}")

    logger.info(f"Resolved end date: {str_end_date}")

    # STEP 2: Configure Report Dates and Aging Method
    # Purpose: Populate the end date field and select the aging method in the Xero report UI
    # Function: configure_report_dates_and_aging()
    # - Enters the resolved end date into the date input field
    # - Opens the aging method dropdown
    # - Verifies and selects the requested aging option (Due Date / Invoice Date / Transaction Date)
    # - Proceeds to GST column configuration
    configure_report_dates_and_aging(
        browser,
        str_end_date,
        is_add_gst_column,
        xero_aging_by,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def configure_report_dates_and_aging(
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
    Configure the report end date and aging method parameters in the Xero Blue UI.

    Interacts with Xero's report settings interface to populate the end date input field
    and select the aging calculation method from the dropdown. Uses Selenium WebDriver to
    locate fields, clear existing values, enter new date values, and select dropdown options.
    Validates that the requested aging method exists before attempting selection, and
    gracefully handles missing options. Delegates to configure_gst_column() for subsequent
    GST configuration.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the current Xero report page.
        str_end_date (str): End date string in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            This value is entered into the report settings custom date input field.
        is_add_gst_column (bool): Flag passed to downstream functions indicating whether
            to add the 'Outstanding GST' column to the report.
        xero_aging_by (str): Aging calculation method to select from dropdown. Expected values:
            'Due Date', 'Invoice Date', or 'Transaction Date'. The function verifies this
            option exists before selection.
        window_title (str): Title of the browser window passed to downstream export functions.
        download_directory (str): Target directory path for report file, passed to
            downstream export functions.
        report_file_name (str): Output filename including extension, passed to downstream
            export functions.
        extension (str): File extension for the exported report.

    Returns:
        None: This function performs UI interactions but does not return a value.

    Raises:
        TimeoutException: If date field or aging dropdown elements cannot be located within
            the specified wait time (10 seconds for date field, 5 seconds for dropdown).
        NoSuchElementException: If the date input field cannot be found after initial wait.
    """
    driver = browser.driver
    logger.info("Configuring report date and aging method parameters in Xero UI...")

    custom_date_id = "//input[@id='report-settings-custom-date-input-to']"

    # Locate and populate the report end date field
    logger.info(f"Entering report end date: {str_end_date}")
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, custom_date_id)),
    ).click()
    logger.info("End date input field clicked and focused")
    time.sleep(1)

    input_field = driver.find_element(By.XPATH, custom_date_id)
    input_field.send_keys("\ue009" + "a")  # CTRL + A to select all
    input_field.send_keys("\ue003")  # DELETE to clear existing value
    input_field.send_keys(str_end_date)  # Type the resolved end date
    input_field.send_keys("\ue004")  # TAB to confirm and move to next field
    logger.info(f"End date entered successfully: {str_end_date}")

    # Open the aging method dropdown to reveal available options
    logger.info(f"Opening aging method dropdown to select: '{xero_aging_by}'")
    ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, ageing_button_xpath)),
    ).click()
    logger.info("Aging method dropdown opened")

    ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"

    # STEP 2a: Verify Aging Option Exists
    # Purpose: Confirm the requested aging method is available in the dropdown before clicking
    # Function: verify_aging_option_exists()
    # - Waits up to 5 seconds for the option to appear
    # - Returns True if visible, False if not found or timed out
    if verify_aging_option_exists(driver, ageing_option_xpath, xero_aging_by):
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        ).click()
        logger.info(f"Aging method selected successfully: '{xero_aging_by}'")
    else:
        logger.warning(
            f"Aging method '{xero_aging_by}' not found in dropdown. Proceeding with current default selection.",
        )

    # STEP 3: Configure GST Column
    # Purpose: Optionally add the 'Outstanding GST' column to the report based on the flag
    # Function: configure_gst_column()
    # - Opens the columns dropdown if GST column is requested
    # - Selects 'Outstanding GST' checkbox option
    # - Closes the dropdown to apply the change
    # - Proceeds to update and export the report
    logger.info("Handing off to GST column configuration...")
    configure_gst_column(
        browser,
        is_add_gst_column,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def verify_aging_option_exists(driver, ageing_option_xpath, xero_str_aging_by) -> bool:
    """
    Verify whether the specified aging method option exists in the Xero dropdown menu.

    Attempts to locate the aging option element in the open dropdown using a WebDriverWait
    with a 5-second timeout. This check prevents NoSuchElementException errors by confirming
    the element is visible before the caller attempts to click it. Returns a boolean result
    used by the calling function to decide whether to proceed with selection or log a warning.

    Args:
        driver: Selenium WebDriver instance pointing to the current browser page with the
            aging method dropdown already open.
        ageing_option_xpath (str): XPath selector targeting the specific aging option button
            in the dropdown (e.g., "//button[...and .//span[normalize-space()='Due Date']]").
        xero_str_aging_by (str): Human-readable label of the aging method being verified
            (e.g., 'Due Date', 'Invoice Date', 'Transaction Date'). Used for log messages only.

    Returns:
        bool: True if the aging option element is visible within 5 seconds,
              False if the element is not found or does not become visible within the timeout.

    Note:
        All exceptions are caught internally and treated as "not found" — the function
        returns False without raising, allowing the workflow to continue gracefully with
        the default dropdown selection when a specific option is unavailable.
    """
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        )
        logger.info(f"Aging option '{xero_str_aging_by}' found in dropdown")
        return True

    except Exception:
        logger.warning(
            f"Aging option '{xero_str_aging_by}' not found in dropdown within timeout",
        )
        return False


def configure_gst_column(
    browser,
    is_add_gst_column,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Configure the 'Outstanding GST' column visibility and proceed to report export.

    Conditionally adds the 'Outstanding GST' column to the aged receivables report based
    on the is_add_gst_column flag. If enabled, opens the column settings dropdown, selects
    the 'Outstanding GST' checkbox option, and closes the menu to apply changes. Regardless
    of GST configuration outcome, delegates to update_and_export_report() to complete the
    report generation and file download workflow.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the Xero report settings page.
        is_add_gst_column (bool): Controls GST column inclusion. If True, the function opens
            the columns menu and selects 'Outstanding GST'. If False, skips GST configuration.
        window_title (str): Title of the browser window used to locate the Save As dialog,
            passed to the export function.
        download_directory (str): Target directory path for the Excel file, passed to
            the export function.
        report_file_name (str): Output filename including .xlsx extension, passed to the
            export function.
        extension (str): File extension for the exported report.

    Returns:
        None: This function performs UI interactions and delegates to the export workflow.

    Raises:
        TimeoutException: If the columns button or 'Outstanding GST' option cannot be located
            within 5 seconds when is_add_gst_column is True.
    """
    driver = browser.driver
    gst_button = "//*[@id='report-settings-columns-button']"
    outstanding_gst_xpath = "//span[contains(@class,'xui-pickitem-multiselect--label')][.//span[normalize-space()='Outstanding GST']]"

    if is_add_gst_column:
        logger.info("GST column addition requested. Opening columns settings menu...")

        # Open the columns dropdown to access column visibility options
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()
        logger.info("Columns settings menu opened")

        # Select the 'Outstanding GST' checkbox to add the GST column to the report
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, outstanding_gst_xpath)),
        ).click()
        logger.info("'Outstanding GST' option selected")

        # Close the columns menu to confirm and apply the column selection
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, gst_button)),
        ).click()
        logger.info("Columns settings menu closed. GST column added successfully.")
    else:
        logger.info(
            "GST column not requested (is_add_gst_column=False). Skipping GST configuration.",
        )

    # STEP 4: Update Report and Export to Excel
    # Purpose: Apply all configured settings and download the report as an Excel file
    # Function: update_and_export_report()
    # - Clicks 'Update' to refresh the report with all configured parameters
    # - Clicks 'Export' to open the export format menu
    # - Selects 'Excel' to trigger the file download
    # - Handles the Windows Save As dialog to save the file to the target directory
    logger.info("Proceeding to update report and initiate Excel export...")
    update_and_export_report(
        browser,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def update_and_export_report(
    browser,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Apply report settings, export to Excel, and save the file via the Save As dialog.

    Finalizes the report generation by clicking 'Update' to apply all configured parameters
    (date range, aging method, GST column), then triggers Excel export through the Export menu.
    Delegates to download_file() to handle the Windows Save As dialog — locating the dialog,
    entering the target file path, and confirming the save operation including any file
    overwrite prompts.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to the
            Xero report page fully configured with all necessary parameters.
        window_title (str): Title of the browser window used by robocorp.windows to locate
            the correct Chrome window for the Save As dialog interaction.
        download_directory (str): Absolute or relative directory path where the Excel
            file will be saved (e.g., 'C:\\Reports' or './output').
        report_file_name (str): Filename for the saved report including .xlsx extension
            (e.g., 'Aged_Receivables_Detail_2024.xlsx').
        extension (str): File extension for the exported report (e.g., '.xlsx').

    Returns:
        None: This function performs file download operations but does not return a value.

    Raises:
        TimeoutException: If the Update, Export, or Excel buttons cannot be located within
            10 seconds.
        Exception: If the Chrome window cannot be found, or if the Save As dialog or its
            child elements (file name field, Save button) cannot be located.
        OSError: If download_directory does not exist or is not accessible.
    """
    driver = browser.driver
    logger.info("Starting report update and Excel export process...")

    update_xpath = "//button[@type='button' and normalize-space(text())='Update']"
    export_xpath = "//button[@type='button' and normalize-space(text())='Export']"
    excel_xpath = "//button[@type='button']//span[normalize-space(text())='Excel']"

    # Click 'Update' to apply all configured report parameters (date, aging method, columns)
    logger.info("Clicking 'Update' button to apply report configuration...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, update_xpath)),
    ).click()
    logger.info("'Update' button clicked. Report is refreshing with new parameters...")

    # Click 'Export' to open the file format selection menu
    logger.info("Clicking 'Export' button to open export format menu...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, export_xpath)),
    ).click()
    logger.info("Export format menu opened successfully")

    # Select 'Excel' to trigger the file download and open the Save As dialog
    logger.info("Selecting 'Excel' format to initiate file download...")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, excel_xpath)),
    ).click()
    logger.info(
        "Excel export triggered. Waiting for Windows Save As dialog to appear...",
    )

    # Handle the Windows Save As dialog to specify file path and save the report
    logger.info(f"Saving report to: {download_directory}\\{report_file_name}")
    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    logger.info(f"Report file saved successfully: {report_file_name}")
