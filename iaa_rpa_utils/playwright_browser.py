"""
Playwright Browser Wrapper for RPA Automation

Provides a wrapper around Playwright sync API similar to SeleniumBrowser.
Supports Chrome/Chromium automation with profile management and screenshot capabilities.
"""

import os
import platform
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, Iterable

from .logger import setup_logger
from .exceptions import WebAutomationError, NavigationError, BrowserError, ElementNotFoundError

logger = setup_logger(__name__)

DEFAULT_ELEMENT_TIMEOUT = 30000  # Playwright uses milliseconds


def _resolve_user_data_dir() -> Path:
    """Resolve Chrome user data directory for the current platform"""
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    elif system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local")
        return Path(local_appdata) / "Google" / "Chrome" / "User Data"
    else:  # Linux
        chrome = home / ".config" / "google-chrome"
        chromium = home / ".config" / "chromium"
        return chrome if chrome.exists() else (chromium if chromium.exists() else chrome)


class PlaywrightBrowser:
    """
    Playwright browser wrapper for sync API.

    Similar to SeleniumBrowser but uses Playwright for automation.
    Supports:
      - Chrome/Chromium automation
      - Profile management (use existing or clean profile)
      - Headless mode
      - Screenshot capture
      - Download directory configuration

    Usage:
        browser = PlaywrightBrowser(headless=False)
        browser.goto("https://example.com")
        browser.screenshot("output.png")
        browser.close()
    """

    def __init__(
        self,
        headless: bool = False,
        download_dir: str = "outputs",
        use_existing_profile: bool = False,
        profile_directory: str = "Default",
        *,
        copy_profile_to_temp: bool = True,
        clean_profile_instead: bool = False,
        page_load_timeout_sec: int = 60,
        browser_type: str = "chromium",  # chromium, firefox, webkit
    ):
        """
        Initialize Playwright browser

        Args:
            headless: Run browser in headless mode
            download_dir: Directory for downloads
            use_existing_profile: Use existing Chrome profile
            profile_directory: Profile directory name (e.g., "Default", "Profile 1")
            copy_profile_to_temp: Copy profile to temp directory (safer)
            clean_profile_instead: Use a fresh/clean profile
            page_load_timeout_sec: Page load timeout in seconds
            browser_type: Browser type - "chromium", "firefox", or "webkit"
        """
        self.download_dir = download_dir
        self._temp_profile_dir: Optional[Path] = None
        self._page_load_timeout_ms = page_load_timeout_sec * 1000
        self._browser_type_name = browser_type

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = None
            self._context = None
            self.page = None

            self._setup_browser(
                headless=headless,
                use_existing_profile=use_existing_profile,
                profile_directory=profile_directory,
                copy_profile_to_temp=copy_profile_to_temp,
                clean_profile_instead=clean_profile_instead,
            )

        except ImportError:
            error_msg = (
                "Playwright not installed. Install with: pip install playwright && playwright install"
            )
            logger.error(error_msg)
            raise WebAutomationError(error_msg)
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise WebAutomationError(f"Could not initialize Playwright: {e}") from e

    def _setup_browser(
        self,
        *,
        headless: bool,
        use_existing_profile: bool,
        profile_directory: str,
        copy_profile_to_temp: bool,
        clean_profile_instead: bool,
    ):
        """Setup Playwright browser with appropriate options"""
        # Get browser type
        if self._browser_type_name == "chromium":
            browser_type = self._playwright.chromium
        elif self._browser_type_name == "firefox":
            browser_type = self._playwright.firefox
        elif self._browser_type_name == "webkit":
            browser_type = self._playwright.webkit
        else:
            raise ValueError(f"Unsupported browser type: {self._browser_type_name}")

        # Prepare launch arguments
        launch_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=RestoreSession,Translate",
        ]

        # Linux/container sandbox hygiene
        if platform.system() == "Linux":
            in_container = Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
            is_root = hasattr(os, "geteuid") and os.geteuid() == 0
            if in_container or is_root:
                launch_args.append("--no-sandbox")
                launch_args.append("--disable-dev-shm-usage")

        # Profile management
        user_data_dir = None
        if use_existing_profile and not clean_profile_instead:
            src_user_data_dir = _resolve_user_data_dir()

            if copy_profile_to_temp:
                # Clone profile to temp directory
                src_profile = src_user_data_dir / profile_directory
                if not src_profile.exists():
                    logger.warning(f"Profile not found: {src_profile}, using clean profile")
                else:
                    tmp = Path(tempfile.mkdtemp(prefix="playwright-chrome-"))
                    self._temp_profile_dir = tmp

                    # Copy profile
                    def _ignore(dirpath, names):
                        ignore_list = set()
                        for n in names:
                            if n.startswith("Singleton") or n in {"Crashpad", "GrShaderCache", "ShaderCache"}:
                                ignore_list.add(n)
                            if n in {"GPUCache", "Code Cache", "Media Cache", "Application Cache"}:
                                ignore_list.add(n)
                        return ignore_list

                    dst_profile = tmp / profile_directory
                    try:
                        shutil.copytree(src_profile, dst_profile, ignore=_ignore)

                        # Copy required files
                        for item in ["Local State", "First Run"]:
                            src_item = src_user_data_dir / item
                            if src_item.exists():
                                try:
                                    shutil.copy2(src_item, tmp / item)
                                except:
                                    pass

                        user_data_dir = str(tmp)
                        logger.info(f"Copied profile to temp: {tmp}")
                    except Exception as e:
                        logger.warning(f"Failed to copy profile: {e}, using clean profile")
            else:
                # Use existing profile directly (requires all Chrome instances to be closed)
                user_data_dir = str(src_user_data_dir)
                logger.warning("Using existing profile directly - ensure all Chrome instances are closed")

        elif clean_profile_instead:
            # Create fresh profile
            fresh = Path(tempfile.mkdtemp(prefix="playwright-empty-"))
            self._temp_profile_dir = fresh
            user_data_dir = str(fresh)
            logger.info(f"Created clean profile: {fresh}")

        # Launch browser
        try:
            if user_data_dir:
                # Launch with persistent context (profile)
                self._context = browser_type.launch_persistent_context(
                    user_data_dir,
                    headless=headless,
                    args=launch_args,
                    downloads_path=os.path.abspath(self.download_dir),
                    viewport={"width": 1920, "height": 1080},
                    accept_downloads=True,
                )
                self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
            else:
                # Launch without profile
                self._browser = browser_type.launch(
                    headless=headless,
                    args=launch_args,
                    downloads_path=os.path.abspath(self.download_dir),
                )
                self._context = self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    accept_downloads=True,
                )
                self.page = self._context.new_page()

            # Set timeouts
            self.page.set_default_timeout(DEFAULT_ELEMENT_TIMEOUT)
            self.page.set_default_navigation_timeout(self._page_load_timeout_ms)

            logger.info(f"Playwright {self._browser_type_name} browser initialized successfully")

        except Exception as e:
            logger.error(f"Failed to launch Playwright browser: {e}")
            raise BrowserError(f"Could not launch Playwright browser: {e}") from e

    def goto(self, url: str, wait_until: str = "domcontentloaded"):
        """
        Navigate to URL

        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation succeeded
                       ("load", "domcontentloaded", "networkidle", "commit")

        Returns:
            The Page instance

        Raises:
            NavigationError: If navigation fails
        """
        try:
            self.page.goto(url, wait_until=wait_until)
            logger.info(f"Navigated to: {url}")
            return self.page
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            raise NavigationError(f"Failed to navigate to {url}: {e}") from e

    def screenshot(self, path: Optional[str] = None, full_page: bool = False):
        """
        Take screenshot

        Args:
            path: Path to save screenshot, or None to auto-generate
            full_page: Capture full scrollable page

        Returns:
            Path to screenshot file
        """
        if path:
            screenshot_path = path
        else:
            timestamp = int(time.time())
            os.makedirs("output", exist_ok=True)
            screenshot_path = f"output/screenshot_{timestamp}.png"

        try:
            self.page.screenshot(path=screenshot_path, full_page=full_page)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            raise BrowserError(f"Screenshot capture failed: {e}") from e

    def wait_for_selector(self, selector: str, timeout: Optional[int] = None, state: str = "visible"):
        """
        Wait for element to appear

        Args:
            selector: CSS or XPath selector
            timeout: Timeout in milliseconds (None uses default)
            state: Element state - "attached", "detached", "visible", "hidden"

        Returns:
            Element handle
        """
        try:
            element = self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return element
        except Exception as e:
            logger.error(f"Element not found: {selector} - {e}")
            raise ElementNotFoundError(f"Element not found: {selector}") from e

    def click(self, selector: str, timeout: Optional[int] = None):
        """
        Click element

        Args:
            selector: CSS or XPath selector
            timeout: Timeout in milliseconds

        Raises:
            ElementNotFoundError: If element cannot be clicked
        """
        try:
            self.page.click(selector, timeout=timeout)
            logger.info(f"Clicked element: {selector}")
        except Exception as e:
            logger.error(f"Failed to click {selector}: {e}")
            raise ElementNotFoundError(f"Failed to click {selector}: {e}") from e

    def fill(self, selector: str, text: str, timeout: Optional[int] = None):
        """
        Fill text input

        Args:
            selector: CSS or XPath selector
            text: Text to fill
            timeout: Timeout in milliseconds
        """
        try:
            self.page.fill(selector, text, timeout=timeout)
            logger.info(f"Filled element {selector} with text")
        except Exception as e:
            logger.error(f"Failed to fill {selector}: {e}")
            raise ElementNotFoundError(f"Failed to fill {selector}: {e}") from e

    def close(self):
        """Close browser and clean up temp profiles"""
        try:
            if self.page:
                self.page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()

            logger.info("Playwright browser closed")
        except Exception as e:
            logger.warning(f"Error closing Playwright browser: {e}")
        finally:
            # Clean up temp profile
            if self._temp_profile_dir and self._temp_profile_dir.exists():
                try:
                    shutil.rmtree(self._temp_profile_dir, ignore_errors=True)
                    logger.debug(f"Cleaned up temp profile: {self._temp_profile_dir}")
                except Exception as e:
                    logger.warning(f"Could not remove temp profile dir {self._temp_profile_dir}: {e}")
            self._temp_profile_dir = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
