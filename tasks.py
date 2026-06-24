
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


logger = get_logger(__name__)

@task
def impact_main() -> None:

#TODO: code below
    insight_url = config.get("InsightLoginUrl", None)
    insight_secret = config.get("InsightSecret", None)

    creds = get_credential("SSP_insight")
    secret = get_credential("InsightSecret")
    
    if (creds is None or not creds.username or not creds.password):
        raise ValueError("Credentials are invalid")
    
    if (secret is None or not secret.username or not secret.password):
        raise ValueError("Secret is invalid")

    browser = SeleniumBrowser(debugger_address="localhost:9222", 
                             hide_automation_banner=False)
    browser = SeleniumBrowser(
        chrome_prefs={
            "download.prompt_for_download": True,
        }
    )

    insight_secret = secret.password

    try:
        with ProcessLogger("Insight Login", logger):
            insight_login(browser, 
                          creds.username, 
                          creds.password,
                          insight_secret, 
                          insight_url)
     
    except Exception:
        logger.exception("Login to Insight failed")

    print ("breakpoint")
   
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




