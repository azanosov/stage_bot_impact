# Move the entire content of initialisation.py here
# No changes needed to the file content yet


import os
import shutil
import csv
import logging
from datetime import datetime
from typing import Optional
from .config import Config

# Configure logger
logger = logging.getLogger("IARPA." + __name__)


def read_csv_to_dicts(file_path: str, fieldnames: Optional[list] = None) -> list:
    """
    Reads a CSV file and returns a list of dictionaries with specified fieldnames.

    Args:
        file_path (str): The path to the CSV file.
        fieldnames (list): Optional. A list of custom field names to override the CSV's header.

    Returns:
        list of dict: A list of dictionaries representing the rows in the CSV file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: The file '{file_path}' was not found.")

    with open(file_path, mode="r", newline="", encoding="utf-8") as csvfile:
        # If no override for fieldnames, the first row of the CSV is used as the header
        if fieldnames:
            reader = csv.DictReader(csvfile, fieldnames=fieldnames)
        else:
            reader = csv.DictReader(csvfile)

        # Convert CSV rows to a list of dictionaries
        csv_data = [row for row in reader]

    return csv_data


def backup_transaction_list(source_file: str, target_directory: str) -> str:
    """
    Copies a backup of the source file to the target directory with a timestamp.

    Args:
        source_file (str): The path to the source file.
        target_directory (str): The path to the target directory.

    Returns:
        str: The path to the backup file.
    """
    if not os.path.exists(source_file):
        logger.error(f"Source file does not exist: {source_file}")
        raise FileNotFoundError(f"Source file does not exist: {source_file}")

    if not os.path.exists(target_directory):
        os.makedirs(target_directory)
        logger.info(f"Created target directory: {target_directory}")

    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Construct the backup file path with timestamp
    base_name = os.path.basename(source_file)
    name, ext = os.path.splitext(base_name)
    backup_file_name = f"{name}_{timestamp}{ext}"
    backup_file_path = os.path.join(target_directory, backup_file_name)

    # Copy the source file to the target directory
    shutil.copy2(source_file, backup_file_path)
    logger.info(f"Backup completed: {backup_file_path}")

    return backup_file_path


def InitialiseApplications(
    init_function_name: str = None, init_module_name: str = "rpaprocess"
) -> dict:
    """
    Initialises applications by calling a function from a module
    Args:
        init_function_name (str, optional): Name of the function to call in the module.
        init_module_name (str, optional): Name of the module containing the function. Defaults to "rpaprocess".


    Returns:
        dict: A dictionary containing initialised application objects.
              Returns empty dict if no initialisation method provided.
    """
    try:
        logger.info("Executing commands to initialise applications")

        # New approach: Import and call a function (preferred)
        if init_function_name:
            init_function_module = __import__(init_module_name)
            init_function = getattr(init_function_module, init_function_name)

            # Call the function - it should return a dictionary of initialised apps
            initialised_apps = init_function() or {}

            logger.info(
                f"Initialised {len(initialised_apps)} application(s) via function: {list(initialised_apps.keys())}"
            )
            return initialised_apps

        else:
            logger.info("No initialisation method provided. Skipping execution.")
            return {}

    except Exception as e:
        logger.error(f"Failed to initialise applications: {e.__class__.__name__}: {e}")
        raise e
