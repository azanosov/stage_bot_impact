"""
Munros Constants
=================
All hardcoded strings for the Munros client in one place.

Usage in other modules:
    from RPA_process.Client.Munros import munros_constants as MC
    Config.get(MC.CFG_REPORT_AGED_PAYABLES, MC.DEFAULT_AGED_PAYABLES)
    pms not in MC.PMS_VALUES
"""

# ---------------------------------------------------------------------------
# Config key names — Excel file paths
# ---------------------------------------------------------------------------
CFG_MASTER_EXCEL_PATH = "Munros_MasterExcelPath"
CFG_MASTER_SHEET_NAME = "Munros_MasterSheetName"
CFG_DETAILS_EXCEL_PATH = "Munros_DetailsExcelPath"
CFG_DETAILS_SHEET_NAME = "Munros_DetailsSheetName"
CFG_REPORT_ROOT_PATH = "Munros_ReportRootPath"
CFG_DISABLE_BROWSER_INIT = "Munros_DisableBrowserInit"

# ---------------------------------------------------------------------------
# Config key names — Report filenames (templates stored in orchestrator config)
# ---------------------------------------------------------------------------
CFG_REPORT_BALANCE_SHEET = "Munros_ReportName_BalanceSheet"
CFG_REPORT_PROFIT_LOSS = "Munros_ReportName_ProfitLoss"
CFG_REPORT_MERGED_FINANCIALS = "Munros_ReportName_MergedFinancials"
CFG_REPORT_AGED_PAYABLES = "Munros_ReportName_AgedPayables"
CFG_REPORT_GST_RECON = "Munros_ReportName_GSTReconciliation"
CFG_REPORT_BANK_REC = "Munros_ReportName_BankReconciliation"
CFG_REPORT_PAYROLL_EMPLOYEE = "Munros_ReportName_PayrollEmployee"
CFG_REPORT_ACCOUNT_TRANS = "Munros_ReportName_AccountTrans"
CFG_REPORT_AGED_RECEIVABLES = "Munros_ReportName_AgedReceivables"

# ---------------------------------------------------------------------------
# Config key names — Xero settings
# ---------------------------------------------------------------------------
CFG_XERO_WINDOW_TITLE = "Munros_XeroWindowTitle"
CFG_XERO_BANK_ACCOUNT = "Munros_XeroBankAccount"
CFG_XERO_AGING_BY = "Munros_XeroAgingBy"
CFG_XERO_ADD_GST_COLUMN = "Munros_XeroAddGSTColumn"
CFG_XERO_GST_REPORT_NAME = "Munros_XeroGSTReportName"
CFG_XERO_BANK_REC_REPORT_NAME = "Munros_XeroBankRecReportName"
CFG_XERO_PAYROLL_REPORT_NAME = "Munros_XeroPayrollReportName"

# ---------------------------------------------------------------------------
# Excel column names
# ---------------------------------------------------------------------------
COL_CLIENT_NAME = "Client Name"
COL_ABN = "ABN"
COL_FINANCIAL_YEAR = "Financial Year"
COL_PMS = "PMS"
COL_CLIENT_CODE = "Client Code"
COL_LAST_NAME = "Last Name"

# ---------------------------------------------------------------------------
# Required column lists
# ---------------------------------------------------------------------------
EXCEL1_REQUIRED = [COL_CLIENT_NAME, COL_ABN, COL_FINANCIAL_YEAR, COL_PMS]
EXCEL2_REQUIRED = [COL_ABN, COL_CLIENT_CODE, COL_LAST_NAME]

# ---------------------------------------------------------------------------
# PMS values
# ---------------------------------------------------------------------------
PMS_XPM = "XPM"
PMS_MYOB = "MYOB"
PMS_VALUES = (PMS_XPM, PMS_MYOB)

# ---------------------------------------------------------------------------
# Queue payload field keys
# ---------------------------------------------------------------------------
QUEUE_CLIENT_NAME = "clientName"
QUEUE_ABN = "abn"
QUEUE_FINANCIAL_YEAR = "financialYear"
QUEUE_PMS = "pms"

# ---------------------------------------------------------------------------
# Report display names  (used as dict keys in report_paths + _track())
# ---------------------------------------------------------------------------
REPORT_BALANCE_SHEET = "Balance Sheet"
REPORT_PROFIT_LOSS = "Profit and Loss"
REPORT_MERGED_FINANCIALS = "Merged Financials"
REPORT_AGED_PAYABLES = "Aged Payables Summary"
REPORT_GST_RECON = "GST Reconciliation"
REPORT_BANK_REC = "Bank Reconciliation"
REPORT_PAYROLL_EMPLOYEE = "Payroll Employee Summary"
REPORT_ACCOUNT_TRANS = "Account Transactions"
REPORT_AGED_RECEIVABLES = "Aged Receivables Summary"

# ---------------------------------------------------------------------------
# Default filename templates  ({fy} substituted at runtime by report_filename())
# ---------------------------------------------------------------------------
DEFAULT_BALANCE_SHEET = "Balance Sheet {fy}"
DEFAULT_PROFIT_LOSS = "Profit and Loss {fy}"
DEFAULT_MERGED_FINANCIALS = "Financial Statements {fy}"
DEFAULT_AGED_PAYABLES = "Aged Payables Summary {fy}"
DEFAULT_GST_RECON = "GST Reconciliation {fy}"
DEFAULT_BANK_REC = "Bank Reconciliation {fy}"
DEFAULT_PAYROLL_EMPLOYEE = "Payroll Employee Summary {fy}"
DEFAULT_ACCOUNT_TRANS = "Account Transactions {fy}"
DEFAULT_AGED_RECEIVABLES = "Aged Receivables Summary {fy}"

# ---------------------------------------------------------------------------
# Xero internal report names  (passed to iaa_rpa_xero_blue functions)
# ---------------------------------------------------------------------------
XERO_RPT_GST_RECON = "GST Reconciliation"
XERO_RPT_BANK_REC = "Bank Reconciliation"
XERO_RPT_PAYROLL = "Payroll Employee Summary"

# ---------------------------------------------------------------------------
# ATO report config key names
# ---------------------------------------------------------------------------
CFG_ATO_REPORT_BAS = "Munros_ATOReportName_BAS"
CFG_ATO_REPORT_ITA = "Munros_ATOReportName_ITA"
CFG_ATO_REPORT_ICA = "Munros_ATOReportName_ICA"
CFG_ATO_REPORT_FBT = "Munros_ATOReportName_FBT"
CFG_ATO_REPORT_SGC = "Munros_ATOReportName_SGC"

# ---------------------------------------------------------------------------
# ATO report display names
# ---------------------------------------------------------------------------
REPORT_ATO_BAS = "ATO BAS"  # Business Activity Statement
REPORT_ATO_ITA = "ATO ITA"  # Income Tax Account
REPORT_ATO_ICA = "ATO ICA"  # Integrated Client Account
REPORT_ATO_FBT = "ATO FBT"  # Fringe Benefits Tax
REPORT_ATO_SGC = "ATO SGC"  # Superannuation Guarantee Charge

# ---------------------------------------------------------------------------
# ATO default filename templates  ({fy} substituted at runtime)
# ---------------------------------------------------------------------------
DEFAULT_ATO_BAS = "ATO BAS {fy}"
DEFAULT_ATO_ITA = "ATO ITA {fy}"
DEFAULT_ATO_ICA = "ATO ICA {fy}"
DEFAULT_ATO_FBT = "ATO FBT {fy}"
DEFAULT_ATO_SGC = "ATO SGC {fy}"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_XERO_WINDOW_TITLE = "Xero"
DEFAULT_AGING_BY = "Due date"
REPORT_EXTENSION = ".xlsx"
ATO_REPORT_EXTENSION = ".json"
