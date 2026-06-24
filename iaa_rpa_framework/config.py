import json
import requests
import yaml
import logging
from .exceptions import InitialisationError, ConfigAPILoadException, ConfigYamlLoadException
from .orchestrator import Orchestrator
# Configure logger
logger = logging.getLogger(__name__)

class Config:
    _config = None

    @classmethod
    def load_config_from_api(self, orchestrator: Orchestrator, job_id):
        try:
            self._config = orchestrator.get_config_for_job(job_id)
        except Exception as e:
            logger.error(f"Original exception: {type(e).__name__}: {e}")
            raise ConfigAPILoadException(f"Failed to load config from API: {e}", error_code="CFGAPI-001") from e
        return self._config

    @classmethod
    def load_config_from_file(self, filepath='config.json'):
        if self._config is None:
            try:
                with open(filepath, 'r') as file:
                    self._config = json.load(file)
            except Exception as e:
                raise ConfigYamlLoadException(f"Failed to load config from YAML file {filepath}. {e.__class__.__name__}: {e}", error_code="CFGYAML-001")
        return self._config

    @classmethod
    def get(self, key, default=None):
        return self._config.get(key, default) if self._config else None

    @classmethod
    def list_all_keys_and_values(self):
        """
        Lists all keys and their corresponding values in the configuration.

        Returns:
            dict: A dictionary of all keys and their values in the configuration.
        """
        if self._config is None:
            raise Exception("Configuration is not loaded.")
        return self._config

def read_config(file_path):
    """
    Reads a JSON configuration file from the specified file path.
    """
    try:
        with open(file_path, 'r') as file:
            config_data = json.load(file)
        return config_data
    except FileNotFoundError:
        logger.error(f"Error: The file '{file_path}' was not found.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error: The file '{file_path}' is not valid JSON.")
        return {}

def read_yaml_config(file_path):
    """
    Reads a YAML configuration file and returns its contents as a dictionary.
    """
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        logger.error(f"Failed to read YAML config file {file_path}: {e.__class__.__name__}: {e}")
        return None 