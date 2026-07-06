from pathlib import Path
import os
import re
from hashlib import md5
from cryptography.fernet import Fernet

from .logger import setup_logger
from .exceptions import (
    DataProcessingError,
    DataValidationError,
    DocumentConversionError,
    UnsupportedDocumentFormatError,
)
from typing import Union
from weasyprint import HTML

# ====================================================================================
# THIRD-PARTY IMPORTS
# ====================================================================================
try:
    import fitz  # PyMuPDF - PDF manipulation library
except ImportError:
    raise ImportError("PyMuPDF (fitz) is required. Install it with: pip install PyMuPDF")


logger = setup_logger(__name__)

def encrypt_string(plain_text, key):
    """
    Encrypts a given string using the provided key.
    
    Args:
        plain_text: The string to encrypt
        key: Fernet encryption key (32 url-safe base64-encoded bytes)
        
    Returns:
        str: Encrypted text as a string
        
    Raises:
        DataProcessingError: If encryption fails
    """
    try:
        fernet = Fernet(key)
        encrypted_text = fernet.encrypt(plain_text.encode())
        logger.debug("String encrypted successfully")
        return encrypted_text.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt string: {e}")
        raise DataProcessingError(f"Encryption failed: {e}") from e

def decrypt_string(encrypted_text, key):
    """
    Decrypts a given string using the provided key.
    
    Args:
        encrypted_text: The encrypted string to decrypt
        key: Fernet encryption key (32 url-safe base64-encoded bytes)
        
    Returns:
        str: Decrypted plain text
        
    Raises:
        DataProcessingError: If decryption fails
    """
    try:
        fernet = Fernet(key)
        decrypted_text = fernet.decrypt(encrypted_text.encode())
        logger.debug("String decrypted successfully")
        return decrypted_text.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt string: {e}")
        raise DataProcessingError(f"Decryption failed: {e}") from e

def str_to_bool(value):
    """
    Convert a string representation of a boolean to an actual boolean value.
    
    Args:
        value: String, boolean, or other value to convert
        
    Returns:
        bool: Converted boolean value
        
    Raises:
        DataValidationError: If value cannot be safely interpreted
    """
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 't', 'yes', 'y', '1')
        return bool(value)
    except Exception as e:
        logger.error(f"Failed to convert value to boolean: {e}")
        raise DataValidationError(f"Cannot convert {value} to boolean: {e}") from e 

def hash_from_string(plain_text, max_length = 0):
    encoded_string = plain_text.encode('utf-8')

    # Create a SHA-256 hash object
    md5_hash = md5()

    # Update the hash object with the encoded string
    md5_hash.update(encoded_string)

    # Get the hexadecimal representation of the hash digest
    hex_digest = md5_hash.hexdigest()

    return hex_digest if max_length == 0 else hex_digest[:max_length]


def generate_html_table_rows(records):
    """
    Generates styled HTML table rows from a list of dictionaries.

    Args:
        records (list): List of dictionaries where each dictionary
            represents a table row.

    Returns:
        str: HTML string containing table rows.

    Raises:
        DataProcessingError: If HTML generation fails.
    """
    try:
        if not records:
            logger.warning("No records provided for HTML table generation")
            return ""

        cell_style = "border:1px solid #ccc; padding:6px 12px;"

        html = "".join(
            [
                "<tr>"
                + "".join(
                    [
                        f'<td style="{cell_style}">{value}</td>'
                        for value in record.values()
                    ]
                )
                + "</tr>"
                for record in records
            ]
        )

        logger.debug(
            "Generated HTML table rows for %s records",
            len(records),
        )

        return html

    except Exception as error:
        logger.error(
            "Failed to generate HTML table rows: %s",
            error,
        )
        raise DataProcessingError(
            f"HTML table generation failed: {error}"
        ) from error


def mask_sensitive_id(value: str, visible_digits: int = 4, mask_position: str = "start") -> str:
    """
    Mask a TFN or ABN for safe logging.

    Strips spaces before masking so formatting doesn't affect the visible digit count.

    Args:
        value:          The TFN or ABN string to mask.
        visible_digits: Number of digits to leave unmasked (default 4).
        mask_position:  Where the mask (*) appears:
                          "end"   — show first N digits, mask the rest  e.g. "1234 *****"
                          "start" — mask the start, show last N digits  e.g. "***** 6789"

    Returns:
        Masked string safe for logging, or the original value if too short to mask.

    Examples:
        mask_sensitive_id("123 456 789")              -> "1234 *****"
        mask_sensitive_id("123 456 789", mask_position="start") -> "***** 6789"
        mask_sensitive_id("12 345 678 901")           -> "1234 *******"
    """
    if not value:
        return value

    digits = value.replace(" ", "")

    if len(digits) <= visible_digits:
        logger.debug(f"mask_sensitive_id: value too short to mask ({len(digits)} digits)")
        return digits

    mask_count = len(digits) - visible_digits

    if mask_position == "start":
        masked = "*" * mask_count + " " + digits[-visible_digits:]
    else:
        masked = digits[:visible_digits] + " " + "*" * mask_count

    logger.debug(f"mask_sensitive_id: masked {len(digits)}-digit value with mask_position='{mask_position}'")
    return masked


# String values treated as True by get_bool_config (case-insensitive).
_TRUTHY_STRINGS = frozenset(("true", "1", "yes"))


def get_bool_config(value, default: bool = False) -> bool:
    """
    Convert a value to a boolean with consistent, non-raising type handling.

    A pure value-coercion helper (no config lookup) intended for values that may
    arrive as strings, ints, or native booleans.  Differs from ``str_to_bool``:
    it returns ``default`` for ``None`` and never raises.

    Args:
        value:   ``bool`` -> as-is; ``str`` -> "true"/"1"/"yes" (ci) -> True,
                 else False; ``int`` -> non-zero -> True; ``None`` -> ``default``;
                 other -> ``bool(value)``.
        default: Returned when ``value`` is ``None`` (default ``False``).

    Returns:
        bool
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY_STRINGS
    return bool(value)


def get_error_message(template: str, **kwargs) -> str:
    """
    Safely format a message template with optional placeholder substitution.

    A pure formatter (no config lookup): attempts ``template.format(**kwargs)``.
    If a placeholder is missing from ``kwargs`` the raw template is returned
    unchanged, so templates can gain/lose placeholders without breaking callers.

    Args:
        template: Message template with ``{placeholder}`` fields, or plain text.
                  Empty / ``None`` returns ``''``.
        **kwargs: Substitution values; extras are ignored.

    Returns:
        str: Formatted message, the raw template when a placeholder is missing,
             or ``''`` when the template is empty.
    """
    if not template:
        return ''
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
    except Exception as exc:
        logger.warning(f"get_error_message: could not format template. Reason: {exc}")
        return template


def clean_ocr_text(text):
    """
    Clean OCR-scanned text by fixing common OCR errors and normalizing whitespace.

    This function addresses typical OCR issues such as:
    - Extra whitespace and line breaks
    - Broken email addresses (spaces around @)
    - Broken domain names (spaces around dots in emails/URLs)
    - Common domain extensions (e.g., 'com au' -> 'com.au')

    Args:
        text: Raw text from OCR scanning (str or None)

    Returns:
        str or None: Cleaned text with common OCR errors corrected, or None if input is None

    Example:
        >>> clean_ocr_text("user @ example . com")
        'user@example.com'
        >>> clean_ocr_text("info @ company . com au")
        'info@company.com.au'
    """
    if text is None or not text:
        return text

    # Normalize whitespace (collapse multiple spaces/newlines to single space)
    cleaned = " ".join(text.split())

    # Fix broken email addresses: remove spaces around @
    cleaned = re.sub(r'\s*@\s*', '@', cleaned)

    # Fix broken domain names in emails/URLs: remove spaces around dots
    # This pattern is more conservative - only fixes dots in email/URL contexts
    # Pattern: word@word.word or www.word.word
    cleaned = re.sub(r'(@[a-zA-Z0-9-]+)\s*\.\s*', r'\1.', cleaned)  # After @
    cleaned = re.sub(r'(www)\s*\.\s*', r'\1.', cleaned)  # After www
    cleaned = re.sub(r'\.\s*([a-zA-Z0-9-]+@)', r'.\1', cleaned)  # Before @
    cleaned = re.sub(r'\.\s*(com|org|net|edu|gov|au|uk|us)\b', r'.\1', cleaned, flags=re.IGNORECASE)  # Common TLDs

    # Fix common OCR error: 'com au' -> 'com.au'
    cleaned = re.sub(r'com\s+au\b', 'com.au', cleaned, flags=re.IGNORECASE)

    logger.debug(f"Cleaned OCR text: '{text}' -> '{cleaned}'")

    return cleaned


def extract_text_from_document(file_path: str, max_pages: int = 5) -> str:
    """Extract plain text from the first *N* pages of a PDF file.

    Args:
        file_path: Absolute or relative path to a ``.pdf`` file.
        max_pages: Maximum number of pages to read. Defaults to 5.

    Returns:
        Concatenated text from up to ``max_pages`` pages, stripped of leading
        and trailing whitespace. Returns an empty string when the file does
        not exist, is not a PDF, or text extraction fails. This is the primary text that will be passed to OpenAI for field extraction.
    """
    if not file_path or not Path(file_path).is_file():
        return ""
    if Path(file_path).suffix.lower() != ".pdf":
        logger.warning("Expected source document to be a PDF, got: %s", file_path)
        return ""
    try:
        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is not available")
        pdf_document = fitz.open(file_path)
        pdf_text = ""
        page_count = len(pdf_document)
        pages_to_read = min(page_count, max_pages)
        for page_num in range(pages_to_read):
            page = pdf_document[page_num]
            pdf_text += page.get_text()
        logger.info(
            "Successfully read source PDF text: pages_read=%s/%s chars=%s",
            pages_to_read,
            page_count,
            len(pdf_text),
        )
        pdf_document.close()
        return pdf_text.strip()
    except Exception as exc:
        logger.warning("Could not extract text from source PDF '%s': %s", file_path, exc)
        return ""


def digits_only(value) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def html_to_pdf(
    html_source: Union[str, Path],
    output_pdf: Union[str, Path],
    *,
    is_file: bool = False,
) -> Path:
    """
    Convert HTML content or an HTML file to a PDF.

    Args:
        html_source:
            HTML content when is_file=False,
            otherwise path to an HTML file.
        output_pdf:
            Path where the PDF will be saved.
        is_file:
            True if html_source is a file path,
            False if html_source is raw HTML.

    Returns:
        Path to the generated PDF.

    Raises:
        FileNotFoundError:
            If the HTML file does not exist.
        RuntimeError:
            If PDF generation fails.
    """
    output_path = Path(output_pdf).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if is_file:
            html_path = Path(html_source).resolve()

            if not html_path.exists():
                raise FileNotFoundError(
                    f"HTML file not found: {html_path}"
                )

            HTML(
                filename=str(html_path),
                base_url=str(html_path.parent),
            ).write_pdf(str(output_path))

        else:
            HTML(
                string=str(html_source),
            ).write_pdf(str(output_path))

        return output_path

    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate PDF '{output_path}': {exc}"
        ) from exc


# ====================================================================================
# DOCUMENT-TO-PDF CONVERSION (ENSURE PDF)
# ====================================================================================
# A queue item may carry a non-PDF file (Word document, spreadsheet, scanned
# image, saved HTML). Downstream steps (text extraction, redaction, upload)
# expect a PDF, so callers run ``ensure_pdf`` early and use the returned path.
#
# Format -> converter:
#   .docx / .doc                         -> Word COM automation (win32com) -> PDF
#   .xlsx / .xls                         -> Excel COM automation (win32com) -> PDF
#   .png/.jpg/.jpeg/.tiff/.tif/.bmp/.gif -> PyMuPDF (fitz) image-to-PDF
#   .html / .htm                         -> html_to_pdf() (WeasyPrint, above)
#   .pdf                                 -> returned unchanged
#   anything else                        -> UnsupportedDocumentFormatError
#
# ``win32com`` is imported lazily inside the Office converters so importing this
# module on a box without Office doesn't fail until a conversion is attempted.
# ``fitz`` and ``weasyprint`` are already hard imports at the top of the module.
WORD_FORMATS = frozenset({".docx", ".doc"})
EXCEL_FORMATS = frozenset({".xlsx", ".xls"})
IMAGE_FORMATS = frozenset({".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"})
HTML_FORMATS = frozenset({".html", ".htm"})


def _convert_word_to_pdf(src_path: str, dst_path: str) -> None:
    """Convert a .doc/.docx to PDF via Word COM automation (Windows only)."""
    logger.info("  Converting Word document to PDF via win32com...")
    try:
        import win32com.client as win32
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc_com = word.Documents.Open(os.path.abspath(src_path))
        try:
            # wdFormatPDF = 17
            doc_com.SaveAs(os.path.abspath(dst_path), FileFormat=17)
            logger.info(f"  Converted: {dst_path}")
        finally:
            doc_com.Close(False)
            word.Quit()
    except Exception as e:
        logger.error(f"  Word-to-PDF conversion failed: {e}")
        raise DocumentConversionError(str(e), source_format="word")


def _convert_excel_to_pdf(src_path: str, dst_path: str) -> None:
    """Convert a .xls/.xlsx to PDF via Excel COM automation (Windows only)."""
    logger.info("  Converting Excel workbook to PDF via win32com...")
    try:
        import win32com.client as win32
        excel = win32.Dispatch("Excel.Application")
        excel.Visible = False
        wb = excel.Workbooks.Open(os.path.abspath(src_path))
        try:
            # xlTypePDF = 0
            wb.ExportAsFixedFormat(0, os.path.abspath(dst_path))
            logger.info(f"  Converted: {dst_path}")
        finally:
            wb.Close(False)
            excel.Quit()
    except Exception as e:
        logger.error(f"  Excel-to-PDF conversion failed: {e}")
        raise DocumentConversionError(str(e), source_format="excel")


def _convert_image_to_pdf(src_path: str, dst_path: str) -> None:
    """Convert a raster image to a single-page PDF via PyMuPDF (fitz)."""
    logger.info("  Converting image to PDF via PyMuPDF...")
    try:
        img_doc = fitz.open(src_path)            # fitz opens most image formats
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()
        with open(dst_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"  Converted: {dst_path}")
    except Exception as e:
        logger.error(f"  Image-to-PDF conversion failed: {e}")
        raise DocumentConversionError(str(e), source_format="image")


def ensure_pdf(file_path: str) -> str:
    """
    Ensure ``file_path`` points to a PDF, converting if necessary.

    Word / Excel / image / HTML inputs are converted to a PDF written alongside
    the source (same name, ``.pdf`` extension). A file that is already a PDF is
    returned unchanged. The HTML branch reuses :func:`html_to_pdf` so there is
    one WeasyPrint code path.

    Args:
        file_path: Path to the source document.

    Returns:
        Path to the PDF (the original path if it was already a PDF, otherwise
        the newly-written ``.pdf`` next to the source file).

    Raises:
        UnsupportedDocumentFormatError: extension has no conversion path
            (caller should treat as business/manual).
        DocumentConversionError: a supported type failed to convert
            (caller should treat as system/transient). Carries ``source_format``.
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    logger.info(f"  File: {file_path}")
    logger.info(f"  Extension: {file_ext}")

    if file_ext == ".pdf":
        logger.info("  File is already PDF -- no conversion needed")
        return file_path

    converted_pdf_path = os.path.splitext(file_path)[0] + ".pdf"

    if file_ext in WORD_FORMATS:
        _convert_word_to_pdf(file_path, converted_pdf_path)
    elif file_ext in EXCEL_FORMATS:
        _convert_excel_to_pdf(file_path, converted_pdf_path)
    elif file_ext in IMAGE_FORMATS:
        _convert_image_to_pdf(file_path, converted_pdf_path)
    elif file_ext in HTML_FORMATS:
        logger.info("  Converting HTML to PDF via html_to_pdf (WeasyPrint)...")
        try:
            html_to_pdf(file_path, converted_pdf_path, is_file=True)
            logger.info(f"  Converted: {converted_pdf_path}")
        except Exception as e:
            logger.error(f"  HTML-to-PDF conversion failed: {e}")
            raise DocumentConversionError(str(e), source_format="html")
    else:
        raise UnsupportedDocumentFormatError(file_ext, file_path)

    logger.info(f"  Final PDF path: {converted_pdf_path}")
    return converted_pdf_path
