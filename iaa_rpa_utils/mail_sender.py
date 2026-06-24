import base64
import requests

from .logger import setup_logger
from .exceptions import EmailNotificationError, ConfigurationError

from pathlib import Path


logger = setup_logger(__name__)

def send_email(EmailConfig: dict, sender: str, to_addresses: str | tuple |list, cc_addresses: str | tuple |list, subject: str, body: str, attachment_path: str | list[str] | None = None):
    """
    Sends an email using the Microsoft Graph API.
    
    Args:
        EmailConfig: Dictionary containing email configuration
        sender: Email address of the sender
        to_addresses: Recipient email address(es) as string, tuple, or list
        cc_addresses: CC recipient email address(es) as string, tuple, or list
        subject: Email subject line
        body: HTML email body content
        attachment_path: Optional path to file attachment
        
    Raises:
        EmailNotificationError: If email sending fails
        ConfigurationError: If email configuration is missing or invalid
    """


    
    if isinstance(to_addresses, str):
        to_addresses = [email.strip() for email in to_addresses.split(',')]
    elif isinstance(to_addresses, tuple):
        to_addresses = list(to_addresses)
        
    if isinstance(cc_addresses, str) and cc_addresses.strip() != "":
        if cc_addresses.strip() == "":
            cc_addresses = None
        else:
            cc_addresses = [email.strip() for email in cc_addresses.split(',')]
    elif isinstance(cc_addresses, tuple):
        cc_addresses = list(cc_addresses)
    else:
        cc_addresses = None

    graph_api_endpoint = 'https://graph.microsoft.com/v1.0'
    email_endpoint = f'{graph_api_endpoint}/users/{sender}/sendMail'

    try:
        tenant_id = EmailConfig.get("TenantId")
        client_id = EmailConfig.get("ClientId")
        client_secret = EmailConfig.get("ClientSecret")
        
        if not all([tenant_id, client_id, client_secret]):
            raise ConfigurationError("Missing required email configuration: TenantId, ClientId, or ClientSecret")
            
    except Exception as e:
        logger.error(f"Failed to retrieve email configuration: {e}")
        raise ConfigurationError(f"Email configuration error: {e}") from e
    
    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default'
    }
    
    try:
        token_response = requests.post(token_url, data=token_data, timeout=30).json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to request access token: {e}")
        raise EmailNotificationError(f"Failed to authenticate with Microsoft Graph API: {e}") from e    

    if 'access_token' in token_response:
        access_token = token_response['access_token']

        # Create the email message
        email_message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": address
                        }
                    } for address in to_addresses
                ]
            }
        }

        # Add CC recipients if provided
        if cc_addresses and len(cc_addresses) > 0:            
            email_message["message"]["ccRecipients"] = [
                {
                    "emailAddress": {
                        "address": address
                    }
                } for address in cc_addresses
            ]

            

        # Add attachment if provided
        if attachment_path:
            if isinstance(attachment_path, str):
                attachment_path = [attachment_path]
            for path in attachment_path:
                try:
                    with open(path, "rb") as attachment_file:
                        attachment_content = attachment_file.read()
                    encoded_content = base64.b64encode(attachment_content).decode('utf-8')
                    email_message["message"]["attachments"].append(
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": path.split("/")[-1],
                            "contentBytes": encoded_content
                        }
                    )
                    logger.info(f"Attached file: {path}")
                except FileNotFoundError as e:
                    logger.error(f"Attachment file not found: {path}")
                    raise EmailNotificationError(f"Attachment file not found: {path}") from e
                except Exception as e:
                    logger.error(f"Failed to read attachment: {e}")
                    raise EmailNotificationError(f"Failed to read attachment: {e}") from e
        else:
            email_message["message"]["attachments"] = []



        # Send the email
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(email_endpoint, headers=headers, json=email_message, timeout=30)
            
            if response.status_code == 202:
                logger.info(f"Email sent successfully to {to_addresses}")
            else:
                error_msg = f"Failed to send email. Status: {response.status_code}, Response: {response.text}"
                logger.error(error_msg)
                raise EmailNotificationError(error_msg)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send email request: {e}")
            raise EmailNotificationError(f"Failed to send email: {e}") from e
    else:
        error_desc = token_response.get('error_description', 'Unknown error')
        logger.error(f"Error acquiring token: {error_desc}")
        raise EmailNotificationError(f"Failed to acquire access token: {error_desc}")





def prepare_attachment(file_path: str) -> dict:
    """Helper to prepare a file as an attachment.
    
    Example of how to attach multiple files

    attachments: ['logs/mylog.html', 'reports/summary.pdf']

    parameters = {
         "report_date": "2026-01-22",
         "attachments": [prepare_attachment(file) for file in attachments]
     }
     
    """
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    return {
        "filename": Path(file_path).name,
        "content_base64": content
    }

