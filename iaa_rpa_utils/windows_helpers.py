"""
Desktop Window Automation Helpers

This module provides reusable functions for Windows desktop automation using
robocorp-windows and RPA.Desktop. Each function that interacts with UI elements
accepts either a WindowElement (from robocorp.windows) or a Desktop instance
(from RPA.Desktop), dynamically adjusting behavior based on the object type.

Centralized from common functions across iaa_rpa_handisoft, iaa_rpa_m1,
iaa_rpa_myob_app, iaa_rpa_vc, and iaa_rpa_aps.
"""

import time
from typing import Optional, Union

from robocorp import windows
from robocorp.windows import WindowElement
from RPA.Desktop import Desktop

from .exceptions import ElementNotFoundError, WindowAutomationError, DataValidationError
from .logger import setup_logger

logger = setup_logger(__name__)

# Type alias for functions that accept both WindowElement and Desktop
WindowContext = Union[WindowElement, Desktop]


def connect_to_window(
    window_locator: str,
    timeout: int = 10,
    window_description: str = "application"
) -> WindowElement:
    """
    Connect to a desktop window using a locator string.

    Args:
        window_locator: Window locator string (can be regex pattern like 'regex:.*M1.*')
        timeout: Maximum time to wait for window in seconds
        window_description: Descriptive name for logging purposes

    Returns:
        WindowElement: The connected window element

    Raises:
        ElementNotFoundError: If window cannot be found within timeout

    Example:
        window = connect_to_window('regex:.*M1.*', timeout=10, window_description="M1")
    """
    try:
        logger.info(f"Attempting to connect to {window_description} window with locator: {window_locator}")
        window = windows.find_window(window_locator, timeout=timeout)
        logger.info(f"Successfully connected to {window_description} window")
        return window
    except Exception as e:
        error_msg = f"Failed to connect to {window_description} window with locator '{window_locator}': {e}"
        logger.error(error_msg)
        raise ElementNotFoundError(error_msg) from e


def connect_to_window_by_regex(
    regex_pattern: str,
    timeout: int = 10,
    window_description: str = "window"
) -> WindowElement:
    """
    Connect to a desktop window using a regex pattern.

    This is a convenience wrapper around connect_to_window that emphasizes regex pattern usage.
    Useful for dynamic window titles.

    Args:
        regex_pattern: Regex pattern for window title (e.g., '.*M1.*' or 'regex:.*M1.*')
        timeout: Maximum time to wait for window in seconds
        window_description: Descriptive name for logging purposes

    Returns:
        WindowElement: The connected window element

    Raises:
        ElementNotFoundError: If window cannot be found within timeout

    Example:
        window = connect_to_window_by_regex('.*M1.*', timeout=10, window_description="M1")
    """
    # Ensure regex: prefix is present
    if not regex_pattern.startswith('regex:'):
        regex_pattern = f'regex:{regex_pattern}'

    return connect_to_window(regex_pattern, timeout, window_description)


def locate(
    locator: str,
    window: WindowContext,
    timeout: int = 10
) -> object:
    """
    Find an element within a window or on the desktop.

    When a WindowElement is passed, uses window.find() and hovers over the element.
    When a Desktop instance is passed, uses desktop.find_elements() and returns the
    first match.

    Args:
        locator: Element locator string
        window: The parent window element (WindowElement) or Desktop instance
        timeout: Maximum time to wait for element in seconds (WindowElement only)

    Returns:
        The located element

    Raises:
        ElementNotFoundError: If element cannot be found

    Example:
        element = locate('name:LoginButton', window, timeout=10)
    """
    try:
        logger.info(f"Locating element with locator: {locator}")

        if isinstance(window, Desktop):
            elements = window.find_elements(locator)
            if not elements:
                raise WindowAutomationError(
                    f"No elements found with locator '{locator}'"
                )
            element = elements[0]
            logger.info(f"Successfully located element via Desktop: {locator}")
            return element
        else:
            element = window.find(locator, timeout=timeout)
            element.mouse_hover()
            logger.info(f"Successfully located and hovered over element: {locator}")
            return element

    except (ElementNotFoundError, WindowAutomationError):
        raise
    except Exception as e:
        error_msg = f"Failed to locate element with locator '{locator}': {e}"
        logger.error(error_msg)
        raise ElementNotFoundError(error_msg) from e


def locate_and_click(
    locator: str,
    window: WindowContext,
    timeout: int = 10
) -> None:
    """
    Find an element and click it.

    When a WindowElement is passed, uses locate() then element.click().
    When a Desktop instance is passed, uses desktop.find_elements() then
    desktop.click() on the first match.

    Args:
        locator: Element locator string
        window: The parent window element (WindowElement) or Desktop instance
        timeout: Maximum time to wait for element in seconds (WindowElement only)

    Raises:
        ElementNotFoundError: If element cannot be found or clicked

    Example:
        locate_and_click('name:LoginButton', window, timeout=10)
    """
    try:
        if isinstance(window, Desktop):
            elements = window.find_elements(locator)
            if not elements:
                raise ElementNotFoundError(
                    f"No elements found with locator '{locator}'"
                )
            window.click(elements[0])
            logger.info(f"Successfully clicked element via Desktop: {locator}")
        else:
            element = locate(locator, window, timeout)
            element.click()
            logger.info(f"Successfully clicked element: {locator}")

    except ElementNotFoundError:
        raise
    except Exception as e:
        error_msg = f"Failed to click element with locator '{locator}': {e}"
        logger.error(error_msg)
        raise ElementNotFoundError(error_msg) from e


def enter_keys_into_input_field(
    element: object,
    text: str,
    clear_first: bool = True,
    desktop: Optional[Desktop] = None
) -> None:
    """
    Enter text into an input field with optional clearing.

    When desktop is None, treats element as a WindowElement and uses send_keys().
    When desktop is provided, uses desktop.click(element), desktop.press_keys(),
    and desktop.type_text() for interaction.

    Args:
        element: The input field element (WindowElement or Desktop element/region)
        text: Text to enter
        clear_first: Whether to clear the field before typing (default: True)
        desktop: Optional Desktop instance for Desktop-based interaction

    Raises:
        WindowAutomationError: If text entry fails

    Example:
        # WindowElement usage:
        element = locate('name:UsernameField', window)
        enter_keys_into_input_field(element, 'john.doe@example.com')

        # Desktop usage:
        element = locate('ocr:"Username"', desktop_instance)
        enter_keys_into_input_field(element, 'john.doe@example.com', desktop=desktop_instance)
    """
    try:
        logger.info("Entering text into input field")

        if desktop is not None:
            desktop.click(element)
            if clear_first:
                desktop.press_keys("ctrl", "a")
                desktop.press_keys("delete")
                logger.debug("Cleared input field via Desktop")
            desktop.type_text(text)
        else:
            element.mouse_hover()
            element.click()
            if clear_first:
                element.send_keys("{Ctrl}a{Delete}")
                logger.debug("Cleared input field")
            element.send_keys(text)

        logger.info("Successfully entered text into input field")
    except Exception as e:
        error_msg = f"Failed to enter text into input field: {e}"
        logger.error(error_msg)
        raise WindowAutomationError(error_msg) from e


def is_logged_in(
    window_locator: str,
    verification_locator: str,
    timeout: int = 5,
    window_description: str = "application"
) -> bool:
    """
    Check if user is logged in by verifying presence of a specific element.

    Args:
        window_locator: Window locator string
        verification_locator: Element locator to verify login status
        timeout: Maximum time to wait for verification element in seconds
        window_description: Descriptive name for logging purposes

    Returns:
        bool: True if logged in (verification element found), False otherwise

    Example:
        logged_in = is_logged_in(
            'regex:.*M1.*',
            'name:DashboardMenu',
            timeout=5,
            window_description="M1"
        )
    """
    try:
        logger.info(f"Checking login status for {window_description}")
        window = connect_to_window(window_locator, timeout, window_description)
        window.find(verification_locator, timeout=timeout)
        logger.info(f"User is logged in to {window_description}")
        return True
    except Exception as e:
        logger.info(f"User is not logged in to {window_description}: {e}")
        return False


def select_dropdown_with_down(
    dropdown_locator: str,
    target_option: str,
    window: WindowContext,
    max_attempts: int = 20
) -> None:
    """
    Select a dropdown option by navigating with DOWN arrow key.

    Opens a dropdown and presses DOWN key repeatedly until the target option is found.
    Useful for dropdowns that don't support direct text entry.

    When a WindowElement is passed, uses window.find() and element.click().
    When a Desktop instance is passed, uses desktop.find_elements(), desktop.click(),
    and desktop.press_keys().

    Args:
        dropdown_locator: Locator for the dropdown element
        target_option: Text of the option to select (or locator string for WindowElement)
        window: The parent window element (WindowElement) or Desktop instance
        max_attempts: Maximum number of DOWN key presses (default: 20)

    Raises:
        ElementNotFoundError: If dropdown cannot be found
        DataValidationError: If target option is not found after max_attempts

    Example:
        select_dropdown_with_down(
            'name:StateDropdown',
            'California',
            window,
            max_attempts=20
        )
    """
    try:
        logger.info(f"Selecting dropdown option '{target_option}' from '{dropdown_locator}'")

        if isinstance(window, Desktop):
            # Desktop path: open dropdown
            elements = window.find_elements(dropdown_locator)
            if not elements:
                raise ElementNotFoundError(
                    f"Dropdown not found with locator '{dropdown_locator}'"
                )
            window.click(elements[0])
            logger.debug(f"Opened dropdown via Desktop: {dropdown_locator}")

            # Navigate with DOWN key to find target option
            for attempt in range(max_attempts):
                window.press_keys("down")

                try:
                    matches = window.find_elements(f'name:"{target_option}"')
                    if matches:
                        window.click(matches[0])
                        logger.info(f"Successfully selected '{target_option}' from dropdown via Desktop")
                        return
                except Exception:
                    pass

        else:
            # WindowElement path: open dropdown
            dropdown = locate(dropdown_locator, window)
            dropdown.click()
            logger.debug(f"Opened dropdown: {dropdown_locator}")

            # Navigate with DOWN key to find target option
            for attempt in range(max_attempts):
                window.send_keys("{Down}")

                # Try to find the target option element directly (M1 approach)
                try:
                    option_element = window.find(target_option, timeout=1)
                    option_element.click()
                    logger.info(f"Successfully selected '{target_option}' from dropdown")
                    return
                except Exception:
                    pass

        # Target option not found after max attempts
        error_msg = f"Could not find option '{target_option}' in dropdown '{dropdown_locator}' after {max_attempts} attempts"
        logger.error(error_msg)
        raise DataValidationError(error_msg)

    except ElementNotFoundError:
        raise
    except DataValidationError:
        raise
    except Exception as e:
        error_msg = f"Failed to select dropdown option '{target_option}': {e}"
        logger.error(error_msg)
        raise DataValidationError(error_msg) from e


def click_using_ocr(
    desktop: Desktop,
    text: str,
    element_description: str = "",
    wait_time: float = 1.0
) -> None:
    """
    Click an element identified by OCR text recognition.

    Uses RPA.Desktop's OCR capabilities to find text on screen and click it.

    Args:
        desktop: RPA.Desktop instance
        text: OCR text to search for on screen
        element_description: Description of the element for logging
        wait_time: Time to wait after clicking (seconds)

    Raises:
        WindowAutomationError: If no OCR match found or click fails

    Example:
        from RPA.Desktop import Desktop
        desktop = Desktop()
        click_using_ocr(desktop, "Ready to Print", "print button")
    """
    description = element_description or text
    try:
        logger.info(f"Looking for {description} via OCR: '{text}'")

        matches = desktop.find_elements(f'ocr:"{text}"')
        if not matches:
            raise WindowAutomationError(
                f"No OCR matches found for text '{text}' ({description})"
            )

        desktop.click(matches[0])
        logger.info(f"Successfully clicked {description} via OCR")

        if wait_time > 0:
            time.sleep(wait_time)

    except WindowAutomationError:
        raise
    except Exception as e:
        error_msg = f"Failed to click {description} via OCR: {e}"
        logger.error(error_msg)
        raise WindowAutomationError(error_msg) from e


def click_image_element(
    desktop: Desktop,
    image_path: str,
    element_description: str = "",
    wait_time: float = 1.0,
    click_index: int = 0
) -> dict:
    """
    Click an element identified by image template matching.

    Uses RPA.Desktop's image recognition to find an element on screen and click it.
    Returns a result dict with status information for callers that check success flags.

    Args:
        desktop: RPA.Desktop instance
        image_path: Path to the reference image file
        element_description: Description of the element for logging
        wait_time: Delay after click in seconds
        click_index: Which match to click if multiple found (default: 0 = first)

    Returns:
        dict with keys:
            - success (bool): True if element was found and clicked
            - element_found (bool): True if element was detected on screen
            - matches_count (int): Number of matches found
            - error_message (str): Error details if failed, empty if successful

    Example:
        result = click_image_element(desktop, "path/to/button.png", "Save Button")
        if result["success"]:
            print("Clicked successfully")
    """
    result = {
        "success": False,
        "element_found": False,
        "matches_count": 0,
        "error_message": ""
    }

    description = element_description or image_path
    try:
        logger.info(f"Looking for {description}: {image_path}")

        image_locator = f"image:{image_path}"
        image_matches = desktop.find_elements(image_locator)
        result["matches_count"] = len(image_matches) if image_matches else 0

        if not image_matches:
            error_msg = f"{description} not found on screen"
            logger.error(f"FAILED: {error_msg}")
            result["error_message"] = error_msg
            return result

        result["element_found"] = True
        logger.info(f"Detected {description} ({result['matches_count']} matches)")

        # Ensure click_index is within range
        if click_index >= len(image_matches):
            logger.warning(
                f"click_index {click_index} out of range for {result['matches_count']} matches, using first match"
            )
            click_index = 0

        desktop.click(image_matches[click_index])
        logger.info(f"Successfully clicked {description} (match index {click_index})")

        if wait_time > 0:
            time.sleep(wait_time)

        result["success"] = True
        return result

    except Exception as e:
        logger.error(f"Error clicking {description}: {e}")
        result["error_message"] = f"Click operation error: {e}"
        return result
