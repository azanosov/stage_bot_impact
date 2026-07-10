"""
Popup Handler for Web and Windows Automation

This module provides comprehensive popup detection and handling capabilities for RPA automation.
Supports Selenium, Playwright, and Windows UI Automation with AI and OCR-based detection.
"""

import base64
import io
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException as SeleniumTimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import (
    BrowserError,
    ConfigurationError,
    ElementNotFoundError,
    RetryExhaustedError,
    TimeoutError,
    WebAutomationError,
)
from .logger import setup_logger

logger = setup_logger(__name__)


# ============================================================================
# Data Classes and Enums
# ============================================================================


class PopupType(Enum):
    """Types of popups that can be detected"""

    MODAL = "modal"
    DIALOG = "dialog"
    ALERT = "alert"
    OVERLAY = "overlay"
    NOTIFICATION = "notification"
    COOKIE_BANNER = "cookie_banner"
    ADVERTISEMENT = "advertisement"
    UNKNOWN = "unknown"


@dataclass
class PopupDetectionResult:
    """Result of popup detection"""

    detected: bool
    popup_type: PopupType
    element: Optional[Any] = None
    confidence: float = 0.0
    close_button: Optional[Any] = None
    detection_method: str = "unknown"
    screenshot_path: Optional[str] = None
    ai_analysis: Optional[str] = None
    ocr_text: Optional[str] = None


# ============================================================================
# DOM Inspection and Detection
# ============================================================================


# Common selectors for popup elements
POPUP_SELECTORS = [
    # Modals and dialogs
    "[role='dialog']",
    "[role='alertdialog']",
    ".modal",
    ".dialog",
    ".popup",
    ".overlay",
    "[class*='modal']",
    "[class*='dialog']",
    "[class*='popup']",
    "[class*='overlay']",
    # Cookie banners
    "#cookie-banner",
    ".cookie-banner",
    "[class*='cookie']",
    "[id*='cookie']",
    # Notifications
    ".notification",
    ".toast",
    ".alert",
    "[role='alert']",
    "[class*='notification']",
    "[class*='toast']",
]

# Common close button selectors
CLOSE_BUTTON_SELECTORS = [
    # By role and aria
    "[role='button'][aria-label*='close' i]",
    "[role='button'][aria-label*='dismiss' i]",
    "[aria-label*='close' i]",
    "[aria-label*='dismiss' i]",
    # By class and ID
    ".close",
    ".dismiss",
    ".modal-close",
    ".dialog-close",
    "[class*='close']",
    "[class*='dismiss']",
    # By title
    "[title*='close' i]",
    "[title*='dismiss' i]",
    # Common button text
    "button:contains('Close')",
    "button:contains('Dismiss')",
    "button:contains('X')",
    "button:contains('×')",
    "a:contains('Close')",
    "a:contains('Dismiss')",
    # SVG close icons
    "svg[class*='close']",
    "svg[class*='dismiss']",
]


def _find_popup_elements_selenium(driver: WebDriver) -> List[WebElement]:
    """Find potential popup elements using Selenium"""
    elements = []
    for selector in POPUP_SELECTORS:
        try:
            found = driver.find_elements(By.CSS_SELECTOR, selector)
            for elem in found:
                # Check if element is visible and has high z-index
                if elem.is_displayed():
                    try:
                        z_index = driver.execute_script(
                            "return window.getComputedStyle(arguments[0]).zIndex;", elem
                        )
                        # Consider elements with z-index > 100 as potential popups
                        if z_index and str(z_index).isdigit() and int(z_index) > 100:
                            elements.append(elem)
                    except:
                        # If z-index check fails, still consider visible modal/dialog elements
                        elements.append(elem)
        except Exception as e:
            logger.debug(f"Error finding elements with selector '{selector}': {e}")

    return elements


def _find_close_button_selenium(
    driver: WebDriver, popup_element: Optional[WebElement] = None
) -> Optional[WebElement]:
    """Find close button within popup or on page"""
    search_context = popup_element if popup_element else driver

    for selector in CLOSE_BUTTON_SELECTORS:
        try:
            # Try direct CSS selector
            if selector.startswith("["):
                elements = search_context.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        return elem
            # For :contains selectors, use XPath
            elif ":contains" in selector:
                text = (
                    selector.split("'")[1]
                    if "'" in selector
                    else selector.split('"')[1]
                )
                tag = selector.split(":")[0]
                xpath = f".//{tag}[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
                elements = search_context.find_elements(By.XPATH, xpath)
                for elem in elements:
                    if elem.is_displayed():
                        return elem
            else:
                elements = search_context.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        return elem
        except Exception as e:
            logger.debug(f"Error finding close button with selector '{selector}': {e}")

    return None


def _find_overlay_element_selenium(driver: WebDriver) -> Optional[WebElement]:
    """Find overlay/backdrop element"""
    overlay_selectors = [
        ".modal-backdrop",
        ".overlay",
        ".backdrop",
        "[class*='backdrop']",
        "[class*='overlay']",
    ]

    for selector in overlay_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for elem in elements:
                if elem.is_displayed():
                    # Check if it covers most of the screen
                    size = elem.size
                    if size["width"] > 500 and size["height"] > 500:
                        return elem
        except:
            pass

    return None


# ============================================================================
# Screenshot and Image Processing
# ============================================================================


def _capture_screenshot_selenium(driver: WebDriver, output_dir: str = "output") -> str:
    """Capture screenshot and return path"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)
    screenshot_path = os.path.join(output_dir, f"popup_screenshot_{timestamp}.png")

    try:
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot captured: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        raise BrowserError(f"Screenshot capture failed: {e}") from e


def _log_screenshot_to_robocorp(
    screenshot_path: str, description: str = "Popup detected"
):
    """Log screenshot to Robocorp HTML log"""
    try:
        from RPA.core import notebook

        notebook.notebook_image(screenshot_path, description)
        logger.info(f"Screenshot logged to Robocorp: {description}")
    except ImportError:
        logger.debug("RPA.core not available, skipping Robocorp logging")
    except Exception as e:
        logger.warning(f"Failed to log screenshot to Robocorp: {e}")


def _image_to_base64(image_path: str) -> str:
    """Convert image file to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# ============================================================================
# OCR Providers
# ============================================================================


def _ocr_with_pytesseract(image_path: str) -> str:
    """Extract text from image using Tesseract OCR"""
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        logger.debug(f"Tesseract OCR extracted {len(text)} characters")
        return text
    except ImportError:
        logger.warning(
            "pytesseract not installed. Install with: pip install pytesseract pillow"
        )
        return ""
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return ""


def _ocr_with_oracle_vision(image_path: str) -> str:
    """Extract text from image using Oracle Cloud Vision"""
    try:
        import oci
        from oci.ai_vision import AIServiceVisionClient
        from oci.ai_vision.models import (
            AnalyzeImageDetails,
            ImageObjectDetectionFeature,
            ImageTextDetectionFeature,
            InlineImageDetails,
        )

        # Load OCI config from environment or default location
        config_file = os.environ.get("OCI_CONFIG_FILE", "~/.oci/config")
        config_profile = os.environ.get("OCI_CONFIG_PROFILE", "DEFAULT")

        config = oci.config.from_file(config_file, config_profile)
        ai_vision_client = AIServiceVisionClient(config)

        # Read and encode image
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        # Create inline image details
        inline_image = InlineImageDetails(
            data=base64.b64encode(image_data).decode("utf-8")
        )

        # Analyze image for text
        analyze_image_details = AnalyzeImageDetails(
            features=[ImageTextDetectionFeature(feature_type="TEXT_DETECTION")],
            image=inline_image,
        )

        response = ai_vision_client.analyze_image(analyze_image_details)

        # Extract text from response
        text_lines = []
        if hasattr(response.data, "image_text") and response.data.image_text:
            for text_item in response.data.image_text.words:
                text_lines.append(text_item.text)

        extracted_text = " ".join(text_lines)
        logger.debug(f"Oracle Vision OCR extracted {len(extracted_text)} characters")
        return extracted_text

    except ImportError:
        logger.warning("OCI SDK not installed. Install with: pip install oci")
        return ""
    except Exception as e:
        logger.error(f"Oracle Vision OCR failed: {e}")
        return ""


# ============================================================================
# AI Analysis (Anthropic Claude Vision)
# ============================================================================


def _analyze_with_claude_vision(
    image_path: str,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    model: str = "claude-3-5-sonnet-20241022",
) -> Dict[str, Any]:
    """Analyze screenshot using Anthropic Claude Vision API with retry logic"""
    try:
        import anthropic

        # Get API key from parameter or environment
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable."
            )
            return {
                "has_popup": False,
                "confidence": 0.0,
                "reasoning": "API key not available",
            }

        client = anthropic.Anthropic(api_key=api_key)

        # Read and encode image
        image_data = _image_to_base64(image_path)

        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(max_retries):
            try:
                # Analyze image
                message = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_data,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": """Analyze this screenshot and determine if there is a blocking popup, modal, dialog, or overlay present.

Look for:
1. Modal dialogs or popups that block the main content
2. Cookie consent banners
3. Advertisement overlays
4. Notification popups
5. Alert dialogs

Respond with a JSON object with these fields:
{
    "has_popup": true/false,
    "popup_type": "modal|dialog|alert|overlay|notification|cookie_banner|advertisement|none",
    "confidence": 0.0-1.0,
    "close_button_location": "description of where the close button is, if visible",
    "reasoning": "brief explanation of your determination"
}""",
                                },
                            ],
                        }
                    ],
                )

                # Parse response
                response_text = message.content[0].text
                logger.debug(f"Claude Vision response: {response_text}")

                # Try to parse JSON response
                import json

                try:
                    result = json.loads(response_text)
                    logger.info(
                        f"Claude Vision analysis: popup={result.get('has_popup')}, confidence={result.get('confidence')}"
                    )
                    return result
                except json.JSONDecodeError:
                    # If not valid JSON, extract key information
                    has_popup = (
                        "true" in response_text.lower()
                        or "popup" in response_text.lower()
                    )
                    return {
                        "has_popup": has_popup,
                        "confidence": 0.5,
                        "reasoning": response_text,
                    }

            except (
                anthropic.RateLimitError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 1.0  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Claude Vision API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Claude Vision API failed after {max_retries} attempts: {e}"
                    )
            except anthropic.APIError as e:
                # For other API errors (e.g., invalid request), don't retry
                logger.error(f"Claude Vision API error: {e}")
                return {
                    "has_popup": False,
                    "confidence": 0.0,
                    "reasoning": f"API Error: {e}",
                }

        # If all retries exhausted
        logger.error(
            f"Claude Vision analysis failed after {max_retries} retries: {last_exception}"
        )
        return {
            "has_popup": False,
            "confidence": 0.0,
            "reasoning": f"Error after {max_retries} retries: {last_exception}",
        }

    except ImportError:
        logger.warning(
            "anthropic package not installed. Install with: pip install anthropic"
        )
        return {
            "has_popup": False,
            "confidence": 0.0,
            "reasoning": "Anthropic SDK not available",
        }
    except Exception as e:
        logger.error(f"Claude Vision analysis failed: {e}")
        return {"has_popup": False, "confidence": 0.0, "reasoning": f"Error: {e}"}


# ============================================================================
# Popup Closing Strategies
# ============================================================================


def _close_with_button(driver: WebDriver, close_button: WebElement) -> bool:
    """Attempt to close popup by clicking close button"""
    try:
        # Scroll into view
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", close_button
        )
        time.sleep(0.2)

        # Try regular click
        try:
            close_button.click()
            logger.info("Closed popup with close button (regular click)")
            return True
        except:
            # Try JavaScript click
            driver.execute_script("arguments[0].click();", close_button)
            logger.info("Closed popup with close button (JavaScript click)")
            return True
    except Exception as e:
        logger.debug(f"Failed to close with button: {e}")
        return False


def _close_with_escape(driver: WebDriver) -> bool:
    """Attempt to close popup by pressing ESC key"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains

        actions = ActionChains(driver)
        actions.send_keys(Keys.ESCAPE)
        actions.perform()
        time.sleep(0.5)  # Wait for popup to close
        logger.info("Sent ESC key to close popup")
        return True
    except Exception as e:
        logger.debug(f"Failed to close with ESC key: {e}")
        return False


def _close_with_overlay(driver: WebDriver, overlay: WebElement) -> bool:
    """Attempt to close popup by clicking overlay/backdrop"""
    try:
        # Click on the overlay
        driver.execute_script("arguments[0].click();", overlay)
        time.sleep(0.5)  # Wait for popup to close
        logger.info("Closed popup by clicking overlay")
        return True
    except Exception as e:
        logger.debug(f"Failed to close with overlay click: {e}")
        return False


# ============================================================================
# Context Manager for Web Popups
# ============================================================================


class WebPopupMonitor:
    """Context manager for monitoring and handling web popups"""

    def __init__(
        self,
        driver: WebDriver,
        popup_handler: "PopupHandler",
        check_on_enter: bool = False,
        check_on_exit: bool = True,
    ):
        self.driver = driver
        self.popup_handler = popup_handler
        self.check_on_enter = check_on_enter
        self.check_on_exit = check_on_exit

    def __enter__(self):
        if self.check_on_enter:
            self.popup_handler.check_and_close_web(self.driver)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.check_on_exit:
            self.popup_handler.check_and_close_web(self.driver)
        return False  # Don't suppress exceptions


# ============================================================================
# Main Popup Handler Class
# ============================================================================


class PopupHandler:
    """
    Comprehensive popup handler for web and Windows automation.

    Supports:
    - Selenium WebDriver
    - Playwright (sync)
    - Windows UI Automation (robocorp-windows)
    - AI-based detection (Anthropic Claude Vision)
    - OCR-based text extraction (Tesseract or Oracle Cloud Vision)

    Usage:
        # Initialize handler
        handler = PopupHandler(
            use_ai=True,
            use_ocr="pytesseract",
            capture_screenshots=True,
            on_failure="warn"
        )

        # Explicit call at checkpoints
        handler.check_and_close_web(driver)

        # Context manager for risky sections
        with handler.monitor_web(driver):
            # automation code
            driver.find_element(By.ID, "submit").click()
    """

    def __init__(
        self,
        use_ai: bool = True,
        use_ocr: Optional[Literal["pytesseract", "oracle"]] = "pytesseract",
        anthropic_api_key: Optional[str] = None,
        anthropic_model: str = "claude-3-5-sonnet-20241022",
        capture_screenshots: bool = True,
        on_failure: Literal["raise", "warn"] = "warn",
        max_attempts: int = 3,
        timeout: float = 5.0,
        screenshot_dir: str = "output",
        log_to_robocorp: bool = True,
    ):
        """
        Initialize PopupHandler

        Args:
            use_ai: Use Anthropic Claude Vision for popup detection
            use_ocr: OCR provider ("pytesseract" or "oracle"), or None to disable
            anthropic_api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            anthropic_model: Anthropic Claude model to use (default: claude-3-5-sonnet-20241022)
            capture_screenshots: Capture screenshots when popups are detected
            on_failure: Action on failure - "raise" exception or "warn" and continue
            max_attempts: Maximum retry attempts for popup detection
            timeout: Timeout in seconds for popup detection operations
            screenshot_dir: Directory to save screenshots
            log_to_robocorp: Log screenshots to Robocorp HTML log
        """
        self.use_ai = use_ai
        self.use_ocr = use_ocr
        self.anthropic_api_key = anthropic_api_key
        self.anthropic_model = anthropic_model
        self.capture_screenshots = capture_screenshots
        self.on_failure = on_failure
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.screenshot_dir = screenshot_dir
        self.log_to_robocorp = log_to_robocorp

        logger.info(
            f"PopupHandler initialized: AI={use_ai}, OCR={use_ocr}, "
            f"failure_mode={on_failure}, attempts={max_attempts}, timeout={timeout}s"
        )

    def _detect_popup_selenium(self, driver: WebDriver) -> PopupDetectionResult:
        """Detect popup using Selenium with DOM inspection, AI, and OCR"""
        logger.debug("Starting popup detection (Selenium)")

        # Step 1: DOM inspection for popup elements
        popup_elements = _find_popup_elements_selenium(driver)

        if not popup_elements:
            logger.debug("No popup elements found via DOM inspection")
            return PopupDetectionResult(
                detected=False,
                popup_type=PopupType.UNKNOWN,
                detection_method="dom_inspection",
            )

        logger.info(f"Found {len(popup_elements)} potential popup elements")

        # Step 2: Capture screenshot if enabled
        screenshot_path = None
        if self.capture_screenshots:
            try:
                screenshot_path = _capture_screenshot_selenium(
                    driver, self.screenshot_dir
                )
                if self.log_to_robocorp:
                    _log_screenshot_to_robocorp(
                        screenshot_path, "Popup detected - analyzing"
                    )
            except Exception as e:
                logger.warning(f"Screenshot capture failed: {e}")

        # Step 3: AI analysis (if enabled)
        ai_result = None
        if self.use_ai and screenshot_path:
            logger.info("Analyzing screenshot with Claude Vision AI")
            ai_result = _analyze_with_claude_vision(
                screenshot_path, self.anthropic_api_key, model=self.anthropic_model
            )

            if not ai_result.get("has_popup", False):
                logger.info("AI analysis: No blocking popup detected")
                # Trust AI if it says no popup
                return PopupDetectionResult(
                    detected=False,
                    popup_type=PopupType.UNKNOWN,
                    detection_method="ai_analysis",
                    screenshot_path=screenshot_path,
                    ai_analysis=ai_result.get("reasoning"),
                    confidence=ai_result.get("confidence", 0.0),
                )

        # Step 4: OCR text extraction (fallback or supplementary)
        ocr_text = None
        if self.use_ocr and screenshot_path:
            logger.info(f"Extracting text with OCR ({self.use_ocr})")
            if self.use_ocr == "pytesseract":
                ocr_text = _ocr_with_pytesseract(screenshot_path)
            elif self.use_ocr == "oracle":
                ocr_text = _ocr_with_oracle_vision(screenshot_path)

            if ocr_text:
                logger.debug(f"OCR extracted text: {ocr_text[:100]}...")

        # Step 5: Find close button
        close_button = None
        for popup_elem in popup_elements:
            close_button = _find_close_button_selenium(driver, popup_elem)
            if close_button:
                logger.info("Found close button within popup")
                break

        if not close_button:
            # Try finding close button on page
            close_button = _find_close_button_selenium(driver, None)
            if close_button:
                logger.info("Found close button on page")

        # Determine popup type based on element attributes and AI analysis
        popup_type = PopupType.UNKNOWN
        if ai_result and ai_result.get("popup_type"):
            try:
                popup_type = PopupType(ai_result["popup_type"])
            except ValueError:
                popup_type = PopupType.UNKNOWN

        confidence = ai_result.get("confidence", 0.7) if ai_result else 0.7

        return PopupDetectionResult(
            detected=True,
            popup_type=popup_type,
            element=popup_elements[0] if popup_elements else None,
            confidence=confidence,
            close_button=close_button,
            detection_method="dom+ai+ocr" if (self.use_ai and self.use_ocr) else "dom",
            screenshot_path=screenshot_path,
            ai_analysis=ai_result.get("reasoning") if ai_result else None,
            ocr_text=ocr_text,
        )

    def _close_popup_selenium(
        self, driver: WebDriver, detection_result: PopupDetectionResult
    ) -> bool:
        """Close popup using various strategies"""
        logger.info("Attempting to close popup")

        # Strategy 1: Click close button
        if detection_result.close_button:
            logger.info("Strategy 1: Attempting to close with close button")
            if _close_with_button(driver, detection_result.close_button):
                time.sleep(0.5)  # Wait for close animation
                return True

        # Strategy 2: Press ESC key
        logger.info("Strategy 2: Attempting to close with ESC key")
        if _close_with_escape(driver):
            time.sleep(0.5)
            # Verify popup is gone
            remaining_popups = _find_popup_elements_selenium(driver)
            if not remaining_popups:
                return True

        # Strategy 3: Click overlay/backdrop
        logger.info("Strategy 3: Attempting to close by clicking overlay")
        overlay = _find_overlay_element_selenium(driver)
        if overlay:
            if _close_with_overlay(driver, overlay):
                time.sleep(0.5)
                # Verify popup is gone
                remaining_popups = _find_popup_elements_selenium(driver)
                if not remaining_popups:
                    return True

        logger.warning("All popup closing strategies failed")
        return False

    def check_and_close_web(
        self,
        driver: Union[WebDriver, "PlaywrightBrowser"],
        detection_mode: Literal["smart", "dom_only", "ai_only"] = "smart",
    ) -> PopupDetectionResult:
        """
        Check for web popups and close them (Selenium or Playwright)

        Args:
            driver: Selenium WebDriver or PlaywrightBrowser instance
            detection_mode: Detection strategy - "smart" (DOM+AI+OCR), "dom_only", "ai_only"

        Returns:
            PopupDetectionResult with detection details

        Raises:
            BrowserError: If popup handling fails and on_failure="raise"
        """
        # Detect if this is Selenium or Playwright
        is_selenium = isinstance(driver, WebDriver)
        is_playwright = hasattr(driver, "_browser_type") or hasattr(driver, "page")

        if is_playwright:
            logger.info("Playwright driver detected - using Playwright handler")
            return self._check_and_close_playwright(driver)
        elif is_selenium:
            logger.info("Selenium driver detected - using Selenium handler")
            return self._check_and_close_selenium(driver)
        else:
            error_msg = f"Unsupported driver type: {type(driver)}"
            logger.error(error_msg)
            if self.on_failure == "raise":
                raise BrowserError(error_msg)
            return PopupDetectionResult(detected=False, popup_type=PopupType.UNKNOWN)

    def _check_and_close_selenium(self, driver: WebDriver) -> PopupDetectionResult:
        """Internal method for Selenium popup handling with retry logic"""
        attempt = 0
        last_error = None

        while attempt < self.max_attempts:
            attempt += 1
            logger.info(f"Popup detection attempt {attempt}/{self.max_attempts}")

            try:
                # Detect popup
                result = self._detect_popup_selenium(driver)

                if not result.detected:
                    logger.info("No popup detected")
                    return result

                # Popup detected, attempt to close
                logger.info(
                    f"Popup detected: type={result.popup_type.value}, confidence={result.confidence}"
                )
                closed = self._close_popup_selenium(driver, result)

                if closed:
                    logger.info("Popup successfully closed")
                    return result
                else:
                    logger.warning(
                        f"Failed to close popup (attempt {attempt}/{self.max_attempts})"
                    )
                    last_error = "Failed to close popup with all strategies"

                    if attempt < self.max_attempts:
                        time.sleep(1)  # Wait before retry
                        continue

            except Exception as e:
                logger.error(
                    f"Error during popup handling (attempt {attempt}/{self.max_attempts}): {e}"
                )
                last_error = str(e)

                if attempt < self.max_attempts:
                    time.sleep(1)
                    continue

        # All attempts failed
        error_msg = (
            f"Failed to handle popup after {self.max_attempts} attempts: {last_error}"
        )
        logger.error(error_msg)

        if self.on_failure == "raise":
            raise RetryExhaustedError(error_msg)
        else:
            logger.warning(
                f"Continuing despite popup handling failure (on_failure={self.on_failure})"
            )
            return PopupDetectionResult(
                detected=True, popup_type=PopupType.UNKNOWN, detection_method="failed"
            )

    def _check_and_close_playwright(
        self, playwright_driver: "PlaywrightBrowser"
    ) -> PopupDetectionResult:
        """Check and close popups using Playwright (sync)"""
        logger.info("Playwright popup handling - converting to Selenium-like approach")

        # For now, use similar approach as Selenium
        # In future, this can be optimized for Playwright-specific features
        try:
            from playwright.sync_api import Page

            page = (
                playwright_driver.page
                if hasattr(playwright_driver, "page")
                else playwright_driver
            )

            # Take screenshot
            screenshot_path = None
            if self.capture_screenshots:
                os.makedirs(self.screenshot_dir, exist_ok=True)
                timestamp = int(time.time() * 1000)
                screenshot_path = os.path.join(
                    self.screenshot_dir, f"popup_screenshot_{timestamp}.png"
                )
                page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot captured: {screenshot_path}")

                if self.log_to_robocorp:
                    _log_screenshot_to_robocorp(
                        screenshot_path, "Popup detected (Playwright)"
                    )

            # AI analysis
            ai_result = None
            if self.use_ai and screenshot_path:
                ai_result = _analyze_with_claude_vision(
                    screenshot_path, self.anthropic_api_key, model=self.anthropic_model
                )

                if not ai_result.get("has_popup", False):
                    return PopupDetectionResult(
                        detected=False,
                        popup_type=PopupType.UNKNOWN,
                        detection_method="ai_analysis",
                        screenshot_path=screenshot_path,
                    )

            # Try to find and close popup
            # Check common popup patterns
            popup_found = False
            for selector in POPUP_SELECTORS[:5]:  # Check most common
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        popup_found = True

                        # Try to find close button
                        for close_sel in CLOSE_BUTTON_SELECTORS[:10]:
                            try:
                                close_btn = element.query_selector(
                                    close_sel.split(":")[0]
                                )  # Simplified
                                if close_btn and close_btn.is_visible():
                                    close_btn.click()
                                    logger.info(
                                        "Closed popup with close button (Playwright)"
                                    )
                                    return PopupDetectionResult(
                                        detected=True,
                                        popup_type=PopupType.MODAL,
                                        detection_method="playwright",
                                        screenshot_path=screenshot_path,
                                    )
                            except:
                                continue

                        # Try ESC key
                        page.keyboard.press("Escape")
                        logger.info("Sent ESC key (Playwright)")
                        return PopupDetectionResult(
                            detected=True,
                            popup_type=PopupType.MODAL,
                            detection_method="playwright",
                            screenshot_path=screenshot_path,
                        )
                except:
                    continue

            if not popup_found:
                return PopupDetectionResult(
                    detected=False,
                    popup_type=PopupType.UNKNOWN,
                    detection_method="playwright",
                )

        except Exception as e:
            logger.error(f"Playwright popup handling failed: {e}")
            if self.on_failure == "raise":
                raise BrowserError(f"Playwright popup handling failed: {e}") from e

        return PopupDetectionResult(detected=False, popup_type=PopupType.UNKNOWN)

    def check_and_close_windows(self, timeout: float = 5.0) -> bool:
        """
        Check for and close Windows popups using robocorp-windows

        Args:
            timeout: Timeout in seconds for finding Windows popups

        Returns:
            True if popup was found and closed, False otherwise

        Raises:
            BrowserError: If Windows popup handling fails and on_failure="raise"
        """
        logger.info("Checking for Windows popups")

        try:
            from robocorp.windows import find_window, Desktop
            import robocorp.windows as windows

            # Common Windows popup patterns
            popup_patterns = [
                # System dialogs
                {"name": "*Error*"},
                {"name": "*Warning*"},
                {"name": "*Alert*"},
                {"name": "*Information*"},
                # Permission prompts
                {"name": "*User Account Control*"},
                {"name": "*Windows Security*"},
                # Application alerts
                {"class": "#32770"},  # Dialog class
                {"class": "MozillaDialogClass"},
                {"class": "Chrome_WidgetWin_*"},
            ]

            desktop = Desktop()

            for pattern in popup_patterns:
                try:
                    # Try to find window
                    window = None
                    if "name" in pattern:
                        windows_list = desktop.windows()
                        for win in windows_list:
                            if pattern["name"].replace("*", "") in win.name:
                                window = win
                                break

                    if window:
                        logger.info(f"Found Windows popup: {window.name}")

                        # Take screenshot if enabled
                        if self.capture_screenshots:
                            try:
                                screenshot_path = os.path.join(
                                    self.screenshot_dir,
                                    f"windows_popup_{int(time.time()*1000)}.png",
                                )
                                desktop.screenshot(screenshot_path)
                                if self.log_to_robocorp:
                                    _log_screenshot_to_robocorp(
                                        screenshot_path, f"Windows popup: {window.name}"
                                    )
                            except Exception as e:
                                logger.warning(f"Windows screenshot failed: {e}")

                        # Try to close window
                        # Strategy 1: Find and click close button
                        try:
                            close_btn = window.find(
                                "Button name:Close or name:Cancel or name:OK or name:X"
                            )
                            if close_btn:
                                close_btn.click()
                                logger.info("Closed Windows popup with close button")
                                return True
                        except:
                            pass

                        # Strategy 2: Send ESC key
                        try:
                            window.send_keys("{ESC}")
                            logger.info("Sent ESC to Windows popup")
                            return True
                        except:
                            pass

                        # Strategy 3: Send ALT+F4
                        try:
                            window.send_keys("%{F4}")
                            logger.info("Sent ALT+F4 to Windows popup")
                            return True
                        except:
                            pass

                        # Strategy 4: Force close
                        try:
                            window.close()
                            logger.info("Force closed Windows popup")
                            return True
                        except:
                            pass

                        logger.warning(f"Failed to close Windows popup: {window.name}")

                except Exception as e:
                    logger.debug(f"Error checking pattern {pattern}: {e}")
                    continue

            logger.info("No Windows popups found")
            return False

        except ImportError:
            logger.warning(
                "robocorp-windows not installed. Install with: pip install robocorp-windows"
            )
            if self.on_failure == "raise":
                raise ConfigurationError("robocorp-windows not installed")
            return False
        except Exception as e:
            logger.error(f"Windows popup handling failed: {e}")
            if self.on_failure == "raise":
                raise BrowserError(f"Windows popup handling failed: {e}") from e
            return False

    def monitor_web(
        self,
        driver: Union[WebDriver, "PlaywrightBrowser"],
        check_on_enter: bool = False,
        check_on_exit: bool = True,
    ) -> WebPopupMonitor:
        """
        Context manager for monitoring web popups

        Args:
            driver: Selenium WebDriver or Playwright instance
            check_on_enter: Check for popups when entering context
            check_on_exit: Check for popups when exiting context

        Returns:
            WebPopupMonitor context manager

        Example:
            with handler.monitor_web(driver):
                driver.find_element(By.ID, "submit").click()
                time.sleep(2)
                # Popup will be checked and closed on exit
        """
        return WebPopupMonitor(driver, self, check_on_enter, check_on_exit)
