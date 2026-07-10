"""
====================================================================================
CONSUMER — XERO REPORT CONSOLIDATION ROBOT (Mode 3, one item per client)
====================================================================================

This is the robot's ``ProcessDataFunction``: it processes ONE client per queue item.
The firm's producer fills a single queue with one record per client, carrying the
non-negotiable fields:

    Client name, ABN, from_period, to_period      (DD/MM/YYYY, delimiter may vary)

The item is a queue envelope: the payload lives under ``transaction_item["data_fields"]``.
We read business fields from there, and we also use it
to persist a checkpoint so a retry resumes at the failed stage rather than redoing work.

STAGED PIPELINE (checkpoint = data_fields["last_step"], guarded by `if step < N`):
    STAGE 0  validate            always runs, no checkpoint (cheap; must re-verify)
    STAGE 1  select client        skip if step >= 1
    STAGE 2  export Xero reports   skip if step >= 2   (empty period -> WARNING)
    STAGE 3  consolidate (Excel)   skip if step >= 3   (fresh target each attempt)
    STAGE 4  deliver to target     skip if step >= 4   (via file-sink seam)
    FINALISE confirm + cleanup, return success ONLY when the delivered file exists

FAILURE CLASSIFICATION (the two-exception-worlds rule, guide §15.1):
    Bad/mis-shaped data, client-not-found, empty-period  -> RPABusinessException (warning)
    Login/nav/download/timeout/browser/COM/IO failures    -> RPASystemException (retry)
    iaa_rpa_utils library exceptions are CAUGHT and TRANSLATED to the framework's two.

WHAT IS STUBBED:
    The actual Xero client-selection and report-export calls (iaa_rpa_xero) are marked
    with `TODO(xero)`. Everything around them — validation, checkpointing, exception
    translation, consolidation, delivery, finalise — is complete.

WHERE ATO / SHAREPOINT PLUG IN LATER (unchanged by this file's structure):
    - ATO becomes a new stage between STAGE 2 and STAGE 3 (export ATO -> temp), its
      files joining what STAGE 4 delivers; renumber the checkpoints and insert.
    - SharePoint becomes a second implementation of the file-sink seam used in STAGE 4;
      this module does not change.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ====================================================================================
# IAA FRAMEWORK IMPORTS
# ====================================================================================
from iaa_rpa_framework.config import Config
from iaa_rpa_framework import RPABusinessException, RPASystemException

# ====================================================================================
# IAA UTILS IMPORTS
# ====================================================================================
from iaa_rpa_utils import setup_logger, ProcessLogger
from iaa_rpa_utils.strfunctions import digits_only, mask_sensitive_id
from iaa_rpa_utils.id_parser import parse_client_id
from iaa_rpa_utils.exceptions import (
    DataValidationError,
    WebAutomationError,
    LoginError,
    NavigationError,
    ElementNotFoundError,
    DownloadError,
    BrowserError,
    TimeoutError as RPATimeoutError,
)
from iaa_rpa_utils.helpers import take_error_screenshot

# ====================================================================================
# APPLICATION MANAGER + CONSOLIDATION MODULE
# ====================================================================================
from application_manager import ensure_browser_session
from consolidate_workbooks import WorkbookConsolidationRequest, consolidate_workbook
from xero_processing import _select_xero_client, _export_xero_reports

# ====================================================================================
# MODULE SETUP
# ====================================================================================
logger = setup_logger(__name__)

# Exceptions from the browser / Xero libraries that mean "transient automation
# failure" -> translate to RPASystemException (retry). DataValidationError is handled
# separately because it means "bad data" -> RPABusinessException (warning).
_SYSTEM_LIBRARY_EXCEPTIONS = (
    WebAutomationError,  # base for Login/Logout/Navigation/Element/Browser/Download...
    LoginError,
    NavigationError,
    ElementNotFoundError,
    DownloadError,
    BrowserError,
    RPATimeoutError,
)


# ====================================================================================
# data_fields ENVELOPE + CHECKPOINT HELPERS
# ====================================================================================
def _data_fields(transaction_item: Dict[str, Any]) -> Dict[str, Any]:
    """Return the payload dict from the queue envelope.

    In queue mode the framework hands us the whole item; our fields live under
    ``data_fields``. A missing/!dict envelope is a malformed item -> system error.
    """
    df = transaction_item.get("data_fields")
    if not isinstance(df, dict):
        raise RPASystemException(
            "Queue item has no usable 'data_fields' payload", transaction_item
        )
    return df


def _checkpoint(data: Dict[str, Any]) -> int:
    """Read the last successfully-completed stage number (0 if none)."""
    try:
        return int(data.get("last_step", 0))
    except (TypeError, ValueError):
        return 0


def _set_checkpoint(
    transaction_item: Dict[str, Any], data: Dict[str, Any], step: int
) -> None:
    """Record that ``step`` completed, and reattach data_fields so it persists.

    Only ``data_fields`` survives a retry, so the checkpoint (and anything a later
    stage needs) must live in ``data`` and be reattached to the envelope.
    """
    data["last_step"] = step
    transaction_item["data_fields"] = data


# ====================================================================================
# STAGE 0 — VALIDATE  (always runs; no checkpoint)
# ====================================================================================
def _parse_period(value: str) -> date:
    """Parse a DD/MM/YYYY date, day-first, tolerating . - / space delimiters.

    Raises DataValidationError (never a US month-first misread) on anything else.
    """
    raw = str(value or "").strip()
    if not raw:
        raise DataValidationError("Period value is empty")
    # Collapse any run of separators/spaces into a single '/'
    normalised = re.sub(r"[.\-\s]+", "/", raw.strip())
    try:
        return datetime.strptime(normalised, "%d/%m/%Y").date()
    except ValueError:
        raise DataValidationError(
            f"Period '{raw}' is not a valid DD/MM/YYYY date"
        ) from None


def _resolve_abn(raw_abn: str) -> Tuple[str, str]:
    """Accept the ABN field either prefixed ('ABN 5182...') or as bare digits.

    Returns (number, id_type). Tries the prefixed parser first; on its
    DataValidationError, falls back to bare digits and infers the type by length
    (11 digits = ABN, 8-9 = TFN). Raises DataValidationError if neither works.
    """
    candidate = str(raw_abn or "").strip()
    if not candidate:
        raise DataValidationError("ABN/identifier is empty")

    # First: try the prefixed form ("ABN 123...", "TFN 123...", case-insensitive).
    # parse_client_id has NO defaults for these two args, so pass them explicitly.
    try:
        number, id_type = parse_client_id(
            candidate, visible_digits=4, mask_position="start"
        )
        return number, id_type
    except DataValidationError:
        pass  # not prefixed — fall back to bare digits

    number = digits_only(candidate)
    if len(number) == 11:
        return number, "ABN"
    if len(number) in (8, 9):
        return number, "TFN"
    raise DataValidationError(
        f"Identifier '{mask_sensitive_id(candidate)}' is not a recognised ABN/TFN "
        f"(expected prefixed 'ABN/TFN <n>' or 11-digit ABN / 8-9 digit TFN)"
    )


def _check_bas_mode(value):
    """Validate and normalise the BAS running mode.

    Accepts 'quarterly' or 'year-end' (case-insensitive), returning the value
    lower-cased so downstream comparisons are exact.

    Raises:
        DataValidationError: if the value is empty or not one of the two allowed
            modes.
    """
    raw = str(value or "").strip().lower()
    if not raw:
        raise DataValidationError("Running mode value is empty")
    if raw not in ("quarterly", "year-end"):
        raise DataValidationError(
            f"Running mode value error, expected 'quarterly' or 'year-end', received '{raw}'"
        )
    return raw


def _validate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the queue record and return a normalised working dict.

    Raises RPABusinessException on any bad field (warning; retry won't help).
    """
    client_name = str(data.get("Client name") or data.get("client_name") or "").strip()
    raw_abn = data.get("ABN") or data.get("abn") or ""
    raw_from = data.get("from_period") or data.get("From period") or ""
    raw_to = data.get("to_period") or data.get("To period") or ""
    raw_bas_mode = data.get("BAS_mode") or data.get("bas_mode") or ""

    if not client_name:
        raise RPABusinessException("Missing required field: Client name")

    try:
        abn_number, abn_type = _resolve_abn(raw_abn)
        from_dt = _parse_period(raw_from)
        to_dt = _parse_period(raw_to)
        bas_mode = _check_bas_mode(raw_bas_mode)
    except DataValidationError as exc:
        # Bad data — a human must fix the queue record. Warning, not retry.
        raise RPABusinessException(str(exc)) from exc

    if from_dt > to_dt:
        raise RPABusinessException(
            f"from_period ({from_dt:%d/%m/%Y}) is after to_period ({to_dt:%d/%m/%Y})"
        )

    logger.info(
        "Validated client '%s' [%s %s], period %s -> %s",
        client_name,
        abn_type,
        mask_sensitive_id(abn_number),
        f"{from_dt:%d/%m/%Y}",
        f"{to_dt:%d/%m/%Y}",
    )

    return {
        "client_name": client_name,
        "abn_number": abn_number,
        "abn_type": abn_type,
        "from_dt": from_dt,  # converted to date object
        "to_dt": to_dt,  # converted to date object
        "bas_mode": bas_mode, 
    }


# ====================================================================================
# PER-ITEM TEMP DIR + DELIVERY (file-sink seam)
# ====================================================================================
def _item_work_dir(abn_number: str) -> str:
    """A unique temp dir for this client+run, so files never collide across items."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(tempfile.gettempdir(), "xero_robot", f"{abn_number}_{stamp}")
    os.makedirs(path, exist_ok=True)
    return path


def _consolidated_filename(vals: Dict[str, Any]) -> str:
    """Deterministic output name from client + period, so a re-run overwrites cleanly."""
    safe_client = "".join(
        c for c in vals["client_name"] if c.isalnum() or c in " _-"
    ).strip()
    # safe_client = safe_client.replace(" ", "_") or vals["abn_number"] # not required
    # return (
    #     f"{safe_client}_{vals['abn_number']}_"
    #     f"{vals['from_dt']:%Y%m%d}-{vals['to_dt']:%Y%m%d}.xlsx"
    # )
    return f"{safe_client}.xlsx"


def _create_temp_workdir(working_dir: str) -> str:
    """Create a timestamped subdirectory inside working_dir.

    The subdirectory name is the current local time formatted as
    DDMMYYYYHHMMSS. The directory (and any missing parents) is created
    on the filesystem.

    Args:
        working_dir: Path to the parent working directory.

    Returns:
        The absolute path to the newly created subdirectory as a str.
    """
    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    return _create_dir(working_dir, timestamp)

def _create_dir(dir: str, subdir: str | None = None) -> str:
    """Create a directory, including any missing parent directories.

    If the directory already exists, it is left unchanged (no error is
    raised).

    Args:
        dir: Path to the directory to create.
        subdir: Optional subdirectory name to append to dir. If given,
            the created directory is dir/subdir.

    Returns:
        The absolute path to the directory as a str.
    """
    if subdir:
        target = Path(dir) / subdir
    else:
        target = Path(dir)

    target.mkdir(parents=True, exist_ok=True)
    return str(target.resolve())

def _deliver_file(local_path: str, dest_name: str) -> str:
    """FILE-SINK SEAM. Put a local file at the delivery destination and return where.

    Current implementation: copy into a target folder (config 'TargetFolder'). Later,
    SharePoint/Graph becomes a second implementation of this same seam — the pipeline
    calls _deliver_file and does not care which sink is behind it.

    Raises RPASystemException on IO failure (transient). A missing target FOLDER is a
    business problem (someone must create it) once SharePoint is in play; for the
    local-folder impl we create it.
    """
    target_folder = Config.get("TargetFolder", "outputs/delivered")
    try:
        os.makedirs(target_folder, exist_ok=True)
        dest_path = os.path.join(target_folder, dest_name)
        shutil.copy2(local_path, dest_path)  # overwrite cleanly on re-run
        logger.info("Delivered file to: %s", dest_path)
        return dest_path
    except OSError as exc:
        raise RPASystemException(
            f"Failed to deliver file to {target_folder}: {exc}"
        ) from exc


# ====================================================================================
# STAGE 1 & 2 — located in xero_processing.py
# ====================================================================================


# ====================================================================================
# STAGE 3 — CONSOLIDATE (Excel COM, via the provided module)
# ====================================================================================
def _consolidate(report_paths: List[str], target_path: str) -> None:
    """Consolidate all exported report tabs into one workbook at target_path.

    Idempotent per attempt: we DELETE any partial target left by a failed prior
    attempt before building, so a retry starts from a clean file and never appends
    duplicate '_copy(N)' tabs onto half-built output.

    The consolidation module raises FileNotFoundError / ValueError / RuntimeError.
    We translate: a missing source or bad sheet name is data-ish but here indicates a
    broken export (the files were just produced), so treat all consolidation failures
    as SYSTEM (retry) — a fresh re-export + rebuild is the right recovery. (COM errors
    are RuntimeError and are clearly system.)
    """
    # Fresh target each attempt (data hygiene lives here, NOT in the kill hook).
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
        except OSError as exc:
            raise RPASystemException(
                f"Could not clear partial target {target_path}: {exc}"
            ) from exc

    try:
        for source_path in report_paths:
            # sheets=None -> the source's first tab; adjust if a report has many tabs.
            consolidate_workbook(
                WorkbookConsolidationRequest(
                    source_path=source_path, target_path=target_path
                )
            )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise RPASystemException(f"Consolidation failed: {exc}") from exc


# ====================================================================================
# THE PROCESS FUNCTION (ProcessDataFunction)
# ====================================================================================
def process_client(transaction_item: Dict[str, Any], agent) -> Dict[str, Any]:
    """Process one client end-to-end: validate -> select -> export -> consolidate ->
    deliver. Returns the item on success; raises to signal warning/retry.

    Re-entrant: a retry resumes at the first incomplete stage via data_fields["last_step"].
    """
    with ProcessLogger("Process Client", logger):
        data = _data_fields(transaction_item)
        step = _checkpoint(data)

        # STAGE 0 — validate (always; cheap; catches bad records before any browser work)
        vals = _validate(data)
        browser = ensure_browser_session(agent)  # heal the shared session if it died

        # Recover per-item scratch paths across a retry (they live in data_fields).
        xero_work_dir = Config.get("WorkingDirectoryXero")
        work_dir = data.get("work_dir") or _create_temp_workdir(xero_work_dir)
        data["work_dir"] = work_dir
        vals["work_dir"] = work_dir

        screenshot_dir = data.get("screenshot_dir") or _create_dir(data["work_dir"], "screenshots")
        data["screenshot_dir"] = screenshot_dir
        vals["screenshot_dir"] = screenshot_dir

        #TODO: not sure about consolidated name
        target_path = os.path.join(work_dir, _consolidated_filename(vals))

        try:
            # STAGE 1 — select client
            if step < 1:
                _select_xero_client(browser, vals)
                _set_checkpoint(transaction_item, data, 1)

            # STAGE 2 — export Xero reports
            if step < 2:
                # The report-config tables were fetched once in init and keyed by
                # clean report name. _export_reports owns all per-report dispatch,
                # request-building, and per-report exception translation.
                report_tables = (getattr(agent, "initialised_apps", None) or {}).get(
                    "report_tables", {}
                )
                report_paths = _export_xero_reports(browser, vals, report_tables)
                data["report_paths"] = report_paths
                _set_checkpoint(transaction_item, data, 2)


            # STAGE 3 — consolidate (fresh target each attempt)
            if step < 3:
                report_paths = data.get("report_paths", [])
                if not report_paths:
                    # Should not happen if stage 2 checkpointed; defensive.
                    raise RPASystemException("No exported reports to consolidate")
                _consolidate(report_paths, target_path)
                _set_checkpoint(transaction_item, data, 3)

            # STAGE 4 — deliver via the file-sink seam
            # if step < 4:
            #     dest = _deliver_file(target_path, _consolidated_filename(vals))
            #     data["delivered_path"] = dest
            #     _set_checkpoint(transaction_item, data, 4)

        except RPABusinessException:
            raise  # already classified — warning
        except RPASystemException:
            _screenshot(browser, "system")
            raise  # already classified — retry
        except DataValidationError as exc:
            raise RPABusinessException(str(exc)) from exc
        except _SYSTEM_LIBRARY_EXCEPTIONS as exc:
            _screenshot(browser, "system")
            raise RPASystemException(f"Xero interaction failed: {exc}") from exc

        # FINALISE — confirm the delivered file truly exists before claiming success.
        # dest = data.get("delivered_path")
        # if not dest or not os.path.exists(dest):
        #     raise RPASystemException(
        #         "Delivery could not be confirmed (file not found at destination)"
        #     )

        # _cleanup_temp(work_dir)
        transaction_item["data_fields"] = data
        logger.info("Client '%s' completed successfully", vals["client_name"])
        return transaction_item


# ====================================================================================
# SMALL HELPERS
# ====================================================================================
def _screenshot(browser: Any, error_type: str) -> None:
    """Best-effort diagnostic screenshot; never raises."""
    try:
        take_error_screenshot(
            error_type=error_type,
            browser=browser,
            screenshot_folder=Config.get("ScreenshotFolder", "outputs/screenshots"),
        )
    except Exception as exc:
        logger.debug("Screenshot skipped: %s", exc)


def _cleanup_temp(work_dir: Optional[str]) -> None:
    """Best-effort removal of the per-item temp dir; never raises."""
    if work_dir and os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception as exc:
            logger.debug("Temp cleanup skipped for %s: %s", work_dir, exc)
