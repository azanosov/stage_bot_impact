"""
Central locator registry for the Xero Blue report modules.

ALL element locators live here (mandated). Every value is a SeleniumBrowser
wrapper locator string ("xpath:..." or "id:...").

Templates contain a {placeholder} the caller fills with .format(); these are
suffixed _TPL. Values ending _ID are bare element ids (not full locators) that
get fed into a _TPL.

Prefix legend (one prefix per module; SH_ = shared across every report):

    SH_     Shared report toolbar + settings panel
            (changing one of these affects EVERY report - tread carefully)
    ASR_    Activity Statement Report
    APDR_   Aged Payables Detail Report
    ARDR_   Aged Receivables Detail Report
    BRR_    Bank Reconciliation Report
    GLDR_   General Ledger Detail Report
    GSTR_   GST Reconciliation Report      (older surface - keep separate)
    PLR_    Profit and Loss Report
    TBR_    Trial Balance Report
"""

# ============================================================================
# SHARED  (SH_)
# The common report toolbar and settings panel, confirmed identical across the
# modern reports. Changing anything here affects EVERY report that uses it.
# ============================================================================

# --- Settings panel buttons ---
SH_MORE_BUTTON = "xpath://button[@data-automationid='report-settings-advanced-button']"
SH_UPDATE_BUTTON = "xpath://button[@data-automationid='settings-panel-update-button']"

# --- Date range inputs (a report uses 'to' only, 'from'+'to', or neither) ---
SH_DATE_FROM_INPUT = "id:report-settings-custom-date-input-from"
SH_DATE_TO_INPUT = "id:report-settings-custom-date-input-to"

# --- Export toolbar ---
SH_EXPORT_BUTTON = "xpath://button[@data-automationid='report-toolbar-export-button']"
# Format menu items. Excel/Sheets carry only an id (no automationid), so for a
# consistent locator across all formats we key every one by id via the _TPL below.
SH_EXPORT_EXCEL_ID = "report-toolbar-export-excel-menuitem"
SH_EXPORT_PDF_ID = "report-toolbar-export-pdf-menuitem"

# --- Report title field ---
SH_REPORT_TITLE_INPUT = "xpath://input[@data-automationid='report-title--input']"

# --- Columns multi-select button (appears on Trial Balance and the aged reports) ---
SH_COLUMNS_BUTTON = "xpath://button[@data-automationid='report-settings-columns-button']"

# --- Pick-list option templates (fill {opt_id}) -----------------------------
# A pick-list option is an <li id="..."> whose clickable target is the element
# carrying class 'xui-pickitem--body' inside it (a <button> in most menus, a
# <div role="button"> in the multi-select column menu - hence '*', not 'button').
# State lives on the <li>:
#   selected -> aria-selected="true"
#   disabled -> class contains 'xui-pickitem-is-disabled'
SH_PICKITEM_BODY_TPL = "xpath://li[@id='{opt_id}']//*[contains(@class,'xui-pickitem--body')]"
SH_PICKITEM_SELECTED_TPL = "xpath://li[@id='{opt_id}' and @aria-selected='true']"
SH_PICKITEM_DISABLED_TPL = "xpath://li[@id='{opt_id}' and contains(@class,'xui-pickitem-is-disabled')]"

# --- Accounting basis options (shared picklist option ids) ---
SH_BASIS_ACCRUAL_ID = "report-settings-accrualbasis-accrual"
SH_BASIS_CASH_ID = "report-settings-accrualbasis-cash"


# ============================================================================
# TRIAL BALANCE  (TBR_)
# An "as at" report: end date only, accounting basis, no comparison. Every
# control it touches is in the SHARED set above, so it has no locators of its
# own. (The legacy "Outstanding GST" column was removed - the option is not
# present in the Trial Balance columns menu.)
# ============================================================================
# (none - fully covered by SH_)


# ============================================================================
# BANK RECONCILIATION  (BRR_)
# Report-specific: the required bank-account autocompleter (a combobox plus its
# dropdown list). The date range and the toolbar are all in the SHARED set.
# (The "Bank statement ending balance" field on this report is out of scope.)
# ============================================================================

# The combobox input. Readonly at rest; clicking it opens the dropdown and
# exits readonly so it can be typed into to filter.
BRR_ACCOUNT_INPUT = "xpath://input[@data-automationid='Bank Account-selector-autocompleter--input']"

# The dropdown list container.
BRR_ACCOUNT_LIST = "xpath://div[@data-automationid='Bank Account-selector-autocompleter--list']"

# Any account option in the list. Its presence means at least one account
# exists; its absence is the no-accounts signal.
BRR_ACCOUNT_ANY_ITEM = (
    "xpath://div[@data-automationid='Bank Account-selector-autocompleter--list']"
    "//li[@aria-label]"
)

# A specific account option's clickable body, scoped to the list and keyed on
# the exact aria-label. {account} MUST be pre-quoted with helpers.xpath_literal
# (handles apostrophes etc.) before .format().
BRR_ACCOUNT_ITEM_TPL = (
    "xpath://div[@data-automationid='Bank Account-selector-autocompleter--list']"
    "//li[@aria-label={account}]//*[contains(@class,'xui-pickitem--body')]"
)


# ============================================================================
# AGED REPORTS shared  (AGED_)
# Controls common to BOTH Aged Payables Detail and Aged Receivables Detail, but
# not to other reports. (Columns *button* is shared more widely -> SH_ above.)
# ============================================================================

# "Ageing By" single-select dropdown trigger.
AGED_AGEING_BY_BUTTON = (
    "xpath://button[@data-automationid='report-settings-ageingBy-select-list-button--button']"
)

# An "Ageing By" option's clickable body, keyed on its short option key.
# {opt} is one of: "due", "invoice", "transaction" (transaction = receivables only).
AGED_AGEING_OPTION_TPL = (
    "xpath://*[@data-automationid='report-settings-ageingBy-select-list-option-{opt}--body']"
)

# The "Outstanding GST" column option in the Columns multi-select. Its id is
# 'taxamountdue' (NOT 'gst'). Driven via the shared pick-item primitives.
AGED_GST_COLUMN_ID = "column-selection-taxamountdue"


# ============================================================================
# PROFIT AND LOSS  (PLR_)
# Report-specific: the comparison-period controls and the show-option
# (by-label) locators. Basis, dates, title, toolbar and export are all SHARED.
# ============================================================================

# "Compare with" dropdown trigger.
PLR_COMPARISON_BUTTON = (
    "xpath://button[@data-automationid='report-settings-comparison-period-button']"
)

# The "Enter a different number" option that opens the custom-count dialog.
PLR_COMPARISON_OTHER = (
    "xpath://li[@id='comparison-period-selection-other']"
    "//*[contains(@class,'xui-pickitem--body')]"
)

# The custom-count dialog's number input and its Select button.
PLR_COMPARISON_MODAL_INPUT = (
    "xpath://section[@role='dialog']//input[contains(@class,'xui-textinput--input')]"
)
PLR_COMPARISON_MODAL_SELECT = (
    "xpath://section[@role='dialog']//button[normalize-space()='Select']"
)

# Comparison-kind pick-list option ids (fed to the shared SH_PICKITEM_* templates
# for click and disabled-state checks).
PLR_COMPARISON_KIND_MONTH_ID = "comparison-period-date-target-Month"
PLR_COMPARISON_KIND_QUARTER_ID = "comparison-period-date-target-Quarter"
PLR_COMPARISON_KIND_YEAR_ID = "comparison-period-date-target-Year"

# Show-option located by visible label (case-insensitive), scoped to a checkbox
# <li> so it cannot collide with the Accrual/Cash radios (which share the label
# class). {label_lower} is the lowercased label. Three variants are derived from
# one private base: exists / checked / clickable body.
_PLR_SHOW_OPTION_BASE = (
    "//li[.//input[@type='checkbox'] and "
    ".//span[contains(@class,'xui-styledcheckboxradio--label') and "
    "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz')='{label_lower}']]"
)
PLR_SHOW_OPTION_EXISTS_TPL = "xpath:" + _PLR_SHOW_OPTION_BASE
PLR_SHOW_OPTION_CHECKED_TPL = "xpath:" + _PLR_SHOW_OPTION_BASE + "[@aria-selected='true']"
PLR_SHOW_OPTION_CLICK_TPL = "xpath:" + _PLR_SHOW_OPTION_BASE + "//*[contains(@class,'xui-pickitem--body')]"


# ============================================================================
# ACTIVITY STATEMENT  (ASR_)
# The BAS flow - structurally different from the modern reports: its own export
# panel (radio-based), a period selector, and an ATO lodge wizard. It shares
# NONE of the SH_ toolbar. Export controls have automation-ids; the wizard /
# period / tab controls are text-located (no stable handle seen - upgrade if
# DOM becomes available). The "Include" checkboxes in the export panel are left
# at their defaults (out of scope).
# ============================================================================

# --- Export panel (automation-ids) ---
ASR_EXPORT_DROPDOWN_BUTTON = "xpath://div[@data-automationid='bas-export-dropdown']//button"
ASR_FORMAT_PDF_RADIO = "xpath://label[@data-automationid='bas-pdf-radio-button']"
ASR_FORMAT_EXCEL_RADIO = "xpath://label[@data-automationid='bas-excel-radio-button']"
ASR_EXPORT_CONFIRM_BUTTON = "xpath://button[@data-automationid='bas-export-button']"

# --- Period selector (automation-ids) ---
# "Create new statement" opens the selector. The period panel's back button
# returns to the tax-year list. Tax year and period each have stable ids.
ASR_CREATE_NEW_STATEMENT_BUTTON = "xpath://button[@data-automationid='period-dropdown-button']"
ASR_YEAR_SELECTOR_BUTTON = "xpath://button[@data-automationid='financial-period-header--button-back']"
# {tax_year} is the FY END year (e.g. 2025 for "2024/25"); {month} is the full
# month name and {year} the calendar year shown (e.g. financial-period-September-2024).
ASR_TAX_YEAR_TPL = "xpath://*[@data-automationid='financial-tax-year-{tax_year}--body']"
ASR_STATEMENT_PERIOD_TPL = "xpath://*[@data-automationid='financial-period-{month}-{year}--body']"
ASR_TRANSACTIONS_TAB = "xpath://button[.//span[normalize-space()='Transactions']]"  # text - no stable handle seen

# --- ATO lodge wizard (text-located; no stable handles seen) ---
ASR_LODGE_BUTTON = "xpath://button[normalize-space(text())='Lodge reports to ATO outside of Xero']"
ASR_GO_TO_STATEMENT_BUTTON = "xpath://button[normalize-space(text())='Go to Activity Statement']"
ASR_WIZARD_NEXT_BUTTON = "xpath://button[normalize-space(text())='Next']"
ASR_WIZARD_OK_BUTTON = "xpath://button[normalize-space(text())='OK']"


# ============================================================================
# GST RECONCILIATION  (GSTR_)  --  LEGACY surface, handle with care
# An older ExtJS page: plain-id date inputs, an onclick-based Update link, and a
# dropdown Export menu of <a> links. Shares NOTHING with SH_ (different dates,
# different toolbar). Excel yields .xls (old binary), not .xlsx.
#
# Xero ships two UI variants of this page (a modern button form and the legacy
# form), so Update / Export / each format link have a DEFAULT and a LEGACY
# locator; the module probes default first, then legacy.
#
# NOTE: this page also emits ExtJS auto-generated ids (ext-genNN) that change
# between renders - they are deliberately never used as locators here.
# ============================================================================

# Date inputs (stable ExtJS field ids).
GSTR_DATE_FROM_INPUT = "id:fromDate"
GSTR_DATE_TO_INPUT = "id:toDate"

# Update: default (modern button) then legacy (<a onclick='...UpdateReport...'>).
GSTR_UPDATE_DEFAULT = "xpath://button[@type='button' and normalize-space(text())='Update']"
GSTR_UPDATE_LEGACY = "xpath://a[normalize-space(text())='Update' and contains(@onclick,'UpdateReport')]"

# Export trigger: default (modern button) then legacy (<span class='words'>Export</span>).
GSTR_EXPORT_DEFAULT = "xpath://button[@type='button' and normalize-space(text())='Export']"
GSTR_EXPORT_LEGACY = "xpath://span[@class='words' and normalize-space(text())='Export']"

# Format links: default (modern <button><span>) then legacy (<a> keyed on its
# ShowReportAs onclick action - the most stable handle on this legacy page).
GSTR_FORMAT_EXCEL_DEFAULT = "xpath://button[@type='button']//span[normalize-space(text())='Excel']"
GSTR_FORMAT_EXCEL_LEGACY = "xpath://a[contains(@onclick,'ExcelReport.aspx')]"
GSTR_FORMAT_PDF_DEFAULT = "xpath://button[@type='button']//span[normalize-space(text())='PDF']"
GSTR_FORMAT_PDF_LEGACY = "xpath://a[contains(@onclick,'PDFReport.aspx')]"
