"""
Custom Exception Classes
Defines custom exceptions for the RPA library
"""


class RPALibraryError(Exception):
    """Base exception for RPA library"""
    pass


class WebAutomationError(RPALibraryError):
    """Exception raised for web automation errors"""
    pass


class WindowAutomationError(RPALibraryError):
    """Exception raised for Windows desktop automation errors"""
    pass


class LoginError(WebAutomationError):
    """Exception raised when login fails"""
    pass


class LogoutError(WebAutomationError):
    """Exception raised when logout operation fails"""
    pass


class NavigationError(WebAutomationError):
    """Exception raised when navigation fails"""
    pass


class ElementNotFoundError(WebAutomationError):
    """Exception raised when element is not found"""
    pass


class DataProcessingError(RPALibraryError):
    """Exception raised for data processing errors"""
    pass


class DataExtractionError(DataProcessingError):
    """Exception raised when data extraction fails"""
    pass


class DataValidationError(DataProcessingError):
    """Exception raised when data validation fails"""
    pass


class DataTransformationError(DataProcessingError):
    """Exception raised when data transformation fails"""
    pass


class UnsupportedDocumentFormatError(DataProcessingError):
    """Raised when a file extension has no known document-to-PDF conversion path.

    Callers should treat this as a business/manual exception (the document
    cannot be processed automatically), not a transient failure.
    """

    def __init__(self, file_ext: str, file_path: str):
        self.file_ext = file_ext
        self.file_path = file_path
        super().__init__(
            f"Unsupported document format '{file_ext}' for '{file_path}'"
        )


class DocumentConversionError(DataProcessingError):
    """Raised when a *supported* document type fails to convert to PDF.

    (Word/Excel COM error, corrupt image, WeasyPrint failure, etc.) Callers
    should treat this as a system/transient exception (worth retrying).
    ``source_format`` is one of 'word' | 'excel' | 'image' | 'html' so the
    caller can pick a format-specific error message if it wants to.
    """

    def __init__(self, message: str, source_format: str = ""):
        self.source_format = source_format
        super().__init__(message)


class ReportGenerationError(RPALibraryError):
    """Exception raised for report generation errors"""
    pass


class EmailNotificationError(RPALibraryError):
    """Exception raised when email notification fails"""
    pass


class ConfigurationError(RPALibraryError):
    """Exception raised for configuration errors"""
    pass


class TimeoutError(RPALibraryError):
    """Exception raised when operation times out"""
    pass


class RetryExhaustedError(RPALibraryError):
    """Exception raised when all retry attempts are exhausted"""
    pass


class BrowserError(WebAutomationError):
    """Exception raised for browser-related errors"""
    pass


class DownloadError(WebAutomationError):
    """Exception raised when file download fails"""
    pass


class UploadError(WebAutomationError):
    """Exception raised when file upload fails"""
    pass


class ScreenshotError(WebAutomationError):
    """Exception raised when screenshot capture fails"""
    pass


class FileOperationError(RPALibraryError):
    """Exception raised for file operation errors"""
    pass


class DatabaseError(RPALibraryError):
    """Exception raised for database operation errors"""
    pass


class APIError(RPALibraryError):
    """Exception raised for API call errors"""
    pass


class AuthenticationError(RPALibraryError):
    """Exception raised for authentication failures"""
    pass


class PermissionError(RPALibraryError):
    """Exception raised for permission-related errors"""
    pass


class PopupHandlerError(WebAutomationError):
    """Exception raised for popup handling errors"""
    pass