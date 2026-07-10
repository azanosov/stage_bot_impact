import json
import logging
import sys
from pathlib import Path

from robocorp.tasks import task
from iaa_rpa_framework import RPAStateMachine

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT)
    log_path = Path("iarpaprocess.log").resolve()

    has_file_handler = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")).resolve() == log_path
        for handler in root_logger.handlers
    )
    if not has_file_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler)
        and getattr(handler, "stream", None) in (sys.stdout, sys.stderr)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)


_configure_logging()
logging.getLogger("comtypes.client._code_cache").setLevel(logging.WARNING)
logging.getLogger("robocorp.windows._control_element").setLevel(logging.WARNING)
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

modulename = "IARPA"
logger = logging.getLogger(
    __name__ if modulename is None or modulename == "" else modulename + ".main"
)


def _log_local_config_hooks(config_file_path: str) -> None:
    config_path = Path(config_file_path)
    if not config_path.is_file():
        logger.info(
            "Local config file not found for preflight hook logging: %s",
            config_file_path,
        )
        return

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "Unable to read local config preflight data from %s: %s",
            config_file_path,
            exc,
        )
        return

    logger.info(
        "Config hooks: UseRobotDataQueue=%s, GetDataFunction=%s, ProcessDataFunction=%s, EndofProcessFunction=%s, InitApplicationsFunction=%s",
        values.get("UseRobotDataQueue", ""),
        values.get("GetDataFunction", ""),
        values.get("ProcessDataFunction", ""),
        values.get("EndofProcessFunction", ""),
        values.get("InitApplicationsFunction", ""),
    )


@task
def main_task(
    orchestrator_url: str,
    job_id: str,
    config_type: str = "",
    config_file_path: str = "",
    keyfile: str = "",
):
    """
    Main task Robocorp/Sema4.ai Task function that initializes the RPA state machine and processes the workflow.

    Args:
        iaa_token (str): The IAA token for authentication.
        orchestrator_url (str): The URL of the orchestrator.
        config_type (str): The type of configuration. Default is "iaaorchestrator".
        job_id (int): The ID of the robot configuration. Default is -1.
        config_file_path (str): The path to the configuration file. Default is "config.yaml".
    """

    if config_type == "":
        config_type = "iaaorchestrator"
    if job_id == "":
        job_id = None
    if config_file_path == "":
        config_file_path = "config/config.json"

    try:
        logger.info(
            "Starting Impact RPA task: orchestrator_url=%s, job_id=%s, config_type=%s, config_file_path=%s, keyfile_set=%s",
            orchestrator_url,
            job_id,
            config_type,
            config_file_path,
            bool(keyfile),
        )

        rpa_sm = RPAStateMachine(
            orchestrator_url=orchestrator_url,
            job_id=job_id,
            config_type=config_type,
            config_file_path=config_file_path,
            keyfile=keyfile,
        )
        logger.info("Impact RPA state machine completed")
    except Exception as e:
        logger.exception("Error occurred - %s: %s", e.__class__.__name__, e)
        raise e
