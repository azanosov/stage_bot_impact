"""
Consumer — Munros Client
=========================
Processes one queue item at a time. Each queue item represents one Excel 1
row (a family group identified by ABN + Financial Year).

For each item the consumer:
    1.  Reads the queue payload  (clientName, abn, financialYear, pms)
    2.  Reads Excel 2 from disk and finds all family members by ABN
    3.  Sorts members  (oldest male first, then by age)
    4.  Assigns Order numbers
    5.  Loops through each member and runs per-member processing
    6.  Writes final queue status for the whole group

Per-member processing (Step 5) has two stages:
    Stage A — PMS routing:  XPM → xero_processes.run_xpm_steps()
                            MYOB → myob_processes.run_myob_steps()
    Stage B — ATO ops (common to both): ato_processes.run_ato_steps()
    TODO: implement each sub-step as the Munros process map is confirmed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from iaa_rpa_framework import Config, RPABusinessException, RPASystemException

from RPA_process.Client.Munros.workpaper_utility import (
    read_excel,
    validate_headers,
    normalise_abn,
    build_abn_index,
    determine_parent_code,
    collect_group_members,
    build_combined_records,
)
from RPA_process.Client.Munros import munros_constants as MC

logger = logging.getLogger("IARPA." + __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_get_data(transaction_item: Dict[str, Any]) -> Dict[str, Any]:
    """Return the mutable queue payload regardless of wrapper shape."""
    if isinstance(transaction_item.get("data_fields"), dict):
        return transaction_item["data_fields"]
    return transaction_item


def _queue_value(data: Dict[str, Any], key: str, default: Any = "") -> Any:
    return data[key] if key in data and data[key] not in (None, "") else default


def _add_note(data: Dict[str, Any], note: str) -> None:
    data.setdefault("process_notes", [])
    data["process_notes"].append(note)
    logger.info(note)


def _get_browser(sm) -> Any:
    return (getattr(sm, "initialised_apps", {}) or {}).get("browser")


def _get_myob_connection(sm) -> Any:
    """Return the MYOB connection object from initialised_apps (used by myob_processes steps)."""
    return (getattr(sm, "initialised_apps", {}) or {}).get("myob_connection")


# ---------------------------------------------------------------------------
# Excel 2 reader (Option A — read fresh per queue item)
# ---------------------------------------------------------------------------


def _read_details_excel() -> List[Dict[str, Any]]:
    """Read Excel 2 (client entity details) from the path in config.

    Config keys:
        MC.CFG_DETAILS_EXCEL_PATH  — full path to Excel 2
        MC.CFG_DETAILS_SHEET_NAME  — (optional) sheet name
    """
    details_path = Path(Config.get(MC.CFG_DETAILS_EXCEL_PATH, ""))
    if not details_path.is_file():
        raise RPASystemException(f"Details Excel (Excel 2) not found: {details_path}")

    records = read_excel(details_path, Config.get(MC.CFG_DETAILS_SHEET_NAME) or None)
    validate_headers(records, MC.EXCEL2_REQUIRED, "Excel 2 (details)")
    return records


# ---------------------------------------------------------------------------
# Per-member processing (placeholder — implement per process map)
# ---------------------------------------------------------------------------


def _process_member_xpm(
    member: Dict[str, Any],
    group_members: List[Dict[str, Any]],
    group_data: Dict[str, Any],
    sm,
) -> Dict[str, Any]:
    """Delegate to xero_processes.run_xpm_steps (report download + Xero PM steps)."""
    from RPA_process.Client.Munros.xero_processes import run_xpm_steps

    return run_xpm_steps(member, group_members, group_data, sm)


def _process_member_myob(
    member: Dict[str, Any],
    group_members: List[Dict[str, Any]],
    group_data: Dict[str, Any],
    sm,
) -> Dict[str, Any]:
    """Delegate to myob_processes.run_myob_steps (report download + MYOB Web/API steps)."""
    from RPA_process.Client.Munros.myob_processes import run_myob_steps

    return run_myob_steps(member, group_members, group_data, sm)


def _process_member_ato(
    member: Dict[str, Any],
    group_data: Dict[str, Any],
    sm,
) -> Dict[str, Any]:
    """Delegate to ato_processes.run_ato_steps."""
    from RPA_process.Client.Munros.ato_processes import run_ato_steps

    return run_ato_steps(member, group_data, sm)


def _process_member(
    member: Dict[str, Any],
    group_members: List[Dict[str, Any]],
    group_data: Dict[str, Any],
    pms: str,
    sm,
) -> Dict[str, Any]:
    """Process a single family member.

    Steps:
        A. PMS-specific processing (XPM → xero_processes, MYOB → myob_processes)
           Includes report download + member output folder creation.
        B. ATO operations (common to both PMS types): ato_processes

    Args:
        member:        Combined record (Client Name, Client Code, Order, TFN, etc.).
        group_members: Full sorted combined list for this group (for folder path).
        group_data:    Queue payload (abn, financialYear, pms, etc.).
        pms:           "XPM" or "MYOB".
        sm:            State machine instance.

    Returns:
        Dict with keys: client_code, order, status, comment, notes,
                        report_result, ato_result.
    """
    client_code = member.get("Client Code", "")
    order = member.get("Order", "")
    client_name = member.get("Client Name", "")
    notes: List[str] = []

    logger.info("-" * 60)
    logger.info(
        "  Member Order=%-2s  Code=%-8s  Name=%-25s  PMS=%s",
        order,
        client_code,
        client_name,
        pms,
    )
    logger.info("-" * 60)

    try:
        # Stage A — PMS routing: downloads reports, creates member folder, runs PMS-specific steps
        pms_result: Dict[str, Any] = {}
        if pms == MC.PMS_XPM:
            pms_result = _process_member_xpm(member, group_members, group_data, sm)
            notes.append(
                f"[{client_code}] XPM steps: {pms_result.get('comment') or 'complete'}"
            )
            # Log downloaded report paths for audit trail
            for report_name, report_path in pms_result.get("report_paths", {}).items():
                logger.info("  [XPM] %s → %s", report_name, report_path)
        else:
            pms_result = _process_member_myob(member, group_members, group_data, sm)
            notes.append(
                f"[{client_code}] MYOB steps: {pms_result.get('comment') or 'complete'}"
            )

        # Stage B — ATO operations (document extract, redact, file, email — runs for all PMS)
        ato_result = _process_member_ato(member, group_data, sm)
        notes.append(
            f"[{client_code}] ATO steps: {ato_result.get('comment') or 'complete'}"
        )

        return {
            "client_code": client_code,
            "order": order,
            "status": "success",
            "comment": f"Member processed via {pms} + ATO.",
            "notes": notes,
            "pms_result": pms_result,  # contains report_paths, folder_path, downloaded, skipped
            "ato_result": ato_result,
        }

    except RPABusinessException as exc:
        return {
            "client_code": client_code,
            "order": order,
            "status": "warning",
            "comment": str(exc),
            "notes": notes,
        }

    except Exception as exc:
        return {
            "client_code": client_code,
            "order": order,
            "status": "failed",
            "comment": f"Member processing error: {exc}",
            "notes": notes,
        }


# ---------------------------------------------------------------------------
# Public consumer functions (wired via config hooks)
# ---------------------------------------------------------------------------


def process_munros_record(transaction_item: Dict[str, Any], sm) -> Dict[str, Any]:
    """Process Data Function (Consumer).

    Processes one Excel 1 group (all family members identified by ABN).

    Args:
        transaction_item: Raw queue item from the orchestrator.
        sm:               State machine instance.

    Returns:
        Mutated transaction_item with status, comment, and data_fields updated.
    """
    data = _safe_get_data(transaction_item)
    data["started_at"] = datetime.now().isoformat()

    try:
        # STEP 1 — Read queue payload
        abn = _queue_value(data, MC.QUEUE_ABN)
        client_name = _queue_value(data, MC.QUEUE_CLIENT_NAME)
        financial_year = _queue_value(data, MC.QUEUE_FINANCIAL_YEAR)
        pms = _queue_value(data, MC.QUEUE_PMS)

        logger.info("=" * 80)
        logger.info("MUNROS CONSUMER - PROCESSING QUEUE ITEM")
        logger.info("Client Name   : %s", client_name)
        logger.info("ABN           : %s", abn)
        logger.info("Financial Year: %s", financial_year)
        logger.info("PMS           : %s", pms)
        logger.info("=" * 80)

        if not abn:
            raise RPABusinessException(
                "Queue item has no ABN — cannot look up family group."
            )

        if pms not in MC.PMS_VALUES:
            raise RPABusinessException(
                f"Unknown PMS value '{pms}' for '{client_name}' — expected {MC.PMS_XPM} or {MC.PMS_MYOB}."
            )

        # STEP 2 — Read Excel 2
        logger.info("Reading Excel 2 (details)...")
        details_records = _read_details_excel()
        abn_index = build_abn_index(details_records)
        logger.info(
            "Excel 2 loaded: %s records, %s unique ABNs",
            len(details_records),
            len(abn_index),
        )

        # STEP 3 — Find matching row and determine parent code
        excel2_matches = abn_index.get(normalise_abn(abn), [])
        if not excel2_matches:
            raise RPABusinessException(
                f"ABN '{abn}' ({client_name}) not found in Excel 2. "
                "Cannot determine family group — manual action required."
            )

        matched_row = excel2_matches[0]
        parent_code = determine_parent_code(matched_row)
        logger.info(
            "Matched Excel 2 row: Client Code=%s, parent_code=%s",
            matched_row.get("Client Code"),
            parent_code,
        )

        # STEP 4 — Collect all group members
        group_members = collect_group_members(details_records, parent_code)
        logger.info("Family group size: %s member(s)", len(group_members))

        if not group_members:
            raise RPABusinessException(
                f"No group members found for parent_code='{parent_code}' (ABN={abn})."
            )

        # STEP 5 + 6 — Sort and assign Order
        combined = build_combined_records(
            group_abn=normalise_abn(abn),
            financial_year=financial_year,
            excel1_client_name=client_name,
            group_members=group_members,
        )
        _add_note(data, f"Family group built: {len(combined)} member(s) for ABN {abn}")
        for m in combined:
            logger.info(
                "  Order=%-2s  Code=%-8s  Name=%-25s  Sex=%-2s  DOB=%-12s  IsParent=%s",
                m["Order"],
                m["Client Code"],
                m["Client Name"],
                m["Sex"],
                m["Date Of Birth"],
                m["is_parent"],
            )

        # STEP 7 — Process each member
        logger.info("")
        logger.info("Processing %s member(s)...", len(combined))
        member_results: List[Dict[str, Any]] = []
        failed_members: List[str] = []

        for member in combined:
            result = _process_member(member, combined, data, pms, sm)
            member_results.append(result)
            if result["status"] == "failed":
                failed_members.append(result["client_code"])

        data["member_results"] = member_results
        logger.info("")
        logger.info("Member processing complete:")
        for r in member_results:
            logger.info(
                "  Order=%-2s  Code=%-8s  Status=%-8s  %s",
                r["order"],
                r["client_code"],
                r["status"],
                r["comment"],
            )

        # STEP 8 — Set group-level queue status
        if failed_members:
            raise RPASystemException(
                f"One or more members failed processing: {', '.join(failed_members)}"
            )

        data["item_status"] = "success"
        data["comment"] = f"All {len(combined)} member(s) processed successfully."
        data["completed_at"] = datetime.now().isoformat()
        transaction_item["data_fields"] = data
        transaction_item["status"] = "success"
        transaction_item["comment"] = data["comment"]
        transaction_item["reprocess"] = False

        logger.info("=" * 80)
        logger.info("Queue item completed: %s", data["comment"])
        logger.info("=" * 80)
        return transaction_item

    except RPABusinessException as exc:
        data["item_status"] = "warning"
        data["comment"] = str(exc)
        transaction_item["data_fields"] = data
        transaction_item["status"] = "warning"
        transaction_item["comment"] = str(exc)
        transaction_item["reprocess"] = False
        raise

    except RPASystemException as exc:
        message = str(exc.args[0]) if exc.args else str(exc)
        data["item_status"] = "failed"
        data["comment"] = message
        transaction_item["data_fields"] = data
        transaction_item["status"] = "failed"
        transaction_item["comment"] = message
        transaction_item["reprocess"] = True
        raise

    except Exception as exc:
        data["item_status"] = "failed"
        data["comment"] = f"Unexpected error: {exc}"
        transaction_item["data_fields"] = data
        transaction_item["status"] = "failed"
        transaction_item["comment"] = data["comment"]
        transaction_item["reprocess"] = True
        raise RPASystemException(
            f"Unexpected consumer error: {exc}", transaction_item
        ) from exc


def end_process_consumer(sm) -> None:
    """End Process Function (Consumer).

    TODO: send billing + summary emails via orchestrator templates.
    """
    logger.info("=" * 80)
    logger.info("MUNROS CONSUMER - END PROCESS")

    data = sm.transaction_data or []
    success = sum(
        1
        for r in data
        if str(
            (r.get("data_fields") or r).get("item_status", r.get("status", ""))
        ).lower()
        == "success"
    )
    warning = sum(
        1
        for r in data
        if str(
            (r.get("data_fields") or r).get("item_status", r.get("status", ""))
        ).lower()
        == "warning"
    )
    failed = len(data) - success - warning

    logger.info(
        "Total=%s  Success=%s  Warning=%s  Failed=%s",
        len(data),
        success,
        warning,
        failed,
    )

    # TODO: send end-of-process emails
    # sm.orchestrator.send_email_template("tmplMunrosEOPBilling_Recs", ...)

    logger.info("MUNROS CONSUMER - END PROCESS COMPLETE")
    logger.info("=" * 80)
