"""
====================================================================================
CLIENT ID PARSER MODULE
====================================================================================

Utilities for parsing and validating Australian client identifiers used across
RPA workflows.  Currently supports Tax File Numbers (TFN) and Australian Business
Numbers (ABN) supplied as prefixed strings (e.g. from an Orchestrator queue field).

KEY FEATURES:
    - Parses "TFN <number>" and "ABN <number>" prefixed strings into a typed tuple
    - Case-insensitive prefix matching
    - Masks the bare number in log output for security compliance
    - Configurable masking position and visible-digit count
    - Raises DataValidationError with a descriptive message on unrecognised format
    - No dependency on project-specific Config or Orchestrator objects —
      fully self-contained for reuse across any iaa_rpa_* client library

MAIN FUNCTIONS:
    - parse_client_id(): Split a prefixed client ID string into (number, type)

SUPPORTED FORMATS:
    Prefix must be the first token, followed by an optional space then the number:
        "TFN 123456789"    ->  ("123456789", "TFN")
        "TFN123456789"     ->  ("123456789", "TFN")
        "ABN 98765432100"  ->  ("98765432100", "ABN")
        "abn98765432100"   ->  ("98765432100", "ABN")   (case-insensitive)

DEPENDENCIES:
    - iaa_rpa_utils.strfunctions: mask_sensitive_id — safe log masking
    - iaa_rpa_utils.exceptions:   DataValidationError — raised on bad format

USAGE EXAMPLE:
    from iaa_rpa_utils.id_parser import parse_client_id
    from iaa_rpa_utils.exceptions import DataValidationError

    try:
        number, id_type = parse_client_id("TFN 123456789")
        # number  -> "123456789"
        # id_type -> "TFN"
    except DataValidationError as exc:
        logger.error(str(exc))
        raise
"""

# ====================================================================================
# STANDARD LIBRARY IMPORTS
# ====================================================================================
import logging

# ====================================================================================
# INTERNAL IMPORTS
# ====================================================================================
from .strfunctions import mask_sensitive_id
from .exceptions import DataValidationError

# ====================================================================================
# MODULE SETUP
# ====================================================================================
_logger = logging.getLogger("IARPA." + __name__)

# Recognised prefix tokens (upper-cased for comparison).
_SUPPORTED_PREFIXES = ("TFN", "ABN")


# ====================================================================================
# PUBLIC API
# ====================================================================================


def parse_client_id(
    client_id: str,
    visible_digits: int,
    mask_position: str,
) -> tuple:
    """
    Parse a prefixed client ID string into a (number, type) tuple.

    The input must begin with a recognised prefix — ``TFN`` or ``ABN``
    (case-insensitive) — optionally followed by a space before the digits.
    The bare number and the upper-cased type label are returned as a 2-tuple.

    Parameters
    ----------
    client_id : str
        Raw client ID string as received from an Orchestrator queue field or
        similar source.  Examples: ``"TFN 123456789"``, ``"ABN 98765432100"``.
    visible_digits : int, optional
        Number of digits left unmasked in log output.  Default is ``4``.
        Passed directly to :func:`~iaa_rpa_utils.strfunctions.mask_sensitive_id`.
    mask_position : str, optional
        Controls which end of the number is shown in logs.
        ``"start"`` — mask the beginning, show the last *N* digits (default).
        ``"end"``   — show the first *N* digits, mask the rest.

    Returns
    -------
    tuple[str, str]
        A 2-tuple of ``(search_number, search_type)`` where:

        * ``search_number`` — the bare identifier with the prefix and any
          leading/trailing whitespace removed (e.g. ``"123456789"``).
        * ``search_type``   — the upper-cased prefix token (``"TFN"`` or ``"ABN"``).

    Raises
    ------
    DataValidationError
        If ``client_id`` is empty, ``None``, or does not begin with a
        supported prefix.  The exception message names the unrecognised value
        and lists the accepted prefixes so the caller can surface it as a
        meaningful business error.

    Notes
    -----
    * Prefix matching is case-insensitive: ``"tfn"``, ``"TFN"``, and ``"Tfn"``
      are all accepted.
    * The raw number is **never** logged in plain text; it is always passed
      through :func:`~iaa_rpa_utils.strfunctions.mask_sensitive_id` first.
    * This function does **not** validate the length or check-digit of the
      returned number — that responsibility belongs to the calling workflow.

    Examples
    --------
    Parse a TFN queue value:

    >>> from iaa_rpa_utils.id_parser import parse_client_id
    >>> parse_client_id("TFN 123456789")
    ('123456789', 'TFN')

    Parse an ABN (no space between prefix and digits):

    >>> parse_client_id("ABN98765432100")
    ('98765432100', 'ABN')

    Case-insensitive prefix:

    >>> parse_client_id("tfn 123456789")
    ('123456789', 'TFN')

    Custom masking — show first 3 digits in logs:

    >>> parse_client_id("TFN 123456789", visible_digits=3, mask_position="end")
    ('123456789', 'TFN')

    Invalid format raises DataValidationError:

    >>> parse_client_id("INVALID 123")
    DataValidationError: Unrecognised client ID format: 'INVALID 123'.
        Expected a value prefixed with one of: TFN, ABN.
    """
    # ====================================================================
    # GUARD: empty input
    # ====================================================================
    if not client_id or not client_id.strip():
        raise DataValidationError(
            "parse_client_id: client_id is empty or None. "
            f"Expected a value prefixed with one of: {', '.join(_SUPPORTED_PREFIXES)}."
        )

    client_id_upper = client_id.strip().upper()

    # ====================================================================
    # PREFIX MATCHING
    # ====================================================================
    matched_prefix = None
    for prefix in _SUPPORTED_PREFIXES:
        if client_id_upper.startswith(prefix):
            matched_prefix = prefix
            break

    if matched_prefix is None:
        raise DataValidationError(
            f"Unrecognised client ID format: '{client_id.strip()}'. "
            f"Expected a value prefixed with one of: {', '.join(_SUPPORTED_PREFIXES)}."
        )

    # Strip the matched prefix and any surrounding whitespace to get the bare number.
    search_number = client_id.strip()[len(matched_prefix) :].strip()
    search_type = matched_prefix  # already upper-cased

    # ====================================================================
    # LOGGING  (masked for security)
    # ====================================================================
    masked = mask_sensitive_id(
        search_number, visible_digits=visible_digits, mask_position=mask_position
    )
    _logger.info(f"parse_client_id: type={search_type} | number={masked}")

    return search_number, search_type


# ====================================================================================
# STANDALONE USAGE EXAMPLE
# ====================================================================================
# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(level=logging.INFO)
#
#     test_cases = [
#         "TFN 123456789",
#         "ABN 98765432100",
#         "tfn123456789",
#         "abn 12 345 678 901",
#     ]
#     for raw in test_cases:
#         number, id_type = parse_client_id(raw)
#         print(f"Input: {raw!r:30s}  ->  type={id_type}, number={number}")
