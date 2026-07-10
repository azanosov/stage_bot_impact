"""
Module for downloading Activity Statement (BAS) reports from Xero Blue.

The Activity Statement is structurally different from the other reports: it uses
the BAS flow rather than the modern report toolbar - an ATO lodge wizard (when
present), a settings panel (when present), a statement-period selector, and its
own radio-based export panel.

Configures and downloads one statement: reaches the report page (clicking
through the lodge wizard if shown), optionally configures the BAS settings panel
(reporting method, GST/PAYG options, additional obligations), selects the
statement period within its financial year, exports it (Excel or PDF), and
confirms the file was saved.

Drives the page through the SeleniumBrowser wrapper. Locators live in config.py
(the ASR_ section); shared behaviour (validation, save-path, file-check) lives
in common.py. This module composes those.

Inputs are modelled as dataclasses:
    StatementPeriod          - a single BAS quarter-end period (month + calendar year)
    ActivityStatementRequest - everything one download needs (period + settings + file/output config)

Settings semantics (see ActivityStatementRequest):
    Each single-choice setting is optional. A concrete value is applied to the
    panel; ``None`` leaves whatever Xero currently has selected for that control.
    Obligations are a dict: only the keys present are driven (True=checked,
    False=unchecked); any obligation NOT in the dict is left as-is, and ``None``
    (the default) leaves every obligation checkbox untouched.
    State is read via a "checked" locator resolved through
    ``does_page_contain_element`` (a CSS ':checked' selector - see config). A
    control is clicked only when its current state differs from the requested one.
    The panel reflects the CLIENT's real BAS configuration, so applying a value
    that differs from the client's current setting WILL overwrite it - pass
    ``None`` (or omit the obligation key) for any control you want left alone.

How to call:
    from download_activity_statement import (
        StatementPeriod, ActivityStatementRequest, download_activity_statement_report,
    )

    request = ActivityStatementRequest(
        period=StatementPeriod("March", 2025),   # the period as it appears in Xero
        download_directory=r"C:\\Reports",
        report_file_name="bas_mar_2025",
        # export_format="excel",                 # "excel" (default, .xlsx) or "pdf" (.pdf)
        # window_title="Activity Statement",
        # --- settings panel (all optional; None = leave as-is) ---
        # configure_settings=True,               # master switch (default False)
        # reporting_method=None,                 # "simpler" | "full" | None (leave as-is)
        # gst_calculation_period=None,           # "monthly" | "quarterly" | "annually" | None
        # gst_accounting_method=None,            # "cash" | "accrual" | None
        # paygw_period=None,                     # "none" | "monthly" | "quarterly" | None
        # payg_income_tax_method=None,           # "none" | "option1" | "option2" | None
        # additional_obligations={"fuel_tax_credits": True},  # {key: bool}; None = touch none
    )
    download_activity_statement_report(browser, request)

Failure behaviour:
    Errors are logged (by ``ProcessLogger``) and RE-RAISED with their original
    types. Invalid inputs raise ``DataValidationError`` (at construction); a
    period/control that cannot be found raises ``ElementNotFoundError``; a missing
    Export control, or a settings panel that fails to render, raises
    ``DataExtractionError``; a file that fails to save raises ``DownloadError``.
    The settings phase is best-effort at the entry point (skipped when the
    Settings button is absent), but once entered, a panel that fails to render
    raises. An individual settings control that cannot be found is warned about
    and skipped (cosmetic), mirroring the Profit and Loss show-option behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Optional, get_args

from iaa_rpa_utils import ProcessLogger, setup_logger
from iaa_rpa_utils.helpers import handle_chrome_save_as_dialog

from iaa_rpa_utils.exceptions import DataExtractionError, DataValidationError

from . import common
from . import config

logger = setup_logger(__name__)


__all__ = [
    "StatementPeriod",
    "ActivityStatementRequest",
    "statement_period",
    "download_activity_statement_report",
]


# --------------------------------------------------------------------
# Module constants (report-specific only; shared ones live in common)
# --------------------------------------------------------------------
_MIN_STATEMENT_YEAR = 2000  # earliest period year we accept

# The four BAS quarter-end months. An invalid month is a type error at the call
# site (and a runtime ValueError via __post_init__) before anything runs.
Month = Literal["March", "June", "September", "December"]

# Export formats: format name -> (format radio locator, saved extension).
# Activity statement picks the format via a radio in its export panel (not the
# shared export menu), so the map holds the radio locator rather than a menu id.
ExportFormat = Literal["excel", "pdf"]
_EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "excel": (config.ASR_FORMAT_EXCEL_RADIO, ".xlsx"),
    "pdf": (config.ASR_FORMAT_PDF_RADIO, ".pdf"),
}

# --------------------------------------------------------------------
# BAS settings panel: friendly value -> control base automation-id (config).
# The id constants live in config.py (ASR_SETTINGS_*_ID); these dicts hold only
# the value->id policy, mirroring the P&L _ACCOUNTING_OPTION_IDS pattern.
# --------------------------------------------------------------------
ReportingMethod = Literal["simpler", "full"]
_REPORTING_METHOD_AIDS: dict[str, str] = {
    "simpler": config.ASR_SETTINGS_REPORTING_SIMPLEBAS_ID,
    "full": config.ASR_SETTINGS_REPORTING_FULLBAS_ID,
}

GstCalculationPeriod = Literal["monthly", "quarterly", "annually"]
_GST_PERIOD_AIDS: dict[str, str] = {
    "monthly": config.ASR_SETTINGS_GST_MONTHLY_ID,
    "quarterly": config.ASR_SETTINGS_GST_QUARTERLY_ID,
    "annually": config.ASR_SETTINGS_GST_ANNUALLY_ID,
}

GstAccountingMethod = Literal["cash", "accrual"]
_GST_ACCOUNTING_AIDS: dict[str, str] = {
    "cash": config.ASR_SETTINGS_ACCOUNTING_CASH_ID,
    "accrual": config.ASR_SETTINGS_ACCOUNTING_ACCRUAL_ID,
}

PaygWithholdingPeriod = Literal["none", "monthly", "quarterly"]
_PAYGW_PERIOD_AIDS: dict[str, str] = {
    "none": config.ASR_SETTINGS_PAYGW_NONE_ID,
    "monthly": config.ASR_SETTINGS_PAYGW_MONTHLY_ID,
    "quarterly": config.ASR_SETTINGS_PAYGW_QUARTERLY_ID,
}

PaygIncomeTaxMethod = Literal["none", "option1", "option2"]
_PAYG_METHOD_AIDS: dict[str, str] = {
    "none": config.ASR_SETTINGS_PAYG_METHOD_NONE_ID,
    "option1": config.ASR_SETTINGS_PAYG_METHOD_OPTION1_ID,  # "Option 1 Amount"
    "option2": config.ASR_SETTINGS_PAYG_METHOD_OPTION2_ID,  # "Option 2 Income x Rate"
}

Obligation = Literal[
    "fuel_tax_credits",
    "wine_equalisation_tax",
    "luxury_car_tax",
    "fringe_benefits_tax",
    "deferred_gst",
]
_OBLIGATION_AIDS: dict[str, str] = {
    "fuel_tax_credits": config.ASR_SETTINGS_OBLIGATION_FUEL_TAX_CREDITS_ID,
    "wine_equalisation_tax": config.ASR_SETTINGS_OBLIGATION_WINE_EQUALISATION_ID,
    "luxury_car_tax": config.ASR_SETTINGS_OBLIGATION_LUXURY_CAR_TAX_ID,
    "fringe_benefits_tax": config.ASR_SETTINGS_OBLIGATION_FRINGE_BENEFITS_TAX_ID,
    "deferred_gst": config.ASR_SETTINGS_OBLIGATION_DEFERRED_GST_ID,
}

# Deferred GST only renders on the panel when GST calculation period = Monthly.
# Shown in the not-found warning so a skipped deferred_gst is self-explaining.
_DEFERRED_GST_HINT = (
    "Deferred GST is only shown when GST calculation period = Monthly; "
    "it may not be set for this client"
)


@dataclass(frozen=True)
class StatementPeriod:
    """A BAS quarter-end statement period, e.g. September 2024.

    `year` is the CALENDAR year shown next to the month in Xero's UI
    (September 2024 -> year=2024; March 2025 -> year=2025) - NOT a financial-year
    label. The FY range that contains the period is derived via `fiscal_year_label`.
    """

    month: Month
    year: int

    def __post_init__(self) -> None:
        if self.month not in get_args(Month):
            raise DataValidationError(
                f"month must be one of {get_args(Month)}, got {self.month!r}"
            )
        # year is typed int but not enforced at runtime; guard it. bool is an int subclass.
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise DataValidationError(
                f"year must be an int, got {type(self.year).__name__}"
            )
        max_year = datetime.now().year + 2
        if not _MIN_STATEMENT_YEAR <= self.year <= max_year:
            raise DataValidationError(
                f"year must be between {_MIN_STATEMENT_YEAR} and {max_year}, got {self.year}"
            )

    def __str__(self) -> str:
        return f"{self.month} {self.year}"  # e.g. "September 2024"

    @property
    def fiscal_year_label(self) -> str:
        """FY range label that contains this period, e.g. "2024/25". Sep/Dec sit
        in the FY's start calendar year; Mar/Jun roll into the following one."""
        start = self.year if self.month in ("September", "December") else self.year - 1
        return f"{start}/{str(start + 1)[-2:]}"

    @property
    def tax_year(self) -> int:
        """The FY END year, as used in the tax-year automation-id (e.g. 2025 for
        the "2024/25" range). Both September 2024 and March 2025 give 2025."""
        start = self.year if self.month in ("September", "December") else self.year - 1
        return start + 1


@dataclass(frozen=True, kw_only=True)
class ActivityStatementRequest:
    """Everything needed to download one Activity Statement report.

    Attributes:
        period:             StatementPeriod (quarter-end month + calendar year).
        download_directory: Directory the report file is saved to.
        report_file_name:   Output filename; extension normalised/forced by dest_path.
        export_format:      "excel" (default, .xlsx) or "pdf" (.pdf).
        window_title:       Title used to locate the Chrome Save As window.
        capture_screenshots: Whether to capture before/after screenshots during
            export (default True). When True, screenshot_path is required.
        screenshot_path: Directory screenshots are written to. Required when
            capture_screenshots is True; may be None when it is False.
    Settings panel (best-effort; skipped when the Settings button is absent):
        configure_settings:      Master switch. False (default) disables the
                                 settings phase entirely, regardless of the fields
                                 below.
        reporting_method:        "simpler" | "full" | None (leave as-is).
        gst_calculation_period:  "monthly" | "quarterly" | "annually" | None.
        gst_accounting_method:   "cash" | "accrual" | None.
        paygw_period:            "none" | "monthly" | "quarterly" | None.
        payg_income_tax_method:  "none" | "option1" | "option2" | None.
        additional_obligations:  Dict mapping obligation keys to the desired
                                 checkbox state (True=checked, False=unchecked).
                                 Only keys present are applied; any obligation NOT
                                 in the dict is left exactly as the client has it.
                                 None (default) leaves every obligation checkbox
                                 untouched. Valid keys: "fuel_tax_credits",
                                 "wine_equalisation_tax", "luxury_car_tax",
                                 "fringe_benefits_tax", "deferred_gst". NOTE:
                                 "deferred_gst" only appears when
                                 gst_calculation_period is monthly.

    NOTE: the settings panel reflects the client's real BAS configuration. A
    concrete value that differs from the client's current setting WILL overwrite
    it. Pass None (or omit the obligation key) for any control you want left
    exactly as the client has it. The individual settings default to None so that
    flipping configure_settings=True alone changes nothing - each overwrite is an
    explicit opt-in.
    """

    period: StatementPeriod
    download_directory: str
    report_file_name: str
    export_format: ExportFormat = "excel"
    window_title: str = "Activity Statement"
    capture_screenshots: bool = True
    screenshot_path: str | None = None

    # --- settings panel (all default to None/"leave as-is"; master switch off) ---
    configure_settings: bool = False
    reporting_method: Optional[ReportingMethod] = None
    gst_calculation_period: Optional[GstCalculationPeriod] = None
    gst_accounting_method: Optional[GstAccountingMethod] = None
    paygw_period: Optional[PaygWithholdingPeriod] = None
    payg_income_tax_method: Optional[PaygIncomeTaxMethod] = None
    additional_obligations: Optional[dict[Obligation, bool]] = None

    def __post_init__(self) -> None:
        common.validate_non_empty_str(self.download_directory, "download_directory")
        common.validate_non_empty_str(self.report_file_name, "report_file_name")
        if not isinstance(self.period, StatementPeriod):
            raise DataValidationError(
                f"period must be a StatementPeriod, got {type(self.period).__name__}"
            )
        if self.export_format not in get_args(ExportFormat):
            raise DataValidationError(
                f"export_format must be one of {get_args(ExportFormat)}, got {self.export_format!r}"
            )

        if self.capture_screenshots and not (self.screenshot_path or "").strip():
            raise DataValidationError(
                "screenshot_path is required when capture_screenshots is True"
            )

        # --- single-choice settings validation (each optional; None = leave as-is) ---
        self._validate_choice(
            "reporting_method", self.reporting_method, ReportingMethod
        )
        self._validate_choice(
            "gst_calculation_period", self.gst_calculation_period, GstCalculationPeriod
        )
        self._validate_choice(
            "gst_accounting_method", self.gst_accounting_method, GstAccountingMethod
        )
        self._validate_choice("paygw_period", self.paygw_period, PaygWithholdingPeriod)
        self._validate_choice(
            "payg_income_tax_method", self.payg_income_tax_method, PaygIncomeTaxMethod
        )

        # --- obligations: dict[obligation_key, bool] or None ---
        if self.additional_obligations is not None:
            if not isinstance(self.additional_obligations, dict):
                raise DataValidationError(
                    "additional_obligations must be a dict[obligation, bool], or None"
                )
            valid = set(get_args(Obligation))
            unknown = set(self.additional_obligations) - valid
            if unknown:
                raise DataValidationError(
                    f"additional_obligations contains unknown keys {sorted(unknown)}; "
                    f"valid: {sorted(valid)}"
                )
            non_bool = [
                k
                for k, v in self.additional_obligations.items()
                if not isinstance(v, bool)
            ]
            if non_bool:
                raise DataValidationError(
                    "additional_obligations values must be bool (True/False); "
                    f"non-bool value(s) for {sorted(non_bool)}"
                )

            # deferred_gst is only available when GST calculation period is monthly.
            # We can only catch the EXPLICIT conflict here (period set to non-monthly);
            # when gst_calculation_period is None ("leave as-is") we cannot know the
            # client's current period until the panel renders, so that case is handled
            # at runtime (warned + skipped) in configure_report_settings.
            if (
                "deferred_gst" in self.additional_obligations
                and self.gst_calculation_period is not None
                and self.gst_calculation_period != "monthly"
            ):
                raise DataValidationError(
                    "deferred_gst is only available when gst_calculation_period='monthly' "
                    f"(got gst_calculation_period={self.gst_calculation_period!r}). Set it "
                    "to 'monthly', or pass gst_calculation_period=None if the client is "
                    "already monthly."
                )

    @staticmethod
    def _validate_choice(field_name: str, value, literal_type) -> None:
        """Value must be None (leave as-is) or one of the literal's allowed options."""
        if value is None:
            return
        allowed = get_args(literal_type)
        if value not in allowed:
            raise DataValidationError(
                f"{field_name} must be one of {allowed} or None, got {value!r}"
            )

    @property
    def format_radio_locator(self) -> str:
        """The export-panel radio locator for the chosen format."""
        return _EXPORT_FORMATS[self.export_format][0]

    @property
    def saved_extension(self) -> str:
        """The extension Xero produces for the chosen format (source of truth)."""
        return _EXPORT_FORMATS[self.export_format][1]

    @property
    def dest_path(self) -> str:
        return common.build_dest_path(
            self.download_directory, self.report_file_name, self.saved_extension
        )

    def summary_lines(self) -> list[str]:
        def _shown(value) -> str:
            return "(leave as-is)" if value is None else str(value)

        if not self.configure_settings:
            obligations = "(settings disabled)"
        elif self.additional_obligations is None:
            obligations = "(leave as-is)"
        elif not self.additional_obligations:
            obligations = "(none specified)"
        else:
            obligations = ", ".join(
                f"{k}={'on' if v else 'off'}"
                for k, v in self.additional_obligations.items()
            )

        rows = {
            "Statement Period": self.period,
            "Financial Year": self.period.fiscal_year_label,
            "Export Format": self.export_format,
            "Saved Extension": self.saved_extension,
            "Download Directory": self.download_directory,
            "Report File Name": self.report_file_name,
            "Window Title": self.window_title,
            "Capture Screenshots": self.capture_screenshots,
            "Screenshot Path": (
                self.screenshot_path if self.capture_screenshots else "(disabled)"
            ),
            "Configure Settings": self.configure_settings,
            "Reporting Method": _shown(self.reporting_method),
            "GST Calculation Period": _shown(self.gst_calculation_period),
            "GST Accounting Method": _shown(self.gst_accounting_method),
            "PAYG Withholding Period": _shown(self.paygw_period),
            "PAYG Income Tax Method": _shown(self.payg_income_tax_method),
            "Additional Obligations": obligations,
        }
        width = max(map(len, rows))
        return [f"{label:<{width}} : {value}" for label, value in rows.items()]


def download_activity_statement_report(
    browser, request: ActivityStatementRequest
) -> str:
    """
    Download an Activity Statement report from Xero Blue.

    Steps, in order (each returns; none calls the next):
        STEP 1 - reach the report page (clicking through the ATO lodge wizard if shown)
        STEP 2 - configure the BAS settings panel (best-effort; skipped if absent)
        STEP 3 - select the statement period within its financial year
        STEP 4 - export to the chosen format, and verify the saved file

    Returns:
        str: The full path of the saved report (directory + filename + extension).

    Raises:
        Re-raises any exception after ``ProcessLogger`` has logged it. Invalid
        inputs raise ``DataValidationError``; a period/control that cannot be
        found raises ``ElementNotFoundError``; a missing Export control or a
        settings panel that fails to render raises ``DataExtractionError``; a
        file that fails to save raises ``DownloadError``.
    """
    with ProcessLogger("Xero Blue Download Activity Statement Report", logger):
        for line in request.summary_lines():
            logger.info(line)

        logger.info("STEP 1: Navigating to Activity Statement report page...")
        navigate_to_report_page(browser, request)
        logger.info("STEP 1 COMPLETED: report page reached")

        logger.info("STEP 2: Configuring BAS settings (best-effort)...")
        configure_report_settings(browser, request)
        logger.info("STEP 2 COMPLETED: settings phase finished")

        logger.info(
            f"STEP 3: Selecting statement period '{request.period}' "
            f"(financial year '{request.period.fiscal_year_label}')..."
        )
        select_statement_period(browser, request)
        logger.info("STEP 3 COMPLETED: statement period selected")

        logger.info(f"STEP 4: Exporting report as '{request.export_format}'...")
        _dest = run_report_export(browser, request)
        logger.info("STEP 4 COMPLETED: report exported and file saved")
        return _dest


def navigate_to_report_page(browser, request: ActivityStatementRequest) -> None:
    """Reach the report page, clicking through the ATO lodge wizard if present.
    Does NOT select a period (that is a separate step)."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    logger.info("Checking if the ATO lodge dialog is present...")
    if browser.does_page_contain_element(config.ASR_LODGE_BUTTON, timeout=timeout):
        logger.info("ATO lodge dialog detected - proceeding through wizard steps")
        browser.click_element(config.ASR_LODGE_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_GO_TO_STATEMENT_BUTTON, timeout=timeout)
        # Steps 1 and 2 of the wizard share the same Next locator; this relies on
        # Xero re-rendering the button between steps. If both ever coexist in the
        # DOM, give each a more specific locator.
        browser.click_element(config.ASR_WIZARD_NEXT_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_WIZARD_NEXT_BUTTON, timeout=timeout)
        browser.click_element(config.ASR_WIZARD_OK_BUTTON, timeout=timeout)
        logger.info("Lodge wizard completed")
    else:
        logger.info(
            "ATO lodge dialog not present - proceeding directly to period selection"
        )


def configure_report_settings(browser, request: ActivityStatementRequest) -> None:
    """Open the BAS settings panel and apply the requested selections, then save.

    Best-effort at the entry point: if ``configure_settings`` is False, or the
    Settings button is not on the page, this returns without doing anything. Once
    the panel is open, a panel that fails to render raises; an individual control
    that cannot be found is warned about and skipped (same as P&L show-options).

    ORDER IS LOAD-BEARING: the single-choice controls are applied BEFORE the
    obligation checkboxes on purpose - setting GST calculation period to Monthly
    is what makes the Deferred GST obligation checkbox appear. Do not reorder.

    Each setting is applied only when non-None, and only when it actually needs
    changing - state is read via a "checked" locator (does_page_contain_element
    on a CSS ':checked' selector), exactly as the Profit and Loss report reads
    its show-options."""
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    if not request.configure_settings:
        logger.info("configure_settings=False - skipping settings phase")
        return

    logger.info("Checking if the Settings button is present...")
    if not browser.does_page_contain_element(
        config.ASR_SETTINGS_BUTTON, timeout=timeout
    ):
        logger.info("Settings button not present - skipping settings phase")
        return

    logger.info("Opening the BAS settings panel...")
    browser.click_element(config.ASR_SETTINGS_BUTTON, timeout=timeout)

    # Confirm the panel actually rendered before touching any control.
    if not browser.does_page_contain_element(
        config.ASR_SETTINGS_SAVE_BUTTON, timeout=timeout
    ):
        raise DataExtractionError(
            "BAS settings panel did not render ('Save & continue' not found)"
        )

    # Single-choice controls (radio / toggle groups). Applied BEFORE obligations
    # so that (e.g.) setting GST period = Monthly reveals the Deferred GST box.
    _apply_single_choice(
        browser,
        "Reporting method",
        request.reporting_method,
        _REPORTING_METHOD_AIDS,
        timeout,
    )
    _apply_single_choice(
        browser,
        "GST calculation period",
        request.gst_calculation_period,
        _GST_PERIOD_AIDS,
        timeout,
    )
    _apply_single_choice(
        browser,
        "GST accounting method",
        request.gst_accounting_method,
        _GST_ACCOUNTING_AIDS,
        timeout,
    )
    _apply_single_choice(
        browser,
        "PAYG withholding period",
        request.paygw_period,
        _PAYGW_PERIOD_AIDS,
        timeout,
    )
    _apply_single_choice(
        browser,
        "PAYG income tax method",
        request.payg_income_tax_method,
        _PAYG_METHOD_AIDS,
        timeout,
    )

    # Additional obligations (checkboxes). None => leave every checkbox untouched;
    # only the keys present in the dict are driven, each to its bool. Any obligation
    # not in the dict is left exactly as the client has it.
    if request.additional_obligations is not None:
        rendered = {
            k: ("on" if v else "off")
            for k, v in request.additional_obligations.items()
        }
        logger.info(
            f"Applying {len(request.additional_obligations)} obligation setting(s): {rendered}"
        )
        for key, desired in request.additional_obligations.items():
            hint = _DEFERRED_GST_HINT if key == "deferred_gst" else None
            _apply_checkbox(
                browser,
                f"Obligation '{key}'",
                _OBLIGATION_AIDS[key],
                desired,
                timeout,
                hint=hint,
            )
    else:
        logger.info("Additional obligations left as-is (None)")

    logger.info("Saving settings ('Save & continue')...")
    browser.click_element(config.ASR_SETTINGS_SAVE_BUTTON, timeout=timeout)
    logger.info("Settings saved")


def _apply_single_choice(
    browser, label: str, value, aid_map: dict[str, str], timeout: int
) -> None:
    """Select one option in a radio/toggle group by its friendly value.

    Locate the control, read its checked state via a 'checked' locator, and click
    only if it is not already selected. No-op when value is None (leave as-is).
    If the control is not found, logs a warning and returns without failing."""
    if value is None:
        logger.info(f"{label}: left as-is (None)")
        return

    aid = aid_map[value]  # membership already validated in __post_init__
    exists_locator = config.ASR_SETTINGS_OPTION_EXISTS_TPL.format(aid=aid)
    checked_locator = config.ASR_SETTINGS_OPTION_CHECKED_TPL.format(aid=aid)
    click_locator = config.ASR_SETTINGS_OPTION_CLICK_TPL.format(aid=aid)

    if not browser.does_page_contain_element(exists_locator, timeout=timeout):
        logger.warning(f"{label}: option '{value}' not found on the panel - skipping")
        return

    if browser.does_page_contain_element(checked_locator, timeout=timeout):
        logger.info(f"{label}: '{value}' already selected - skipping")
        return

    browser.click_element(click_locator, timeout=timeout)
    logger.info(f"{label}: selected '{value}'")


def _apply_checkbox(
    browser, label: str, aid: str, desired: bool, timeout: int, *, hint: str | None = None
) -> None:
    """Ensure a checkbox matches the desired state, clicking only if it differs.

    Read the checked state via a 'checked' locator, and click only when the current
    state differs from the requested one. If the control is not found, logs a
    warning (with ``hint`` appended when given) and returns without failing."""
    exists_locator = config.ASR_SETTINGS_OPTION_EXISTS_TPL.format(aid=aid)
    checked_locator = config.ASR_SETTINGS_OPTION_CHECKED_TPL.format(aid=aid)
    click_locator = config.ASR_SETTINGS_OPTION_CLICK_TPL.format(aid=aid)

    if not browser.does_page_contain_element(exists_locator, timeout=timeout):
        message = f"{label}: checkbox not found on the panel - skipping"
        if hint:
            message += f" ({hint})"
        logger.warning(message)
        return

    currently_checked = browser.does_page_contain_element(
        checked_locator, timeout=timeout
    )
    if currently_checked == desired:
        logger.info(
            f"{label}: already {'checked' if desired else 'unchecked'} - skipping"
        )
        return

    browser.click_element(click_locator, timeout=timeout)
    logger.info(f"{label}: set to {'checked' if desired else 'unchecked'}")


def select_statement_period(browser, request: ActivityStatementRequest) -> None:
    """Create a new statement and select the requested period: open the year
    selector, pick the FY range that contains the period, pick the period, then
    open the Transactions tab."""
    period = request.period
    timeout = common.DEFAULT_ELEMENT_TIMEOUT

    browser.click_element(config.ASR_CREATE_NEW_STATEMENT_BUTTON, timeout=timeout)
    logger.info("Clicked 'Create new statement'")

    # Periods in other financial years are not rendered until that year is
    # selected, so open the year selector (back button) and pick the tax year first.
    browser.click_element(config.ASR_YEAR_SELECTOR_BUTTON, timeout=timeout)
    logger.info("Opened financial year selector")

    browser.click_element(
        config.ASR_TAX_YEAR_TPL.format(tax_year=period.tax_year), timeout=timeout
    )
    logger.info(
        f"Selected tax year: '{period.fiscal_year_label}' (id {period.tax_year})"
    )

    browser.click_element(
        config.ASR_STATEMENT_PERIOD_TPL.format(month=period.month, year=period.year),
        timeout=timeout,
    )
    logger.info(f"Selected statement period: '{period}'")

    browser.click_element(config.ASR_TRANSACTIONS_TAB, timeout=timeout)
    logger.info("Opened the 'Transactions' tab - statement details visible")


def run_report_export(browser, request: ActivityStatementRequest) -> str:
    """Open the export panel, pick the format radio, confirm, save, and verify."""
    # The statement has rendered by now (period selected). Capture it before we
    # touch the export panel. Best-effort: BAS has no stable render-confirmation
    # element, so this is taken right after selection without a render gate.
    common.capture_report_screenshot(
        browser,
        request.screenshot_path,
        "activity_statement",
        "rendered",
        enabled=request.capture_screenshots,
    )

    if not browser.does_page_contain_element(
        config.ASR_EXPORT_DROPDOWN_BUTTON, timeout=common.DEFAULT_ELEMENT_TIMEOUT
    ):
        raise DataExtractionError("'Export' control not found - cannot export report")

    logger.info("Opening the export panel...")
    browser.click_element(
        config.ASR_EXPORT_DROPDOWN_BUTTON, timeout=common.EXPORT_TIMEOUT
    )

    logger.info(f"Selecting '{request.export_format}' format...")
    browser.click_element(request.format_radio_locator, timeout=common.EXPORT_TIMEOUT)

    logger.info("Confirming export...")
    browser.click_element(
        config.ASR_EXPORT_CONFIRM_BUTTON, timeout=common.EXPORT_TIMEOUT
    )
    logger.info("Export triggered. Waiting for the Windows Save As dialog...")

    dest_path = request.dest_path
    logger.info(f"Handling file save dialog - saving to: '{dest_path}'")
    handle_chrome_save_as_dialog(
        window_locator=common.chrome_window_locator(request.window_title),
        dest_path=dest_path,
    )

    common.verify_saved_file(dest_path)
    logger.info(f"File successfully saved: '{dest_path}'")
    return dest_path


MONTH_NAMES = {3: "March", 6: "June", 9: "September", 12: "December"}


def statement_period(d: date) -> tuple[str, int]:
    """
    Determine the quarterly statement period that a given date falls into.

    Statement periods close at the end of March, June, September, and
    December. This function returns the name and year of the most recent
    such period that has closed on or before the given date's month.

    For January and February (before the first quarter closes in a new
    year), the date is considered to fall within the December statement
    period of the *previous* year.

    Args:
        d: The date to evaluate. A datetime.datetime will be converted to
            a date automatically.

    Returns:
        A tuple of (month_name, year) representing the statement period,
        e.g. ("June", 2024).

    Raises:
        TypeError: If `d` is not a datetime.date (or datetime.datetime).

    Examples:
        >>> statement_period(date(2024, 4, 15))
        ('March', 2024)
        >>> statement_period(date(2024, 12, 1))
        ('December', 2024)
        >>> statement_period(date(2024, 1, 10))
        ('December', 2023)
    """
    if isinstance(d, datetime):
        d = d.date()
    elif not isinstance(d, date):
        raise TypeError(f"Expected datetime.date, got {type(d).__name__}")

    candidates = [m for m in MONTH_NAMES if m <= d.month]
    if candidates:
        return (MONTH_NAMES[max(candidates)], d.year)
    return ("December", d.year - 1)  # January / February