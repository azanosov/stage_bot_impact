from __future__ import annotations

import os
import time
from typing import Any

from iaa_rpa_utils import setup_logger
from robocorp import windows

from . import selenium_helper as helper
from .take_screenshot import take_screenshot

# Set up logger
logger = setup_logger(__name__)

_DEFAULT_UPDATE_XPATH = "//button[@type='button' and normalize-space(text())='Update']"
_LEGACY_UPDATE_XPATH = (
    "//a[normalize-space(text())='Update' and contains(@onclick,'UpdateReport')]"
)
_DEFAULT_EXPORT_XPATH = "//button[@type='button' and normalize-space(text())='Export']"
_LEGACY_EXPORT_XPATH = "//span[@class='words' and normalize-space(text())='Export']"
_DEFAULT_FORMAT_XPATHS = {
    ".xlsx": "//button[@type='button']//span[normalize-space(text())='Excel']",
    ".pdf": "//button[@type='button']//span[normalize-space(text())='PDF']",
}
_LEGACY_FORMAT_XPATHS = {
    ".xlsx": "//a[@title='Export to Excel' and normalize-space(text())='Excel']",
    ".pdf": "//a[@title='Export to PDF' and normalize-space(text())='PDF']",
}


def download_file(
    window_title,
    download_folder_path,
    file_name,
    extension,
):

    app = windows.find_window(f"regex:.*{window_title}.* - Google Chrome")

    # Type file name
    file_input = app.find(
        'control:"EditControl" and class:"Edit" and name:"File name:"',
    ).click()
    file_path = os.path.join(download_folder_path, file_name + extension)
    file_input.send_keys("{CTRL}a")
    file_input.send_keys("{DEL}")
    file_input.send_keys(file_path)
    logger.info(f"Typed file path {file_path}")
    time.sleep(2)

    # # Select the All file type
    # app.find(
    #     'control:"ComboBoxControl" and class:"AppControlHost" and name:"Save as type:"',
    # ).click()
    # app.find('control:"ListItemControl" and name:"regex:.*All Files.*"').click()
    # logger.info("Clicked into All Files format")

    app.find('control:"ButtonControl" and name:"Save"').click()
    logger.info("Clicked save button")
    time.sleep(1)

    try:
        save_confirm_popup = app.find(
            'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"',
            timeout=3,
        )
        logger.info(f"Confirm Save As window found. Overwriting.")
        save_confirm_popup.find(
            'control:"ButtonControl" and class:"CCPushButton" and name:"Yes"',
        ).click()
    except Exception:
        logger.info("No overwrite confirmation window appeared.")


def generate_and_export_report(
    driver: Any,
    window_title: str,
    download_directory: str,
    report_file_name: str,
    extension: list[str],
    take_screenshot_flag: bool = False,
) -> str | None:
    """
    Generate a Xero report and export it in one or more formats.

    Clicks Update to regenerate the report, optionally takes a screenshot, verifies
    the Export button is present, then iterates over each requested file extension —
    opening the Export menu, clicking the matching format, and saving via the OS save dialog.

    Args:
        driver: Selenium WebDriver instance.
        window_title (str): Browser window title used to locate the save dialog.
        download_directory (str): Directory path where files will be saved.
        report_file_name (str): Base filename without extension.
        extension (list[str]): Formats to export, e.g. [".xlsx", ".pdf"]. Defaults to [".xlsx"].
        take_screenshot_flag (bool): Whether to capture a screenshot after render. Default False.

    Returns:
        str | None: Screenshot file path if taken, otherwise None.

    Raises:
        Exception: If the Export button is absent (no data) or any export/save step fails.
    """
    extensions = extension if extension else [".xlsx"]

    if helper.element_exists(driver, _DEFAULT_UPDATE_XPATH, timeout=5):
        helper.click_element(driver, _DEFAULT_UPDATE_XPATH)
    else:
        helper.click_element(driver, _LEGACY_UPDATE_XPATH)
    logger.info("Clicked Update button")

    screenshot_file_path = None
    if take_screenshot_flag:
        screenshot_file_path = take_screenshot(driver)
        logger.info(f"Screenshot saved: {screenshot_file_path}")

    if helper.element_exists(driver, _DEFAULT_EXPORT_XPATH, timeout=5):
        export_xpath = _DEFAULT_EXPORT_XPATH
    elif helper.element_exists(driver, _LEGACY_EXPORT_XPATH, timeout=5):
        export_xpath = _LEGACY_EXPORT_XPATH
    else:
        logger.warning(
            "Export button not found — no report data available for this client"
        )
        raise Exception("No report data available for this client.")

    for ext in extensions:
        logger.info(f"Exporting as {ext}...")
        helper.click_element(driver, export_xpath)

        default_format_xpath = _DEFAULT_FORMAT_XPATHS.get(
            ext, _DEFAULT_FORMAT_XPATHS[".xlsx"]
        )
        legacy_format_xpath = _LEGACY_FORMAT_XPATHS.get(
            ext, _LEGACY_FORMAT_XPATHS[".xlsx"]
        )
        format_xpath = (
            default_format_xpath
            if helper.element_exists(driver, default_format_xpath, timeout=5)
            else legacy_format_xpath
        )
        helper.click_element(driver, format_xpath)

        time.sleep(3)

        logger.info(f"Saving report to: {download_directory}")
        download_file(window_title, download_directory, report_file_name, ext)
        logger.info(
            f"Report saved as '{report_file_name}{ext}' in '{download_directory}'"
        )

    return screenshot_file_path
