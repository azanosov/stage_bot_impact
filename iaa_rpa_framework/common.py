import os
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
import functools
import logging
import importlib

# Configure logger
logger = logging.getLogger(__name__)


def ExecuteProcessFunction(function_name, *args, **kwargs):
    """
    Executes a function from a rpa module
    """
    try:
        logger.info(f"Executing {function_name}")

        # New approach: Import and call a function (preferred)
        if function_name:
            # Split from the right to get module path and function name
            # e.g. "Clients.Altus.rpaprocess_altus.get_next_email_transaction"
            # becomes ("Clients.Altus.rpaprocess_altus", "get_next_email_transaction")
            parts = function_name.rsplit(".", 1)

            if len(parts) != 2:
                raise ValueError(
                    f"Invalid function name format: {function_name}. Expected 'module.function'"
                )

            module_path, func_name = parts

            # Use importlib to properly handle nested module paths
            _module = importlib.import_module(module_path)
            _function = getattr(_module, func_name)
            return _function(*args, **kwargs)
        else:
            logger.info(f"No function provided. Skipping execution.")
    except Exception as e:
        logger.error(f"Failed to execute: {e.__class__.__name__}: {e}")
        raise e


def create_processlog_subfolder(processlog_parent_folder):
    """
    Creates a subfolder under the specified parent folder with the current date in YYYYMMDD format.

    Args:
        parent_folder (str): The path to the parent folder where the subfolder should be created.
    """
    try:
        current_date = datetime.now().strftime("%Y%m%d")
        subfolder_path = os.path.join(processlog_parent_folder, current_date)

        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
            logger.info(f"Created Billing Process Log Subfolder: {subfolder_path}")
        else:
            logger.info(
                f"Billing Process Log Subfolder already exists: {subfolder_path}"
            )

        return subfolder_path
    except Exception as e:
        logger.error(
            f"Failed to create Billing Process Log Subfolder in {processlog_parent_folder}: {e.__class__.__name__}: {e}"
        )
        return processlog_parent_folder + "/" + "default"


def retry(times, delay=1):
    """A decorator that retries the function up to 'times' times with a delay between attempts."""

    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            attempts = 0
            while attempts < times:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f"Attempt {attempts} failed: {e}")
                    if attempts < times:
                        time.sleep(delay)
            raise Exception(f"Function failed after {times} attempts")

        return wrapper_retry

    return decorator_retry
