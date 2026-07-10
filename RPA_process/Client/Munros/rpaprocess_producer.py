"""
Producer — Munros Client
=========================
Reads Excel 1 (master client list) and pushes one queue item per row.
All family-member grouping and sorting is handled by the consumer.

Excel 1 — Master client list  (config key: MC.CFG_MASTER_EXCEL_PATH)
    Columns: Client Name, ABN, Financial Year, PMS

Producer steps (per record):
    1. Validate required fields (MC.EXCEL1_REQUIRED)
    2. Validate PMS is one of MC.PMS_VALUES ("XPM" or "MYOB")
    3. Push payload {clientName, abn, financialYear, pms} to the queue
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from iaa_rpa_framework import Config, RPABusinessException, RPASystemException
from RPA_process.Client.Munros.workpaper_utility import (
    read_excel,
    validate_headers,
    normalise_abn,
)
from RPA_process.Client.Munros import munros_constants as MC

logger = logging.getLogger("IARPA." + __name__)


def _safe_item_name(*parts: str) -> str:
    """Build a queue item name from parts, stripping characters illegal in orchestrator item names."""
    raw = "_".join(str(p or "").strip() for p in parts if str(p or "").strip())
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return safe[:180] or "munros_record"


# ---------------------------------------------------------------------------
# Public producer functions (wired via config hooks)
# ---------------------------------------------------------------------------


def get_munros_source_records(state_machine) -> List[Dict[str, Any]]:
    """Get Data Function (Producer).

    Reads Excel 1 and returns one record per row.

    Config keys:
        MC.CFG_MASTER_EXCEL_PATH  — full path to Excel 1
        MC.CFG_MASTER_SHEET_NAME  — (optional) sheet name in Excel 1
    """
    logger.info("=" * 80)
    logger.info("MUNROS PRODUCER - GET SOURCE RECORDS")
    logger.info("=" * 80)

    try:
        master_path = Path(Config.get(MC.CFG_MASTER_EXCEL_PATH, ""))
        if not master_path.is_file():
            raise RPASystemException(f"Master Excel (Excel 1) not found: {master_path}")

        records = read_excel(master_path, Config.get(MC.CFG_MASTER_SHEET_NAME) or None)
        validate_headers(records, MC.EXCEL1_REQUIRED, "Excel 1 (master)")
        logger.info("Excel 1 records loaded: %s", len(records))
        return records

    except RPASystemException:
        raise
    except Exception as exc:
        raise RPASystemException(f"Producer failed reading Excel 1: {exc}") from exc


def process_munros_record_to_queue(
    transaction_item: Dict[str, Any], state_machine
) -> Dict[str, Any]:
    """Process Data Function (Producer).

    Validates one Excel 1 row and pushes it to the queue.
    """
    logger.info("=" * 80)
    logger.info("MUNROS PRODUCER - PUSH RECORD TO QUEUE")
    logger.info("=" * 80)

    try:
        missing = [
            f
            for f in MC.EXCEL1_REQUIRED
            if not str(transaction_item.get(f, "") or "").strip()
        ]
        if missing:
            raise RPABusinessException(
                f"Record missing required field(s): {', '.join(missing)}"
            )

        abn = normalise_abn(transaction_item.get(MC.COL_ABN, ""))
        client_name = str(transaction_item.get(MC.COL_CLIENT_NAME, "")).strip()
        financial_year = str(transaction_item.get(MC.COL_FINANCIAL_YEAR, "")).strip()
        pms = str(transaction_item.get(MC.COL_PMS, "")).strip().upper()

        if pms not in MC.PMS_VALUES:
            raise RPABusinessException(
                f"Invalid PMS value '{pms}' for '{client_name}' — must be {MC.PMS_XPM} or {MC.PMS_MYOB}."
            )

        payload = {
            MC.QUEUE_CLIENT_NAME: client_name,
            MC.QUEUE_ABN: abn,
            MC.QUEUE_FINANCIAL_YEAR: financial_year,
            MC.QUEUE_PMS: pms,
        }

        item_name = _safe_item_name(abn, financial_year)
        logger.info("Pushing queue item: %s  (%s)", item_name, client_name)

        queue_result = state_machine.push_item_to_queue(item_name, payload)
        if queue_result is None:
            raise RPASystemException(f"Queue push returned None for item: {item_name}")

        transaction_item["status"] = "success"
        transaction_item["comment"] = f"Queued: {item_name}"
        return transaction_item

    except RPABusinessException:
        transaction_item["status"] = "warning"
        transaction_item["comment"] = "Business validation failed in producer"
        raise
    except RPASystemException:
        transaction_item["status"] = "failed"
        transaction_item["comment"] = "System failure in producer queue push"
        raise
    except Exception as exc:
        transaction_item["status"] = "failed"
        transaction_item["comment"] = f"Unexpected producer error: {exc}"
        raise RPASystemException(
            f"Unexpected producer error: {exc}", transaction_item
        ) from exc


def end_process_producer(state_machine) -> None:
    """End Process Function (Producer) — log a run summary."""
    data = state_machine.transaction_data or []
    success = sum(1 for r in data if r.get("status") == "success")
    warning = sum(1 for r in data if r.get("status") == "warning")
    failed = len(data) - success - warning

    logger.info("=" * 80)
    logger.info("MUNROS PRODUCER - END PROCESS")
    logger.info(
        "Total=%s  Success=%s  Warning=%s  Failed=%s",
        len(data),
        success,
        warning,
        failed,
    )
    logger.info("=" * 80)
