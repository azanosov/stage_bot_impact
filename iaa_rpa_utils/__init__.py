from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .browser import safe_click, SeleniumBrowser
from .playwright_browser import PlaywrightBrowser
from .popup_handler import PopupHandler, PopupDetectionResult, PopupType, WebPopupMonitor
from .exceptions import (
    APIError,
    AuthenticationError,
    BrowserError,
    ConfigurationError,
    DatabaseError,
    DataExtractionError,
    DataProcessingError,
    DataTransformationError,
    DataValidationError,
    DocumentConversionError,
    DownloadError,
    ElementNotFoundError,
    EmailNotificationError,
    FileOperationError,
    LoginError,
    LogoutError,
    NavigationError,
    PermissionError,
    PopupHandlerError,
    ReportGenerationError,
    RetryExhaustedError,
    RPALibraryError,
    ScreenshotError,
    TimeoutError,
    UnsupportedDocumentFormatError,
    UploadError,
    WebAutomationError,
)
from .logger import get_logger, setup_logger, ProcessLogger
from .mail_sender import send_email
# from .mfa_totp import get_otp
from .strfunctions import decrypt_string, encrypt_string, generate_html_table_rows, str_to_bool, mask_sensitive_id, get_bool_config, get_error_message, html_to_pdf, ensure_pdf
from .pdf_redactor import search_and_redact_text, redact_tfn_from_pdf
from .pdf_merger import merge_pdfs
from .id_parser import parse_client_id
from .helpers import take_error_screenshot, take_full_page_screenshot, handle_chrome_save_as_dialog

__all__ = [
    # String functions
    'encrypt_string',
    'decrypt_string',
    'str_to_bool',
    'generate_html_table_rows',
    'mask_sensitive_id',
    'get_bool_config',
    'get_error_message',
    'html_to_pdf',
    'ensure_pdf',
    # Email
    'send_email',
    # Browser
    'safe_click',
    'SeleniumBrowser',
    'PlaywrightBrowser',
    # Popup Handler
    'PopupHandler',
    'PopupDetectionResult',
    'PopupType',
    'WebPopupMonitor',
    # MFA
    # 'get_otp',
    # Selenium imports (for convenience)
    'WebDriverWait',
    'EC',
    'By',
    'TimeoutException',
    # Logger
    'setup_logger',
    'get_logger',
    'ProcessLogger',
    # Exceptions
    'RPALibraryError',
    'WebAutomationError',
    'LoginError',
    'LogoutError',
    'NavigationError',
    'ElementNotFoundError',
    'BrowserError',
    'DownloadError',
    'UploadError',
    'ScreenshotError',
    'DataProcessingError',
    'DataExtractionError',
    'DataValidationError',
    'DataTransformationError',
    'UnsupportedDocumentFormatError',
    'DocumentConversionError',
    'ReportGenerationError',
    'EmailNotificationError',
    'ConfigurationError',
    'TimeoutError',
    'RetryExhaustedError',
    'FileOperationError',
    'DatabaseError',
    'APIError',
    'AuthenticationError',
    'PermissionError',
    'PopupHandlerError',
    # Credentials
    'Credential',
    'get_credential',
    # PDF Redaction
    'search_and_redact_text',
    'redact_tfn_from_pdf',
    # PDF Merger
    'merge_pdfs',
    # Client ID Parser
    'parse_client_id',
    # Screenshots
    'take_error_screenshot',
    'take_full_page_screenshot',
    # Windows dialogs
    'handle_chrome_save_as_dialog',
] 