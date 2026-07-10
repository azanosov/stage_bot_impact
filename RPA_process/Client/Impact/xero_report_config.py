from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from iaa_rpa_utils import DataValidationError
from iaa_rpa_utils.strfunctions import str_to_bool
from iaa_rpa_xero_blue.download_activity_statement import (
    ActivityStatementRequest, StatementPeriod,
    download_activity_statement_report, statement_period)
from iaa_rpa_xero_blue.download_aged_payables_detail import (
    AgedPayablesRequest, download_aged_payables_detail_report)
from iaa_rpa_xero_blue.download_aged_receivables_detail import (
    AgedReceivablesRequest, download_aged_receivables_detail_report)
from iaa_rpa_xero_blue.download_bank_reconciliation import (
    BankReconciliationRequest, BankReconciliationMultiRequest,
    download_bank_reconciliation_report_multi_account)
from iaa_rpa_xero_blue.download_general_ledger_detail import (
    GeneralLedgerDetailRequest, download_general_ledger_detail_report)
from iaa_rpa_xero_blue.download_gst_reconciliation import (
    GstReconciliationRequest, download_gst_reconciliation_report)
from iaa_rpa_xero_blue.download_payroll_activity_summary import (
    PayrollActivitySummaryRequest, download_payroll_activity_summary_report)
from iaa_rpa_xero_blue.download_payroll_employee_summary import (
    PayrollEmployeeSummaryRequest, download_payroll_employee_summary_report)
from iaa_rpa_xero_blue.download_trial_balance import (
    TrialBalanceRequest, download_trial_balance_report)

if TYPE_CHECKING:
    from iaa_rpa_utils.browser import SeleniumBrowser


class ReportName(StrEnum):
    BANK_RECONCILIATION = "Bank Reconciliation"
    AGED_RECEIVABLES_DETAIL = "Aged Receivables Detail"
    AGED_PAYABLES_DETAIL = "Aged Payables Detail"
    GST_RECONCILIATION = "GST Reconciliation"
    GENERAL_LEDGER_DETAIL = "General Ledger Detail"
    TRIAL_BALANCE = "Trial Balance"
    ACTIVITY_STATEMENT = "Activity Statement"
    PAYROLL_EMPLOYEE_SUMMARY = "Payroll Employee Summary"
    PAYROLL_ACTIVITY_SUMMARY = "Payroll Activity Summary"

    # PROFIT_AND_LOSS = "Profit and Loss"
    # AGED_RECEIVABLES_SUMMARY = "Aged Receivables Summary"
    # AGED_PAYABLES_SUMMARY = "Aged Payables Summary"
    # ACCOUNT_TRANSACTIONS = "Account Transactions"
    # LEAVE_BALANCES = "Leave Balances"


# explicit: enum member -> config-table key (the ReportTable_<suffix> suffix)
_TABLE_KEY = {
    ReportName.BANK_RECONCILIATION: "BankReconciliation",
    ReportName.AGED_RECEIVABLES_DETAIL: "AgedReceivablesDetail",
    ReportName.AGED_PAYABLES_DETAIL: "AgedPayablesDetail",
    ReportName.GST_RECONCILIATION: "GSTReconciliation",
    ReportName.GENERAL_LEDGER_DETAIL: "GeneralLedgerDetail",
    ReportName.TRIAL_BALANCE: "TrialBalance",
    ReportName.ACTIVITY_STATEMENT: "ActivityStatement",
    ReportName.PAYROLL_EMPLOYEE_SUMMARY: "PayrollEmployeeSummary",
    ReportName.PAYROLL_ACTIVITY_SUMMARY: "PayrollActivitySummary",
}

C = TypeVar("C")  # the coonfig dataclass type


@dataclass(frozen=True)
class ReportTask(Generic[C]):
    name: ReportName
    func: Callable[[SeleniumBrowser, C], None]
    conf: C


def _build_report_tasks(
    vals: dict[str, Any], report_tables: dict[str, Any]
) -> list[ReportTask]:
    # values shared by every report

    work_dir = vals.get("work_dir")
    screenshot_dir = vals.get("screenshot_dir")

    common = dict(
        download_directory=work_dir,
        screenshot_path=screenshot_dir,
        capture_screenshots=True,
        export_format="excel",
    )

    start_date = vals.get("from_dt")
    end_date = vals.get("to_dt")
    activity_statement_period = statement_period(end_date)

    bank_reconciliation_settings = _parse_br_table(
        ReportName.BANK_RECONCILIATION, report_tables
    )
    aged_receivables_detail_settings = _parse_ard_table(
        ReportName.AGED_RECEIVABLES_DETAIL, report_tables
    )
    aged_payables_detail_settings = _parse_apd_table(
        ReportName.AGED_PAYABLES_DETAIL, report_tables
    )
    general_ledger_detail_settings = _parse_gld_table(
        ReportName.GENERAL_LEDGER_DETAIL, report_tables
    )
    trial_balance_settings = _parse_tb_table(ReportName.TRIAL_BALANCE, report_tables)
    activity_statement_settings = _parse_as_table(
        ReportName.ACTIVITY_STATEMENT, report_tables
    )

    activity_statement_mode = vals.get("bas_mode")
    if activity_statement_mode == "quarterly":
        activity_statement_settings = activity_statement_settings.get("quarterly") or {}
    elif activity_statement_mode == "year-end":
        activity_statement_settings = activity_statement_settings.get("year_end") or {}
    else:
        activity_statement_settings = {}

    return [
        ReportTask(
            ReportName.BANK_RECONCILIATION,
            download_bank_reconciliation_report_multi_account,
            BankReconciliationMultiRequest(
                report_file_name=str(ReportName.BANK_RECONCILIATION),
                start_date=start_date,
                end_date=end_date,
                window_title=str(ReportName.BANK_RECONCILIATION),
                **common,
                **bank_reconciliation_settings,
            ),
        ),
        ReportTask(
            ReportName.AGED_RECEIVABLES_DETAIL,
            download_aged_receivables_detail_report,
            AgedReceivablesRequest(
                report_file_name=str(ReportName.AGED_RECEIVABLES_DETAIL),
                end_date=end_date,
                window_title=str(ReportName.AGED_RECEIVABLES_DETAIL),
                **common,
                **aged_receivables_detail_settings,
            ),
        ),
        ReportTask(
            ReportName.AGED_PAYABLES_DETAIL,
            download_aged_payables_detail_report,
            AgedPayablesRequest(
                report_file_name=str(ReportName.AGED_PAYABLES_DETAIL),
                end_date=end_date,
                window_title=str(ReportName.AGED_PAYABLES_DETAIL),
                **common,
                **aged_payables_detail_settings,
            ),
        ),
        ReportTask(
            ReportName.GST_RECONCILIATION,
            download_gst_reconciliation_report,
            GstReconciliationRequest(
                report_file_name=str(ReportName.GST_RECONCILIATION),
                start_date=start_date,
                end_date=end_date,
                window_title=str(ReportName.GST_RECONCILIATION),
                **common,
            ),
        ),
        ReportTask(
            ReportName.GENERAL_LEDGER_DETAIL,
            download_general_ledger_detail_report,
            GeneralLedgerDetailRequest(
                report_file_name=str(ReportName.GENERAL_LEDGER_DETAIL),
                start_date=start_date,
                end_date=end_date,
                window_title=str(ReportName.GENERAL_LEDGER_DETAIL),
                **common,
                **general_ledger_detail_settings,
            ),
        ),
        ReportTask(
            ReportName.TRIAL_BALANCE,
            download_trial_balance_report,
            TrialBalanceRequest(
                report_file_name=str(ReportName.TRIAL_BALANCE),
                end_date=end_date,
                window_title=str(ReportName.TRIAL_BALANCE),
                **common,
                **trial_balance_settings,
            ),
        ),
        ReportTask(
            ReportName.ACTIVITY_STATEMENT,
            download_activity_statement_report,
            ActivityStatementRequest(
                period=activity_statement_period,
                report_file_name=str(ReportName.ACTIVITY_STATEMENT),
                window_title=str(ReportName.ACTIVITY_STATEMENT),
                **common,
                **activity_statement_settings,
            ),
        ),
        ReportTask(
            ReportName.PAYROLL_EMPLOYEE_SUMMARY,
            download_payroll_employee_summary_report,
            PayrollEmployeeSummaryRequest(
                report_file_name=str(ReportName.PAYROLL_EMPLOYEE_SUMMARY),
                start_date=start_date,
                end_date=end_date,
                window_title=str(ReportName.PAYROLL_EMPLOYEE_SUMMARY),
                **common,
            ),
        ),
        ReportTask(
            ReportName.PAYROLL_ACTIVITY_SUMMARY,
            download_payroll_activity_summary_report,
            PayrollActivitySummaryRequest(
                report_file_name=str(ReportName.PAYROLL_ACTIVITY_SUMMARY),
                start_date=start_date,
                end_date=end_date,
                window_title=str(ReportName.PAYROLL_ACTIVITY_SUMMARY),
                **common,
            ),
        ),
    ]


def _parse_br_table(report, report_tables):
    table = report_tables.get(_TABLE_KEY[report])
    if not table:
        return {"accounts": "All"}     # docstring: "All" (case-insensitive) enumerates every account

    accounts = table.column_values("account_name")
    cleaned = [s.strip() for s in accounts if s and s.strip()]
    return {"accounts": cleaned or "All"}   # fall back to "All" if the column was all-blank


def _parse_ard_table(
    report: ReportName, report_tables: dict[str, Any]
) -> dict[str, Any]:
    table = report_tables.get(_TABLE_KEY[report])
    if table is None or not table:  # no config table exist or table is empty
        return {}

    row = table[0]  # single-settings-row report
    settings: dict[str, Any] = {}

    # Only include a field if the table actually specifies it. Omitting a field
    # means the request dataclass default stands — we never read that default here.
    if row.get("aging_by"):
        settings["aging_by"] = row["aging_by"]
    if row.get("outstanding_gst_column") not in (None, ""):
        settings["add_gst_column"] = str_to_bool(row["outstanding_gst_column"])

    return settings


def _parse_apd_table(
    report: ReportName, report_tables: dict[str, Any]
) -> dict[str, Any]:
    table = report_tables.get(_TABLE_KEY[report])
    if table is None or not table:  # no config table exist or table is empty
        return {}

    row = table[0]  # single-settings-row report
    settings: dict[str, Any] = {}

    # Only include a field if the table actually specifies it. Omitting a field
    # means the request dataclass default stands — we never read that default here.
    if row.get("aging_by"):
        settings["aging_by"] = row["aging_by"]
    if row.get("outstanding_gst_column") not in (None, ""):
        settings["add_gst_column"] = str_to_bool(row["outstanding_gst_column"])

    return settings


def _parse_gld_table(
    report: ReportName, report_tables: dict[str, Any]
) -> dict[str, Any]:
    table = report_tables.get(_TABLE_KEY[report])
    if table is None or not table:  # no config table exist or table is empty
        return {}

    row = table[0]  # single-settings-row report
    settings: dict[str, Any] = {}

    # Only include a field if the table actually specifies it. Omitting a field
    # means the request dataclass default stands — we never read that default here.
    if row.get("accounting_method"):
        settings["accounting_method"] = row["accounting_method"]

    return settings


def _parse_tb_table(
    report: ReportName, report_tables: dict[str, Any]
) -> dict[str, Any]:
    table = report_tables.get(_TABLE_KEY[report])
    if table is None or not table:  # no config table exist or table is empty
        return {}

    row = table[0]  # single-settings-row report
    settings: dict[str, Any] = {}

    # Only include a field if the table actually specifies it. Omitting a field
    # means the request dataclass default stands — we never read that default here.
    if row.get("accounting_method"):
        settings["accounting_method"] = row["accounting_method"]

    return settings


def _parse_as_table(
    report: ReportName, report_tables: dict[str, Any]
) -> dict[str, Any]:
    table = report_tables.get(_TABLE_KEY[report])
    if table is None or not table:  # no config table exist or table is empty
        return {}

    settings: dict[str, Any] = {}
    settings["quarterly"] = {}
    settings["year_end"] = {}
    # settings for quarterly BAS
    quarterly_row = table.get_row("running_mode", "quarterly")
    if quarterly_row is not None:
        settings["quarterly"] = _parse_as_row(quarterly_row)

    year_end = table.get_row("running_mode", "year-end")
    if year_end is not None:
        settings["year_end"] = _parse_as_row(year_end)

    return settings


_MAP_METHOD = {"Simpler BAS": "simpler", "Full BAS": "full", "leave default": None}
_MAP_GST_CALC = {
    "Monthly": "monthly",
    "Quarterly": "quarterly",
    "Annually": "annually",
    "leave default": None,
}
_MAP_GST_ACC = {"Accrual": "accrual", "Cash": "cash", "leave default": None}
_MAP_PAYGW_P = {
    "None": "none",
    "Monthly": "monthly",
    "Quarterly": "quarterly",
    "leave default": None,
}
_MAP_PAYG_IT = {
    "None": "none",
    "Amount": "option1",
    "Income x Rate": "option2",
    "leave default": None,
}
_MAP_OBLIGAT = {"Checked": True, "Unchecked": False, "leave default": None}


def _lookup(mapping: dict, value, field_name: str):
    if value not in mapping:
        raise DataValidationError(
            f"{field_name}: unexpected value {value!r}; allowed: {sorted(k for k in mapping)}"
        )
    return mapping[value]


def _parse_as_row(row: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "configure_settings": True,  # we're configuring, so master switch on
        "reporting_method": _lookup(
            _MAP_METHOD, row.get("reporting_method"), "reporting_method"
        ),
        "gst_calculation_period": _lookup(
            _MAP_GST_CALC, row.get("gst_calculation_period"), "gst_calculation_period"
        ),
        "gst_accounting_method": _lookup(
            _MAP_GST_ACC, row.get("gst_accounting_method"), "gst_accounting_method"
        ),
        "paygw_period": _lookup(_MAP_PAYGW_P, row.get("paygw_period"), "paygw_period"),
        "payg_income_tax_method": _lookup(
            _MAP_PAYG_IT, row.get("payg_income_tax_method"), "payg_income_tax_method"
        ),
    }

    # Obligations: collect into ONE dict; omit any that map to None ("leave default"),
    # since the request leaves out-of-dict obligations untouched.
    obligations = {}
    for key in (
        "fuel_tax_credits",
        "wine_equalisation_tax",
        "luxury_car_tax",
        "fringe_benefits_tax",
        "deferred_gst",
    ):
        state = _lookup(_MAP_OBLIGAT, row.get(key), key)
        if state is not None:  # None = leave default = don't include
            obligations[key] = state

    settings["additional_obligations"] = obligations or None  # None if nothing set
    return settings