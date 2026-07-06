from __future__ import annotations

import logging
import os
from datetime import datetime

from bs4 import BeautifulSoup
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# Set up logger
logger = logging.getLogger("IARPA." + __name__)
logging.basicConfig(level=logging.INFO)


def xero_blue_screenshot_gst_reconciliation_report(
    browser,
    client_name,
    xero_end_date,
    xero_financial_year,
    xero_start_date,
    download_directory_path,
    xero_report_file_name,
    crop_top,
    crop_bottom,
    file_format,
):
    """
    Capture a screenshot of the GST Reconciliation report in Xero Blue and extract GST totals.

    This function automates the process of generating a GST Reconciliation report in Xero Blue,
    configuring the date range, extracting GST Paid and GST Collected totals from the report table,
    taking a screenshot of the report, cropping it to specified dimensions, and saving it to the
    download directory. It returns the extracted GST totals for further processing.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        client_name (str): The name of the Xero client/organization for logging purposes.
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                           If None or empty, defaults to the end of the financial year.
        xero_financial_year (str): The financial year for the report (e.g., "2024").
                                  Used to calculate default date range if specific dates not provided.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                             If None or empty, defaults to the start of the financial year.
        download_directory_path (str): Absolute path to the directory where the screenshot will be saved.
        xero_report_file_name (str): Base filename for the saved screenshot (without extension).
        crop_top (int): Number of pixels to crop from the top of the screenshot.
        crop_bottom (int): Number of pixels from the top where cropping should end (bottom boundary).
        file_format (str): File extension for the screenshot (e.g., ".png", ".jpg").

    Returns:
        tuple: A tuple containing two elements:
            - gst_collected_total (str or None): The GST Collected total extracted from the report.
                                                Returns None if extraction fails.
            - gst_paid_total (str or None): The GST Paid total extracted from the report.
                                          Returns None if extraction fails.

    Raises:
        TimeoutException: If web elements cannot be located within the specified wait times.
        NoSuchElementException: If required elements are not found on the page.
        Exception: Any other exceptions that occur during report generation, extraction, or screenshot capture.
                  All exceptions are logged with full stack traces and re-raised.

    Notes:
        - The function uses Australian financial year convention (1 Jul - 30 Jun).
        - If both xero_start_date and xero_end_date are not provided, the function calculates
          the date range based on the financial year (1 Jul YYYY-1 to 30 Jun YYYY).
        - The screenshot is taken of the full page, then cropped according to crop_top and crop_bottom
          parameters to focus on the relevant report content.
        - A temporary screenshot file is created and then removed after cropping.
        - The function logs comprehensive start and end information with timestamps and duration.
        - GST totals are extracted by parsing the HTML table structure using BeautifulSoup.

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> gst_collected, gst_paid = xero_blue_screenshot_gst_recconciliation_report(
        ...     browser=browser,
        ...     client_name="ABC Company Pty Ltd",
        ...     xero_end_date="30 Jun 2024",
        ...     xero_financial_year="2024",
        ...     xero_start_date="1 Jul 2023",
        ...     download_directory_path="C:\\Reports\\Screenshots",
        ...     xero_report_file_name="GST_Reconciliation_ABC_2024",
        ...     crop_top=100,
        ...     crop_bottom=800,
        ...     file_format=".png"
        ... )
        >>> print(f"GST Collected: {gst_collected}, GST Paid: {gst_paid}")
        GST Collected: $15,234.50, GST Paid: $12,456.75
    """
    # Record the start time for duration calculation
    start_time = datetime.now()

    # Log the start of the process with banner separator
    logger.info("=" * 80)
    logger.info(f"STARTING PROCESS: XERO BLUE SCREENSHOT GST RECONCILIATION REPORT")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client Name: {client_name}")
    logger.info(
        f"Start Date: {xero_start_date if xero_start_date else 'Using Financial Year Default'}",
    )
    logger.info(
        f"End Date: {xero_end_date if xero_end_date else 'Using Financial Year Default'}",
    )
    logger.info(f"Financial Year: {xero_financial_year}")
    logger.info(f"Download Directory: {download_directory_path}")
    logger.info(f"Report File Name: {xero_report_file_name}")
    logger.info(f"Crop Top: {crop_top}")
    logger.info(f"Crop Bottom: {crop_bottom}")
    logger.info("=" * 80)

    try:
        # Configure the report date range and run the GST Reconciliation report
        # This populates the From and To date fields using the provided dates or financial year defaults
        # and clicks the Update button to refresh the report with the new date range
        run_report_and_export(
            browser,
            xero_end_date,
            xero_financial_year,
            xero_start_date,
        )

        # Extract GST Collected and GST Paid totals from the report table
        # This parses the HTML table structure to find the "GST Paid" section and extracts
        # the values from the last row containing Actual and Unfiled amounts
        gst_collected_total, gst_paid_total = extract_gst_paid_totals(browser)

        # Capture a full-page screenshot, crop it to specified dimensions, and save to file
        # This creates a temporary screenshot, crops it using PIL to focus on report content,
        # saves the cropped version with the specified file format, and removes the temporary file
        takescreenshot_and_save(
            browser,
            download_directory_path,
            xero_report_file_name,
            crop_top,
            crop_bottom,
            file_format,
        )

        # Calculate duration and log successful completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(
            f"PROCESS COMPLETED SUCCESSFULLY: XERO BLUE SCREENSHOT GST RECONCILIATION REPORT",
        )
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Client Name: {client_name}")
        logger.info(f"Report File Name: {xero_report_file_name}")
        logger.info(f"GST Collected Total: {gst_collected_total}")
        logger.info(f"GST Paid Total: {gst_paid_total}")
        logger.info(f"Status: SUCCESS")
        logger.info("=" * 80)

        return gst_collected_total, gst_paid_total

    except Exception as e:
        # Calculate duration and log failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error("=" * 80)
        logger.error(f"PROCESS FAILED: XERO BLUE SCREENSHOT GST RECONCILIATION REPORT")
        logger.error("=" * 80)
        logger.error(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Client Name: {client_name}")
        logger.error(f"Report File Name: {xero_report_file_name}")
        logger.error(f"Error: {e}")
        logger.error(f"Status: FAILED")
        logger.error("=" * 80)
        logger.error(
            f"xero_blue_screenshot_gst_recconciliation_report failed due to {e}",
            exc_info=True,
        )
        raise


def date_argument(xero_end_date, xero_financial_year, xero_start_date):
    """
    Determine the date range for the GST Reconciliation report based on provided dates or financial year.

    This function calculates the start and end dates for the report. If specific start and end dates
    are not provided, it defaults to the Australian financial year date range (1 Jul to 30 Jun)
    based on the provided financial year parameter.

    Args:
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                           If None or empty, defaults to end of financial year.
        xero_financial_year (str): The financial year for the report (e.g., "2024").
                                  Used to calculate default date range.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                             If None or empty, defaults to start of financial year.

    Returns:
        tuple: A tuple containing two strings:
            - str_start_date (str): Start date in "d MMM yyyy" format (e.g., "1 Jul 2023").
            - str_end_date (str): End date in "d MMM yyyy" format (e.g., "30 Jun 2024").

    Notes:
        - Australian financial year runs from 1 July to 30 June.
        - For financial year "2024", the date range would be "1 Jul 2023" to "30 Jun 2024".
        - The function logs whether it's using default financial year dates or user-provided dates.

    Example:
        >>> # Using financial year default
        >>> start, end = date_argument(None, "2024", None)
        >>> print(start, end)
        1 Jul 2023 30 Jun 2024

        >>> # Using specific dates
        >>> start, end = date_argument("31 Dec 2023", "2024", "1 Oct 2023")
        >>> print(start, end)
        1 Oct 2023 31 Dec 2023
    """
    if not xero_end_date or not xero_start_date:
        logger.info("Entering Default Date range")
        str_start_date = f"1 Jul {int(xero_financial_year) - 1}"
        str_end_date = f"30 Jun {xero_financial_year}"
    else:
        logger.info("Entering InputFile Date range")
        str_start_date = xero_start_date
        str_end_date = xero_end_date
    return str_start_date, str_end_date


def run_report_and_export(browser, xero_end_date, xero_financial_year, xero_start_date):
    """
    Configure the date range for the GST Reconciliation report and run it in Xero Blue.

    This function populates the From and To date fields on the GST Reconciliation report page
    using keyboard automation. It first determines the appropriate date range (either from provided
    dates or financial year defaults), then interacts with the date input fields, and finally
    clicks the Update button to refresh the report with the new date range.

    Args:
        browser: Selenium WebDriver browser instance for web automation.
        xero_end_date (str): End date for the report in "d MMM yyyy" format (e.g., "30 Jun 2024").
                           If None or empty, defaults to end of financial year.
        xero_financial_year (str): The financial year for the report (e.g., "2024").
                                  Used to calculate default date range if specific dates not provided.
        xero_start_date (str): Start date for the report in "d MMM yyyy" format (e.g., "1 Jul 2023").
                             If None or empty, defaults to start of financial year.

    Returns:
        None

    Raises:
        TimeoutException: If the date fields or Update button cannot be located within 5 seconds.
        NoSuchElementException: If the required input elements are not found on the page.

    Notes:
        - Uses explicit waits (5 seconds) to ensure elements are visible before interacting.
        - Clears existing date values before entering new ones to prevent data concatenation.
        - Logs each step including the date values entered and button clicks.
        - The Update button refreshes the report to display data for the specified date range.
        - Date fields are identified by HTML IDs: "fromDate" and "toDate".

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> # Navigate to GST Reconciliation report page first
        >>> run_report_and_export(browser, "30 Jun 2024", "2024", "1 Jul 2023")
        # Logs: "Type into start date : 1 Jul 2023"
        # Logs: "Type into to date : 30 Jun 2024"
        # Logs: "Clicked Update button"
    """
    from_date_id = "fromDate"
    to_date_id = "toDate"
    update_button_xpath = (
        "//div[@id='AttributePageMain']//a[normalize-space(text())='Update']"
    )

    # Calculate the date range based on provided dates or financial year defaults
    # Calls date_argument() which returns tuple of (start_date, end_date) in "d MMM yyyy" format
    str_start_date, str_end_date = date_argument(
        xero_end_date,
        xero_financial_year,
        xero_start_date,
    )

    # Populate the From date field with the calculated start date
    # Wait up to 5 seconds for the field to become visible before interacting
    # Click to focus, clear existing value, then send the new start date
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.ID, from_date_id)),
    )
    from_date_element = browser.driver.find_element(By.ID, from_date_id)
    from_date_element.click()
    from_date_element.clear()
    from_date_element.send_keys(str_start_date)
    logger.info(f"Type into start date : {str_start_date}")

    # Populate the To date field with the calculated end date
    # Wait up to 5 seconds for the field to become visible before interacting
    # Click to focus, clear existing value, then send the new end date
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.ID, to_date_id)),
    )
    to_date_element = browser.driver.find_element(By.ID, to_date_id)
    to_date_element.click()
    to_date_element.clear()
    to_date_element.send_keys(str_end_date)
    logger.info(f"Type into to date : {str_end_date}")

    # Click the Update button to refresh the report with the new date range
    # Wait up to 5 seconds for the button to become visible, then click it
    # This triggers Xero to regenerate the report with the specified dates
    WebDriverWait(browser.driver, 5).until(
        EC.visibility_of_element_located((By.XPATH, update_button_xpath)),
    ).click()
    logger.info("Clicked Update button")


def extract_gst_paid_totals(browser):
    """
    Extract GST Collected and GST Paid totals from the GST Reconciliation report table.

    This function parses the HTML table structure of the GST Reconciliation report to locate
    the "GST Paid" section and extract the total amounts from the last row of that section.
    It uses BeautifulSoup to parse the HTML and find cells by their ID patterns.

    Args:
        browser: Selenium WebDriver browser instance containing the loaded GST Reconciliation report page.

    Returns:
        tuple: A tuple containing two elements:
            - gst_collected_total (str or None): The GST Collected total (from "Actual" cell).
                                                Returns None if extraction fails or section not found.
            - gst_paid_total (str or None): The GST Paid total (from "Unfiled" cell).
                                          Returns None if extraction fails or section not found.

    Raises:
        NoSuchElementException: If the statement table element cannot be found on the page.

    Notes:
        - The function looks for a table with ID "statementTable" on the page.
        - It searches for a section with title "GST Paid" (class "SectionTitle1").
        - The function extracts values from the last row in the GST Paid section.
        - Cell IDs are identified by patterns: ending with ".Actual" for GST Collected
          and ".Unfiled" for GST Paid.
        - Returns (None, None) if the "GST Paid" section or data rows cannot be found.
        - Text is extracted with leading/trailing whitespace stripped.

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> # Navigate to GST Reconciliation report first and ensure it's loaded
        >>> gst_collected, gst_paid = extract_gst_paid_totals(browser)
        >>> print(f"GST Collected: {gst_collected}, GST Paid: {gst_paid}")
        GST Collected: $15,234.50, GST Paid: $12,456.75
    """
    # Locate the statement table on the page using XPath
    # This table contains the GST Reconciliation report data
    table_xpath = "//table[@id='statementTable']"
    element = browser.driver.find_element(By.XPATH, table_xpath)

    # Extract the outer HTML of the table element and parse it with BeautifulSoup
    # BeautifulSoup provides easier navigation and searching of HTML structure
    html = element.get_attribute("outerHTML")
    soup = BeautifulSoup(html, "html.parser")

    # Find the "GST Paid" section title in the table
    # This section contains the GST amounts we need to extract
    gst_paid_title = next(
        (
            tag
            for tag in soup.find_all("div", class_="SectionTitle1")
            if tag.string == "GST Paid"
        ),
        None,
    )
    if not gst_paid_title:
        return None, None

    # Navigate to the parent table row containing the section title
    # Then collect all data rows that follow until the next section starts
    section_tr = gst_paid_title.find_parent("tr")
    if not section_tr:
        return None, None
    gst_rows = []

    for row in section_tr.find_next_siblings("tr"):
        # Stop when another section starts (identified by SectionTitle1 class)
        if row.find("div", class_="SectionTitle1"):
            break

        # Only include rows that have table data cells
        if row.find_all("td"):
            gst_rows.append(row)

    if not gst_rows:
        return None, None

    # Get the last row which contains the total amounts
    # The last row typically contains the summary totals for the section
    last_row = gst_rows[-1]

    # Extract GST Collected (Actual) and GST Paid (Unfiled) cells by ID pattern
    # Cell IDs follow a pattern where they end with ".Actual" or ".Unfiled"
    gst_paid_cell = last_row.find("td", id=lambda x: x and x.endswith(".Actual"))
    unfiled_cell = last_row.find("td", id=lambda x: x and x.endswith(".Unfiled"))

    # Extract text content from the cells, stripping whitespace
    # Return None if cells are not found
    gst_collected_total = gst_paid_cell.get_text(strip=True) if gst_paid_cell else None
    gst_paid_total = unfiled_cell.get_text(strip=True) if unfiled_cell else None

    return gst_collected_total, gst_paid_total


def takescreenshot_and_save(
    browser,
    download_directory_path,
    xero_report_file_name,
    crop_top,
    crop_bottom,
    file_format,
):
    """
    Capture a full-page screenshot, crop it to specified dimensions, and save to file.

    This function takes a screenshot of the entire current browser page, crops the image
    to focus on the relevant report content by removing unwanted header/footer areas,
    and saves the cropped screenshot to the specified directory with the given filename
    and file format. A temporary file is created during the process and removed after cropping.

    Args:
        browser: Selenium WebDriver browser instance for capturing the screenshot.
        download_directory_path (str): Absolute path to the directory where the screenshot will be saved.
        xero_report_file_name (str): Base filename for the saved screenshot (without extension).
        crop_top (int): Number of pixels to crop from the top of the screenshot.
                       This removes header elements and navigation bars.
        crop_bottom (int): Number of pixels from the top where cropping should end (bottom boundary).
                          This defines the vertical extent of the cropped area.
        file_format (str): File extension for the screenshot (e.g., ".png", ".jpg", ".jpeg").

    Returns:
        None

    Raises:
        Exception: Any exceptions during screenshot capture, file operations, or image processing.
                  Exceptions are logged but not re-raised to prevent workflow interruption.

    Notes:
        - Creates a temporary file named "temp_{xero_report_file_name}" during processing.
        - The temporary file is automatically removed after cropping is complete.
        - Uses PIL (Python Imaging Library) for image cropping operations.
        - The crop_bottom parameter is automatically adjusted if it exceeds the image height.
        - Cropping preserves the full width of the screenshot (crops only vertically).
        - Crop coordinates are specified as (left, top, right, bottom) in the crop() function.
        - Final filename format: "{xero_report_file_name}{file_format}".

    Example:
        >>> from selenium import webdriver
        >>> browser = webdriver.Chrome()
        >>> # Navigate to report page first
        >>> takescreenshot_and_save(
        ...     browser=browser,
        ...     download_directory_path="C:\\Reports\\Screenshots",
        ...     xero_report_file_name="GST_Reconciliation_ABC_2024",
        ...     crop_top=100,
        ...     crop_bottom=800,
        ...     file_format=".png"
        ... )
        # Creates: C:\\Reports\\Screenshots\\GST_Reconciliation_ABC_2024.png
        # Logs: "Screenshot cropped and saved to: C:\\Reports\\Screenshots\\GST_Reconciliation_ABC_2024.png"
    """
    try:
        # Create temporary filename for the original full-page screenshot
        # This temporary file will be used for cropping and then removed
        temp_filename = os.path.join(
            download_directory_path,
            f"temp_{xero_report_file_name}",
        )

        # Create the final filename by combining the base name with the file format extension
        final_filename = os.path.join(
            download_directory_path,
            xero_report_file_name + file_format,
        )

        # Capture a full-page screenshot using Selenium's save_screenshot method
        # This saves the entire visible browser content to the temporary file
        browser.driver.save_screenshot(temp_filename)

        # Open the screenshot image using PIL and perform cropping operations
        # The context manager ensures the file is properly closed after processing
        with Image.open(temp_filename) as img:
            # Get the dimensions of the original screenshot
            width, height = img.size

            # Ensure crop_bottom doesn't exceed the image height
            # This prevents errors if the specified bottom value is too large
            crop_bottom = min(crop_bottom, height)

            # Crop the image using the specified boundaries
            # Crop format: (left, top, right, bottom) - preserves full width, crops vertically
            # left=0: starts from the left edge
            # top=crop_top: removes header/navigation elements from the top
            # right=width: extends to the right edge (preserves full width)
            # bottom=crop_bottom: defines where the cropped region ends
            cropped_img = img.crop((0, crop_top, width, crop_bottom))

            # Save the cropped image to the final destination with specified file format
            cropped_img.save(final_filename)

        # Remove the temporary original screenshot to clean up disk space
        # Only the cropped version is retained
        os.remove(temp_filename)

        logger.info(f"Screenshot cropped and saved to: {final_filename}")

    except Exception as e:
        logger.error(f"Error taking or cropping screenshot: {str(e)}")
