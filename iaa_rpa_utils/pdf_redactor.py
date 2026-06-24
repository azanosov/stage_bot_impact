"""
====================================================================================
PDF REDACTION MODULE
====================================================================================

General-purpose utility for redacting sensitive information from PDF documents.
Supports any text pattern redaction, with built-in convenience for Australian
Tax File Numbers (TFN) including format variation handling and PRN exclusion.

KEY FEATURES:
    - Search for any text patterns across all pages of a PDF
    - Apply permanent white-box redaction over matched text
    - Support for multiple TFN format variations (with/without spaces or hyphens)
    - PRN (Payment Reference Number) exclusion — prevents over-redaction when
      the TFN digits appear as a substring inside the PRN
    - Automatically converts non-PDF inputs (e.g., HTML) to PDF before processing
    - Preserves original PDF structure while permanently removing sensitive data

MAIN FUNCTIONS:
    - search_and_redact_text(): Generic text search and redaction for any patterns
    - redact_tfn_from_pdf(): TFN-specific redaction with automatic format handling

SECURITY NOTE:
    Redactions are applied permanently using PyMuPDF's built-in redaction feature.
    The original text is completely removed from the PDF, not just visually covered.

DEPENDENCIES:
    - PyMuPDF (fitz): PDF manipulation library
    - shutil: For file copy operations when no redaction is needed
"""

# ====================================================================================
# STANDARD LIBRARY IMPORTS
# ====================================================================================
import shutil
import logging
import os
from typing import List, Union
from pathlib import Path

# ====================================================================================
# THIRD-PARTY IMPORTS
# ====================================================================================
try:
    import fitz  # PyMuPDF - PDF manipulation library
except ImportError:
    raise ImportError("PyMuPDF (fitz) is required. Install it with: pip install PyMuPDF")

# ====================================================================================
# MODULE SETUP
# ====================================================================================
# Set up logger with standard naming convention
_logger = logging.getLogger("IARPA." + __name__)


def search_and_redact_text(input_pdf: str, output_pdf: str, search_texts: List[str],
                           exclude_texts: List[str] = None) -> bool:
    """
    Search for specific text in a PDF and redact (white out) all instances.

    This function:
    1. Opens the input PDF file
    2. Searches for each text pattern on every page
    3. Adds redaction annotations (white rectangles) over matching text
    4. Applies the redactions permanently
    5. Saves the redacted PDF to the output path

    Args:
        input_pdf: Full file path to the input PDF document
        output_pdf: Full file path where the redacted PDF will be saved
        search_texts: List of text strings to search for and redact
                     Example: ["123 456 789", "Tax File Number: 123456789"]
        exclude_texts: List of text strings where matches should NOT be redacted.
                      If a match falls within the bounding box of any exclude text,
                      redaction is skipped. Used to protect PRN from TFN redaction.

    Returns:
        bool: True if redaction was successful, False otherwise

    Example:
        input_pdf = "C:\\temp\\document.pdf"
        output_pdf = "C:\\temp\\document_redacted.pdf"
        search_texts = ["123 456 789", "TFN 123456789"]
        success = search_and_redact_text(input_pdf, output_pdf, search_texts)
    """
    try:
        _logger.info(f"Starting PDF redaction process")
        _logger.info(f"  Input PDF: {input_pdf}")
        _logger.info(f"  Output PDF: {output_pdf}")
        _logger.info(f"  Texts to redact: {len(search_texts)} item(s)")

        # ====================================================================
        # INPUT VALIDATION
        # ====================================================================
        # Validate input file exists before attempting to process
        if not os.path.exists(input_pdf):
            _logger.error(f"  ERROR: Input PDF file not found: {input_pdf}")
            return False

        # Validate search_texts is not empty
        # If no texts to redact, simply copy the file as-is
        if not search_texts or len(search_texts) == 0:
            _logger.warning(f"  WARNING: No search texts provided - skipping redaction")
            # Copy input to output preserving metadata (copy2 preserves timestamps)
            shutil.copy2(input_pdf, output_pdf)
            return True

        # ====================================================================
        # OUTPUT DIRECTORY SETUP
        # ====================================================================
        # Create output directory if it doesn't exist
        # This ensures the save operation won't fail due to missing directories
        output_dir = os.path.dirname(output_pdf)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            _logger.info(f"  Created output directory: {output_dir}")

        # ====================================================================
        # PDF PROCESSING
        # ====================================================================
        # Open the document using PyMuPDF
        # If the input is not a PDF (e.g., HTML from ATO portal), convert it to PDF first
        pdf_document = fitz.open(input_pdf)
        if not pdf_document.is_pdf:
            _logger.info(f"  Input is not a PDF ({os.path.splitext(input_pdf)[1]}) - converting to PDF")
            pdf_bytes = pdf_document.convert_to_pdf()
            pdf_document.close()
            pdf_document = fitz.open("pdf", pdf_bytes)
        _logger.info(f"  Opened PDF: {len(pdf_document)} page(s)")

        # Counter to track total redactions across all pages
        total_redactions = 0

        # ====================================================================
        # PAGE-BY-PAGE REDACTION
        # ====================================================================
        # Iterate through each page in the PDF document
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            page_redactions = 0

            # Find bounding boxes of all exclude texts on this page (once per page)
            # Used to skip redaction when a match falls inside an excluded region (e.g., PRN)
            exclude_rects = []
            if exclude_texts:
                for exclude_text in exclude_texts:
                    if exclude_text and exclude_text.strip():
                        exclude_rects.extend(page.search_for(exclude_text))

            # Search for each text pattern on this page
            for search_text in search_texts:
                # Skip empty or whitespace-only search texts
                if not search_text or search_text.strip() == "":
                    continue

                # Use PyMuPDF's search_for() to find all instances of the text
                # Returns a list of fitz.Rect objects representing bounding boxes
                text_instances = page.search_for(search_text)

                if text_instances:
                    _logger.info(f"    Page {page_num + 1}: Found {len(text_instances)} instance(s) of text to redact")

                # Apply redaction annotation to each found instance
                for inst in text_instances:
                    # Check if this match falls within any excluded text region
                    if exclude_rects:
                        skip = False
                        for ex_rect in exclude_rects:
                            # Skip if the match is contained within or overlaps the exclude region
                            if ex_rect.contains(inst) or inst.intersects(ex_rect):
                                _logger.info(f"    Page {page_num + 1}: Skipping redaction - text is part of excluded region (e.g., PRN)")
                                skip = True
                                break
                        if skip:
                            continue

                    # Add white-filled redaction annotation over the text
                    # fill=(1, 1, 1) means RGB white color
                    # This marks the area for redaction but doesn't apply it yet
                    page.add_redact_annot(inst, fill=(1, 1, 1))
                    page_redactions += 1
                    total_redactions += 1

            # Apply all queued redactions on this page
            # This permanently removes the text under the redaction annotations
            if page_redactions > 0:
                page.apply_redactions()
                _logger.info(f"  Page {page_num + 1}: Applied {page_redactions} redaction(s)")

        # ====================================================================
        # SAVE AND CLEANUP
        # ====================================================================
        # Save the modified PDF to the output path
        pdf_document.save(output_pdf)
        # Close the document to release file handles
        pdf_document.close()

        _logger.info(f"  Total redactions applied: {total_redactions}")
        _logger.info(f"  Successfully saved redacted PDF: {output_pdf}")

        return True

    except Exception as e:
        _logger.error(f"  ERROR: Failed to redact PDF: {str(e)}", exc_info=True)
        return False


def redact_tfn_from_pdf(input_pdf: str, output_pdf: str, tfn_number: str,
                        additional_patterns: List[str] = None,
                        prn_numbers: Union[str, List[str]] = None) -> bool:
    """
    Convenience function to redact Tax File Number (TFN) from a PDF.
    Only redacts the TFN number itself (not labels like "TFN" or "Tax file number").
    Uses white color for redaction.

    Args:
        input_pdf: Full file path to the input PDF document
        output_pdf: Full file path where the redacted PDF will be saved
        tfn_number: The TFN to redact (e.g., "123456789" or "123 456 789")
        additional_patterns: Additional text patterns to redact (optional)
        prn_numbers: One or more Payment Reference Numbers to exclude from redaction.
                     Accepts a single string or a list of strings. TFN digits that
                     appear within any PRN will NOT be redacted.
                     e.g. "551008362461054301" or ["551008362461054301", "449123456789012"]

    Returns:
        bool: True if redaction was successful, False otherwise

    Example:
        success = redact_tfn_from_pdf(
            input_pdf="C:\\temp\\notice.pdf",
            output_pdf="C:\\temp\\notice_redacted.pdf",
            tfn_number="123456789",
            prn_numbers=["551008362461054301", "449123456789012"]
        )
    """
    try:
        # ====================================================================
        # TFN FORMAT HANDLING
        # ====================================================================
        # TFNs can appear in various formats in PDF documents:
        # - With spaces: "123 456 789"
        # - Without spaces: "123456789"
        # - With hyphens: "123-456-789"
        # This function searches for all common variations to ensure complete redaction

        # Create list of TFN patterns to search for
        search_texts = []

        if tfn_number:
            # Pattern 1: Original format as provided (exact match)
            # This catches the TFN exactly as it appears in the source data
            search_texts.append(tfn_number.strip())

            # Clean the TFN by removing all spaces and hyphens
            # This gives us a normalized 9-digit number to work with
            tfn_clean = tfn_number.replace(" ", "").replace("-", "")

            # Pattern 2: Cleaned format without any separators (e.g., "123456789")
            search_texts.append(tfn_clean)

            # Pattern 3: Standard ATO format with spaces (XXX XXX XXX)
            # Only apply if the TFN has at least 9 digits
            if len(tfn_clean) >= 9:
                search_texts.append(f"{tfn_clean[:3]} {tfn_clean[3:6]} {tfn_clean[6:9]}")

            # Log the TFN being redacted (masked for security in logs)
            _logger.info(f"Redacting TFN number only (not labels): {tfn_clean[:3]}***{tfn_clean[-2:]} (masked for security)")

        # ====================================================================
        # ADDITIONAL PATTERNS
        # ====================================================================
        # Add any additional patterns provided by the caller
        # This allows for custom text redaction alongside TFN
        if additional_patterns:
            search_texts.extend(additional_patterns)

        # ====================================================================
        # PRN EXCLUSION
        # ====================================================================
        # Build list of PRN text variations to exclude from redaction.
        # Accepts a single PRN string or a list (e.g. NOA PRN + SOA PRN).
        # For each PRN, generate format variations so all appearances are protected.
        exclude_texts = []
        if prn_numbers:
            raw_list = [prn_numbers] if isinstance(prn_numbers, str) else prn_numbers
            for prn in raw_list:
                if not prn:
                    continue
                prn_clean = prn.replace(" ", "").replace("-", "")
                exclude_texts.append(prn.strip())
                exclude_texts.append(prn_clean)
                exclude_texts.append(f"{prn_clean[:3]} {prn_clean[3:8]} {prn_clean[8:11]} {prn_clean[11:14]} {prn_clean[14:]}")
            _logger.info(f"PRN exclusion: {len(raw_list)} PRN(s), {len(exclude_texts)} variation(s) total")

        # ====================================================================
        # PERFORM REDACTION
        # ====================================================================
        # Call the generic redaction function with all patterns
        return search_and_redact_text(input_pdf, output_pdf, search_texts, exclude_texts=exclude_texts)

    except Exception as e:
        _logger.error(f"ERROR: Failed to redact TFN from PDF: {str(e)}", exc_info=True)
        return False


# Example usage (commented out)
# if __name__ == "__main__":
#     input_pdf = "C:\\temp\\document.pdf"
#     output_pdf = "C:\\temp\\document_redacted.pdf"
#
#     # Method 1: Redact arbitrary text patterns
#     search_texts = ["Confidential", "123 456 789"]
#     success = search_and_redact_text(input_pdf, output_pdf, search_texts)
#
#     # Method 2: Redact a TFN — handles all common formats automatically
#     #            and optionally excludes matches that fall within the PRN
#     success = redact_tfn_from_pdf(
#         input_pdf=input_pdf,
#         output_pdf=output_pdf,
#         tfn_number="123456789",
#         prn_number="551008362461054301",   # optional
#     )
