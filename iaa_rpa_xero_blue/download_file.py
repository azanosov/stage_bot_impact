from __future__ import annotations

import os
import time

from iaa_rpa_utils import setup_logger
from robocorp import windows

# Set up logger
logger = setup_logger(__name__)


def download_file(
    window_title,
    download_folder_path,
    file_name,
    extension,
):

    app = windows.find_window(f"regex:.*{window_title}.* - Google Chrome")

    # Type file name
    file_input = app.find(
        'control:"EditControl" and class:"Edit" and name:"File name:"',
    ).click()
    file_path = os.path.join(download_folder_path, file_name + extension)
    file_input.send_keys("{CTRL}a")
    file_input.send_keys("{DEL}")
    file_input.send_keys(file_path)
    logger.info(f"Typed file path {file_path}")
    time.sleep(2)

    # # Select the All file type
    # app.find(
    #     'control:"ComboBoxControl" and class:"AppControlHost" and name:"Save as type:"',
    # ).click()
    # app.find('control:"ListItemControl" and name:"regex:.*All Files.*"').click()
    # logger.info("Clicked into All Files format")

    app.find('control:"ButtonControl" and name:"Save"').click()
    logger.info("Clicked save button")
    time.sleep(1)

    try:
        save_confirm_popup = app.find(
            'control:"WindowControl" and name:"Confirm Save As" and path:"1|1"',
            timeout=3,
        )
        logger.info(f"Confirm Save As window found. Overwriting.")
        save_confirm_popup.find(
            'control:"ButtonControl" and class:"CCPushButton" and name:"Yes"',
        ).click()
    except Exception:
        logger.info("No overwrite confirmation window appeared.")
