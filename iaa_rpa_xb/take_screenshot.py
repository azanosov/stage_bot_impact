"""
Module: take_screen_shot

This module provides a function to capture screenshots and save them to a specified location.
Replicates the UiPath screenshot workflow with file path validation and directory creation.
"""

from __future__ import annotations

import os
from datetime import datetime

from iaa_rpa_utils import setup_logger

# Set up logger
logger = setup_logger(__name__)


def take_screenshot(driver, file_path=None, folder_path=None):
    """
    Take a screenshot and save it to a specified location.


    1. Takes a screenshot
    2. If no file path is provided, generates a default name with timestamp
    3. Creates the directory if it doesn't exist
    4. Saves the screenshot to the specified path
    5. Logs the screenshot location

    Args:
        driver: Selenium WebDriver instance for taking browser screenshots.
        file_path (str, optional): Full path where the screenshot should be saved.
                                       If None or empty, a default name will be generated.
        folder_path (str, optional): Folder path where screenshot should be saved if file_path is not provided.
                                   Defaults to current directory if not specified.

    Returns:
        str: The full path where the screenshot was saved.

    Example:
        >>> # Save with specific path
        >>> take_screenshot(driver, file_path="C:/screenshots/error.png")

        >>> # Auto-generate filename in specific folder
        >>> take_screenshot(driver, folder_path="C:/screenshots")

        >>> # Auto-generate filename in current directory
        >>> take_screenshot(driver)
    """

    # Step 1: Generate default file path if not provided
    if not file_path or file_path.strip() == "":
        # Default folder to current directory if not provided
        if not folder_path or folder_path.strip() == "":
            folder_path = os.getcwd()

        # Generate timestamp-based filename
        timestamp = datetime.now().strftime("%y%m%d.%H%M%S")
        filename = f"ExceptionScreenshot_{timestamp}.png"
        file_path = os.path.join(folder_path, filename)

    # Step 2: Get file info and extract directory path
    screenshot_file_info = os.path.abspath(file_path)
    directory_name = os.path.dirname(screenshot_file_info)

    # Step 3: Create directory if it doesn't exist
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
        logger.info(f"Created directory: {directory_name}")

    # Step 4: Take screenshot using Selenium WebDriver
    driver.save_screenshot(file_path)

    # Step 5: Log the screenshot location
    log_message = f"Screenshot saved at: {file_path}"
    logger.info(log_message)

    return file_path
