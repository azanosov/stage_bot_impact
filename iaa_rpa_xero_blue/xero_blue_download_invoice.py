from __future__ import annotations

import os
import time
from datetime import datetime

from bs4 import BeautifulSoup
from iaa_rpa_utils import setup_logger
from iaa_rpa_utils.browser import safe_click
from robocorp import windows
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

# Set up logger
logger = setup_logger(__name__)


def xero_blue_download_invoice(
    browser,
    invoice_number: str,
    file_to_save_invoice: str,
    max_rows: int,
    max_retries: int,
):
    """Download a specific invoice as a PDF from Xero Blue.

    Navigates to the Invoices page, searches for the given invoice number
    across paginated table data, opens the invoice record, downloads it as a
    PDF to the specified path, handles the Mark as Sent popup, and returns
    to the home page.

    Args:
        browser: Selenium browser instance used to interact with Xero Blue.
        invoice_number (str): The invoice number to search for and download.
        file_to_save_invoice (str): Directory path where the invoice PDF will be saved.
        max_rows (int): Maximum number of table rows to scan before stopping.
        max_retries (int): Maximum number of navigation retry attempts.

    Raises:
        Exception: If the invoice is not found, the page fails to load,
                   or the download cannot be completed.
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(
        f"STARTING: Xero Blue Download Invoice - {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
    )
    logger.info(f"Invoice Number: {invoice_number}")
    logger.info(f"File Save Path: {file_to_save_invoice}")
    logger.info(f"Max Rows: {max_rows}")
    logger.info(f"Max Retries: {max_retries}")
    logger.info("=" * 80)

    try:
        row_number = 0

        # STEP 1: Navigate to Invoices Page
        # Purpose: Access the invoices list page via Sales or Business menu
        # Function: navigate_to_invoices_page(browser, max_retries)
        # - Tries new UI (Sales > Invoices), falls back to old UI (Business > Invoices)
        # - Retries up to max_retries times until the invoice table is visible
        navigate_to_invoices_page(browser, max_retries)

        # STEP 2: Extract Invoice Table Data
        # Purpose: Scrape all invoice rows across paginated pages to find the target invoice
        # Function: extract_invoice_table_data(browser, invoice_number, max_rows)
        # - Iterates through each page of the invoice table
        # - Collects row data until invoice is found, max_rows is reached, or no more pages
        # - Returns early with a found flag if the invoice is matched during extraction
        all_data, is_invoice_found = extract_invoice_table_data(
            browser,
            invoice_number,
            max_rows,
        )

        # STEP 3: Verify Invoice Existence and Locate Row
        # Purpose: Confirm the invoice exists in the extracted data and get its row position
        # Function: find_invoice_row_number(all_data, invoice_number)
        # - Scans extracted rows for a case-insensitive match on the invoice number
        # - Returns the 1-based row index for use in the XPath click target
        # - Raises an exception if the invoice is not found
        is_invoice_found, row_number = find_invoice_row_number(all_data, invoice_number)

        # STEP 4: Open the Invoice Record
        # Purpose: Click the invoice link in the table to open the invoice detail page
        # - Builds an XPath using the matched row number to target the correct row
        # - Waits for the link to be visible before clicking
        invoice_link_xpath = f"(//table//tbody//tr)[{row_number}]//td[4]//a"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_link_xpath)),
        )
        browser.driver.find_element(By.XPATH, invoice_link_xpath).click()
        logger.info(
            f"Clicked invoice link at row {row_number} to open invoice detail page",
        )
        time.sleep(2)

        # STEP 5: Verify Invoice Detail Page Loaded
        # Purpose: Confirm the correct invoice page has opened before attempting download
        # Function: is_invoice_detail_page(browser, invoice_number)
        # - Checks for the invoice heading element containing the invoice number
        if is_invoice_detail_page(browser, invoice_number):
            logger.info(f"Invoice detail page confirmed for invoice: {invoice_number}")

            # STEP 6: Download Invoice as PDF
            # Purpose: Trigger the print/PDF download and save the file to the specified path
            # Function: download_invoice_as_pdf(browser, file_to_save_invoice)
            # - Clicks the PDF/Print button to open the Save As dialog
            # - Retrieves the default filename from the dialog
            # - Replaces the path with the target save directory and filename
            # - Confirms overwrite if a file already exists
            download_invoice_as_pdf(browser, file_to_save_invoice)

            # STEP 7: Handle Mark as Sent Popup
            # Purpose: Dismiss the Mark as Sent modal if it appears after downloading
            # Function: handle_mark_as_sent_popup(browser)
            # - Checks whether the Mark as Sent modal is visible
            # - Clicks Cancel to dismiss without marking the invoice as sent
            handle_mark_as_sent_popup(browser)

            # STEP 8: Navigate Back to Home Page
            # Purpose: Return to the home/dashboard after the download is complete
            # Function: navigate_to_home_page(browser)
            # - Tries new UI Home link, falls back to old UI Business button
            navigate_to_home_page(browser)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info("=" * 80)
            logger.info(
                f"COMPLETED: Xero Blue Download Invoice - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Invoice Number: {invoice_number}")
            logger.info(f"File Saved To: {file_to_save_invoice}")
            logger.info(f"Row Number Found: {row_number}")
            logger.info("=" * 80)

        else:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error("=" * 80)
            logger.error(
                f"FAILED: Xero Blue Download Invoice - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error(f"Invoice Number: {invoice_number}")
            logger.error(
                f"Error: Invoice detail page did not open for invoice '{invoice_number}'",
            )
            logger.error("=" * 80)

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error("=" * 80)
        logger.error(
            f"FAILED: Xero Blue Download Invoice - {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )
        logger.error(f"Duration: {duration:.2f} seconds")
        logger.error(f"Invoice Number: {invoice_number}")
        logger.error(f"File Save Path: {file_to_save_invoice}")
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise


# ------------------- HELPERS -------------------


def is_invoice_detail_page(browser, invoice_number) -> bool:
    """Check whether the invoice detail page for the given invoice number is loaded.

    Looks for the invoice heading element that contains the expected invoice number.
    Returns True immediately if the heading is found; returns False on timeout.

    Args:
        browser: Selenium browser instance containing the driver.
        invoice_number (str): The invoice number expected in the page heading.

    Returns:
        bool: True if the invoice detail page heading is visible, False otherwise.
    """
    try:
        invoice_page_xpath = f"//h1[normalize-space(text())='Invoice {invoice_number}']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, invoice_page_xpath)),
        )
        logger.info(
            f"Invoice detail page heading confirmed for invoice: {invoice_number}",
        )
        return True
    except Exception:
        logger.warning(
            f"Invoice detail page heading not found for invoice: {invoice_number}",
        )
        return False


def navigate_to_invoices_page(browser, max_retries) -> bool:
    """Navigate to the Invoices list page using the Sales or Business menu.

    Attempts navigation using the new UI (Sales > Invoices) first. If that
    fails, falls back to the old UI (Business > Invoices). After each attempt,
    verifies that the invoice table is visible before returning success.
    Retries up to max_retries times on failure.

    Args:
        browser: Selenium browser instance containing the driver.
        max_retries (int): Maximum number of navigation attempts before giving up.

    Returns:
        bool: True if navigation succeeded and the invoice table is visible,
              False if all retry attempts were exhausted.
    """
    driver = browser.driver
    retries = 0

    while retries < max_retries:
        try:
            logger.info(
                f"Navigation attempt {retries + 1} of {max_retries} to reach Invoices page",
            )

            try:
                # New UI: Sales > Invoices
                sales_xpath = "//button[@type='button' and .//span[normalize-space(text())='Sales']]"
                invoice_xpath = (
                    "//a[@role='link' and span[normalize-space(text())='Invoices']]"
                )

                sales_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, sales_xpath)),
                )
                safe_click(driver, sales_ele, "Sales button")
                logger.info("Clicked Sales button (new UI)")

                invoice_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, invoice_xpath)),
                )
                safe_click(driver, invoice_ele, "Invoices menu item")
                logger.info("Clicked Invoices menu item (new UI)")

            except Exception:
                # Old UI: Business > Invoices
                logger.info(
                    "New UI navigation failed, attempting old UI (Business > Invoices)",
                )
                business_xpath = "//button[normalize-space(text())='Business']"
                invoices_tab_xpath = "//a[normalize-space(text())='Invoices']"

                business_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, business_xpath)),
                )
                safe_click(driver, business_ele, "Business button")
                logger.info("Clicked Business button (old UI)")

                invoices_tab_ele = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, invoices_tab_xpath)),
                )
                safe_click(driver, invoices_tab_ele, "Invoices tab")
                logger.info("Clicked Invoices tab (old UI)")

            time.sleep(2)
            if is_invoice_table_visible(driver):
                logger.info(
                    "Successfully navigated to Invoices page — invoice table is visible",
                )
                return True
            else:
                logger.warning(
                    f"Invoice table not visible after attempt {retries + 1}, retrying...",
                )
                retries += 1
                if retries < max_retries:
                    time.sleep(2)

        except Exception as e:
            logger.warning(f"Navigation attempt {retries + 1} failed: {e}")
            retries += 1
            if retries < max_retries:
                time.sleep(2)

    logger.error(f"Failed to navigate to Invoices page after {max_retries} attempts")
    return False


def is_invoice_table_visible(driver) -> bool:
    """Check whether the invoice data table is visible on the current page.

    Waits up to 5 seconds for the table element to appear. Used after
    navigation to confirm the Invoices page has fully loaded.

    Args:
        driver: Selenium WebDriver instance.

    Returns:
        bool: True if the invoice table is visible, False otherwise.
    """
    try:
        table_xpath = "//table[@id='ext-gen43']"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, table_xpath)),
        )
        logger.info("Invoice table is visible on the page")
        return True
    except Exception:
        logger.warning("Invoice table is not visible on the page")
        return False


def navigate_to_home_page(browser):
    """Navigate back to the Xero Blue home or dashboard page.

    Attempts to click the Home navigation item using the new UI selector.
    Falls back to clicking the Business button in the old UI if the Home
    item is not found.

    Args:
        browser: Selenium browser instance containing the driver.
    """
    try:
        # New UI: Home link in side navigation
        home_xpath = (
            "//span[@class='x-nav--nav-item-text' and normalize-space(text())='Home']"
        )
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, home_xpath)),
        )

        browser.driver.find_element(By.XPATH, home_xpath).click()
        logger.info("Clicked Home link to return to dashboard (new UI)")
    except Exception:
        # Old UI: Business button as fallback
        logger.info("Home link not found, falling back to Business button (old UI)")
        business_xpath = "//button[normalize-space(text())='Business']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, business_xpath)),
        )
        browser.driver.find_element(By.XPATH, business_xpath).click()
        logger.info("Clicked Business button to return to dashboard (old UI)")


def extract_invoice_table_data(browser, invoice_number, max_rows):
    """Extract invoice rows from the paginated invoice table.

    Iterates through each page of the invoice table, parsing HTML rows via
    BeautifulSoup. Stops early if the target invoice is found, the max row
    limit is reached, or no more pages are available. Raises an exception
    if the first page contains no data.

    Args:
        browser: Selenium browser instance containing the driver.
        invoice_number (str): The invoice number to search for during extraction.
        max_rows (int): Maximum number of rows to collect before stopping.

    Returns:
        tuple[list, bool]: A tuple of (all_data, is_invoice_found) where
            all_data is a list of row cell values and is_invoice_found
            indicates whether the target invoice was matched.

    Raises:
        Exception: If no invoices exist on the first page of the table.
    """
    logger.info(
        f"Starting data extraction for invoice: '{invoice_number}' (max rows: {max_rows})",
    )
    table_xpath = "//table[@id='ext-gen43']"
    all_data = []
    page_number = 1
    is_invoice_found = False

    while True:
        logger.info(f"Extracting rows from page {page_number}")

        try:
            html = browser.driver.find_element(By.XPATH, table_xpath).get_attribute(
                "outerHTML",
            )
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")

            if not table:
                logger.warning(
                    f"No table element found on page {page_number} — stopping extraction",
                )
                break

            rows_on_page = 0
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                row_data = [cell.text.strip() for cell in cells]
                all_data.append(row_data)
                rows_on_page += 1

                if (
                    row_data
                    and row_data[0].strip().lower() == invoice_number.strip().lower()
                ):
                    logger.info(
                        f"Invoice '{invoice_number}' found on page {page_number} — total rows collected: {len(all_data)}",
                    )
                    is_invoice_found = True
                    return all_data, is_invoice_found

                if len(all_data) >= max_rows:
                    logger.warning(
                        f"Max row limit of {max_rows} reached — stopping extraction",
                    )
                    return all_data, is_invoice_found

            logger.info(
                f"Page {page_number}: extracted {rows_on_page} rows — cumulative total: {len(all_data)}",
            )

            if page_number == 1 and len(all_data) < 1:
                logger.error(
                    "No invoices found in Xero Blue — invoice table is empty on the first page",
                )
                raise Exception("There is no invoices exist in XERO Blue")

            # Navigate to next page if available
            try:
                next_button = browser.driver.find_element(
                    By.XPATH,
                    "//a[contains(normalize-space(.), 'Next')]",
                )
                if "disabled" in next_button.get_attribute("class"):
                    logger.info(
                        f"Next button is disabled — reached last page ({page_number})",
                    )
                    break

                logger.info(f"Navigating to page {page_number + 1}")
                next_button.click()
                WebDriverWait(browser.driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, table_xpath)),
                )
                page_number += 1

            except Exception:
                logger.info(
                    f"No further pages available after page {page_number} — pagination complete",
                )
                break

        except Exception as e:
            logger.error(f"Error extracting data from page {page_number}: {e}")
            break

    logger.info(
        f"Extraction complete — total rows: {len(all_data)}, invoice found: {is_invoice_found}",
    )
    return all_data, is_invoice_found


def find_invoice_row_number(all_data, invoice_number):
    """Find the row number of the specified invoice within extracted table data.

    Performs a case-insensitive search through the first cell of each row
    to match the invoice number. Returns the 1-based row index used to
    build the XPath selector for clicking the invoice link.

    Args:
        all_data (list): List of row data extracted from the invoice table.
        invoice_number (str): The invoice number to locate within the data.

    Returns:
        tuple[bool, int]: A tuple of (is_invoice_found, row_number) where
            is_invoice_found is True if matched, and row_number is the
            1-based index of the matching row.

    Raises:
        Exception: If all_data is empty or the invoice number is not found.
    """
    is_invoice_found = False
    row_number = 0

    if all_data:
        for index, row in enumerate(all_data):
            if row and row[0].strip().lower() == invoice_number.strip().lower():
                is_invoice_found = True
                row_number = index + 1
                logger.info(f"Invoice '{invoice_number}' matched at row {row_number}")
                break
    else:
        logger.error(
            "No invoice data available to search — Xero Blue invoice list is empty",
        )
        raise Exception("There are no invoices in XERO Blue")

    if not is_invoice_found:
        logger.error(
            f"Invoice '{invoice_number}' was not found in the extracted invoice data",
        )
        raise Exception(
            f"Required invoice '{invoice_number}' was not found in XERO Blue",
        )

    return is_invoice_found, row_number


def download_invoice_as_pdf(browser, file_to_save_invoice):
    """Download the currently open invoice as a PDF via the Print/PDF button.

    Clicks the PDF print button to trigger the browser Save As dialog,
    retrieves the default filename, constructs the full save path, enters
    it into the filename field, and clicks Save. Handles any overwrite
    confirmation dialog that appears.

    Args:
        browser: Selenium browser instance containing the driver.
        file_to_save_invoice (str): Directory path where the PDF will be saved.
    """
    try:
        logger.info("Initiating invoice PDF download")
        WebDriverWait(browser.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "PrintDropdown-print")),
        )
        browser.driver.find_element(By.ID, "PrintDropdown-print").click()
        logger.info("Clicked PDF/Print button to open Save As dialog")

        time.sleep(2)
        app = windows.find_window("regex:.*– Xero - Google Chrome")
        save_as_dialog = app.find(
            'control:"WindowControl" and name:"Save As" and path:"1"',
        )

        filename_input = save_as_dialog.find(
            'control:"EditControl" and name:"File name:"',
        )
        current_filename = filename_input.get_value() or ""
        logger.info(f"Default filename detected in Save As dialog: {current_filename}")

        file_path = os.path.normpath(
            os.path.join(str(file_to_save_invoice), current_filename),
        )
        logger.info(f"Saving invoice PDF to: {file_path}")

        filename_input.send_keys("{CTRL}a")
        filename_input.send_keys("{DEL}")
        filename_input.send_keys(file_path)
        time.sleep(2)
        app.find('control:"ButtonControl" and name:"Save"').click()
        logger.info("Clicked Save button in Save As dialog")

        try:
            save_confirm_popup = app.find(
                'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"',
                timeout=3,
            )
            save_confirm_popup.find('control:"ButtonControl" and name:"Yes"').click()
            logger.info("Confirmed file overwrite in Confirm Save As dialog")
        except Exception:
            logger.info(
                "No overwrite confirmation dialog appeared — file saved without conflict",
            )

        logger.info(f"Invoice PDF successfully saved: {file_path}")

    except Exception as e:
        logger.error(f"Invoice PDF download failed: {e}")


def is_mark_as_sent_popup_visible(browser) -> bool:
    """Check whether the Mark as Sent modal dialog is currently visible.

    Waits up to 10 seconds for the modal header element to appear.
    Used to determine whether the popup needs to be dismissed after download.

    Args:
        browser: Selenium browser instance containing the driver.

    Returns:
        bool: True if the Mark as Sent modal is visible, False otherwise.
    """
    try:
        mark_as_xpath = "//header[@id='MarkAsSentModal--header' and normalize-space(text())='Mark as sent']"
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, mark_as_xpath)),
        )
        logger.info("Mark as Sent popup is visible")
        return True
    except Exception:
        logger.info("Mark as Sent popup is not visible — no action required")
        return False


def handle_mark_as_sent_popup(browser):
    """Dismiss the Mark as Sent popup by clicking Cancel if it is present.

    Checks for the presence of the Mark as Sent modal after the invoice
    download. If the popup is visible, clicks the Cancel button to close
    it without changing the invoice status.

    Args:
        browser: Selenium browser instance containing the driver.
    """
    if is_mark_as_sent_popup_visible(browser):
        logger.info("Dismissing Mark as Sent popup by clicking Cancel")
        cancel_button_xpath = (
            "//button[@type='button' and normalize-space(text())='Cancel']"
        )
        WebDriverWait(browser.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, cancel_button_xpath)),
        )
        browser.driver.find_element(By.XPATH, cancel_button_xpath).click()
        logger.info("Clicked Cancel — Mark as Sent popup dismissed")
