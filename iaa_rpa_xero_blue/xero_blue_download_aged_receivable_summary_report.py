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


def xero_blue_download_aged_receivables_summary_report(
    browser,
    client_name: str,
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
    Download Aged Receivables Summary report from Xero Blue.

    Orchestrates the complete workflow for downloading an Aged Receivables Summary report
    from Xero Blue. This includes determining the appropriate date range (custom or default
    financial year end), configuring report parameters such as aging method and GST column
    visibility, updating the report with these settings, and exporting it to Excel format
    via automated Windows Save As dialog handling.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for interacting
            with the Xero web application.
        client_name (str): Name of the client organization for logging and audit trail purposes.
        end_date (str): Report end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty string, defaults to '30 Jun {financial_year}'.
        financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            calculate default end date (30 Jun YYYY) when end_date is not provided.
        is_add_gst_column (bool): Flag indicating whether to include the 'Tax Amount Due'
            column in the exported report showing GST/tax amounts.
        xero_aging_by (str): Aging calculation method. Valid values are:
            - 'Due Date': Age receivables based on invoice due date.
            - 'Invoice Date': Age receivables based on invoice date.
            - 'Transaction Date': Age receivables based on transaction date.
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Absolute or relative directory path where the
            Excel report file will be saved (e.g., 'C:\\Reports' or './output').
        report_file_name (str): Filename for the saved report including .xlsx extension
            (e.g., 'Aged_Receivables_Summary_2024.xlsx').
        extension (str): File extension for the report (e.g., '.xlsx').

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
        >>> xero_blue_download_aged_receivables_summary_report(
        ...     browser=my_browser,
        ...     client_name="ACME Corp",
        ...     end_date="31 Dec 2024",
        ...     financial_year="2024",
        ...     is_add_gst_column=True,
        ...     xero_aging_by="Due Date",
        ...     window_title="Aged Receivables Summary",
        ...     download_directory="C:\\Reports",
        ...     report_file_name="ACME_Receivables_Summary_2024.xlsx",
        ...     extension=".xlsx"
        ... )
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Aged Receivables Summary Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name: {client_name}")
    logger.info(f"End Date: {end_date if end_date else f'30 Jun {financial_year}'}")
    logger.info(f"Financial Year: {financial_year}")
    logger.info(f"Add GST Column: {is_add_gst_column}")
    logger.info(f"Aging By: {xero_aging_by}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info("=" * 80)

    try:

        # STEP 1: Resolve Report End Date
        # Purpose: Determine the correct end date to use for the report
        # Function: resolve_report_end_date()
        # - Checks whether a custom end_date was provided by the caller
        # - Falls back to the financial year end date (30 Jun YYYY) if not provided
        # - Delegates to configure_report_date_and_aging() with the resolved date
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
            f"COMPLETED: Xero Blue Download Aged Receivables Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: SUCCESS")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Aged Receivables Summary Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
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
    Resolve the report end date and delegate to report configuration.

    Evaluates the provided end_date parameter and determines whether to use it as-is
    or construct a default end date based on the financial year. For Australian financial
    years, defaults to 30 Jun of the specified year (e.g., '30 Jun 2024' for FY 2024).
    After resolving the appropriate end date, delegates to configure_report_date_and_aging()
    for UI configuration.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for web interactions.
        end_date (str): Custom end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty/None, automatically calculates '30 Jun {financial_year}'.
        financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            construct default end date when end_date is not provided.
        is_add_gst_column (bool): Flag indicating whether to include the 'Tax Amount Due'
            column in the report output.
        xero_aging_by (str): Aging calculation method - 'Due Date', 'Invoice Date', or
            'Transaction Date'.
        window_title (str): Browser window title used to locate the Save As dialog.
        download_directory (str): Target directory path for saving the Excel report file.
        report_file_name (str): Output filename including .xlsx extension.
        extension (str): File extension for the report (e.g., '.xlsx').

    Returns:
        None: This function orchestrates the workflow but does not return a value.

    Note:
        The function includes a 1-second sleep to allow the report page to stabilize
        after any navigation or page load operations before proceeding with configuration.
    """
    logger.info("Resolving report end date based on input parameters...")

    if not end_date:
        str_end_date = f"30 Jun {financial_year}"
        logger.info(
            f"No custom end date provided. Defaulting to financial year end date: {str_end_date}",
        )
    else:
        str_end_date = end_date
        logger.info(f"Custom end date provided. Using: {str_end_date}")

    logger.info("Waiting 1 second for report page to stabilize before configuration...")
    time.sleep(1)

    # STEP 2: Configure Report Date and Aging Method
    # Purpose: Populate the report settings UI with the resolved date and aging method
    # Function: configure_report_date_and_aging()
    # - Enters the resolved end date into the report date input field
    # - Opens the aging method dropdown and selects the specified option
    # - Validates the aging option exists before attempting selection
    # - Delegates to configure_gst_column_and_export() for next steps
    configure_report_date_and_aging(
        browser,
        str_end_date,
        is_add_gst_column,
        xero_aging_by,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def configure_report_date_and_aging(
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
    Configure the report end date and aging method in the Xero Blue UI.

    Interacts with Xero's report settings interface to populate the end date input field
    and select the aging calculation method from the dropdown. Uses Selenium WebDriverWait
    with explicit waits (10 seconds for date field, 5 seconds for aging dropdown) to ensure
    elements are visible before interaction. Validates that the requested aging method exists
    in the dropdown before attempting selection, gracefully handling cases where options are
    unavailable. Delegates to configure_gst_column_and_export() for subsequent GST
    configuration and export.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the Xero report settings page.
        str_end_date (str): Resolved end date string in 'DD MMM YYYY' format
            (e.g., '30 Jun 2024'). Entered into the report-settings-custom-date-input-to field.
        is_add_gst_column (bool): Flag passed to downstream functions indicating whether
            to add the 'Tax Amount Due' column to the report.
        xero_aging_by (str): Aging calculation method to select from dropdown.
            Expected values: 'Due Date', 'Invoice Date', or 'Transaction Date'.
        window_title (str): Browser window title used to locate the Save As dialog.
        download_directory (str): Target directory path for report file, passed to
            downstream export functions.
        report_file_name (str): Output filename including extension, passed to downstream
            export functions.
        extension (str): File extension for the report (e.g., '.xlsx').

    Returns:
        None: This function performs UI interactions but does not return a value.

    Raises:
        Exception: If any step fails including:
            - TimeoutException if date field or aging dropdown cannot be located within wait time.
            - NoSuchElementException if date input field cannot be found after initial wait.
            - General exceptions from UI interaction failures, all re-raised with logging.
    """
    try:
        driver = browser.driver
        wait = WebDriverWait(driver, 10)
        logger.info("Starting report date and aging method configuration...")

        custom_date_id = (By.ID, "report-settings-custom-date-input-to")

        # Locate the end date input field and enter the resolved end date
        logger.info(f"Locating end date input field and entering date: {str_end_date}")
        input_field = wait.until(EC.visibility_of_element_located(custom_date_id))
        input_field.send_keys("\ue009" + "a")  # CTRL + A to select all existing text
        input_field.send_keys("\ue003")  # DELETE to clear the field
        input_field.send_keys(str_end_date)  # Type the resolved end date
        input_field.send_keys("\ue004")  # TAB to confirm and move to next field
        logger.info(
            f"End date '{str_end_date}' entered successfully into the report date field",
        )

        # Open the aging method dropdown to access available options
        logger.info(f"Opening aging method dropdown to select: '{xero_aging_by}'")
        ageing_button_xpath = "//button[contains(@class,'xui-select--button')][.//span[contains(@class,'xui-select--content-truncated')]]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_button_xpath)),
        ).click()
        logger.info("Aging method dropdown opened successfully")

        # Build the XPath to locate the specific aging option in the dropdown
        ageing_option_xpath = f"//button[contains(@class,'xui-pickitem--body') and .//span[normalize-space()='{xero_aging_by}']]"

        # STEP 3: Validate Aging Option Availability
        # Purpose: Confirm the requested aging method exists in the dropdown before clicking
        # Function: check_aging_option_exists()
        # - Uses WebDriverWait to check for the option within 5 seconds
        # - Returns True if found, False if not found or timed out
        # - Prevents NoSuchElementException when option is unavailable
        if check_aging_option_exists(driver, ageing_option_xpath, xero_aging_by):
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
            ).click()
            logger.info(
                f"Aging method '{xero_aging_by}' selected successfully from dropdown",
            )
        else:
            logger.warning(
                f"Aging method '{xero_aging_by}' not found in dropdown. Proceeding with the current default selection.",
            )

        # STEP 4: Configure GST Column and Initiate Export
        # Purpose: Optionally add the GST column and proceed to export the report
        # Function: configure_gst_column_and_export()
        # - Checks the is_add_gst_column flag
        # - If True: opens columns menu and selects 'Tax Amount Due' checkbox
        # - Delegates to update_and_export_to_excel() regardless of GST setting
        logger.info(
            "Date and aging configuration complete. Proceeding to GST column configuration...",
        )
        configure_gst_column_and_export(
            browser,
            is_add_gst_column,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )

    except Exception as e:
        logger.error(
            f"Failed to configure report date and aging parameters: {str(e)}",
            exc_info=True,
        )
        raise


def check_aging_option_exists(driver, ageing_option_xpath, xero_str_aging_by) -> bool:
    """
    Verify whether the specified aging option exists in the dropdown menu.

    Attempts to locate the aging method option in the Xero UI dropdown using a WebDriverWait
    with a 5-second timeout. This validation step prevents NoSuchElementException errors by
    confirming the element exists and is visible before attempting to click it. Returns a
    boolean result that the calling function uses to decide whether to proceed with selection
    or log a warning and skip.

    Args:
        driver: Selenium WebDriver instance with access to the current browser page containing
            the aging method dropdown menu.
        ageing_option_xpath (str): XPath selector string targeting the specific aging option
            button element in the dropdown
            (e.g., "//button[...and .//span[normalize-space()='Due Date']]").
        xero_str_aging_by (str): Human-readable name of the aging method being validated
            (e.g., 'Due Date', 'Invoice Date', or 'Transaction Date'). Used for logging only.

    Returns:
        bool: True if the aging option element is visible within 5 seconds.
              False if the element is not found or does not become visible within the timeout.

    Note:
        All exceptions during the wait period are caught and treated as "element not found"
        scenarios, returning False without raising. This allows the workflow to continue
        with the current default when a specific option is unavailable.
    """
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, ageing_option_xpath)),
        )
        logger.info(
            f"Aging option '{xero_str_aging_by}' found and visible in the dropdown",
        )
        return True

    except Exception:
        logger.warning(
            f"Aging option '{xero_str_aging_by}' was not found in the dropdown within the timeout period",
        )
        return False


def configure_gst_column_and_export(
    browser,
    is_add_gst_column,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Conditionally configure the GST column and proceed to report export.

    Optionally adds the 'Tax Amount Due' column to the Aged Receivables Summary report
    based on the is_add_gst_column flag. If enabled, locates and clicks the columns settings
    button by ID, selects the 'Tax Amount Due' checkbox (also by ID), then closes the dropdown
    to apply changes. Uses WebDriverWait with a 10-second timeout for all element interactions.
    Regardless of GST configuration, delegates to update_and_export_to_excel() to complete
    the report generation and file download workflow.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the Xero report settings page.
        is_add_gst_column (bool): Flag controlling GST column inclusion. If True, opens the
            columns menu and selects 'Tax Amount Due'. If False, skips GST configuration entirely.
        window_title (str): Browser window title used to locate the Save As dialog during export.
        download_directory (str): Target directory path for the Excel file, passed to
            the export function.
        report_file_name (str): Output filename including .xlsx extension, passed to the
            export function.
        extension (str): File extension for the report (e.g., '.xlsx').

    Returns:
        None: This function performs UI interactions and delegates to the export workflow.

    Raises:
        TimeoutException: If the columns button (report-settings-columns-button) or
            Tax Amount Due checkbox (column-selection-taxamountdue) cannot be located
            within 10 seconds when is_add_gst_column is True.

    Note:
        Element IDs are used rather than XPath selectors, making interactions more resilient
        to UI layout changes but requiring exact ID matches in the Xero UI.
    """
    driver = browser.driver
    wait = WebDriverWait(driver, 10)

    gst_column_id = (By.ID, "report-settings-columns-button")
    gst_checkbox_id = (By.ID, "column-selection-taxamountdue")

    if is_add_gst_column:
        logger.info("GST column addition is enabled. Opening columns settings menu...")

        # Open the columns dropdown to reveal available column options
        wait.until(EC.visibility_of_element_located(gst_column_id)).click()
        logger.info("Columns settings menu opened successfully")

        # Select the 'Tax Amount Due' checkbox to add the GST column to the report
        wait.until(EC.visibility_of_element_located(gst_checkbox_id)).click()
        logger.info("'Tax Amount Due' (GST) checkbox selected successfully")

        # Close the columns dropdown to apply the column selection
        wait.until(EC.visibility_of_element_located(gst_column_id)).click()
        logger.info(
            "Columns settings menu closed. GST column configuration applied successfully.",
        )
    else:
        logger.info(
            "GST column addition is disabled (is_add_gst_column=False). Skipping GST column configuration.",
        )

    # STEP 5: Update Report and Export to Excel
    # Purpose: Apply all configured settings and download the report as an Excel file
    # Function: update_and_export_to_excel()
    # - Clicks the 'Update' button to apply date, aging, and column settings
    # - Clicks 'Export' to open the export format menu
    # - Clicks 'Excel' to trigger the file download
    # - Handles the Windows Save As dialog to save the file to the target directory
    logger.info(
        "GST configuration complete. Proceeding to update report and export to Excel...",
    )
    update_and_export_to_excel(
        browser,
        window_title,
        download_directory,
        report_file_name,
        extension,
    )


def update_and_export_to_excel(
    browser,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Apply all report settings and export the report to an Excel file.

    Finalizes the report generation workflow by clicking the 'Update' button to apply all
    configured settings (date range, aging method, GST column), then initiating Excel export
    via the 'Export' and 'Excel' buttons. Uses Selenium WebDriverWait with a 10-second timeout
    for all button interactions. After triggering the download, delegates to download_file()
    to handle the Windows Save As dialog, construct the full file path, and save the report
    to the specified directory.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to the
            Xero report page configured with all necessary parameters.
        window_title (str): Browser window title used by download_file() to locate the
            correct Chrome window for Save As dialog handling.
        download_directory (str): Absolute or relative directory path where the Excel
            file will be saved (e.g., 'C:\\Reports' or './output').
        report_file_name (str): Filename for the saved report including .xlsx extension
            (e.g., 'Aged_Receivables_Summary_2024.xlsx').
        extension (str): File extension for the report (e.g., '.xlsx').

    Returns:
        None: This function performs file download operations but does not return a value.

    Raises:
        TimeoutException: If the Update, Export, or Excel buttons cannot be located or
            clicked within the 10-second wait timeout.
        Exception: If download_file() fails to locate the browser window, Save As dialog,
            or encounters errors writing the file to disk.

    Note:
        A 2-second sleep is applied after clicking 'Excel' to allow the Save As dialog
        to fully appear before download_file() attempts to interact with it.
    """
    driver = browser.driver
    wait = WebDriverWait(driver, 10)
    logger.info("Starting report update and Excel export process...")

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

    # Click 'Update' to apply all configured report settings (date, aging method, columns)
    logger.info(
        "Clicking 'Update' button to apply all report settings (date, aging method, GST column)...",
    )
    wait.until(EC.element_to_be_clickable(update_xpath)).click()
    logger.info(
        "'Update' button clicked successfully. Report is refreshing with the configured settings...",
    )

    # Click 'Export' to open the export format selection menu
    logger.info("Clicking 'Export' button to open the export format menu...")
    wait.until(EC.element_to_be_clickable(export_xpath)).click()
    logger.info("Export format menu opened successfully")

    # Click 'Excel' to trigger the file download and open the Save As dialog
    logger.info("Selecting 'Excel' format to initiate the file download...")
    wait.until(EC.element_to_be_clickable(excel_xpath)).click()
    logger.info(
        "Excel export triggered. Waiting 2 seconds for the Save As dialog to appear...",
    )

    time.sleep(2)

    # Handle the Windows Save As dialog and save the file to the target directory
    logger.info(
        f"Handling Save As dialog to save report to: {download_directory}\\{report_file_name}",
    )
    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    logger.info(
        f"Report successfully saved as '{report_file_name}' in '{download_directory}'",
    )
