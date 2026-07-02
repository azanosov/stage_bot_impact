"""
Module for downloading a single invoice as a PDF from Xero Blue.

This is NOT a report - it is a record download from the Accounts Receivable
invoice list. The list holds thousands of invoices across many pages, so the
target is reached by SEARCH, not by scraping/paging: select the "All" status
tab, type the invoice number, Search, then open the matching row and print it
to PDF.

Separation of concerns:
    download_invoice(browser, request) does ONLY invoice processing and assumes
    the browser is already on the Invoices list page. NAVIGATION is separate -
    the caller/runner invokes navigate_to_invoices_page() once before a batch
    and navigate_to_home_page() after, rather than re-navigating per invoice.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(the INV_ section); shared behaviour lives in common.py.

ERROR HANDLING: typed exceptions from ``iaa_rpa_utils.exceptions``:
  - DataValidationError - a request input failed validation
  - DataExtractionError - the invoice was not found, or its page did not open
  - DownloadError       - the PDF did not land on disk
  - NavigationError     - (navigation helpers) could not reach a page

Output:
    Invoices are PDF only (Xero prints them; there is no format choice). The
    request takes a directory + file name (WITHOUT extension, like the reports);
    ``.pdf`` is enforced behind the scenes.

How to call:
    from download_invoice import (
        InvoiceRequest, download_invoice,
        navigate_to_invoices_page, navigate_to_home_page,
    )

    navigate_to_invoices_page(browser)          # caller navigates once
    download_invoice(browser, InvoiceRequest(
        invoice_number="INV-4140",
        download_directory=r"C:\\Invoices",
        report_file_name="INV-4140",            # -> INV-4140.pdf
    ))
    navigate_to_home_page(browser)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.exceptions import (
    DataExtractionError,
    DataValidationError,
    DownloadError,
    NavigationError,
)
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog, xpath_literal

from . import common
from . import config


logger = setup_logger(__name__)


__all__ = [
    "InvoiceRequest",
    "download_invoice",
    "navigate_to_invoices_page",
    "navigate_to_home_page",
]


_PDF_EXT = ".pdf"
_NAV_MAX_RETRIES = 3


@dataclass(frozen=True, kw_only=True)
class InvoiceRequest:
    """Everything needed to download one invoice as a PDF.

    Attributes:
        invoice_number:     The invoice number to find and download (e.g. "INV-4140").
        download_directory: Directory the PDF is saved to.
        report_file_name:   Output filename WITHOUT extension; ".pdf" is enforced.
        window_title:       Fragment used to locate the Chrome Save As window.

    Raises (on construction):
        DataValidationError: if any input fails validation.
    """

    invoice_number: str
    download_directory: str
    report_file_name: str
    window_title: str = "Xero"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.invoice_number, str) or not self.invoice_number.strip():
            raise DataValidationError("invoice_number is required and must be a non-empty string")
        if not isinstance(self.download_directory, str) or not self.download_directory.strip():
            raise DataValidationError("download_directory is required and must be a non-empty string")
        if not isinstance(self.report_file_name, str) or not self.report_file_name.strip():
            raise DataValidationError("report_file_name is required and must be a non-empty string")

        if self.capture_screenshots and not (self.screenshot_path or "").strip():
            raise DataValidationError(
                "screenshot_path is required when capture_screenshots is True"
            )

    @property
    def dest_path(self) -> str:
        # PDF only; build_dest_path adds .pdf when missing and never doubles it.
        return common.build_dest_path(self.download_directory, self.report_file_name, _PDF_EXT)

    def summary_lines(self) -> list[str]:
        rows = {
            "Invoice Number": self.invoice_number,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Saved As": self.dest_path,
            "Window Title": self.window_title,
            "Capture Screenshots": self.capture_screenshots,
            "Screenshot Path": self.screenshot_path if self.capture_screenshots else "(disabled)",
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


# --------------------------------------------------------------------
# Navigation (caller-invoked; text-located, dual UI)
# --------------------------------------------------------------------
def navigate_to_invoices_page(browser, max_retries: int = _NAV_MAX_RETRIES) -> None:
    """Reach the Invoices list page via the Sales (new UI) or Business (old UI)
    menu, retrying up to max_retries times. Raises NavigationError if the list
    (its search box) never appears."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    for attempt in range(1, max_retries + 1):
        logger.info(f"Navigating to Invoices page (attempt {attempt}/{max_retries})...")
        try:
            if browser.does_page_contain_element(config.INV_NAV_SALES_BUTTON, timeout=timeout):
                browser.click_element(config.INV_NAV_SALES_BUTTON, timeout=timeout)
                browser.click_element(config.INV_NAV_INVOICES_LINK, timeout=timeout)
                logger.info("Used new-UI navigation (Sales -> Invoices)")
            else:
                browser.click_element(config.INV_NAV_BUSINESS_BUTTON, timeout=timeout)
                browser.click_element(config.INV_NAV_INVOICES_TAB, timeout=timeout)
                logger.info("Used old-UI navigation (Business -> Invoices)")
        except Exception as e:
            logger.warning(f"Navigation attempt {attempt} failed: {e}")

        if browser.does_page_contain_element(config.INV_SEARCH_INPUT, timeout=timeout):
            logger.info("Invoices list reached")
            return

    raise NavigationError(f"Could not reach the Invoices page after {max_retries} attempts")


def navigate_to_home_page(browser) -> None:
    """Return to the Home/dashboard page (new-UI Home link, old-UI Business
    button as fallback)."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    if browser.does_page_contain_element(config.INV_NAV_HOME_LINK, timeout=timeout):
        browser.click_element(config.INV_NAV_HOME_LINK, timeout=timeout)
        logger.info("Returned home (new UI)")
    else:
        browser.click_element(config.INV_NAV_BUSINESS_BUTTON, timeout=timeout)
        logger.info("Returned home via Business button (old UI)")


# --------------------------------------------------------------------
# Invoice processing (assumes already on the Invoices list page)
# --------------------------------------------------------------------
def download_invoice(browser, request: InvoiceRequest) -> None:
    """
    Download one invoice as a PDF. Assumes the browser is already on the Invoices
    list page (the caller navigates).

    Steps, in order (each returns; none calls the next):
        STEP 1 - select the "All" tab and search for the invoice number
        STEP 2 - open the matching invoice row and confirm its detail page
        STEP 3 - print to PDF, save, verify the file, dismiss the Mark-as-Sent modal

    Raises:
        Re-raises after ``ProcessLogger`` logs it. DataExtractionError if the
        invoice is not found or its page does not open; DownloadError if the file
        does not save.
    """
    with ProcessLogger("Xero Blue Download Invoice", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Selecting 'All' and searching for the invoice...")
        find_invoice(browser, request)
        logger.info("STEP 1 COMPLETED: search performed")

        logger.info("STEP 2: Opening the invoice...")
        open_invoice(browser, request)
        logger.info("STEP 2 COMPLETED: invoice detail page open")

        logger.info("STEP 3: Printing to PDF and saving...")
        print_invoice_to_pdf(browser, request)
        logger.info("STEP 3 COMPLETED: PDF saved")


def find_invoice(browser, request: InvoiceRequest) -> None:
    """Select the All status tab (widest, deterministic set), then search the
    invoice number."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    browser.click_element(config.INV_TAB_ALL, timeout=timeout)
    logger.info("Selected 'All' invoices tab")

    common.clear_and_type(browser, config.INV_SEARCH_INPUT, request.invoice_number)
    browser.click_element(config.INV_SEARCH_BUTTON, timeout=timeout)
    logger.info(f"Searched for invoice: '{request.invoice_number}'")

    # Search has run: capture the results before the found/not-found check, so a
    # not-found invoice still gets its evidence screenshot.
    common.capture_report_screenshot(
        browser, request.screenshot_path, "invoice", "search_results",
        enabled=request.capture_screenshots,
    )


def open_invoice(browser, request: InvoiceRequest) -> None:
    """Open the row whose ref cell matches the invoice number exactly, then
    confirm the detail page loaded."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT
    number_literal = xpath_literal(request.invoice_number)

    row_link = config.INV_ROW_LINK_BY_NUMBER_TPL.format(invoice=number_literal)
    if not browser.does_page_contain_element(row_link, timeout=timeout):
        raise DataExtractionError(f"Invoice not found in Xero Blue: {request.invoice_number!r}")
    browser.click_element(row_link, timeout=timeout)
    logger.info(f"Opened invoice row: '{request.invoice_number}'")

    heading = config.INV_DETAIL_HEADING_TPL.format(heading=xpath_literal(f"Invoice {request.invoice_number}"))
    if not browser.does_page_contain_element(heading, timeout=timeout):
        raise DataExtractionError(
            f"Invoice detail page did not open for {request.invoice_number!r}"
        )
    logger.info("Invoice detail page confirmed")


def print_invoice_to_pdf(browser, request: InvoiceRequest) -> None:
    """Click Print PDF, save via the Chrome dialog, verify the file, then dismiss
    the Mark-as-Sent modal if it appears."""
    logger.info("Clicking 'Print PDF'...")
    browser.click_element(config.INV_PRINT_PDF_BUTTON, timeout=common.EXPORT_TIMEOUT)

    time.sleep(2)   # brief settle so the save dialog has rendered

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)   # principle 10: confirm it actually landed
    logger.info(f"Invoice PDF saved: '{dest_path}'")

    dismiss_mark_as_sent(browser)


def dismiss_mark_as_sent(browser) -> None:
    """If the Mark-as-Sent modal appears after printing, click Cancel to dismiss
    it WITHOUT marking the invoice as sent. Best-effort - absence is fine."""
    if browser.does_page_contain_element(config.INV_MARK_AS_SENT_MODAL, timeout=common.DEFAULT_ELEMENT_TIMEOUT):
        browser.click_element(config.INV_MARK_AS_SENT_CANCEL, timeout=common.DEFAULT_ELEMENT_TIMEOUT)
        logger.info("Dismissed the Mark-as-Sent modal (Cancel)")
    else:
        logger.info("No Mark-as-Sent modal appeared - nothing to dismiss")
