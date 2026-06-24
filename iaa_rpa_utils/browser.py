import json
import os
import base64
import platform
import shutil
import tempfile
import time
import socket
from pathlib import Path
from typing import Any, Iterable, Optional, Set

from selenium import webdriver
from selenium.webdriver.common.by import By  # kept for callers that import from here
from selenium.webdriver.support.ui import WebDriverWait, Select  # kept for callers
from selenium.webdriver.support import expected_conditions as EC  # kept for callers
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

from .logger import setup_logger
from .exceptions import WebAutomationError, NavigationError, ElementNotFoundError

iaalogger = setup_logger(__name__)

DEFAULT_ELEMENT_TIMEOUT = 30


def safe_click(driver, element, description: str = ""):
    """
    Safely click an element with fallback to JavaScript click if regular click fails.

    Args:
        driver: The Selenium WebDriver object
        element: The element to click
        description: Description of the element for logging
    
    Raises:
        ElementNotFoundError: If the element cannot be clicked even with JavaScript fallback
    """
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.2)  # small settle time
        element.click()
        if description:
            iaalogger.info(f"Successfully clicked {description}")
    except Exception as e:
        iaalogger.warning(f"Regular click failed for {description}, trying JavaScript click: {e}")
        try:
            driver.execute_script("arguments[0].click();", element)
            if description:
                iaalogger.info(f"Successfully clicked {description} using JavaScript")
        except Exception as js_error:
            iaalogger.error(f"Both click methods failed for {description}: {js_error}")
            raise ElementNotFoundError(f"Failed to click element {description}: {js_error}") from js_error


# ---------- Profile helpers ----------

def _resolve_user_data_dir() -> Path:
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


def _clone_profile_to_temp(src_user_data_dir: Path, profile_directory: str) -> Path:
    """
    Copy the selected Chrome profile into a temporary user-data-dir to avoid locks.
    Skips lock files and heavy caches for speed.
    """
    tmp = Path(tempfile.mkdtemp(prefix="selenium-chrome-"))

    src_profile = src_user_data_dir / profile_directory
    if not src_profile.exists():
        raise FileNotFoundError(f"Profile directory not found: {src_profile}")

    def _ignore(dirpath, names):
        ignore_list = set()
        for n in names:
            if n.startswith("Singleton") or n in {"Crashpad", "GrShaderCache", "ShaderCache"}:
                ignore_list.add(n)
            if n in {"GPUCache", "Code Cache", "Media Cache", "Application Cache"}:
                ignore_list.add(n)
        return ignore_list

    # Copy the profile directory to temp location
    dst_profile = tmp / profile_directory
    shutil.copytree(src_profile, dst_profile, ignore=_ignore)

    # Also copy Local State and other required files from user data dir root
    for item in ["Local State", "First Run"]:
        src_item = src_user_data_dir / item
        if src_item.exists():
            try:
                shutil.copy2(src_item, tmp / item)
            except Exception:
                pass  # Non-critical files

    return tmp


def _apply_prefs_to_cloned_profile(profile_dir: Path, prefs: dict) -> None:
    """
    Chrome reads Preferences from --user-data-dir and ignores chromedriver's
    experimental_options "prefs" for keys that already exist in that file.
    When use_existing_profile=True the cloned profile carries the user's
    Preferences (e.g. download.prompt_for_download=False), which then shadows
    our intended overrides — e.g. the Save As dialog never appears. Patch the
    cloned Preferences file directly so the prefs we pass to experimental_options
    actually win. Best-effort: any read/parse/write failure leaves the file
    untouched and Chrome falls back to its existing behaviour.
    """
    pref_file = profile_dir / "Preferences"
    if not pref_file.exists():
        return
    try:
        data = json.loads(pref_file.read_text(encoding="utf-8"))
    except Exception:
        return
    for dotted_key, value in prefs.items():
        parts = dotted_key.split(".")
        cursor = data
        for p in parts[:-1]:
            nxt = cursor.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[p] = nxt
            cursor = nxt
        cursor[parts[-1]] = value
    try:
        pref_file.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _maybe_linux_sandbox_fixes(opts: Options):
    if platform.system() != "Linux":
        return
    # In containers/CI or when running as root, Chrome may need these:
    in_container = Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    if in_container or is_root:
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")  # fall back to /tmp if /dev/shm is tiny


# ---------- Primary API ----------

class SeleniumBrowser:
    """
    Primary browser helper (source of truth). Extended with:
      - Optional use of an existing Chrome profile (safely cloned to a temp dir by default)
      - Clean/throwaway profile option
      - Optional debuggerAddress attach
      - Optional extensions
      - Hidden automation banner
      - Remote debugging port auto-pick
      - Page load timeout control
    Defaults preserve original behavior if you don’t pass the new knobs.
    """

    def __init__(
        self,
        headless: bool = False,
        download_dir: str = "outputs",
        use_existing_profile: bool = False,
        profile_directory: str = "Default",
        *,
        user_data_dir: Optional[str] = None,
        copy_profile_to_temp: bool = True,
        clean_profile_instead: bool = False,
        debugger_address: Optional[str] = None,
        crx_paths: Optional[Iterable[str]] = None,
        unpacked_extension_dirs: Optional[Iterable[str]] = None,
        hide_automation_banner: bool = True,
        page_load_timeout_sec: int = 60,
        chrome_prefs: Optional[dict[str, Any]] = None,
        chrome_args: Optional[list[str]] = None,
    ):
        self.download_dir = download_dir
        self.driver: Optional[webdriver.Chrome] = None
        self._temp_profile_dir: Optional[Path] = None
        self._page_load_timeout_sec = page_load_timeout_sec

        self._setup_driver(
            headless=headless,
            use_existing_profile=use_existing_profile,
            profile_directory=profile_directory,
            user_data_dir=user_data_dir,
            copy_profile_to_temp=copy_profile_to_temp,
            clean_profile_instead=clean_profile_instead,
            debugger_address=debugger_address,
            crx_paths=crx_paths,
            unpacked_extension_dirs=unpacked_extension_dirs,
            hide_automation_banner=hide_automation_banner,
            chrome_prefs=chrome_prefs,
            chrome_args=chrome_args,
        )

    def _setup_driver(
        self,
        *,
        headless: bool,
        use_existing_profile: bool,
        profile_directory: str,
        user_data_dir: Optional[str],
        copy_profile_to_temp: bool,
        clean_profile_instead: bool,
        debugger_address: Optional[str],
        crx_paths: Optional[Iterable[str]],
        unpacked_extension_dirs: Optional[Iterable[str]],
        hide_automation_banner: bool,
        chrome_prefs: Optional[dict[str, Any]],
        chrome_args: Optional[list[str]],

    ):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()

        prefs = {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": True,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        if chrome_prefs:
            prefs.update(chrome_prefs)
        chrome_options.add_experimental_option("prefs", prefs)

        # Default Chrome arguments (can be overridden entirely via chrome_args)
        default_chrome_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=RestoreSession,Translate",

        ]
        # Let Chrome pick a free DevTools port (reduces clashes)
   
        for arg in (chrome_args if chrome_args is not None else default_chrome_args):
            chrome_options.add_argument(arg)

        if hide_automation_banner:
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        if headless:
            # Use modern headless where available
            chrome_options.add_argument("--headless=new")

        # Linux/container sandbox hygiene
        _maybe_linux_sandbox_fixes(chrome_options)

        # Debugger attach OR profile selection
        if debugger_address:
            chrome_options.add_experimental_option("debuggerAddress", debugger_address)
        else:
            if use_existing_profile and not clean_profile_instead:
                resolved_user_data_dir = Path(user_data_dir) if user_data_dir else _resolve_user_data_dir()
                if copy_profile_to_temp:
                    cloned = _clone_profile_to_temp(resolved_user_data_dir, profile_directory)
                    self._temp_profile_dir = cloned
                    # Overwrite the same prefs (download.prompt_for_download etc.)
                    # in the cloned Preferences file — chromedriver's
                    # experimental_options "prefs" silently loses to existing
                    # values in --user-data-dir's Preferences. See
                    # _apply_prefs_to_cloned_profile docstring.
                    _apply_prefs_to_cloned_profile(cloned / profile_directory, prefs)
                    chrome_options.add_argument(f"--user-data-dir={cloned}")
                    chrome_options.add_argument(f"--profile-directory={profile_directory}")
                else:
                    # Requires that all Chrome windows using this profile are closed
                    chrome_options.add_argument(f"--user-data-dir={resolved_user_data_dir}")
                    chrome_options.add_argument(f"--profile-directory={profile_directory}")
            elif clean_profile_instead:
                fresh = Path(tempfile.mkdtemp(prefix="selenium-empty-"))
                self._temp_profile_dir = fresh
                chrome_options.add_argument(f"--user-data-dir={fresh}")

        # Extensions (optional)
        if crx_paths:
            for crx in crx_paths:
                chrome_options.add_extension(crx)
        if unpacked_extension_dirs:
            chrome_options.add_argument(f"--load-extension={','.join(unpacked_extension_dirs)}")

        # Try to find ChromeDriver in common locations (original behavior)
        chrome_driver_paths = [
            "chromedriver.exe",
            "chromedriver",
            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            os.path.join(os.getcwd(), "chromedriver.exe"),
        ]

        driver_path = None
        for path in chrome_driver_paths:
            if os.path.exists(path):
                driver_path = path
                iaalogger.info(f"Found ChromeDriver at: {path}")
                break

        try:
            if driver_path:
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                iaalogger.warning("ChromeDriver not found in common locations, trying default PATH lookup...")
                self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            iaalogger.error(f"Failed to initialize Chrome driver: {e}")
            iaalogger.error("Please ensure Chrome and ChromeDriver are installed and versions match.")
            iaalogger.error("Download ChromeDriver: https://chromedriver.chromium.org/")
            raise WebAutomationError(f"Could not initialize Chrome driver. Error: {e}") from e

        # Original implicit wait
        self.driver.implicitly_wait(10)
        # New: page load timeout (optional; defaults safe)
        try:
            self.driver.set_page_load_timeout(self._page_load_timeout_sec)
        except Exception as e:
            # Some drivers might not support this; ignore quietly to keep behavior
            iaalogger.debug(f"Driver does not support page load timeout setting: {e}")

    def _get_free_port(self, preferred_port: int = 9222) -> int:
        """
        Get a free port number. Try preferred port first, then find any free port.
        """

        
        # Try preferred port first
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', preferred_port))
                return preferred_port
        except OSError:
            iaalogger.debug(f"Port {preferred_port} in use, finding alternative...")
        
        # Find any free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
            iaalogger.info(f"Using free port: {port}")
            return port


    def _parse_locator(self, locator: str) -> tuple:
        """
        Parse a locator string in format "type:value" into Selenium By constant and value.
        
        Args:
            locator: Locator string in format "type:value" where type can be:
                     link, partial_link, id, name, xpath, css, tag_name, class_name
                     
        Returns:
            tuple: (By constant, locator value)
            
        Raises:
            WebAutomationError: If locator format is invalid or type is unknown
        """
        if ":" not in locator and not locator.startswith("/"):
            raise WebAutomationError(f"Invalid locator format (missing colon or does not start with /): {locator}")
        
        if locator.startswith("/"):
            locator_type = "xpath"
            locator_value = locator
        else:
            locator_type, locator_value = locator.split(":", 1)
            locator_type = locator_type.strip().lower()
            locator_value = locator_value.strip()
        
        # Map locator type to Selenium By constant
        by_mapping = {
            "link": By.LINK_TEXT,
            "partial_link": By.PARTIAL_LINK_TEXT,
            "id": By.ID,
            "name": By.NAME,
            "xpath": By.XPATH,
            "css": By.CSS_SELECTOR,
            "tag_name": By.TAG_NAME,
            "class_name": By.CLASS_NAME,
        }
        
        if locator_type not in by_mapping:
            raise WebAutomationError(f"Unknown locator type: {locator_type}")
        
        return by_mapping[locator_type], locator_value

    # ----- Public API (unchanged signatures where possible) -----

    def goto(self, url: str):
        """
        Navigate to URL
        
        Args:
            url: The URL to navigate to
            
        Returns:
            The WebDriver instance
            
        Raises:
            NavigationError: If navigation fails
        """
        try:
            self.driver.get(url)
            iaalogger.info(f"Navigated to: {url}")
            return self.driver
        except Exception as e:
            iaalogger.error(f"Failed to navigate to {url}: {e}")
            raise NavigationError(f"Failed to navigate to {url}: {e}") from e

    def screenshot(self, path: Optional[str] = None):
        """Take screenshot"""
        if path:
            self.driver.save_screenshot(path)
        else:
            timestamp = int(time.time())
            os.makedirs("output", exist_ok=True)
            self.driver.save_screenshot(f"output/screenshot_{timestamp}.png")


    def send_keys_to_active_element(self, keys: str):
        """
        Send keys to the currently active element.
        
        Args:
            keys: The keys to send to the active element
        """
        active_element = self.driver.switch_to.active_element
        active_element.send_keys(keys)
        iaalogger.debug(f"Sent keys to active element: {keys}")
    
    def press_tab(self):
        """
        Press the Tab key.
        """
        self.send_keys_to_active_element("Tab")
        iaalogger.debug("Pressed Tab key")
    
    def press_enter(self):
        """
        Press the Enter key.
        """
        self.send_keys_to_active_element("Enter")
        iaalogger.debug("Pressed Enter key")

    def does_page_contain_element(self, locator: str, timeout: int = 5) -> bool:
        """
        Check if an element is present on the page within the specified timeout.
        
        Args:
            locator: Locator string in format "type:value" where type can be:
                     link, partial_link, id, name, xpath, css, tag_name, class_name
            timeout: Timeout in seconds (default: 5)
            
        Returns:
            bool: True if element is found, False otherwise
            
        Example:
            browser.does_page_contain_element("link:View company details")
            browser.does_page_contain_element("id:submit-button", timeout=10)
        """
        try:
            # Parse locator string using helper method
            by_type, locator_value = self._parse_locator(locator)
            
            iaalogger.debug(f"Checking for element: {locator} (timeout: {timeout}s)")
            
            # Wait for element to be present
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_type, locator_value))
            )
            
            iaalogger.debug(f"Element found: {locator}")
            return True
            
        except TimeoutException:
            iaalogger.debug(f"Element not found within {timeout}s: {locator}")
            return False
        except WebAutomationError as e:
            iaalogger.debug(f"Invalid locator: {e}")
            return False
        except Exception as e:
            iaalogger.debug(f"Error checking for element {locator}: {e}")
            return False

    def get_page_source(self) -> str:
        """
        Get the HTML source of the current page.
        
        Returns:
            str: The HTML source code of the current page
            
        Raises:
            WebAutomationError: If unable to retrieve page source
            
        Example:
            browser.goto("https://example.com")
            html = browser.get_page_source()
        """
        try:
            source = self.driver.page_source
            iaalogger.debug(f"Retrieved page source ({len(source)} characters)")
            return source
        except Exception as e:
            iaalogger.error(f"Failed to get page source: {e}")
            raise WebAutomationError(f"Could not retrieve page source: {e}") from e

    def execute_javascript(self, script: str, *args):
        """
        Execute JavaScript code in the browser.
        
        Args:
            script: JavaScript code to execute
            *args: Optional arguments to pass to the script
            
        Returns:
            The result of the JavaScript execution
            
        Example:
            browser.execute_javascript("return document.title;")
            browser.execute_javascript("arguments[0].click();", element)
        """
        try:
            result = self.driver.execute_script(script, *args)
            iaalogger.debug(f"Executed JavaScript: {script[:100]}...")
            return result
        except Exception as e:
            iaalogger.error(f"Failed to execute JavaScript: {e}")
            raise WebAutomationError(f"JavaScript execution failed: {e}") from e

    def _current_handles(self) -> Set[str]:
        return set(self.driver.window_handles)

    def switch_to_new_window(self, before_handles: Set[str]) -> Optional[str]:
        """
        Wait until a new handle appears compared to before_handles, switch to it and return it.
        Returns None on timeout.
        """
        try:
            WebDriverWait(self.driver, self._page_load_timeout_sec).until(
                lambda d: len(set(d.window_handles) - before_handles) > 0
            )
        except TimeoutException:
            iaalogger.exception("Timed out waiting for new window to appear.")
            raise

        new_handles = set(self.driver.window_handles) - before_handles
        if not new_handles:
            iaalogger.warning("No new handle found after wait.")
            raise TimeoutException("No new window handle found after wait.")

        new_handle = new_handles.pop()
        iaalogger.debug(f"Switching to new window handle: {new_handle}")
        self.driver.switch_to.window(new_handle)
        return new_handle

    def safe_switch(self, handle: str) -> bool:
        """
        Switch to handle if it exists, return True if switched, False otherwise.
        """
        if handle in self._current_handles():
            self.driver.switch_to.window(handle)
            iaalogger.debug(f"Switched to handle: {handle}")
            return True
        iaalogger.warning(
            f"Requested handle {handle} not present in current handles."
        )
        return False

    def close_current_and_switch(
        self, target_handle: Optional[str] = None
    ) -> Optional[str]:
        """
        Close the current window and then switch to target_handle if provided and exists.
        If target_handle is None or doesn't exist, switch to a surviving handle:
          - Prefer the last handle in driver.window_handles
          - Return the handle switched to, or None if no handles left
        """
        try:
            current = self.driver.current_window_handle
        except Exception as e:
            iaalogger.error(f"Could not read current_window_handle: {e}")
            current = None

        # Close current window
        try:
            self.driver.close()
            iaalogger.debug(f"Closed handle: {current}")
        except Exception as e:
            iaalogger.error(f"Error closing window {current}: {e}")

        # Wait a moment for handles to settle
        end_time = time.time() + 3
        while time.time() < end_time:
            handles = self._current_handles()
            if len(handles) >= 1:
                break
            time.sleep(0.1)

        handles = self._current_handles()
        if not handles:
            iaalogger.error(
                "No window handles present after closing window. Browser likely quit."
            )
            return None

        # If user requested a target, try to switch to it if present
        if target_handle and target_handle in handles:
            self.driver.switch_to.window(target_handle)
            iaalogger.debug(f"Switched to requested target handle: {target_handle}")
            return target_handle

        # Otherwise switch to the last available handle (deterministic)
        # sort handles to make choice deterministic
        handles_list = sorted(handles)
        chosen = handles_list[-1]
        self.driver.switch_to.window(chosen)
        iaalogger.debug(f"Switched to fallback handle: {chosen}")
        return chosen

    def get_window_handles(self):
        """
        Get all window handles.
        
        Returns:
            list: List of window handle strings
            
        Example:
            handles = browser.get_window_handles()
            browser.switch_to_window(handles[-1])
        """
        try:
            handles = self.driver.window_handles
            iaalogger.debug(f"Retrieved {len(handles)} window handle(s)")
            return handles
        except Exception as e:
            iaalogger.error(f"Failed to get window handles: {e}")
            raise WebAutomationError(f"Could not get window handles: {e}") from e

    def switch_to_window(self, window_handle: str):
        """
        Switch to a different browser window/tab.
        
        Args:
            window_handle: The window handle to switch to
            
        Example:
            handles = browser.get_window_handles()
            browser.switch_to_window(handles[-1])  # Switch to last opened window
        """
        try:
            self.driver.switch_to.window(window_handle)
            iaalogger.info(f"Switched to window: {window_handle}")
        except Exception as e:
            iaalogger.error(f"Failed to switch to window {window_handle}: {e}")
            raise WebAutomationError(f"Could not switch to window: {e}") from e


    def wait_for_element(self, locator, timeout=DEFAULT_ELEMENT_TIMEOUT):
        """Wait for element to be present and visible"""
        try:
            by_type, locator_value = self._parse_locator(locator)
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.visibility_of_element_located((by_type, locator_value)))
            return element
        except TimeoutException:
            iaalogger.error(f"Element not found within {timeout}s: {locator}")
            raise
    
    def wait_for_element_clickable(self, locator,  timeout=DEFAULT_ELEMENT_TIMEOUT):
        """Wait for element to be clickable"""
        try:
            by_type, locator_value = self._parse_locator(locator)
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.element_to_be_clickable((by_type, locator_value)))
            return element
        except TimeoutException:
            iaalogger.error(f"Element not clickable within {timeout}s: {locator}")
            raise






    def click_element(self, locator: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT):
        """
        Click an element using locator string.
        
        Args:
            locator: Locator string in format "type:value" where type can be:
                     link, partial_link, id, name, xpath, css, tag_name, class_name
            timeout: Timeout in seconds (default: 30)
            
        Raises:
            ElementNotFoundError: If element cannot be found or clicked
            
        Example:
            browser.click_element("id:submit-button")
            browser.click_element("xpath://button[@type='submit']")
        """
        try:
            # Parse locator string
            by_type, locator_value = self._parse_locator(locator)
            
            # Wait for element to be present
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_type, locator_value))
            )
            
            # Use safe_click helper for robust clicking
            safe_click(self.driver, element, locator)
            
        except TimeoutException:
            iaalogger.error(f"Element not found within {timeout}s: {locator}")
            raise ElementNotFoundError(f"Element not found: {locator}") from None
        except WebAutomationError:
            raise  # Re-raise parsing errors
        except Exception as e:
            iaalogger.error(f"Failed to click element {locator}: {e}")
            raise ElementNotFoundError(f"Could not click element {locator}: {e}") from e


    def click_link(self, link_text: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT):
        """
        Click a link by text.
        
        Args:
            link_text: The text of the link to click
            timeout: Timeout in seconds (default: 30)
        """
        return self.click_element(f"link:{link_text}", timeout=timeout)

    def type_text(self, locator: str, text: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT, clear_first: bool = True):
        """
        Type text into an element.
        
        Args:
            locator: Locator string in format "type:value" where type can be:
                     link, partial_link, id, name, xpath, css, tag_name, class_name
            text: Text to type into the element
            timeout: Timeout in seconds (default: 30)
            
        Raises:
            ElementNotFoundError: If element cannot be found
            
        Example:
            browser.type_text("id:username", "myuser")
            browser.type_text("name:search-box", "query text")
        """
        try:
            # Parse locator string
            by_type, locator_value = self._parse_locator(locator)
            
            # Wait for element to be present
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_type, locator_value))
            )
            
            # Clear existing content and type new text
            if clear_first:
                element.clear()
            element.send_keys(text)
            iaalogger.info(f"Typed text into element: {locator}")
            
        except TimeoutException:
            iaalogger.error(f"Element not found within {timeout}s: {locator}")
            raise ElementNotFoundError(f"Element not found: {locator}") from None
        except WebAutomationError:
            raise  # Re-raise parsing errors
        except Exception as e:
            iaalogger.error(f"Failed to type text into element {locator}: {e}")
            raise ElementNotFoundError(f"Could not type into element {locator}: {e}") from e

    def select_dropdown_by_text(self, locator: str, visible_text: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT):
        """
        Select a dropdown option by visible text.
        
        Args:
            locator: Locator string in format "type:value" where type can be:
                     link, partial_link, id, name, xpath, css, tag_name, class_name
            visible_text: The visible text of the option to select
            timeout: Timeout in seconds (default: 30)
            
        Raises:
            ElementNotFoundError: If dropdown or option cannot be found
            
        Example:
            browser.select_dropdown_by_text("id:country", "United States")
            browser.select_dropdown_by_text("name:user-type", "Registered agents")
        """
        try:
            # Parse locator string
            by_type, locator_value = self._parse_locator(locator)
            
            # Wait for element to be present
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_type, locator_value))
            )
            
            # Create Select object and select by visible text
            select = Select(element)
            select.select_by_visible_text(visible_text)
            iaalogger.info(f"Selected '{visible_text}' from dropdown: {locator}")
            
        except TimeoutException:
            iaalogger.error(f"Dropdown not found within {timeout}s: {locator}")
            raise ElementNotFoundError(f"Dropdown not found: {locator}") from None
        except WebAutomationError:
            raise  # Re-raise parsing errors
        except Exception as e:
            iaalogger.error(f"Failed to select option '{visible_text}' from dropdown {locator}: {e}")
            raise ElementNotFoundError(f"Could not select dropdown option: {e}") from e


    def generate_pdf(self):
        """
        Generate a PDF of the current page.
        """
        try:
            result = self.driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
            pdf_data = base64.b64decode(result['data'])
            iaalogger.info("Generated PDF successfully")
            return pdf_data
        except Exception as e:
            iaalogger.error(f"Failed to generate PDF: {e}")
            raise WebAutomationError(f"Failed to generate PDF: {e}") from e

    def close(self):
        """Close browser and clean temp profiles, if any"""
        try:
            if self.driver:
                self.driver.quit()
        finally:
            if self._temp_profile_dir and self._temp_profile_dir.exists():
                # Best-effort cleanup of temp profile
                try:
                    shutil.rmtree(self._temp_profile_dir, ignore_errors=True)
                except Exception as e:
                    iaalogger.warning(f"Could not remove temp profile dir {self._temp_profile_dir}: {e}")
            self._temp_profile_dir = None
