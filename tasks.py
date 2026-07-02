
import json
from robocorp.tasks import task
from datetime import date
from dataclasses import replace
from RPA.MFA import MFA

# TODO: remove logging code below once development is over
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
# End of logging code to remove

from iaa_rpa_utils.logger import get_logger, ProcessLogger
from iaa_rpa_utils.browser import SeleniumBrowser
from iaa_rpa_utils.credentials import get_credential
#from RPA_process.Client.Impact.process import xero_login
# from iaa_rpa_xb.xero_login import xero_blue_login
# from iaa_rpa_xero_blue.xero_blue_download_bank_reconciliation_report import xero_blue_download_bank_reconciliation_report
# from iaa_rpa_xb.xero_blue_navigate_to_reports_dashboard import xero_blue_navigate_to_reports_dashboard
# from iaa_rpa_xb.xero_blue_navigate_to_report import xero_blue_navigate_to_report
# from iaa_rpa_xero_blue.add_ons.xero_blue_get_bank_reconciliation_accounts import get_bank_reconciliation_accounts
#from iaa_rpa_xb.add_ons.xero_navigate_to_report_wrapper import navigate_to_xero_report_wrapper
# from iaa_rpa_xero_blue.xero_blue_downlaod_aged_payables_detail_report import xero_blue_download_aged_payables_details_report
# from iaa_rpa_xero_blue.xero_blue_download_aged_receivables_detail_report import xero_blue_download_aged_receivables_detail_report
# from iaa_rpa_xero_blue.xero_blue_download_gst_reconciliation_report import xero_blue_download_gst_reconciliation_report
# from iaa_rpa_xero_blue.xero_blue_download_general_ledger_detail_report import xero_blue_download_general_ledger_details_report
# from iaa_rpa_xero_blue.xero_blue_download_trial_balance_report import xero_blue_download_trial_balance_report
# from iaa_rpa_xero_blue.xero_blue_download_activity_statement_report import xero_blue_download_activity_statement_report
from iaa_rpa_xero_blue.login import xero_blue_login
from iaa_rpa_xero_blue.navigation import navigate_to_all_reports_page, navigate_to_dashboard_page, navigate_to_report_page
from iaa_rpa_xero_blue.logout import xero_blue_logout


from iaa_rpa_xero_blue.download_activity_statement import (
        StatementPeriod,
        ActivityStatementRequest,
        download_activity_statement_report,
    )
#from iaa_rpa_xero_blue.xero_blue_switch_client import xero_blue_switch_client
#from iaa_rpa_xero_blue.add_ons.switch_client import xero_blue_switch_client
from iaa_rpa_xero_blue.download_trial_balance import (
        TrialBalanceRequest,
        download_trial_balance_report,
    )
from iaa_rpa_xero_blue.download_gst_reconciliation import (
    GstReconciliationRequest,
    download_gst_reconciliation_report,
)
from iaa_rpa_xero_blue.download_general_ledger_detail import (
    GeneralLedgerDetailRequest,
    download_general_ledger_detail_report,
)

from iaa_rpa_xero_blue.download_bank_reconciliation import (
    BankReconciliationRequest,
    list_all_bank_accounts,
    download_bank_reconciliation_report,
)

from iaa_rpa_xero_blue.download_aged_payables_detail import (
    AgedPayablesRequest,
    download_aged_payables_detail_report,
)
from iaa_rpa_xero_blue.download_aged_receivables_detail import (
    AgedReceivablesRequest,
    download_aged_receivables_detail_report
)

from iaa_rpa_xero_blue.download_activity_statement import (
    ActivityStatementRequest,
    StatementPeriod,
    download_activity_statement_report,
)





logger = get_logger(__name__)

@task
def impact_main() -> None:

    DOWNDIR = r"C:\\Users\\VirtualAssistant\\Downloads\\xero"


    FY = 2025                 # financial year (int)
    

    # reports_to_process = [
    #     {"name": "Activity Statement", "fn": download_activity_statement_report, "request": ActivityStatementRequest(
    #         period=StatementPeriod("September", 2025),   # StatementPeriod, not a tuple
    #         download_directory=DOWNDIR,
    #         report_file_name="Activity Statement",
    #     ), "args": None},

    #     # ---- Aged Receivables Detail  ("Due Date" / "Invoice Date") ------------
    #     {"name": "Aged Receivables Detail", "fn": download_aged_receivables_detail_report, "request": AgedReceivablesRequest(
    #         financial_year=FY,
    #         aging_by="Due Date",
    #         download_directory=DOWNDIR,
    #         report_file_name="Aged Receivables Detail",
    #         # end_date=date(2025, 5, 15),   # optional datetime.date; omit to use 30 Jun {FY}
    #         # add_gst_column=True,
    #     ), "args": None},

    #     # ---- Aged Payables Detail  ("Due Date" / "Invoice Date") ---------------
    #     {"name": "Aged Payables Detail", "fn": download_aged_payables_detail_report, "request": AgedPayablesRequest(
    #         financial_year=FY,
    #         aging_by="Due Date",
    #         download_directory=DOWNDIR,
    #         report_file_name="Aged Payables Detail",
    #         # end_date=date(2025, 5, 15),   # optional datetime.date; omit to use 30 Jun {FY}
    #         # add_gst_column=True,
    #     ), "args": None},

    #     # ---- General Ledger Detail  (datetime.date; accounting_method) ---------
    #     {"name": "General Ledger Detail", "fn": download_general_ledger_detail_report, "request": GeneralLedgerDetailRequest(
    #         download_directory=DOWNDIR,
    #         report_file_name="General Ledger Detail",
    #         start_date=date(2024, 7, 1),
    #         end_date=date(2025, 6, 30),
    #         # financial_year=FY,        # alternative to start/end; either date can fall back to FY
    #         accounting_method="Cash",   # "Cash" (default) or "Accrual"
    #     ), "args": None},

    #     # ---- Trial Balance  ("as at" end_date only) ----------------------------
    #     {"name": "Trial Balance", "fn": download_trial_balance_report, "request": TrialBalanceRequest(
    #         download_directory=DOWNDIR,
    #         report_file_name="Trial Balance",
    #         end_date=date(2025, 6, 30),
    #         # financial_year=FY,        # alternative to end_date
    #         accounting_method="Cash",   # "Cash" (default) or "Accrual"
    #     ), "args": None},

    #     # ---- GST Reconciliation  (datetime.date; excel -> .xls, or pdf) --------
    #     {"name": "GST Reconciliation", "fn": download_gst_reconciliation_report, "request": GstReconciliationRequest(
    #         download_directory=DOWNDIR,
    #         report_file_name="GST Reconciliation",
    #         start_date=date(2024, 7, 1),
    #         end_date=date(2025, 6, 30),
    #         # financial_year=FY,
    #         # export_format="pdf",      # "excel" (default, saves .xls) or "pdf"
    #     ), "args": None},

    #     # ---- Bank Reconciliation -----------------------------------------------
    #     # ALL accounts: bank_account is a placeholder (the runner overrides it per
    #     # account); args="all" tells the runner to enumerate and loop.
    #     {"name": "Bank Reconciliation", "fn": download_bank_reconciliation_report, "request": BankReconciliationRequest(
    #         bank_account="(all accounts)",   # placeholder; replaced per account by the runner
    #         download_directory=DOWNDIR,
    #         report_file_name="Bank Reconciliation",
    #         start_date=date(2024, 7, 1),
    #         end_date=date(2025, 6, 30),
    #     ), "args": "all"},
    #     # Or specific accounts:  "args": ["1-0100 - Impact Operating Account", "1-1000 - Cheque account"]

    # ]

#TODO: code below
    xero_url = "https://go.xero.com/Dashboard/default.aspx"
    payroll_url = "https://payroll.xero.com"

    creds = get_credential("xero")
    secret = get_credential("xero_secret")
    
    if (creds is None or not creds.username or not creds.password):
        raise ValueError("Credentials are invalid")
    
    if (secret is None or not secret.username or not secret.password):
        raise ValueError("Secret is invalid")

    mfa = MFA()
    otp_code = mfa.get_time_based_otp(secret.password)
    
    browser = SeleniumBrowser(
        use_existing_profile=True,
        profile_directory="Default",   # or "Profile 1" — whichever has Xero logged in
        copy_profile_to_temp=True,
    )

    

    try:
        with ProcessLogger("Login to Xero", logger):
            xero_blue_login(
                browser=browser,
                email=creds.username,
                password=creds.password,
                otp=otp_code,
                xero_blue_url=xero_url,
                payroll_url=payroll_url
            )
    except Exception:
         logger.exception("Login to Xero failed")
    

    navigate_to_all_reports_page(browser)
    navigate_to_dashboard_page(browser)
    navigate_to_report_page(browser, "General Ledger Detail")

    xero_blue_logout(browser)


    # try:
    #     with ProcessLogger("Insight Login", logger):
    #         xero_blue_login(
    #             browser,
    #             creds.username,
    #             creds.password,
    #             xero_url,
    #             payroll_url,
    #             xero_secret,
    #             max_retry=1,
    #             is_authentication_code_is_entered=False,
    #             is_user_logged_in_to_xero=False  
    #         )
      
    # except Exception:
    #     logger.exception("Login to Xero failed")


    # try:
    #     with ProcessLogger("Report page", logger):

    #         #request = XeroClientSwitchRequest(account_name="Heyday Furniture Pty. Ltd")
    #         xero_blue_switch_client(browser, "R & R FARAH PTY LTD")
    #         # xero_blue_switch_client(
    #         #     browser,
    #         #     "Heyday Furniture Pty. Ltd"
    #         # )

    # except Exception:
    #     logger.exception("Navigation to report pages failed")

    # navigate_to_xero_report_wrapper(
    #     browser=browser,
    #     report_name='General Ledger Detail', 
    #     title="Reports"
    #     )

    # for report in reports_to_process:
    #     navigate_to_xero_report_wrapper(
    #         browser=browser,
    #         report_name=report["name"],
    #         title="Reports",
    #     )

    #     fn = report["fn"]
    #     args = report.get("args")  # matches the config key

    #     # Bank Reconciliation multi-account fan-out
    #     if report["name"] == "Bank Reconciliation" and args is not None:
    #         accounts = list_all_bank_accounts(browser) if args == "all" else args
    #         if not accounts:
    #             logger.warning(f"{report['name']}: no bank accounts to process — skipping")
    #             continue
    #         base = report["request"]
    #         for account in accounts:
    #             per_account = replace(
    #                 base,
    #                 bank_account=account,
    #                 report_file_name=f"{base.report_file_name}_{account}",
    #             )
    #             fn(browser, per_account)
    #         continue  # done with this report — do NOT fall through

    #     # Everything else (and single-account bank rec): one call
    #     fn(browser, report["request"])

    print ("breakpoint")
    # request = ActivityStatementRequest(
    #     period=StatementPeriod("September", 2025),   # the period as it appears in Xero
    #     download_directory=r"C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #     report_file_name="BAS_Q3_2025",
    #     # window_title="Activity Statement",      # optional, has a default
    #     # extension="xlsx",                        # optional, has a default
    # )
    # download_activity_statement_report(browser, request)



    # try:
    #     with ProcessLogger("Report page", logger):
    #         download_activity_statement_report(
    #             browser,
    #             xero_statement_period= "June 2025",
    #             xero_financial_year = "2024/25",
    #             window_title = "Activity Statement",
    #             xero_download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             xero_report_file_name = "ACME_Activity_Statement_2026",  
    #             #xero_report_name = "GST Reconciliation",
    #             extension = ".xlsx",
    #         )
            
    # xero_statement_period: str,
    # xero_financial_year: str,
    # window_title: str,
    # xero_download_directory: str,
    # xero_report_file_name: str,
    # extension: str,

    # except Exception:
    #     logger.exception("Navigation to report pages failed")



    # try:
    #     with ProcessLogger("Report page", logger):
    #         xero_blue_download_trial_balance_report(
    #             browser,
    #             xero_client_name = "ACME Corp",
    #             xero_end_date = "01 06 2026",
    #             xero_financial_year = "2025",
    #             is_add_gst_column = False,
    #             window_title = "Trial Balance",
    #             download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name = "ACME_Trial_Balance_2026",  
    #             #xero_report_name = "GST Reconciliation",
    #             extension = ".xlsx",
    #         )
            
    # except Exception:
    #     logger.exception("Navigation to report pages failed")  



    # try:
    #     with ProcessLogger("Report page", logger):   
    #         xero_blue_download_general_ledger_details_report(
    #             browser,
    #             xero_client_name = "ACME Corp",
    #             xero_end_date = "01 06 2026",
    #             xero_financial_year = "2025",
    #             xero_start_date = "01 06 2025",
    #             window_title = "General Ledger Detail",
    #             download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name = "ACME_General_Ledger_Detail_2026",  
    #             #xero_report_name = "GST Reconciliation",
    #             extension = ".xlsx",
    #         )

    # except Exception:
    #      logger.exception("Navigation to report pages failed")  

    # try:
    #     with ProcessLogger("Report page", logger):   
    #         xero_blue_download_gst_reconciliation_report(
    #             browser,
    #             xero_client_name = "ACME Corp",
    #             xero_end_date = "01 06 2026",
    #             xero_financial_year = "",
    #             xero_start_date = "01 06 2025",
    #             window_title = "GST Reconciliation",
    #             download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name = "ACME_GST_Reconciliation_2026",  
    #             xero_report_name = "GST Reconciliation",
    #             extension = ".xls",
    #         )

    # except Exception:
    #      logger.exception("Navigation to report pages failed")
    
    # try:
    #     with ProcessLogger("Report page", logger):   
    #         xero_blue_download_aged_receivablesdetailreport(
    #             browser,
    #             xero_client_name = "ACME Corp",
    #             xero_end_date = "01 06 2026",
    #             xero_financial_year = "",
    #             is_add_gst_column = True,
    #             xero_aging_by = "Due date",
    #             window_title = "Aged Receivables Detail",
    #             download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name = "ACME_Aged_Receivables_Detail_2026",
    #             extension = ".xlsx",
    #         )


    # except Exception:
    #      logger.exception("Navigation to report pages failed")
    
   
    # try:
    #     with ProcessLogger("Report page", logger):   
    #       xero_blue_download_aged_payables_details_report(
    #             browser,
    #             xero_client_name = "ACME Corp",
    #             xero_end_date = "01 06 2026",
    #             xero_financial_year = "",
    #             is_add_gst_column = True,
    #             xero_aging_by = "Due date",
    #             window_title = "Aged Payables Detail",
    #             download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name = "ACME_Aged_Payables_Detail_2026",
    #             extension = ".xlsx",
    #         )

    # except Exception:
    #      logger.exception("Navigation to report pages failed")
    
    
 
    
    
    # try:
    #     with ProcessLogger("Report page", logger):
    #         xero_blue_navigate_to_reports_dashboard(browser)
    # except Exception:
    #     logger.exception("Navigation to report pages failed")

    #button = browser.wait_for_element("xpath://div[@id='report-centre-parent']//span[normalize-space(text())='Aged Payables Detail']")
    #browser.does_page_contain_element()
    #report_button_elements = driver.find_elements(By.XPATH, report_button_xpath)

    #button.click()

    # try:
    #     with ProcessLogger("Report page", logger):
    #         xero_blue_navigate_report(
    #             browser,
    #             xero_blue_report_name = "Bank Reconciliation",
    #             xero_blue_title = "Reports"
    #         )
    # except Exception:
    #     logger.exception("Navigation to report pages failed")



    # bank reconsiliation report
    # try:
    #     with ProcessLogger("Report page", logger):
    #         accounts = get_bank_reconciliation_accounts(browser)
    #         logger.info("accounts: %s", accounts)
    # except Exception:
    #     logger.exception("Navigation to report pages failed")

    # try:
    #     with ProcessLogger("Insight Login", logger):
    #         xero_blue_download_bank_reconciliation_report(
    #             browser=browser,
    #             client_name="ACME Corp",
    #             xero_end_date="24 06 2026",
    #             xero_financial_year="",
    #             xero_start_date="1 06 2026",
    #             xero_bank_account="1-0101 - Impact Saving Account",
    #             window_title="Xero | Bank Reconciliation",
    #             download_directory="C:\\Users\\VirtualAssistant\\Downloads\\xero",
    #             report_file_name="ACME_Bank_Rec_2026",
    #             xero_report_name="Bank Reconciliation",
    #             is_no_bank_accounts=False,
    #             extension=".xlsx"
    #         )
    # except Exception:
    #     logger.exception("Login to Xero failed")
    
  
    
    
    

   
      # try:
    #     with ProcessLogger("", logger):

    # except Exception:
    #     logger.exception("")


    # try:
    #     with ProcessLogger("Navigating to client record", logger):
    #         insight_goto_client_page(browser, "881564")
    # except:
    #     logger.exception("Navigation to client record failed")

    # try:
    #     with ProcessLogger("Navigating to invoice record", logger):
    #         insight_goto_policy_page(browser, "882704", "5256093")
    # except:
    #     logger.exception("Navigation to invoice record failed")
    
    # try:
    #     with ProcessLogger("Creating doc from template", logger):
    #         insight_generate_doc_from_template(browser, "CBN - Pre Renewal Client Letter Small No Visit")
    # except:
    #     logger.exception("Creation of doc from tem failed")
    
    # try:
    #     with ProcessLogger("Document upload", logger):
    #         insight_upload_document(browser, "")
    # except:
    #     logger.exception("Document upload failed")

    # insight_upload_document

    # try:
    #     with ProcessLogger("Insight logout", logger):
    #         insight_logout(browser)
    # except:
    #     logger.exception("Logout from Insight failed")
    

    # word_path = get_directory_path(r"c:\Users\AlexanderZanosov\OneDrive - Ioppolo Assoc\Customers\SSP", 
    #                                "templates")
    # word_file = get_file_name("Private Motor Insurance", "23A3037514")
    # full_word_path = word_path + "\\" + word_file

    # pdf_path = get_directory_path(r"c:\Users\AlexanderZanosov\OneDrive - Ioppolo Assoc\Customers\SSP", 
    #                                "pdf")
    # pdf_file = get_file_name("Private Motor Insurance","23A3037514", "pdf")
    # full_pdf_path =  pdf_path + "\\" + pdf_file

    # try:
    #     with ProcessLogger("Word processing", logger):
    #         process_word(full_word_path, full_pdf_path, "23A3037514", "Private Motor Insurance")
    # except:
    #     logger.exception("Word processing failed")




