"""
====================================================================================
PDF MERGER MODULE
====================================================================================

General-purpose utility for merging multiple PDF documents into a single output
file. Designed for use in RPA workflows where downloaded or generated PDFs need
to be combined before archiving, emailing, or uploading to a client portal.

KEY FEATURES:
    - Merge any number of PDF files into a single output document
    - Preserves page order based on the input list sequence
    - Skips missing files gracefully with a logged warning (no silent failures)
    - Validates dependencies and inputs before attempting any file I/O
    - Creates the output directory automatically if it does not exist
    - Reports final file size for downstream verification

MAIN FUNCTIONS:
    - merge_pdfs(): Merge an ordered list of PDF paths into one output PDF

TYPICAL USE CASES:
    - Combine a cover page PDF with a body PDF before sending to a portal
    - Stitch multiple downloaded statement PDFs into a single archive file
    - Concatenate per-entity PDFs into a single batch report

DEPENDENCIES:
    - PyMuPDF (fitz): PDF manipulation library  (pip install PyMuPDF)
    - os: Standard library — path checks and directory creation

USAGE EXAMPLE:
    from iaa_rpa_utils.pdf_merger import merge_pdfs

    success = merge_pdfs(
        pdf_paths=["cover.pdf", "body.pdf", "appendix.pdf"],
        output_path="C:/temp/merged_output.pdf",
    )
    if not success:
        raise RuntimeError("PDF merge failed — check logs for details")
"""

# ====================================================================================
# STANDARD LIBRARY IMPORTS
# ====================================================================================
import logging
import os
from typing import List

# ====================================================================================
# THIRD-PARTY IMPORTS
# ====================================================================================
try:
    import fitz  # PyMuPDF — PDF manipulation library
except ImportError:
    raise ImportError(
        "PyMuPDF (fitz) is required for PDF merging. "
        "Install it with: pip install PyMuPDF"
    )

# ====================================================================================
# MODULE SETUP
# ====================================================================================
_logger = logging.getLogger("IARPA." + __name__)


# ====================================================================================
# PUBLIC API
# ====================================================================================


def merge_pdfs(pdf_paths: List[str], output_path: str) -> bool:
    """
    Merge multiple PDF files into a single output PDF using PyMuPDF (fitz).

    Pages are appended in the order supplied by ``pdf_paths``. Any path that
    does not exist on disk is skipped with a ``WARNING`` log entry so the merge
    can still complete with the remaining files. If *every* path is missing the
    function returns ``False`` after logging an error.

    Parameters
    ----------
    pdf_paths : list[str]
        Ordered list of absolute (or resolvable relative) paths to the PDF
        files that should be merged.  The list must contain at least one entry.
    output_path : str
        Destination path for the merged PDF.  The parent directory is created
        automatically if it does not already exist.

    Returns
    -------
    bool
        ``True``  — merged PDF was written to ``output_path`` successfully.
        ``False`` — an error occurred (dependency missing, empty input list,
                    all source files missing, or an unexpected exception).
                    All failure reasons are written to the logger.

    Raises
    ------
    This function does **not** raise.  All exceptions are caught internally and
    reported via ``_logger.error``.  Callers should treat a ``False`` return
    value as a hard failure and inspect the logs for the root cause.

    Notes
    -----
    * Each source PDF is opened in a ``with`` block so its file handle is
      released immediately after its pages have been inserted.
    * The merged document is built in memory and written to disk in one
      ``save()`` call — no temporary files are created.
    * Non-PDF inputs (e.g. HTML files accepted by ``fitz.open``) are **not**
      supported by this function; pre-convert them to PDF first if needed.

    Examples
    --------
    Merge three PDFs into one output file:

    >>> from iaa_rpa_utils.pdf_merger import merge_pdfs
    >>> success = merge_pdfs(
    ...     pdf_paths=[
    ...         "C:/reports/cover.pdf",
    ...         "C:/reports/body.pdf",
    ...         "C:/reports/appendix.pdf",
    ...     ],
    ...     output_path="C:/reports/final_report.pdf",
    ... )
    >>> assert success, "Merge failed — check the IARPA logs"

    Merge two files where one might not exist yet (safe — it is skipped):

    >>> merge_pdfs(
    ...     pdf_paths=["mandatory.pdf", "optional_attachment.pdf"],
    ...     output_path="C:/out/combined.pdf",
    ... )
    True
    """
    try:
        # ====================================================================
        # INPUT VALIDATION
        # ====================================================================
        if not pdf_paths:
            _logger.warning("merge_pdfs: no PDF paths provided — nothing to merge")
            return False

        _logger.info(f"merge_pdfs: merging {len(pdf_paths)} file(s) → {output_path}")

        # ====================================================================
        # OUTPUT DIRECTORY SETUP
        # ====================================================================
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            _logger.info(f"  Created output directory: {output_dir}")

        # ====================================================================
        # MERGE
        # ====================================================================
        merged_pdf = fitz.open()
        files_added = 0

        for i, pdf_path in enumerate(pdf_paths, start=1):
            if not os.path.exists(pdf_path):
                _logger.warning(
                    f"  [{i}/{len(pdf_paths)}] File not found, skipping: {pdf_path}"
                )
                continue

            _logger.info(
                f"  [{i}/{len(pdf_paths)}] Adding: {os.path.basename(pdf_path)}"
            )
            with fitz.open(pdf_path) as pdf_doc:
                merged_pdf.insert_pdf(pdf_doc)
            files_added += 1

        if files_added == 0:
            _logger.error(
                "merge_pdfs: no valid PDF files were found — output not written"
            )
            merged_pdf.close()
            return False

        # ====================================================================
        # SAVE AND CLEANUP
        # ====================================================================
        merged_pdf.save(output_path)
        merged_pdf.close()

        file_size_kb = os.path.getsize(output_path) / 1024
        _logger.info(f"  Merged PDF saved: {output_path}")
        _logger.info(
            f"  Pages from {files_added} file(s) | Size: {file_size_kb:.2f} KB"
        )

        return True

    except Exception as e:
        _logger.error(f"merge_pdfs: unexpected error — {e}", exc_info=True)
        return False


# ====================================================================================
# STANDALONE USAGE EXAMPLE
# ====================================================================================
# if __name__ == "__main__":
#     result = merge_pdfs(
#         pdf_paths=[
#             "C:/temp/cover_page.pdf",
#             "C:/temp/main_body.pdf",
#             "C:/temp/appendix.pdf",
#         ],
#         output_path="C:/temp/merged_output.pdf",
#     )
#     print("Merge successful:" if result else "Merge failed — check logs")
