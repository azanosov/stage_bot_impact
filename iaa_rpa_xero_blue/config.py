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
# {opt} is one of: "due", "invoice" (both aged reports offer only these two).
AGED_AGEING_OPTION_TPL = (
    "xpath://*[@data-automationid='report-settings-ageingBy-select-list-option-{opt}--body']"
)

# The "Outstanding GST" column option in the Columns multi-select. Its id is
# 'taxamountdue' (NOT 'gst'). Driven via the shared pick-item primitives.
AGED_GST_COLUMN_ID = "column-selection-taxamountdue"

# --- Ageing Periods modal (summary reports) ---------------------------------
# "N periods of M {kind}". The first input is the period COUNT, the second the
# period FREQUENCY/size; the kind (Month/Week/Day) is a pick-list. The modal's
# checkbox and title-format radios are left at their defaults (out of scope).
AGED_AGEING_PERIODS_TRIGGER = (
    "xpath://button[@id='report-settings-ageing-periods-modal-trigger']"
)
AGED_AGEING_PERIODS_COUNT_INPUT = (
    "xpath://input[@data-automationid='report-settings-ageing-periods-modal-periodCount--input']"
)
AGED_AGEING_PERIODS_FREQ_INPUT = (
    "xpath://input[@data-automationid='report-settings-ageing-periods-modal-periodFrequency--input']"
)
AGED_AGEING_PERIODS_KIND_BUTTON = (
    "xpath://button[@data-automationid='report-settings-ageing-periods-modal-periodKind-button']"
)
# {kind} is the visible label: Month / Week / Day. Options are the shared
# pick-item bodies inside the modal dialog, matched by text.
AGED_AGEING_PERIODS_KIND_OPTION_TPL = (
    "xpath://section[@role='dialog']//button[contains(@class,'xui-pickitem--body')]"
    "[.//span[normalize-space()='{kind}']]"
)
AGED_AGEING_PERIODS_APPLY_BUTTON = (
    "xpath://button[@data-automationid='report-settings-ageing-periods-modal-apply-button']"
)


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


# ============================================================================
# ACCOUNT TRANSACTIONS  (ACCT_)
# Date-range report with a MULTI-select accounts filter (distinct from bank
# rec's single-select combobox). Same XUI autocompleter family - the open list
# panel carries automationid 'Accounts-selector-autocompleter--list' (mirrors
# bank rec's confirmed pattern). Each row exposes a stable
# <li aria-label="{code} - {name}"> - the meaningful handle. The row's
# data-automationid 'Accounts-selector-dropdown-item-{N}' is POSITIONAL and
# renumbers as the list is filtered, so it is deliberately NOT used to target.
# ============================================================================

# Open button + search input (automation-ids).
ACCT_SELECTOR_OPEN_BUTTON = "xpath://button[@data-automationid='Accounts-selector-input-open']"
ACCT_SELECTOR_INPUT = "xpath://input[@data-automationid='Accounts-selector-autocompleter--input']"

# Select all / Deselect all are ONE toggle button sharing a single automationid
# ('Accounts-selector-dropdown-select-all--body'); only the inner text swaps
# ("Select all" <-> "Deselect all"). So each state is distinguished by its text
# on that shared body - the id alone can't tell which state is showing.
ACCT_SELECT_ALL = (
    "xpath://button[@data-automationid='Accounts-selector-dropdown-select-all--body']"
    "[.//span[normalize-space()='Select all']]"
)
ACCT_DESELECT_ALL = (
    "xpath://button[@data-automationid='Accounts-selector-dropdown-select-all--body']"
    "[.//span[normalize-space()='Deselect all']]"
)

# One account row's clickable body, matched EXACTLY on its aria-label.
# {label} must be an xpath string literal (build it with xpath_literal()).
ACCT_ITEM_BODY_TPL = "xpath://li[@aria-label={label}]//button[contains(@class,'xui-pickitem--body')]"


# ============================================================================
# DOWNLOAD INVOICE  (INV_)
# NOT a report - a record download from the Accounts Receivable invoice list
# (legacy ExtJS surface) + the modern invoice detail page. The list is reached
# by SEARCH (not by scraping/paging 3000+ rows): pick the "All" tab, type the
# number, Search, then match the row by its ref cell. Navigation (Sales/Business
# -> Invoices, and Home) is text-located and dual-UI - the caller invokes it.
# ============================================================================

# --- Navigation (text-located, dual UI; caller drives these) ---
INV_NAV_SALES_BUTTON = "xpath://button[@type='button' and .//span[normalize-space(text())='Sales']]"          # new UI
INV_NAV_INVOICES_LINK = "xpath://a[@role='link' and span[normalize-space(text())='Invoices']]"                 # new UI
INV_NAV_BUSINESS_BUTTON = "xpath://button[normalize-space(text())='Business']"                                 # old UI
INV_NAV_INVOICES_TAB = "xpath://a[normalize-space(text())='Invoices']"                                         # old UI
INV_NAV_HOME_LINK = "xpath://span[@class='x-nav--nav-item-text' and normalize-space(text())='Home']"           # new UI (Business is old-UI fallback)

# --- Invoice list: status tabs + search ---
# "All" tab is the only status link whose href has no invoiceStatus query - the
# unfiltered set. Searching within All guarantees the widest, deterministic set.
INV_TAB_ALL = "xpath://ul[contains(@class,'group')]//a[normalize-space(text())='All']"
INV_SEARCH_INPUT = "id:sb_txtReference"
INV_SEARCH_BUTTON = "xpath://span[@data-automationid='Search-button']"

# One invoice row's clickable contact link, matched EXACTLY on the invoice
# number in that row's ref cell (position-independent - the link text is the
# CONTACT, not the number, so we key off the ref <td>). {invoice} is an xpath
# string literal (build with xpath_literal()).
INV_ROW_LINK_BY_NUMBER_TPL = (
    "xpath://tr[td[contains(@class,'ref')][normalize-space()={invoice}]]//a[contains(@class,'nav')]"
)
# The detail-page heading confirming the right invoice opened. {heading} is an
# xpath string literal of the full "Invoice {number}" text (build with xpath_literal()).
INV_DETAIL_HEADING_TPL = "xpath://h1[normalize-space(text())={heading}]"

# --- Invoice detail page: Print PDF + Mark as Sent modal (automation-ids) ---
INV_PRINT_PDF_BUTTON = "xpath://button[@data-automationid='PrintDropdown-print']"
INV_MARK_AS_SENT_MODAL = "xpath://section[@data-automationid='MarkAsSentModal--header' or @id='MarkAsSentModal--header']"
INV_MARK_AS_SENT_CANCEL = "xpath://button[@data-automationid='MarkAsSentModal--cancelButton']"


# ============================================================================
# LOGIN  (LOGIN_)
# The session/auth entry point (not a download). Credentials + a pre-generated
# OTP are passed IN by the caller - this surface never holds the TOTP secret and
# never generates a code. Locators below are on stable ids/automation-ids; the
# logged-in check is layered (new-UI dashboard <main>, then legacy Dashboard
# text) so it survives across UI versions.
# ============================================================================

# --- Login form (stable ids) ---
LOGIN_EMAIL_INPUT = "id:xl-form-email"
LOGIN_PASSWORD_INPUT = "id:xl-form-password"
LOGIN_SUBMIT_BUTTON = "id:xl-form-submit"

# --- MFA step (automation-ids) ---
LOGIN_MFA_OTP_INPUT = "xpath://input[@data-automationid='auth-onetimepassword--input']"
LOGIN_MFA_CONFIRM_BUTTON = "xpath://button[@data-automationid='auth-submitcodebutton']"

# --- Logged-in check (layered: new-UI <main> first, legacy Dashboard fallback) ---
# Dashboard SPA container. Token-safe class match (the <main> may carry other
# classes alongside this one), so we match the stable token, not an exact string.
LOGIN_HOME_MAIN = "xpath://main[contains(concat(' ', normalize-space(@class), ' '), ' homepage-spa-SharedLayout--body ')]"
# Legacy fallback (flagged: text-located, older UI).
LOGIN_DASHBOARD_LINK = "xpath://a[normalize-space(.)='Dashboard']"


# ============================================================================
# NAVIGATION - dashboard / home  (NAV_)
# Shared home-nav locators. Layered new-UI-first, legacy fallback.
# ============================================================================
# New-UI top-nav Home link.
NAV_HOME_LINK = "xpath://a[@role='link' and span[normalize-space(text())='Home']]"
# Dashboard SPA container - token-safe class match (the <main> may carry other
# classes alongside this one). NOTE: same element as login.LOGIN_HOME_MAIN;
# kept separate for now, worth collapsing to one shared marker later.
NAV_HOME_MAIN = (
    "xpath://main[contains(concat(' ', normalize-space(@class), ' '), "
    "' homepage-spa-SharedLayout--body ')]"
)
# Legacy fallback (flagged: text-located, older UI, unverified against a capture).
NAV_DASHBOARD_LINK = "xpath://a[normalize-space(.)='Dashboard']"

# ============================================================================
# NAVIGATION - report centre  (REPORTS_)
# ============================================================================
# Report-centre SPA container. Stable id; present across all report-centre tabs.
REPORTS_CENTRE_PARENT = "xpath://div[@id='report-centre-parent']"
# New-UI "All reports" nav link.
REPORTS_ALL_REPORTS_LINK = "xpath://li/a[span[normalize-space(text())='All reports']]"
# Legacy fallback: Accounting menu -> Reports (unverified against a capture).
REPORTS_ACCOUNTING_TAB = "xpath://button[@type='button' and normalize-space(text())='Accounting']"
REPORTS_ACCOUNTING_REPORTS_LINK = "xpath://a[normalize-space(text())='Reports']"
# A report row inside the centre, keyed on the report-name span. Pass the name
# through helpers.xpath_literal() into {report_literal} (safe-quotes apostrophes).
# NOTE: report names are non-unique in this DOM (favourites + group), so this may
# match multiple rows; their hrefs are identical, so any match is equivalent.
REPORTS_REPORT_LINK_BY_NAME_TPL = (
    "xpath://div[@id='report-centre-parent']"
    "//a[.//span[@data-automationid='report-name']"
    "[normalize-space(text())={report_literal}]]"
)


# ============================================================================
# LOGOUT  (LOGOUT_)
# Session teardown (auth). Success is verified by the login form reappearing
# (reuses LOGIN_EMAIL_INPUT), so no locale-dependent page-title match is needed.
# ============================================================================
# User-avatar button in the top nav. Stable automation-id - no username needed,
# so no html.unescape and no xpath-injection surface.
LOGOUT_USER_MENU_BUTTON = "xpath://button[@data-automationid='xnav-addon-user-iconbutton']"
# "Log out" link inside the (initially hidden) user-menu flyout. Keyed on the
# stable /logout href rather than the locale-dependent 'Log out' link text.
LOGOUT_LINK = "xpath://a[@href='https://go.xero.com/logout']"


# ============================================================================
# SWITCH CLIENT  (SWITCH_)
# Switch the active Xero organisation. Layered: new UI (Home) vs legacy UI
# (Dashboard). The Home/Dashboard indicators reuse the shared NAV_ pair
# (NAV_HOME_LINK / NAV_DASHBOARD_LINK) - not duplicated here.
# Active-org checks and account links are {account}-templated (_TPL); feed them
# helpers.xpath_literal(account) (safe-quotes apostrophes and ampersands).
# ============================================================================

# --- New UI ---
SWITCH_NEW_SEARCH = "xpath://input[@placeholder='Search organizations']"
SWITCH_NEW_NO_RESULTS = "xpath://p[starts-with(normalize-space(.), 'No results found for')]"
# FRAGILE (carried from original): "the first button on the page" is not a robust
# anchor for the organisation selector. Replace with a real data-automationid /
# aria-label when the page HTML is available.
SWITCH_NEW_USER_BUTTON = "xpath://button[@type='button']"
SWITCH_NEW_ACTIVE_ORG_TPL = (
    "xpath://div[@class='header-and-quick-actions-mfe-Header--organisation-name-text' "
    "and text()={account_literal}]"
)
SWITCH_NEW_ACCOUNT_LINK_TPL = (
    "xpath://a[@role='link' and .//span[normalize-space(.)={account_literal}]]"
)

# --- Legacy UI (verbatim from the original; unverified against a capture) ---
SWITCH_OLD_CHANGE_ORG = (
    "xpath://button[@type='button']//span[normalize-space(text())='Change organisation']"
)
SWITCH_OLD_ACCOUNT_SELECT = "xpath://div[@class='xnav-appbutton--body']"
SWITCH_OLD_SEARCH_ORG = "xpath://input[@role='searchbox' and @aria-label='Search organisations']"
SWITCH_OLD_SEARCH_BOX = "xpath://input[normalize-space(@placeholder)='Search organisations']"
SWITCH_OLD_NO_RESULTS = "xpath://div[starts-with(normalize-space(.), 'No results found for')]"
SWITCH_OLD_ACTIVE_ORG_TPL = (
    "xpath://div[@class='xnav-appbutton--body']"
    "//span[@class='xnav-appbutton--text' and normalize-space(text())={account_literal}]"
)
SWITCH_OLD_ACCOUNT_LINK_TPL = (
    "xpath://a[@class='xnav-verticalmenuitem--body xnav-menuitem-orgpractice']"
    "//span[normalize-space(.)={account_literal}]"
)
