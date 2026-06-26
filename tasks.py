
import json
from robocorp.tasks import task

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
from iaa_rpa_xero_blue.xero_login import xero_blue_login
from iaa_rpa_xero_blue.xero_blue_download_bank_reconciliation_report import xero_blue_download_bank_reconciliation_report
from iaa_rpa_xero_blue.xero_blue_navigate_to_reports_dashboard import xero_blue_navigate_to_reports_dashboard
from iaa_rpa_xero_blue.xero_blue_navigate_to_report import xero_blue_navigate_to_report
from iaa_rpa_xero_blue.add_ons.xero_blue_get_bank_reconciliation_accounts import get_bank_reconciliation_accounts
from iaa_rpa_xero_blue.add_ons.xero_navigate_to_report_wrapper import navigate_to_xero_report_wrapper
from iaa_rpa_xero_blue.xero_blue_downlaod_aged_payables_detail_report import xero_blue_download_aged_payables_details_report
from iaa_rpa_xero_blue.xero_blue_download_aged_receivables_detail_report import xero_blue_download_aged_receivables_detail_report
from iaa_rpa_xero_blue.xero_blue_download_gst_reconciliation_report import xero_blue_download_gst_reconciliation_report
from iaa_rpa_xero_blue.xero_blue_download_general_ledger_detail_report import xero_blue_download_general_ledger_details_report
from iaa_rpa_xero_blue.xero_blue_download_trial_balance_report import xero_blue_download_trial_balance_report
from iaa_rpa_xero_blue.xero_blue_download_activity_statement_report import xero_blue_download_activity_statement_report
from iaa_rpa_xero_blue.add_ons.download_activity_statement_report import download_activity_statement_report



logger = get_logger(__name__)

@task
def impact_main() -> None:

#TODO: code below
    xero_url = "https://go.xero.com/Dashboard/default.aspx"
    payroll_url = "https://payroll.xero.com"

    creds = get_credential("xero")
    secret = get_credential("xero_secret")
    
    if (creds is None or not creds.username or not creds.password):
        raise ValueError("Credentials are invalid")
    
    if (secret is None or not secret.username or not secret.password):
        raise ValueError("Secret is invalid")

    
    browser = SeleniumBrowser(
        use_existing_profile=True,
        profile_directory="Default",   # or "Profile 1" — whichever has Xero logged in
        copy_profile_to_temp=True,
    )

    xero_secret = secret.password

    try:
        with ProcessLogger("Insight Login", logger):
            xero_blue_login(
                browser,
                creds.username,
                creds.password,
                xero_url,
                payroll_url,
                xero_secret,
                max_retry=1,
                is_authentication_code_is_entered=False,
                is_user_logged_in_to_xero=False  
            )
      
    except Exception:
        logger.exception("Login to Xero failed")


    navigate_to_xero_report_wrapper(
        browser=browser,
        report_name='Activity Statement', 
        title="Reports"
        )


    try:
        with ProcessLogger("Report page", logger):
            download_activity_statement_report(
                browser,
                xero_statement_period= "June 2025",
                xero_financial_year = "2024/25",
                window_title = "Activity Statement",
                xero_download_directory ="C:\\Users\\VirtualAssistant\\Downloads\\xero",
                xero_report_file_name = "ACME_Activity_Statement_2026",  
                #xero_report_name = "GST Reconciliation",
                extension = ".xlsx",
            )
            
    # xero_statement_period: str,
    # xero_financial_year: str,
    # window_title: str,
    # xero_download_directory: str,
    # xero_report_file_name: str,
    # extension: str,

    except Exception:
        logger.exception("Navigation to report pages failed")



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
    
    
    print ("breakpoint")
    
    
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




