"""Helper modules"""

from typing import Tuple, Optional, Iterable
import base64
import math
import time
import functools
import os
import uuid
from .logger import setup_logger

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By  # noqa: F401 (public API uses By)
from selenium.common.exceptions import TimeoutException

logger = setup_logger(__name__)

_DEFAULT_SCREENSHOT_FOLDER = r"C:\IAAUTOMATE\Error Screenshots"


def take_error_screenshot(error_type="error", browser=None, screenshot_folder=None):
    """Capture and save a screenshot of the current browser state on error.

    Switches to the most recently opened window before capturing, so the
    screenshot reflects the page that caused the failure. Silently logs and
    returns on any capture failure — never raises, as this is a diagnostic aid
    and must not mask the original exception.

    Args:
        error_type: Label prefix for the screenshot filename (e.g. "system_exception").
        browser: Browser wrapper object with a ``driver`` attribute and ``screenshot(path)`` method.
                 If None, the call is a no-op.
        screenshot_folder: Directory to save screenshots. Defaults to C:\\IAAUTOMATE\\Error Screenshots.
    """
    try:
        if browser is None:
            logger.warning("Browser not provided for screenshot — skipping.")
            return

        driver = browser.driver

        if not driver.window_handles:
            logger.error("No browser windows open to capture.")
            return

        # Switch to the most recent window (active tab after any popups or redirects)
        driver.switch_to.window(driver.window_handles[-1])

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            logger.warning("Page body not found before screenshot — capturing anyway.")

        # Allow final DOM rendering to settle
        time.sleep(1)

        folder = screenshot_folder or _DEFAULT_SCREENSHOT_FOLDER
        os.makedirs(folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{error_type}_{timestamp}_{uuid.uuid4().hex[:6]}.png"
        filepath = os.path.join(folder, filename)

        browser.screenshot(filepath)
        logger.info(f"Error screenshot saved: {filepath}")

    except Exception as err:
        logger.error(f"Could not take error screenshot: {err}", exc_info=True)


def take_full_page_screenshot(driver, save_path: str) -> bool:
    """
    Take a full-page screenshot using Chrome DevTools Protocol.

    Uses CDP Page.captureScreenshot with captureBeyondViewport so the full
    page is rendered regardless of scroll position — works correctly on SPAs
    where the body does not scroll and scrollHeight equals the viewport height.

    Args:
        driver: Selenium WebDriver instance (Chrome with CDP support).
        save_path: Absolute path where the .png will be saved. Parent directory
                   is created automatically if it does not exist.

    Returns:
        True on success, False on failure (never raises).
    """
    try:
        folder = os.path.dirname(save_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        metrics = driver.execute_cdp_cmd('Page.getLayoutMetrics', {})
        content_width = math.ceil(metrics['contentSize']['width'])
        content_height = math.ceil(metrics['contentSize']['height'])

        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'mobile': False,
            'width': content_width,
            'height': content_height,
            'deviceScaleFactor': 1,
        })

        result = driver.execute_cdp_cmd('Page.captureScreenshot', {
            'format': 'png',
            'captureBeyondViewport': True,
        })

        with open(save_path, 'wb') as f:
            f.write(base64.b64decode(result['data']))

        logger.info(f"Full-page screenshot saved: {save_path}")
        return True
    except Exception as err:
        logger.error(f"Full-page screenshot failed: {err}", exc_info=True)
        return False
    finally:
        try:
            driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})
        except Exception:
            pass


def find_element_with_fallback(
    driver,
    locators: Iterable[Tuple[str, str]],
    timeout: int = 30,
    condition: str = "presence",
):
    """
    Try multiple locators until one succeeds.
    condition: 'presence' | 'visible' | 'clickable'
    """
    deadline = time.time() + timeout
    last_exc: Optional[Exception] = None
    condition = (condition or "presence").lower()

    for by, value in locators:
        remaining = max(0, deadline - time.time())
        if remaining <= 0:
            break
        try:
            if condition == "clickable":
                return WebDriverWait(driver, remaining).until(
                    EC.element_to_be_clickable((by, value))
                )
            elif condition == "visible":
                return WebDriverWait(driver, remaining).until(
                    EC.visibility_of_element_located((by, value))
                )
            else:
                return WebDriverWait(driver, remaining).until(
                    EC.presence_of_element_located((by, value))
                )
        except Exception as e:
            # Optional: log if you have a logger hooked here
            last_exc = e
            continue

    raise TimeoutException(f"Element not found with any of: {list(locators)}") from last_exc


def handle_chrome_save_as_dialog(
    window_locator: str,
    dest_path: str,
    timeout: int = 15,
    dialog_timeout: int = 30,
    download_wait: int = 30,
    *,
    dialog_name: str = "Save As",
) -> bool:
    """
    Interact with Chrome's file-save dialog and save the file to dest_path.

    REQUIRED browser chrome_prefs for the Save As dialog to appear:
    |
    |   browser = SeleniumBrowser(chrome_prefs={
    |       "download.prompt_for_download": True,
    |       "profile.default_content_setting_values.notifications": 2,
    |   })
    |
    Without "prompt_for_download": True Chrome silently downloads to the default
    folder and the Save As dialog never appears.

    - All robocorp.windows find calls are made from the Chrome window root (app),
      NOT from the dialog control.
    - EditControl is located via its fixed accessibility path from the Chrome root.
    - Save button is found by name from the Chrome root.
    - File existence is polled after clicking Save rather than using a fixed sleep.

    Args:
        window_locator:  Full robocorp.windows locator for the Chrome window,
                         e.g. 'regex:.*Nowinfinity - Google Chrome'.
        dest_path:       Absolute path where the file should be saved.
        timeout:         Seconds to wait for the Chrome window to appear.
        dialog_timeout:  Seconds to wait for the save dialog to appear as a
                         child of the Chrome window (server-side exports may be slow).
        download_wait:   Maximum seconds to poll for the saved file.
        dialog_name:     Title of the Windows file-save dialog to interact with.
                         Default "Save As" covers direct downloads (zip / Excel
                         export). Use "Save Print Output As" for the Chrome
                         Ctrl+P → Print-to-PDF flow, which produces a
                         differently-titled dialog with the same internal
                         structure (File name: EditControl + Save button).

    Returns:
        True on success.

    Raises:
        Exception if the dialog cannot be found, interaction fails,
        or the file is not present at dest_path after download_wait seconds.
    """
    from robocorp import windows as rob_windows

    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    # Wait for the save dialog to render before searching
    time.sleep(2)

    # Find the Chrome window by its full locator
    app = rob_windows.find_window(window_locator, timeout=timeout)
    logger.info("Chrome window found")

    # Wait for the save dialog to appear anywhere inside the Chrome window.
    # path:"1" is intentionally omitted - on some Chrome builds the GPU overlay
    # occupies path:1 before the dialog renders, causing an immediate failure.
    # Searching by name alone lets robocorp.windows poll the full dialog_timeout.
    app.find(f'control:"WindowControl" and name:"{dialog_name}"', timeout=dialog_timeout)
    logger.info(f"{dialog_name!r} dialog found")

    normalized = os.path.normpath(dest_path)
    logger.info(f"Normalized save path: {normalized}")

    # Locate the filename EditControl via its accessibility path from the Chrome root.
    # path:"1|1|1|6|3|2|1" is the stable path used in the Xero reference implementation.
    logger.info("Locating file name input field...")
    find_input = app.find(
        'control:"EditControl" and class:"Edit" and name:"File name:" and path:"1|1|1|6|3|2|1"'
    ).click()
    find_input.send_keys("{CTRL}a")   # select all existing text
    find_input.send_keys("{DEL}")      # clear it
    find_input.send_keys(normalized)
    logger.info(f"File path entered: {normalized}")
    time.sleep(2)

    # Click Save - found from the Chrome root, same as Xero reference
    logger.info("Clicking Save button...")
    app.find('control:"ButtonControl" and name:"Save"').click()
    logger.info("Save button clicked")

    # Handle optional "Confirm Save As" overwrite dialog
    try:
        save_confirm_popup = app.find(
            'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"', timeout=3
        )
        save_confirm_popup.find(
            'control:"ButtonControl" and class:"CCPushButton" and name:"Yes"'
        ).click()
        logger.info("Overwrite confirmed")
    except Exception:
        pass  # no overwrite prompt - file did not already exist

    # Poll until the file appears at dest_path
    for elapsed in range(download_wait):
        time.sleep(1)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            logger.info(f"File saved after {elapsed + 1}s: {dest_path}")
            return True
        if (elapsed + 1) % 5 == 0:
            logger.info(f"Waiting for file... ({elapsed + 1}/{download_wait}s)")

    raise Exception(f"File not found at dest_path after {download_wait}s: {dest_path}")


def focus_browser_window(driver) -> bool:
    """
    Bring the Chrome window associated with this Selenium driver to the foreground.

    Uses the Windows API (ctypes) to:
      1. Find all child processes of the ChromeDriver process (the actual Chrome PIDs).
      2. Enumerate visible top-level windows and match by PID.
      3. Restore + foreground the matching window.

    Windows-only. Best-effort — never raises; returns True on success, False otherwise.
    Call this at the start of each step that switches to a different browser so the
    correct Chrome window is visible on screen during automation.
    """
    try:
        import ctypes
        import ctypes.wintypes
        import platform

        if platform.system() != "Windows":
            return False

        kernel32 = ctypes.windll.kernel32
        user32   = ctypes.windll.user32

        # ----------------------------------------------------------------
        # 1. Enumerate all processes and build a parent→children map so we
        #    can find every Chrome PID that is a descendant of ChromeDriver.
        # ----------------------------------------------------------------
        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize",              ctypes.wintypes.DWORD),
                ("cntUsage",            ctypes.wintypes.DWORD),
                ("th32ProcessID",       ctypes.wintypes.DWORD),
                ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID",        ctypes.wintypes.DWORD),
                ("cntThreads",          ctypes.wintypes.DWORD),
                ("th32ParentProcessID", ctypes.wintypes.DWORD),
                ("pcPriClassBase",      ctypes.c_long),
                ("dwFlags",             ctypes.wintypes.DWORD),
                ("szExeFile",           ctypes.c_char * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.wintypes.HANDLE(-1).value:
            return False

        children_map: dict = {}
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if kernel32.Process32First(snap, ctypes.byref(entry)):
                while True:
                    children_map.setdefault(entry.th32ParentProcessID, []).append(
                        entry.th32ProcessID
                    )
                    if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)

        cd_pid = driver.service.process.pid
        chrome_pids: set = set()
        queue = [cd_pid]
        while queue:
            p = queue.pop()
            for child in children_map.get(p, []):
                chrome_pids.add(child)
                queue.append(child)

        if not chrome_pids:
            return False

        # ----------------------------------------------------------------
        # 2. Find the visible top-level window that belongs to one of those PIDs.
        # ----------------------------------------------------------------
        target_hwnd: list = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_void_p)
        def _enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in chrome_pids:
                target_hwnd.append(hwnd)
            return True

        user32.EnumWindows(_enum_cb, None)

        if not target_hwnd:
            return False

        hwnd = target_hwnd[0]

        # ----------------------------------------------------------------
        # 3. Restore (un-minimise) and foreground the window.
        #    AttachThreadInput is required because Windows blocks
        #    SetForegroundWindow from processes that are not already in the
        #    foreground — attaching to the foreground thread temporarily
        #    grants the right to steal focus.
        # ----------------------------------------------------------------
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid  = user32.GetWindowThreadProcessId(fg_hwnd, None)
        cur_tid = kernel32.GetCurrentThreadId()

        if fg_tid and fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, True)

        user32.ShowWindow(hwnd, 9)       # SW_RESTORE — un-minimise if needed
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)

        if fg_tid and fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, False)

        # Let Selenium maximise the window through Chrome's own channel so the
        # browser fills the screen in its normal maximised state (not OS fullscreen).
        try:
            driver.maximize_window()
        except Exception:
            pass

        return True

    except Exception as e:
        logger.debug(f"focus_browser_window non-fatal: {e}")
        return False


def xpath_literal(s: str) -> str:
    """Safely quote arbitrary string for XPath literal."""
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


def retry(attempts=3, delay=1, exceptions=Exception, backoff=1):
    """
    Retry decorator.

    Args:
        attempts (int): Number of retry attempts.
        delay (int/float): Wait time before each retry.
        exceptions (Exception or tuple): Exception(s) that should trigger retry.
        backoff (float): Multiplier to increase delay per retry.
    """

    # Ensure exceptions is always a tuple
    if not isinstance(exceptions, (tuple, list)):
        exceptions = (exceptions,)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _attempt = 1
            _delay = delay

            while _attempt <= attempts:
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    if _attempt == attempts:
                        logger.error(
                            f"[{func.__name__}] Attempt {_attempt}/{attempts} failed. No retries left."
                        )
                        raise

                    logger.warning(
                        f"[{func.__name__}] Attempt {_attempt}/{attempts} failed with: {e}. "
                        f"Retrying in {_delay} seconds..."
                    )

                    time.sleep(_delay)
                    _delay *= backoff
                    _attempt += 1

        return wrapper

    return decorator
