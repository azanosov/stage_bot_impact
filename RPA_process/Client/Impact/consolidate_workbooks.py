"""
====================================================================================
WORKBOOK CONSOLIDATION MODULE
====================================================================================

Move worksheet tabs from ONE source workbook into ONE target workbook, preserving
each tab's full appearance - formatting, column widths, merged cells, number
formats and values - by driving the installed Excel application via COM
automation (win32com). Because Excel itself performs the sheet copy, fidelity is
exact, and both legacy ``.xls`` and modern ``.xlsx`` sources are read natively.

SINGLE SOURCE -> SINGLE TARGET, ONE CALL:
    The function moves tabs from one source into one target. To consolidate many
    reports, the operator loops over their sources and calls this once per source;
    the target accumulates tabs across calls (append mode). Partial-failure policy
    across many files is therefore the operator's concern - this function does one
    merge and raises on its own failure.

    The target workbook is CREATED on the first call if it does not yet exist, so
    the operator can simply call the function N times without pre-creating a file.

KEY FEATURES:
    - Faithful tab copy (formatting/widths/merges/number formats) via Excel COM
    - Reads mixed .xls and .xlsx sources; always saves the target as .xlsx
    - Optional per-call sheet selection; defaults to the source's first tab
    - Duplicate-name protection: the original keeps its name, later collisions get
      a ``_copy(N)`` suffix, truncated to respect Excel's 31-character tab limit
    - Disciplined COM cleanup (workbooks closed, Excel quit) in a finally block

MAIN FUNCTIONS:
    - consolidate_workbook(): Move selected tabs from one source into the target

DEPENDENCIES:
    - pywin32 (win32com): Excel COM automation. Windows only; Excel must be
      installed on the machine that runs this.
    - iaa_rpa_utils: ProcessLogger, setup_logger.

USAGE EXAMPLE:
    from consolidate_workbooks import (
        WorkbookConsolidationRequest,
        consolidate_workbook,
    )

    target = r"C:\\Reports\\consolidated.xlsx"
    sources = [
        (r"C:\\Reports\\aged_receivables.xlsx", None),                 # first tab
        (r"C:\\Reports\\trial_balance.xlsx", ["Trial Balance"]),       # named tab
        (r"C:\\Reports\\gst.xls", ["GST Calc", "GST Audit"]),          # several tabs
    ]
    for source_path, sheets in sources:
        request = WorkbookConsolidationRequest(
            source_path=source_path,
            target_path=target,
            sheets=sheets,
        )
        consolidate_workbook(request)
"""

# ====================================================================================
# STANDARD LIBRARY IMPORTS
# ====================================================================================
import os
from dataclasses import dataclass

# ====================================================================================
# INTERNAL IMPORTS
# ====================================================================================
from iaa_rpa_utils import ProcessLogger, setup_logger

# ====================================================================================
# MODULE SETUP
# ====================================================================================
logger = setup_logger(__name__)

# Public API of this module.
__all__ = [
    "WorkbookConsolidationRequest",
    "consolidate_workbook",
]

# ====================================================================================
# MODULE CONSTANTS
# ====================================================================================
_MAX_SHEET_NAME_LEN = 31  # Excel's hard limit on worksheet tab names
_INVALID_SHEET_CHARS = set(r"[]:*?/\\")  # characters Excel forbids in tab names
_XL_FILEFORMAT_XLSX = 51  # xlOpenXMLWorkbook - save target as .xlsx


@dataclass(frozen=True, kw_only=True)
class WorkbookConsolidationRequest:
    """Inputs for moving tabs from one source workbook into one target workbook.

    Holds configuration only; this module owns no browser/engine. One request
    describes one source -> target merge; the operator loops for many sources.

    Attributes:
        source_path: Path to the source workbook (``.xls`` or ``.xlsx``). Must exist.
        target_path: Path to the consolidated workbook (always saved as ``.xlsx``).
                     Created on the first call if it does not already exist; on
                     later calls it is opened and appended to.
        sheets:      Optional list of tab names to move from the source. When
                     omitted (``None``), only the source's first tab (leftmost by
                     position) is moved. Every named tab must exist in the source.
    """

    source_path: str
    target_path: str
    sheets: list[str] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, str) or not self.source_path.strip():
            raise ValueError("source_path is required and must be a non-empty string")
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("target_path is required and must be a non-empty string")

        if self.sheets is not None:
            if not isinstance(self.sheets, list) or not all(
                isinstance(s, str) for s in self.sheets
            ):
                raise TypeError("sheets must be a list of strings, or None")
            if not self.sheets:
                raise ValueError(
                    "sheets must be a non-empty list when provided (use None for first tab)"
                )


def _unique_sheet_name(desired: str, existing: set[str]) -> str:
    """Return a tab name that does not collide with ``existing``.

    The first use of a name is kept as-is. A name already present is suffixed
    ``_copy(1)``, ``_copy(2)``, ... until free. The base name is truncated as
    needed so the final name never exceeds Excel's 31-character limit.

    Args:
        desired:  The source tab's own name.
        existing: Names already present in the target (lower-cased compare is not
                  used - Excel treats tab names case-insensitively, but we mirror
                  its exact-string behaviour here and let Excel be the final arbiter).

    Returns:
        A collision-free name of at most 31 characters.
    """
    # Truncate the desired name itself if it is already over the limit.
    base = desired[:_MAX_SHEET_NAME_LEN]
    if base not in existing:
        return base

    n = 1
    while True:
        suffix = f"_copy({n})"
        # Reserve room for the suffix, truncating the base so base+suffix <= 31.
        trimmed = base[: _MAX_SHEET_NAME_LEN - len(suffix)]
        candidate = f"{trimmed}{suffix}"
        if candidate not in existing:
            return candidate
        n += 1


def consolidate_workbook(request: WorkbookConsolidationRequest) -> None:
    """
    Move selected tabs from one source workbook into the target workbook.

    Faithfully copies each chosen worksheet (formatting and all) from
    ``request.source_path`` into ``request.target_path`` using Excel COM
    automation. The target is created on the first call if absent, and appended
    to on subsequent calls, so the operator can call this once per source in a
    loop.

    Behaviour:
        - If ``request.sheets`` is None, only the source's first tab is moved.
          Otherwise each named tab is moved, in the given order.
        - Tab-name collisions in the target are resolved by ``_unique_sheet_name``
          (original kept, later copies suffixed ``_copy(N)``, truncated to 31 chars).
        - The target is always saved as ``.xlsx`` regardless of the source format.
        - The function only ADDS tabs to the target; it never deletes or alters
          tabs already there. A freshly created target keeps Excel's default blank
          sheet - create the target deliberately if you do not want it.

    Args:
        request (WorkbookConsolidationRequest): Source, target, and optional sheets.

    Returns:
        None

    Raises:
        FileNotFoundError: If the source workbook does not exist.
        ValueError: If a name in ``request.sheets`` is not a tab in the source.
        RuntimeError: If Excel COM is unavailable or a COM operation fails.
    """
    with ProcessLogger("Consolidate Workbook Tabs", logger):
        source_path = os.path.abspath(request.source_path)
        target_path = os.path.abspath(request.target_path)
        logger.info(f"  Source: {source_path}")
        logger.info(f"  Target: {target_path}")
        logger.info(
            f"  Sheets: {request.sheets if request.sheets is not None else '(first tab)'}"
        )

        # ====================================================================
        # INPUT VALIDATION
        # ====================================================================
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source workbook not found: {source_path}")

        # Ensure the target's parent directory exists (matches pdf_merger/redactor).
        # Excel's SaveAs creates the FILE but not missing parent FOLDERS.
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            logger.info(f"  Created target directory: {target_dir}")

        # ====================================================================
        # COM IMPORT (lazy - so importing this module does not require pywin32
        # or Excel until a consolidation is actually attempted)
        # ====================================================================
        try:
            import win32com.client as win32
            import pythoncom
        except ImportError as e:
            raise RuntimeError(
                "pywin32 (win32com) is required for workbook consolidation. "
                "Install it with: pip install pywin32"
            ) from e

        excel = None
        source_wb = None
        target_wb = None
        # Initialise COM for this thread (safe to call; balanced in finally).
        pythoncom.CoInitialize()
        try:
            # ================================================================
            # LAUNCH EXCEL (hidden, non-interactive)
            # ================================================================
            excel = win32.DispatchEx("Excel.Application")  # dedicated instance
            excel.Visible = False
            excel.DisplayAlerts = False  # suppress overwrite/compat prompts

            # ================================================================
            # OPEN OR CREATE TARGET
            # ================================================================
            if os.path.exists(target_path):
                logger.info("  Opening existing target workbook")
                target_wb = excel.Workbooks.Open(target_path)
            else:
                logger.info("  Target does not exist - creating new workbook")
                target_wb = excel.Workbooks.Add()
                target_wb.SaveAs(target_path, FileFormat=_XL_FILEFORMAT_XLSX)

            # Names already present in the target (collision set).
            existing_names = {ws.Name for ws in target_wb.Worksheets}

            # ================================================================
            # OPEN SOURCE
            # ================================================================
            source_wb = excel.Workbooks.Open(source_path)

            # Resolve which source sheets to move.
            if request.sheets is None:
                sheets_to_move = [source_wb.Worksheets(1).Name]  # first tab by position
                logger.info(
                    f"  No sheets specified - using first tab: '{sheets_to_move[0]}'"
                )
            else:
                source_names = {ws.Name for ws in source_wb.Worksheets}
                missing = [s for s in request.sheets if s not in source_names]
                if missing:
                    raise ValueError(
                        f"Sheet(s) not found in source '{os.path.basename(source_path)}': {missing}. "
                        f"Available: {sorted(source_names)}"
                    )
                sheets_to_move = list(request.sheets)

            # ================================================================
            # COPY EACH SELECTED TAB INTO THE TARGET
            # ================================================================
            for sheet_name in sheets_to_move:
                src_ws = source_wb.Worksheets(sheet_name)

                # Copy AFTER the target's current last sheet so order is preserved.
                last_index = target_wb.Worksheets.Count
                src_ws.Copy(After=target_wb.Worksheets(last_index))

                # The copy lands as the new active sheet; rename if it collides.
                new_ws = target_wb.ActiveSheet
                final_name = _unique_sheet_name(sheet_name, existing_names)
                if final_name != new_ws.Name:
                    new_ws.Name = final_name
                if final_name != sheet_name:
                    logger.info(
                        f"  Copied '{sheet_name}' -> '{final_name}' (renamed to avoid collision)"
                    )
                else:
                    logger.info(f"  Copied '{sheet_name}'")
                existing_names.add(final_name)

            # ================================================================
            # SAVE TARGET (always .xlsx)
            # ================================================================
            target_wb.SaveAs(target_path, FileFormat=_XL_FILEFORMAT_XLSX)
            logger.info(f"  Saved consolidated workbook: {target_path}")

        except Exception as e:
            # Surface a clear, single failure; ProcessLogger logs the timing/trace.
            raise RuntimeError(f"Workbook consolidation failed: {e}") from e

        finally:
            # ================================================================
            # CLEANUP - close workbooks without saving (target already saved),
            # quit Excel, release COM. Orphaned EXCEL.EXE is the classic COM
            # failure on RPA boxes, so each step is best-effort and independent.
            # ================================================================
            if source_wb is not None:
                try:
                    source_wb.Close(SaveChanges=False)
                except Exception as e:
                    logger.warning(f"  Could not close source workbook: {e}")
            if target_wb is not None:
                try:
                    target_wb.Close(SaveChanges=False)
                except Exception as e:
                    logger.warning(f"  Could not close target workbook: {e}")
            if excel is not None:
                try:
                    excel.Quit()
                except Exception as e:
                    logger.warning(f"  Could not quit Excel: {e}")
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
