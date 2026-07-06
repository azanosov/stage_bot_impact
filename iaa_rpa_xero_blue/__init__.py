"""
iaa_rpa_xero_blue - automation for downloading reports and records from Xero Blue.

Built on the shared ``iaa_rpa_utils`` library. Report functions take a live
``SeleniumBrowser`` plus a frozen request dataclass and save the export to disk,
raising typed exceptions from ``iaa_rpa_utils.exceptions`` on failure.

Public API:
  - Session:    ``xero_blue_login``, ``xero_blue_logout``, ``switch_client``
  - Navigation: ``navigate_to_dashboard_page``, ``navigate_to_all_reports_page``,
                ``navigate_to_report_page``
  - Reports:    a ``<Report>Request`` dataclass + ``download_<report>_report``
                function for each report, plus the ``StatementPeriod`` /
                ``ComparisonPeriod`` value objects and ``list_all_bank_accounts``
                (used for the Bank Reconciliation all-accounts flow).

See docs/README.md for usage, including the Bank Reconciliation all-accounts
pattern.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("iaa-rpa-xero-blue")
except PackageNotFoundError:          # running from a source checkout, not installed
    __version__ = "1.0.0"

# --- Session / auth ---
from .auth import xero_blue_login, xero_blue_logout
from .switch_client import switch_client

# --- Navigation ---
from .navigation import (
    navigate_to_dashboard_page,
    navigate_to_all_reports_page,
    navigate_to_report_page,
)

# --- Reports & records ---
from .download_trial_balance import TrialBalanceRequest, download_trial_balance_report
from .download_bank_reconciliation import (
    BankReconciliationRequest,
    download_bank_reconciliation_report,
    list_all_bank_accounts,
)
from .download_profit_and_loss import (
    ProfitAndLossRequest,
    ComparisonPeriod,
    download_profit_and_loss_report,
)
from .download_general_ledger_detail import (
    GeneralLedgerDetailRequest,
    download_general_ledger_detail_report,
)
from .download_gst_reconciliation import (
    GstReconciliationRequest,
    download_gst_reconciliation_report,
)
from .download_account_transactions import (
    AccountTransactionsRequest,
    download_account_transactions_report,
)
from .download_activity_statement import (
    StatementPeriod,
    ActivityStatementRequest,
    download_activity_statement_report,
)
from .download_aged_receivables_detail import (
    AgedReceivablesRequest,
    download_aged_receivables_detail_report,
)
from .download_aged_payables_detail import (
    AgedPayablesRequest,
    download_aged_payables_detail_report,
)
from .download_aged_receivables_summary import (
    AgedReceivablesSummaryRequest,
    download_aged_receivables_summary_report,
)
from .download_aged_payables_summary import (
    AgedPayablesSummaryRequest,
    download_aged_payables_summary_report,
)
from .download_leave_balances import (
    LeaveBalancesRequest,
    download_leave_balances_report,
)
from .download_payroll_employee_summary import (
    PayrollEmployeeSummaryRequest,
    download_payroll_employee_summary_report,
)
from .download_payroll_activity_summary import (
    PayrollActivitySummaryRequest,
    download_payroll_activity_summary_report,
)
from .download_invoice import InvoiceRequest, download_invoice

__all__ = [
    "__version__",
    # session
    "xero_blue_login",
    "xero_blue_logout",
    "switch_client",
    # navigation
    "navigate_to_dashboard_page",
    "navigate_to_all_reports_page",
    "navigate_to_report_page",
    # trial balance
    "TrialBalanceRequest",
    "download_trial_balance_report",
    # bank reconciliation
    "BankReconciliationRequest",
    "download_bank_reconciliation_report",
    "list_all_bank_accounts",
    # profit and loss
    "ProfitAndLossRequest",
    "ComparisonPeriod",
    "download_profit_and_loss_report",
    # general ledger detail
    "GeneralLedgerDetailRequest",
    "download_general_ledger_detail_report",
    # gst reconciliation
    "GstReconciliationRequest",
    "download_gst_reconciliation_report",
    # account transactions
    "AccountTransactionsRequest",
    "download_account_transactions_report",
    # activity statement
    "StatementPeriod",
    "ActivityStatementRequest",
    "download_activity_statement_report",
    # aged receivables / payables (detail + summary)
    "AgedReceivablesRequest",
    "download_aged_receivables_detail_report",
    "AgedPayablesRequest",
    "download_aged_payables_detail_report",
    "AgedReceivablesSummaryRequest",
    "download_aged_receivables_summary_report",
    "AgedPayablesSummaryRequest",
    "download_aged_payables_summary_report",
    # leave / payroll
    "LeaveBalancesRequest",
    "download_leave_balances_report",
    "PayrollEmployeeSummaryRequest",
    "download_payroll_employee_summary_report",
    "PayrollActivitySummaryRequest",
    "download_payroll_activity_summary_report",
    # invoice
    "InvoiceRequest",
    "download_invoice",
]