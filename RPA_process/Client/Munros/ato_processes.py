"""
ATO Processes — Munros Client
================================
Single public entry point: run_ato_steps()

Called by the consumer for every family member after the PMS step
(XPM or MYOB) completes.

Downloads ATO reports for the member and saves them as JSON files
into the member output folder (already created by the PMS step).

Reports downloaded (all TODO — placeholders in place):
    1.  ATO BAS  — Business Activity Statement
    2.  ATO ITA  — Income Tax Account
    3.  ATO ICA  — Integrated Client Account
    4.  ATO FBT  — Fringe Benefits Tax
    5.  ATO SGC  — Superannuation Guarantee Charge
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaa_rpa_framework import Config

from RPA_process.Client.Munros.workpaper_utility import (
    build_member_folder_path,
    ensure_folder,
    report_filename as _resolve_report_filename,
    financial_year_dates,
)
from RPA_process.Client.Munros import munros_constants as MC

logger = logging.getLogger("IARPA." + __name__)

# Local alias — ATO reports are JSON, not Excel.
_EXTENSION = MC.ATO_REPORT_EXTENSION


# ---------------------------------------------------------------------------
# Private report download helpers
# (placeholder — implement as ATO API / source is confirmed)
# ---------------------------------------------------------------------------


def _dl_bas(
    client_name: str,
    fy: str,
    start_date: str,
    end_date: str,
    folder: Path,
    filename: str,
) -> Optional[Path]:
    """TODO: implement ATO Business Activity Statement download."""
    output_path = folder / f"{filename}{_EXTENSION}"
    logger.info(
        "    [ATO] BAS — TODO: implement (client=%s, fy=%s, %s→%s, file=%s)",
        client_name,
        fy,
        start_date,
        end_date,
        output_path.name,
    )
    return None


def _dl_ita(
    client_name: str,
    fy: str,
    start_date: str,
    end_date: str,
    folder: Path,
    filename: str,
) -> Optional[Path]:
    """TODO: implement ATO Income Tax Account download."""
    output_path = folder / f"{filename}{_EXTENSION}"
    logger.info(
        "    [ATO] ITA — TODO: implement (client=%s, fy=%s, %s→%s, file=%s)",
        client_name,
        fy,
        start_date,
        end_date,
        output_path.name,
    )
    return None


def _dl_ica(
    client_name: str,
    fy: str,
    start_date: str,
    end_date: str,
    folder: Path,
    filename: str,
) -> Optional[Path]:
    """TODO: implement ATO Integrated Client Account download."""
    output_path = folder / f"{filename}{_EXTENSION}"
    logger.info(
        "    [ATO] ICA — TODO: implement (client=%s, fy=%s, %s→%s, file=%s)",
        client_name,
        fy,
        start_date,
        end_date,
        output_path.name,
    )
    return None


def _dl_fbt(
    client_name: str,
    fy: str,
    start_date: str,
    end_date: str,
    folder: Path,
    filename: str,
) -> Optional[Path]:
    """TODO: implement ATO Fringe Benefits Tax download."""
    output_path = folder / f"{filename}{_EXTENSION}"
    logger.info(
        "    [ATO] FBT — TODO: implement (client=%s, fy=%s, %s→%s, file=%s)",
        client_name,
        fy,
        start_date,
        end_date,
        output_path.name,
    )
    return None


def _dl_sgc(
    client_name: str,
    fy: str,
    start_date: str,
    end_date: str,
    folder: Path,
    filename: str,
) -> Optional[Path]:
    """TODO: implement ATO Superannuation Guarantee Charge download."""
    output_path = folder / f"{filename}{_EXTENSION}"
    logger.info(
        "    [ATO] SGC — TODO: implement (client=%s, fy=%s, %s→%s, file=%s)",
        client_name,
        fy,
        start_date,
        end_date,
        output_path.name,
    )
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_ato_steps(
    member: Dict[str, Any],
    group_data: Dict[str, Any],
    sm,
) -> Dict[str, Any]:
    """Download all ATO reports for one family member and save as JSON into the member folder.

    Called by the consumer after the PMS step (XPM or MYOB) completes.
    The member output folder is already created by the PMS step — this
    function adds the ATO JSON files alongside the financial reports.

    Args:
        member:     Combined member record (Client Code, Client Name, TFN, ABN, etc.).
        group_data: Queue payload (abn, financialYear, pms).
        sm:         State machine instance.

    Returns:
        Dict with keys: folder_path, downloaded, skipped, report_paths, status, comment.
    """
    client_code = str(member.get("Client Code", "") or "").strip()
    client_name = str(member.get("Client Name", "") or "").strip()
    fy = str(group_data.get("financialYear", "") or "").strip()

    # group_members is needed to resolve the folder path — pull from member's embedded reference
    # if the consumer didn't pass it separately.  Fall back to a single-member list.
    group_members: List[Dict[str, Any]] = group_data.get("_group_members", [member])

    # sm will be passed to _dl_* functions once they have API/browser implementations.
    browser = (getattr(sm, "initialised_apps", {}) or {}).get("browser")

    start_date, end_date = financial_year_dates(fy)
    logger.info(
        "    [ATO] Starting ATO report downloads for %s (%s)  FY=%s  (%s → %s)  browser=%s",
        client_code,
        client_name,
        fy,
        start_date,
        end_date,
        "ready" if browser else "none",
    )

    result: Dict[str, Any] = {
        "folder_path": "",
        "downloaded": [],  # report names successfully downloaded
        "skipped": [],  # report names skipped or failed
        "report_paths": {},  # {report_name: str(file_path)} for each downloaded report
        "status": "success",
        "comment": "",
    }

    # Re-use the existing member folder created by the PMS step.
    try:
        folder = build_member_folder_path(member, group_members, group_data)
        ensure_folder(folder)
        logger.info("    [ATO] Member folder: %s", folder)
        result["folder_path"] = str(folder)
    except Exception as exc:
        result.update(status="failed", comment=f"Folder resolution failed: {exc}")
        logger.error("    [ATO] Folder resolution failed: %s", exc)
        return result

    # fn: resolves filename from config with {fy} substituted.
    def fn(key: str, default: str) -> str:
        return _resolve_report_filename(key, default, fy)

    # _track: records the downloaded file path on success, or the report name in skipped on failure.
    def _track(path: Optional[Path], name: str) -> None:
        if path is not None:
            result["downloaded"].append(name)
            result["report_paths"][name] = str(path)
        else:
            result["skipped"].append(name)

    _track(
        _dl_bas(
            client_name,
            fy,
            start_date,
            end_date,
            folder,
            fn(MC.CFG_ATO_REPORT_BAS, MC.DEFAULT_ATO_BAS),
        ),
        MC.REPORT_ATO_BAS,
    )
    _track(
        _dl_ita(
            client_name,
            fy,
            start_date,
            end_date,
            folder,
            fn(MC.CFG_ATO_REPORT_ITA, MC.DEFAULT_ATO_ITA),
        ),
        MC.REPORT_ATO_ITA,
    )
    _track(
        _dl_ica(
            client_name,
            fy,
            start_date,
            end_date,
            folder,
            fn(MC.CFG_ATO_REPORT_ICA, MC.DEFAULT_ATO_ICA),
        ),
        MC.REPORT_ATO_ICA,
    )
    _track(
        _dl_fbt(
            client_name,
            fy,
            start_date,
            end_date,
            folder,
            fn(MC.CFG_ATO_REPORT_FBT, MC.DEFAULT_ATO_FBT),
        ),
        MC.REPORT_ATO_FBT,
    )
    _track(
        _dl_sgc(
            client_name,
            fy,
            start_date,
            end_date,
            folder,
            fn(MC.CFG_ATO_REPORT_SGC, MC.DEFAULT_ATO_SGC),
        ),
        MC.REPORT_ATO_SGC,
    )

    n_ok, n_skip = len(result["downloaded"]), len(result["skipped"])
    result["status"] = (
        "success" if n_skip == 0 else ("partial" if n_ok > 0 else "failed")
    )
    result["comment"] = (
        f"ATO reports: {n_ok} downloaded, {n_skip} skipped — folder: {folder.name}"
    )
    logger.info("    [ATO] Reports complete — %s downloaded, %s skipped", n_ok, n_skip)
    if result["skipped"]:
        logger.info("    [ATO] Skipped: %s", result["skipped"])
    return result
