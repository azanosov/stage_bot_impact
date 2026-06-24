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


def xero_blue_download_bank_reconciliation_report(
    browser,
    client_name,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
    xero_bank_account,
    window_title,
    download_directory,
    report_file_name,
    xero_report_name,
    is_no_bank_accounts,
    extension,
):
    """
    Download Bank Reconciliation report from Xero Blue.

    Orchestrates the complete workflow for downloading a Bank Reconciliation report from
    Xero Blue. This includes checking if bank accounts exist, determining the appropriate
    date range (custom or default financial year), configuring the bank account selection,
    updating the report with these settings, and exporting it to Excel format via automated
    Windows Save As dialog handling.

    Args:
        browser: Browser instance containing an active Selenium WebDriver for interacting
            with the Xero web application.
        client_name (str): Name of the client organization for logging and audit trail purposes.
        xero_end_date (str): Report end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty string, defaults to '30 Jun {xero_financial_year}'.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            calculate default date range (1 Jul previous year to 30 Jun current year).
        xero_start_date (str): Report start date in 'DD MMM YYYY' format (e.g., '1 Jul 2023').
            If empty string, defaults to '1 Jul {xero_financial_year - 1}'.
        xero_bank_account (str): Name of the bank account to reconcile (e.g., 'Business Cheque Account').
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Absolute or relative directory path where the Excel
            report file will be saved (e.g., 'C:\\Reports' or './output').
        report_file_name (str): Filename for the saved report including .xlsx extension
            (e.g., 'Bank_Reconciliation_2024.xlsx').
        xero_report_name (str): Display name of the report as shown in Xero UI and Chrome
            window title, used for window identification (e.g., 'Bank Reconciliation').
        is_no_bank_accounts (bool): Flag indicating whether the organization has no bank
            accounts configured in Xero.
        extension (str): File extension for the exported report (e.g., '.xlsx').

    Returns:
        None: This function performs actions and saves files but does not return a value.

    Raises:
        Exception: If any step fails including:
            - Bank account validation failures
            - Date field population errors
            - Bank account selection failures
            - Export button interaction failures
            - Windows Save As dialog handling errors
            - File save operation failures

    Example:
        >>> xero_blue_download_bank_reconciliation_report(
        ...     browser=my_browser,
        ...     client_name="ACME Corp",
        ...     xero_end_date="31 Dec 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jan 2024",
        ...     xero_bank_account="Business Cheque Account",
        ...     window_title="Bank Reconciliation - Xero",
        ...     download_directory="C:\\Reports",
        ...     report_file_name="ACME_Bank_Rec_2024.xlsx",
        ...     xero_report_name="Bank Reconciliation",
        ...     is_no_bank_accounts=False,
        ...     extension=".xlsx"
        ... )
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue - Download Bank Reconciliation Report - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Client Name: {client_name}")
    logger.info(f"Bank Account: {xero_bank_account}")
    logger.info(
        f"Start Date: {xero_start_date if xero_start_date else f'1 Jul {int(xero_financial_year) - 1}'}",
    )
    logger.info(
        f"End Date: {xero_end_date if xero_end_date else f'30 Jun {xero_financial_year}'}",
    )
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Report File Name: {report_file_name}")
    logger.info(f"Download Directory: {download_directory}")
    logger.info(f"Report Name in Xero: {xero_report_name}")
    logger.info(f"Has No Bank Accounts (initial): {is_no_bank_accounts}")
    logger.info("=" * 80)

    try:
        # STEP 1: Configure Bank Account and Date Range
        # Purpose: Validate bank account availability, resolve the appropriate date range,
        #          populate date fields, select the bank account, and trigger the export
        # Function: configure_bank_account_and_date_range()
        # - Clicks the bank account search field to open the dropdown
        # - Checks if bank accounts exist via has_no_bank_accounts()
        # - Resolves start/end dates via resolve_report_date_range()
        # - Enters start and end dates into the report date fields
        # - Selects the specified bank account from the dropdown
        # - Calls update_and_export_to_excel() to apply settings and download the report
        configure_bank_account_and_date_range(
            browser,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
            xero_bank_account,
            window_title,
            download_directory,
            report_file_name,
            is_no_bank_accounts,
            extension,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("=" * 80)
        logger.info(
            f"COMPLETED: Xero Blue - Download Bank Reconciliation Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Bank Account: {xero_bank_account}")
        logger.info(f"Report Saved As: {report_file_name}")
        logger.info(f"Download Directory: {download_directory}")
        logger.info("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue - Download Bank Reconciliation Report - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Bank Account: {xero_bank_account}")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


def configure_bank_account_and_date_range(
    browser,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
    xero_bank_account,
    window_title,
    download_directory,
    report_file_name,
    is_no_bank_accounts,
    extension,
):
    """
    Configure bank account selection and date range for the Bank Reconciliation report.

    Validates bank account availability, determines the appropriate date range (custom or
    default financial year), populates the start and end date fields in the Xero UI, and
    selects the specified bank account from the dropdown. Uses Selenium WebDriverWait with
    a 5-second timeout for all element interactions. Only proceeds with date configuration
    and bank account selection if bank accounts exist. Delegates to update_and_export_to_excel()
    for report generation and file download.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the Xero Bank Reconciliation report page.
        xero_end_date (str): Report end date in 'DD MMM YYYY' format. If empty/None,
            calculates '30 Jun {xero_financial_year}' as default.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024') used
            for default date range calculation.
        xero_start_date (str): Report start date in 'DD MMM YYYY' format. If empty/None,
            calculates '1 Jul {xero_financial_year - 1}' as default.
        xero_bank_account (str): Name of the bank account to select from the dropdown
            (e.g., 'Business Cheque Account').
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Target directory path for the Excel file, passed to
            the export function.
        report_file_name (str): Output filename including .xlsx extension, passed to
            the export function.
        is_no_bank_accounts (bool): Initial flag for bank account availability, updated
            by has_no_bank_accounts() validation.
        extension (str): File extension for the exported report (e.g., '.xlsx').

    Returns:
        None: This function performs UI interactions and delegates to the export workflow.

    Raises:
        TimeoutException: If the bank account search field, date fields, or bank account
            dropdown option cannot be located within 5 seconds.

    Note:
        The function uses keyboard automation (CTRL+A, DELETE, TAB) to clear and populate
        date fields, ensuring clean data entry without residual values.
    """
    driver = browser.driver
    wait = WebDriverWait(driver, 5)

    start_pack_date_id = (By.ID, "report-settings-custom-date-input-from")
    end_pack_date_id = (By.ID, "report-settings-custom-date-input-to")

    search_bank_account_xpath = "//input[@data-automationid='Bank Account-selector-autocompleter--input' and @aria-label='Search for bank account']"

    # STEP 1: Open Bank Account Search Field
    # Purpose: Activate the bank account dropdown so the "No Bank Account" indicator
    #          becomes visible for validation
    logger.info("Clicking bank account search field to open dropdown...")
    wait.until(
        EC.visibility_of_element_located((By.XPATH, search_bank_account_xpath)),
    ).click()
    logger.info("Bank account search field clicked successfully")

    # STEP 2: Validate Bank Account Availability
    # Purpose: Check whether the organisation has any bank accounts configured in Xero
    # Function: has_no_bank_accounts()
    # - Waits for the 'No Bank Account' indicator element in the UI
    # - Returns True if no bank accounts exist, False if bank accounts are present
    logger.info("Validating bank account availability...")
    is_no_bank_accounts = has_no_bank_accounts(browser)
    logger.info(
        f"Bank account availability check result — No bank accounts: {is_no_bank_accounts}",
    )

    if not is_no_bank_accounts:

        # STEP 3: Resolve Report Date Range
        # Purpose: Determine the start and end dates to use for the report —
        #          either the custom dates from input or the default financial year range
        # Function: resolve_report_date_range()
        # - Checks if both xero_start_date and xero_end_date are provided
        # - Returns custom dates if provided, otherwise calculates default FY dates
        #   (1 Jul previous year to 30 Jun current year)
        logger.info("Resolving report date range...")
        str_start_date, str_end_date = resolve_report_date_range(
            xero_end_date,
            xero_financial_year,
            xero_start_date,
        )
        logger.info(f"Resolved Start Date: {str_start_date}")
        logger.info(f"Resolved End Date: {str_end_date}")

        # STEP 4: Enter Start Date
        # Purpose: Populate the report start date field with the resolved date value
        logger.info(f"Entering start date: {str_start_date}")
        start_date_input = wait.until(
            EC.visibility_of_element_located(start_pack_date_id),
        )
        start_date_input.send_keys("\ue009" + "a")  # CTRL + A (select all)
        start_date_input.send_keys("\ue003")  # DELETE (clear field)
        start_date_input.send_keys(str_start_date)
        start_date_input.send_keys("\ue004")  # TAB (confirm input)
        logger.info(f"Start date entered successfully: {str_start_date}")

        # STEP 5: Enter End Date
        # Purpose: Populate the report end date field with the resolved date value
        logger.info(f"Entering end date: {str_end_date}")
        end_date_input = wait.until(EC.visibility_of_element_located(end_pack_date_id))
        end_date_input.send_keys("\ue009" + "a")  # CTRL + A (select all)
        end_date_input.send_keys("\ue003")  # DELETE (clear field)
        end_date_input.send_keys(str_end_date)
        end_date_input.send_keys("\ue004")  # TAB (confirm input)
        logger.info(f"End date entered successfully: {str_end_date}")

        # STEP 6: Open Bank Account Dropdown
        # Purpose: Reactivate the bank account dropdown to display available account options
        logger.info(f"Opening bank account dropdown to select: {xero_bank_account}")
        bank_search_elem = wait.until(
            EC.presence_of_element_located((By.XPATH, search_bank_account_xpath)),
        )
        bank_search_elem.click()
        logger.info("Bank account dropdown opened successfully")

        bank_search_elem.send_keys("\ue009a")  # CTRL+A
        bank_search_elem.send_keys("\ue003")  # BACKSPACE
        bank_search_elem.send_keys(xero_bank_account)
        logger.info(f"Successfully entered end date: {xero_bank_account}")

        handle_no_bank_account(driver, xero_bank_account)

        # STEP 7: Select Specified Bank Account
        # Purpose: Choose the target bank account from the dropdown options

        logger.info(f"Selecting bank account from dropdown: {xero_bank_account}")
        dropdown_option_xpath = f"//div[contains(@data-automationid,'Bank Account-selector-dropdown-text') and normalize-space(.)='{xero_bank_account}']"
        wait.until(
            EC.visibility_of_element_located((By.XPATH, dropdown_option_xpath)),
        ).click()
        logger.info(f"Bank account selected successfully: {xero_bank_account}")

        # STEP 8: Update Report Settings and Export to Excel
        # Purpose: Apply all configured settings by clicking the Update button,
        #          then trigger the Excel export and handle the Windows Save As dialog
        # Function: update_and_export_to_excel()
        # - Clicks the 'Update' button to refresh the report with the selected parameters
        # - Clicks the 'Export' button to reveal the export format options
        # - Clicks 'Excel' to trigger the file download
        # - Handles the Windows Save As dialog to save the file to the target directory
        logger.info("Applying report settings and initiating Excel export...")
        update_and_export_to_excel(
            browser,
            window_title,
            download_directory,
            report_file_name,
            extension,
        )
        logger.info(f"Report exported and saved successfully: {report_file_name}")


def has_no_bank_accounts(browser) -> bool:
    """
    Verify if the organisation has no bank accounts configured in Xero.

    Attempts to locate the 'No Bank Account' indicator element in the Xero UI using a
    WebDriverWait with a 5-second timeout. This validation step determines whether the
    organisation has any bank accounts set up, which is required before attempting to
    generate bank reconciliation reports. Returns a boolean that the calling function
    uses to decide whether to proceed with date configuration and report generation.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to
            the current Xero Bank Reconciliation report page.

    Returns:
        bool: True if the 'No Bank Account' element is visible (indicating no bank accounts
            are configured), False if the element is not found within 5 seconds (indicating
            bank accounts exist).

    Note:
        This function catches all exceptions during the wait period and treats them as
        'bank accounts exist' scenarios, returning False without raising errors. This allows
        the workflow to continue with bank account selection when accounts are available.
    """
    driver = browser.driver
    try:
        no_bank_account_xpath = (
            "//input[@aria-role='combobox' and @aria-label='No Bank Account']"
        )
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, no_bank_account_xpath)),
        )
        logger.info(
            "Validation result: No bank accounts are configured for this organisation",
        )
        return True

    except Exception:
        logger.info(
            "Validation result: Bank accounts exist for this organisation — proceeding with configuration",
        )
        return False


def resolve_report_date_range(xero_end_date, xero_financial_year, xero_start_date):
    """
    Determine the report date range based on input parameters.

    Evaluates the provided start and end date parameters and determines whether to use
    them as-is or calculate default dates based on the financial year. For Australian
    financial years, the default date range spans from 1 Jul (previous year) to 30 Jun
    (current year). Supports both custom date ranges for specific reporting periods and
    standard financial year ranges.

    Args:
        xero_end_date (str): Custom end date in 'DD MMM YYYY' format (e.g., '30 Jun 2024').
            If empty/None, the function calculates '30 Jun {xero_financial_year}' as default.
        xero_financial_year (str): Financial year as a 4-digit string (e.g., '2024') used to
            calculate the default start date (1 Jul previous year) and end date (30 Jun current year).
        xero_start_date (str): Custom start date in 'DD MMM YYYY' format (e.g., '1 Jul 2023').
            If empty/None, the function calculates '1 Jul {xero_financial_year - 1}' as default.

    Returns:
        tuple: A tuple containing (str_start_date, str_end_date) both in 'DD MMM YYYY' format.

    Note:
        The financial year calculation assumes the Australian financial year convention where
        FY 2024 runs from 1 Jul 2023 to 30 Jun 2024. Both start_date and end_date must be
        provided together; if either is missing the function defaults to the full financial
        year date range.
    """
    if not xero_end_date or not xero_start_date:
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        str_end_date = f"30 Jun {xero_financial_year}"
        logger.info(
            f"No custom dates provided — using default financial year range: {str_start_date} to {str_end_date}",
        )
    else:
        str_start_date = xero_start_date
        str_end_date = xero_end_date
        logger.info(
            f"Custom dates provided — using input date range: {str_start_date} to {str_end_date}",
        )

    return str_start_date, str_end_date


def update_and_export_to_excel(
    browser,
    window_title,
    download_directory,
    report_file_name,
    extension,
):
    """
    Update the Bank Reconciliation report and export it to Excel format.

    Finalises the report generation workflow by applying all configured settings (date range
    and bank account selection) through the Update button, then initiating the Excel export.
    Uses Selenium WebDriverWait with a 5-second timeout to interact with Xero's Update,
    Export, and Excel buttons. Delegates to download_file() to handle the Windows Save As
    dialog and save the exported file to the specified directory.

    Args:
        browser: Browser instance containing an active Selenium WebDriver with access to the
            Xero Bank Reconciliation report page configured with all necessary parameters.
        window_title (str): Title of the browser window used to locate the Save As dialog.
        download_directory (str): Absolute or relative directory path where the Excel
            file will be saved (e.g., 'C:\\Reports' or './output').
        report_file_name (str): Filename for the saved report including .xlsx extension
            (e.g., 'Bank_Reconciliation_2024.xlsx').
        extension (str): File extension for the exported report (e.g., '.xlsx').

    Returns:
        None: This function performs file download operations but does not return a value.

    Raises:
        TimeoutException: If the Update, Export, or Excel buttons cannot be located within
            5 seconds.
        Exception: If the Chrome window cannot be found, or if the Save As dialog or its
            child elements cannot be located.
        OSError: If the download_directory does not exist or is not accessible.
    """
    driver = browser.driver
    wait = WebDriverWait(driver, 5)

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

    # Click 'Update' to apply the configured date range and bank account selection
    logger.info("Clicking 'Update' button to apply report settings...")
    wait.until(EC.element_to_be_clickable(update_xpath)).click()
    logger.info("'Update' button clicked — report settings applied successfully")

    # Click 'Export' to open the export format selection menu
    logger.info("Clicking 'Export' button to open export format options...")
    wait.until(EC.element_to_be_clickable(export_xpath)).click()
    logger.info("'Export' button clicked — export format menu opened successfully")

    # Click 'Excel' to trigger the file download
    logger.info("Clicking 'Excel' to initiate the Excel file download...")
    wait.until(EC.element_to_be_clickable(excel_xpath)).click()
    logger.info("'Excel' button clicked — file download triggered successfully")

    # Handle the Windows Save As dialog and save the file to the target directory
    logger.info(
        f"Handling Save As dialog — saving file to: {download_directory}\\{report_file_name}",
    )
    download_file(
        window_title,
        download_directory,
        report_file_name,
        extension,
    )
    logger.info(f"File saved successfully: {report_file_name} → {download_directory}")


def handle_no_bank_account(driver, xero_bank_account):

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "Bank Account-selector-dropdown--empty",
                ),
            ),
        )
        logger.error(f"{xero_bank_account} not visible in the drop down")
        raise Exception(f"{xero_bank_account} not visible in the drop down")

    except Exception:
        logger.info(f"{xero_bank_account} visible in the drop down")
