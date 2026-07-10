from datetime import datetime
import requests
import logging
import base64
import gzip
import json
import sys
from typing import Optional
from .config_table import ConfigTable
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# Windows-specific imports for named pipe communication
if sys.platform == "win32":
    import win32file
    import win32con
    import win32pipe
    import pywintypes


###
# Get Config

# Get Asset

# Apply Email Template
# Render Email Template

# Put Item to Queue
# Process Queue Item
# Update Queue Item
# Move Queue Item

logger = logging.getLogger(__name__)

# Default token pipe name - must match the one in task_executor.py
DEFAULT_TOKEN_PIPE_NAME = r"\\.\pipe\iaa_rpa_token_pipe"

# HTTP session with headers for Cloudflare WAF compatibility
_http_session = requests.Session()
_http_session.headers.update(
    {
        "User-Agent": "IAARPAFramework/1.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


class TokenProvider:
    """
    Manages token acquisition via named pipe communication with the Agent.
    Caches the token and refreshes it when authentication errors occur.
    """

    def __init__(self, pipe_name: str, job_id: str):
        """
        Args:
            pipe_name: The named pipe to connect to for token requests
            job_id: The job ID to validate token requests
        """
        self.pipe_name = pipe_name
        self.job_id = job_id
        self._cached_token: Optional[str] = None

    def get_token(self) -> str:
        """
        Get a valid token. Returns cached token if available, otherwise fetches a new one.
        """
        if self._cached_token is None:
            self._cached_token = self._fetch_token_from_pipe()
        return self._cached_token

    def refresh_token(self) -> str:
        """
        Force refresh the token by fetching a new one from the pipe.
        """
        logger.info("Refreshing token via pipe...")
        self._cached_token = self._fetch_token_from_pipe()
        return self._cached_token

    def invalidate_token(self):
        """
        Invalidate the cached token, forcing a refresh on next get_token() call.
        """
        self._cached_token = None

    def _fetch_token_from_pipe(self) -> str:
        """
        Fetch a fresh token from the Agent via named pipe.
        """
        if sys.platform != "win32":
            raise RuntimeError("Token pipe communication is only supported on Windows")

        try:
            # Wait for the pipe to be available
            try:
                win32pipe.WaitNamedPipe(self.pipe_name, 5000)
            except pywintypes.error as e:
                logger.error(f"Token pipe not available: {e}")
                raise RuntimeError(f"Token pipe not available: {self.pipe_name}") from e

            # Connect to the pipe
            pipe_handle = win32file.CreateFile(
                self.pipe_name,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )

            try:
                # Send token request
                request = {"command": "get_token", "job_id": self.job_id}
                win32file.WriteFile(pipe_handle, json.dumps(request).encode("utf-8"))

                # Read response
                _, data = win32file.ReadFile(pipe_handle, 4096)
                response = json.loads(data.decode("utf-8"))

                if response.get("success"):
                    token = response.get("token")
                    logger.debug("Token obtained successfully via pipe")
                    return token
                else:
                    error = response.get("error", "Unknown error")
                    logger.error(f"Failed to get token: {error}")
                    raise RuntimeError(f"Failed to get token from pipe: {error}")

            finally:
                win32file.CloseHandle(pipe_handle)

        except pywintypes.error as e:
            logger.error(f"Pipe communication error: {e}")
            raise RuntimeError(f"Pipe communication error: {e}") from e


class RenderedEmailResponse:
    def __init__(
        self, to: list[str], cc: list[str], bcc: list[str], subject: str, body: str
    ):
        self.to = to
        self.cc = cc
        self.bcc = bcc
        self.subject = subject
        self.body = body

    @classmethod
    def from_dict(cls, data: dict) -> "RenderedEmailResponse":
        return cls(
            to=data.get("to", []),
            cc=data.get("cc", []),
            bcc=data.get("bcc", []),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
        )


class Orchestrator:

    def __init__(self, orchestrator_url: str, job_id: str):
        """
        Initialize Orchestrator.

        Args:
            orchestrator_url: The base URL of the orchestrator API
            job_id: Job ID for token validation (required for pipe-based token refresh)
        """
        self.url = orchestrator_url
        self._token_provider = TokenProvider(DEFAULT_TOKEN_PIPE_NAME, job_id)
        logger.info(
            f"Orchestrator initialized with token pipe: {DEFAULT_TOKEN_PIPE_NAME}"
        )
        logger.info(f"Orchestrator Service Initialized")
        super().__init__()

    @property
    def token(self) -> str:
        """Get the current access token."""
        return self._token_provider.get_token()

    def _refresh_token_and_retry(self, request_func):
        """
        Execute a request function, and if it fails with 401, refresh the token and retry once.

        Args:
            request_func: A callable that takes no arguments and returns a requests.Response

        Returns:
            The response from the request
        """
        response = request_func()

        if response.status_code == 401:
            logger.warning("Received 401, refreshing token and retrying...")
            self._token_provider.refresh_token()
            response = request_func()

        return response

    def check_cancel_signal(self, job_id: str) -> bool:
        """
        Check with the agent's token pipe whether a graceful cancel has been requested.

        Returns True if the agent has signalled a cancel for this job, False otherwise.
        Returns False silently on any pipe error so normal processing is never disrupted.
        """
        if sys.platform != "win32":
            return False

        pipe_name = self._token_provider.pipe_name
        try:
            try:
                win32pipe.WaitNamedPipe(pipe_name, 2000)
            except pywintypes.error:
                return False

            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )

            try:
                request = {"command": "check_cancel", "job_id": job_id}
                win32file.WriteFile(pipe_handle, json.dumps(request).encode("utf-8"))
                _, data = win32file.ReadFile(pipe_handle, 4096)
                response = json.loads(data.decode("utf-8"))
                return bool(response.get("cancel_requested", False))
            finally:
                win32file.CloseHandle(pipe_handle)

        except Exception as e:
            logger.debug(f"check_cancel_signal pipe error (ignored): {e}")
            return False

    # Config APIs
    def get_config_for_job(self, job_id):
        """
        Retrieve the runtime configuration for a specific job.

        Called automatically by the state machine during the InitialiseProcess state.
        Do not call this directly — access configuration via the ``Config`` class instead.

        Args:
            job_id: The unique identifier of the job whose configuration to retrieve.

        Returns:
            dict: The job's configuration data.

        Raises:
            Exception: If the request fails or the job is not found.
        """
        config = {}
        url = f"{self.url}/job_config/{job_id}"
        logger.info("Calling API: " + url)

        def make_request():
            headers = {"Authorization": f"Bearer {self.token}"}
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)
        if response.status_code == 200:
            if response.content[:2] == b"\x1f\x8b":
                logger.debug("Response is gzip-compressed, decompressing...")
                config = json.loads(gzip.decompress(response.content).decode("utf-8"))
            else:
                logger.debug(f"Response is JSON...")
                config = response.json()
            logger.debug("---Config---")
            logger.debug(config)
        else:
            raise Exception(f"Failed to get config: {response.status_code}")
        return config

    # Queue APIs

    # Gets the next queue item using the queue assigned to the automation
    def get_queue_items(self, filter):
        """
        Retrieve a list of queue items matching the given filter criteria.

        Args:
            filter (dict): A filter object specifying which queue to query and the
                conditions to apply. Must include exactly one of ``queue_id``,
                ``queue_name``, or ``job_id`` to identify the target queue.
                Optionally include a ``filter`` key with ``conditions`` (list) and
                ``logic`` ("AND"/"OR") for field-level filtering. Set ``redact``
                to True to mask sensitive data fields in the response.

        Returns:
            list: A list of matching queue item dictionaries, or None if the queue
                does not exist or no items match.

        Example::

            items = orchestrator.get_queue_items({
                "queue_name": "my_queue",
                "filter": {
                    "conditions": [
                        {"field": "status", "operator": "equals", "value": "pending"},
                        {"field": "data_fields.customer_name", "operator": "contains", "value": "John"},
                        {"field": "created_at", "operator": "greater_than", "value": "2024-01-01T00:00:00Z"}
                    ],
                    "logic": "AND"
                },
                "redact": False
            })
        """
        url = f"{self.url}/robot_data_items/filter/"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, headers=headers, json=filter)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(f"No pending items found in the queue or queue does not exist.")
        else:
            logger.error(
                f"Failed to retrieve the next item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def get_queue_items_by_job(
        self, job_id: str, filter: Optional[dict] = None, redact: bool = True
    ):
        """
        Retrieve items from the queue associated with a job.

        Prefer using ``RPAStateMachine.get_queue_items()`` instead, which resolves
        the job ID automatically from the current context.

        Args:
            job_id: The unique identifier of the job whose queue to query.
            filter: Optional field-level filter dict with ``conditions`` (list) and
                ``logic`` ("AND"/"OR").
            redact: Apply redaction to sensitive fields. Defaults to True.

        Returns:
            list: Matching queue item dictionaries, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_items/filter/"
        body: dict = {"job_id": job_id, "redact": redact}
        if filter is not None:
            body["filter"] = filter

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, headers=headers, json=body)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info("No items found or queue does not exist.")
        else:
            logger.error(
                f"Failed to retrieve items. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def get_queue_items_by_queue_name(
        self, queue_name: str, filter: Optional[dict] = None, redact: bool = True
    ):
        """
        Retrieve items from a named queue.

        Prefer using ``RPAStateMachine.get_queue_items(queue_name=...)`` instead,
        which wraps this method.

        Args:
            queue_name: The name of the queue to query.
            filter: Optional field-level filter dict with ``conditions`` (list) and
                ``logic`` ("AND"/"OR").
            redact: Apply redaction to sensitive fields. Defaults to True.

        Returns:
            list: Matching queue item dictionaries, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_items/filter/"
        body: dict = {"queue_name": queue_name, "redact": redact}
        if filter is not None:
            body["filter"] = filter

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, headers=headers, json=body)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(
                f"No items found in queue '{queue_name}' or queue does not exist."
            )
        else:
            logger.error(
                f"Failed to retrieve items. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def get_queue_item_count(self, job_id):
        """
        Retrieve the number of pending items in the queue associated with a job.

        Called automatically by the state machine during InitialiseProcess to determine
        whether there is work to process. Do not call this directly.

        Args:
            job_id: The unique identifier of the job whose queue to query.

        Returns:
            int: The count of pending items, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_count/by_job/{job_id}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(f"No pending items found in the queue or queue does not exist.")
        else:
            logger.error(
                f"Failed to retrieve the next item. Status code: {response.status_code}, Error: {response.text}"
            )
        return None

    # Gets the next queue item using the queue assigned to the automation
    def get_next_queue_item(self, job_id):
        """
        Retrieve the next pending item from the queue associated with a job.

        Called automatically by the state machine during the RetrieveData state.
        Do not call this directly — the framework handles item retrieval and
        exposes the current item via ``RPAStateMachine.transaction_item``.

        Args:
            job_id: The unique identifier of the job whose queue to pull from.

        Returns:
            dict: The next pending queue item, or None if the queue is empty
                or does not exist.
        """
        url = f"{self.url}/robot_data_queues/by_job/{job_id}/next_item"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(f"No pending items found in the queue or queue does not exist.")
        else:
            logger.error(
                f"Failed to retrieve the next item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def get_queue_item_count_by_queue_name(self, queue_name):
        """
        Retrieve the number of pending items in a named queue.

        Called automatically by the state machine during InitialiseProcess when the
        job is configured to use a named queue (``DataQueueName``). Do not call this directly.

        Args:
            queue_name (str): The name of the queue to query.

        Returns:
            int: The count of pending items, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_count/by_name/{queue_name}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(
                f"No pending items found in the queue '{queue_name}' or queue does not exist."
            )
        else:
            logger.error(
                f"Failed to retrieve the next item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def get_next_item_by_queue_name(self, queue_name):
        """
        Retrieve the next pending item from a named queue.

        Called automatically by the state machine during the RetrieveData state when
        the job is configured to use a named queue (``DataQueueName``). Do not call
        this directly — the framework exposes the current item via
        ``RPAStateMachine.transaction_item``.

        Args:
            queue_name (str): The name of the queue to pull from.

        Returns:
            dict: The next pending queue item, or None if the queue is empty
                or does not exist.
        """
        url = f"{self.url}/robot_data_queues/by_name/{queue_name}/next_item"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(
                f"No pending items found in the queue '{queue_name}' or queue does not exist."
            )
        else:
            logger.error(
                f"Failed to retrieve the next item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def put_item_by_job(self, job_id, item_id, item):
        """
        Push a new item onto the queue associated with a job.

        Prefer using ``RPAStateMachine.push_item_to_queue(item_id, item)`` instead,
        which resolves the job ID and queue name automatically from the current context.

        Args:
            job_id: The unique identifier of the job whose queue to push to.
            item_id (str): A unique identifier/name for this item within the queue.
            item (dict): The data payload for the queue item, stored as ``data_fields``.

        Returns:
            dict: The created queue item, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_items/by_job/{job_id}"
        data = {"name": item_id, "data_fields": item}

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, headers=headers, data=json.dumps(data))

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(f"Queue does not exist.")
        else:
            logger.error(
                f"Failed to populate the item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def put_item_by_queue_name(self, queue_name, item_id, item):
        """
        Push a new item onto a named queue.

        Prefer using ``RPAStateMachine.push_item_to_queue(item_id, item, queueName)``
        instead, which wraps both this method and ``put_item_by_job`` behind a single call.

        Args:
            queue_name (str): The name of the queue to push to.
            item_id (str): A unique identifier/name for this item within the queue.
            item (dict): The data payload for the queue item, stored as ``data_fields``.

        Returns:
            dict: The created queue item, or None if the queue does not exist.
        """
        url = f"{self.url}/robot_data_items/by_name/{queue_name}"
        data = {"name": item_id, "data_fields": item}

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, headers=headers, data=json.dumps(data))

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.info(f"Queue '{queue_name}' does not exist.")
        else:
            logger.error(
                f"Failed to populate the item. Status code: {response.status_code}, Error: {response.text}"
            )

        return None

    def update_data_queue_item(self, item: dict) -> bool:
        """
        Update an existing queue item on the portal.

        Called automatically by the state machine after each transaction to persist
        the item's status (success, failure, warning) and any output fields. Do not
        call this directly — set the outcome via ``RPAStateMachine.set_transaction_status()``
        and the framework will write it back at the end of the transaction.

        Args:
            item (dict): The queue item to update. Must include the ``id`` key.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        logger.info("---Updating Queue Item---")

        item_id = item["id"]
        url = f"{self.url}/robot_data_items/{item_id}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.put(url, headers=headers, json=item)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            logger.debug(
                f"Item updated successfully. Item ID: {item_id}, Status code: {response.status_code}"
            )
            return True
        else:
            logger.error(
                f"Failed to update the Item ID: {item_id}. Status code: {response.status_code}, Error: {response.text}"
            )
            return False

    def get_config_table(self, tablename: str) -> ConfigTable | None:
        """
        Retrieve a named configuration table from the portal.

        Configuration tables contain reference or lookup data managed centrally in
        the portal and shared across automations — for example, business rules, code
        mappings, or static datasets that would otherwise be hard-coded in the bot.

        Prefer using ``RPAStateMachine.get_config_table(tablename)`` instead,
        which wraps this method.

        Args:
            tablename (str): The name of the configuration table to retrieve.

        Returns:
            ConfigTable: The configuration table, or None if the table is not found.
        """
        url = f"{self.url}/configtable_data/{tablename}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            try:
                data = json.loads(response.json())
                if not isinstance(data, list):
                    logger.error(f"Unexpected config table data type: {type(data)}")
                    return None
                return ConfigTable.from_list(data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to parse config table data: {e}")
                return None
        elif response.status_code == 404:
            logger.info(f"Config table not found")
        else:
            logger.error(
                f"Failed to retrieve the config table: {response.status_code}, Error: {response.text}"
            )

        return None

    # Asset APIs

    def get_asset(self, asset_name: str, private_key_file: str):
        """
        Retrieve and decrypt a sensitive asset from the portal.

        Assets store secret values such as passwords, API keys, connection strings,
        or any other sensitive data managed on the portal. The value is encrypted
        at rest and decrypted locally using the bot's RSA private key.

        Prefer using ``RPAStateMachine.get_asset(asset_name)`` instead, which resolves
        the private key path automatically from the bot's configuration.

        Args:
            asset_name (str): The name of the asset to retrieve.
            private_key_file (str): Path to the PEM-encoded RSA private key file
                used to decrypt the asset value.

        Returns:
            str: The decrypted asset value as a string.

        Raises:
            Exception: If the asset cannot be retrieved.
            ValueError: If decryption fails (wrong key or corrupted data).
        """
        url = f"{self.url}/assets/by-name/{asset_name}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.get(url, headers=headers)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve the asset. Status code: {response.status_code}, Error: {response.text}"
            )

        return self._decrypt_asset(response.json()["value"], private_key_file)

    def _decrypt_asset(self, encrypted_asset_hex: str, private_key_file: str) -> str:

        encrypted_asset = base64.b64decode(encrypted_asset_hex)

        with open(private_key_file, "rb") as key_file:
            private_key_pem = key_file.read()

            private_key = serialization.load_pem_private_key(
                private_key_pem, password=None, backend=default_backend()
            )

            # Decrypt the asset
            decrypted_asset = private_key.decrypt(
                encrypted_asset,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return decrypted_asset.decode()

    def finish_job(
        self,
        job_id: str,
        total_records_processed: int,
        success_records: int,
        exception_records: int,
    ):
        """
        Report the outcome of a completed job back to the portal.

        Called automatically by the state machine during the EndProcessTasks state.
        Do not call this directly — the framework tallies and submits job statistics
        at the end of the run.

        Args:
            job_id (str): The unique identifier of the job to mark as complete.
            total_records_processed (int): Total number of records processed during the job.
            success_records (int): Number of records processed successfully.
            exception_records (int): Number of records that resulted in an error.

        Returns:
            tuple: A ``(response_text, status_code)`` tuple from the portal API.

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        logging.info(f"IA Portal --> Finish Job --> Start Time: {datetime.now()}")

        # Prepare request payload
        json_data = {
            "record_processed": total_records_processed,
            "record_success": success_records,
            "record_failed": exception_records,
        }
        url = f"{self.url}/job/result/{job_id}"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.put(url, json=json_data, headers=headers, timeout=30.0)

        try:
            response = self._refresh_token_and_retry(make_request)

            logging.info(
                f"IA Portal --> AddProcessTransaction --> End Time: {datetime.now()}"
            )

            return response.text, response.status_code

        except requests.exceptions.RequestException as e:
            print(f"Error making HTTP request: {str(e)}")
            logging.error(f"Error making HTTP request: {str(e)}")
            raise

    def get_credits(self):
        """
        Retrieve the current billing credits balance from the portal.

        Called automatically by the state machine during InitialiseProcess to verify
        the account has sufficient credits before processing begins. Do not call this directly.

        Returns:
            The credits information returned by the portal API.

        Raises:
            Exception: If the request fails.
        """
        credits = False
        url = f"{self.url}/billing/credits"
        logger.info("Calling API: " + url)

        def make_request():
            headers = {"Authorization": f"Bearer {self.token}"}
            return _http_session.get(url, headers=headers, timeout=120.0)

        response = self._refresh_token_and_retry(make_request)

        if response.status_code == 200:
            credits = response.json()
            logger.info("---Credits---")
            logger.info(credits)
        else:
            raise Exception(f"Failed to get credits: {response.status_code}")
        return credits

    def send_email_template(
        self,
        template: str,
        to: str = None,
        cc: str = None,
        bcc: str = None,
        params: dict[str, any] = None,
        attachments: list[str] = None,
    ):
        """
        Send an email from the orchestrator/portal using an Email Template Asset.

        Args:
            template: The name of the email template asset to use.
            to: Comma-separated list of recipient email addresses. Optional if configured in template.
            cc: Comma-separated list of CC email addresses. Optional if configured in template.
            bcc: Comma-separated list of BCC email addresses. Optional if configured in template.
            params: Dictionary of template parameters to substitute in the email body.
            attachments: List of file paths to attach to the email. Files will be
                base64-encoded and sent with their filename (without path).

        Example:
            # Minimal call - template has recipients configured
            orchestrator.send_email_template(template="daily_report")

            # With parameters and overrides
            orchestrator.send_email_template(
                template="order_confirmation",
                to="customer@example.com",
                params={
                    "customer_name": "John Doe",
                    "order_id": "ORD-12345",
                    "order_total": "$99.99"
                },
                attachments=["C:/invoices/invoice.pdf"]
            )
        """
        import os as _os

        # Build request body - only include fields that are provided
        body = {"template": template}
        if to is not None:
            body["to"] = to
        if cc is not None:
            body["cc"] = cc
        if bcc is not None:
            body["bcc"] = bcc
        if params is not None:
            body["params"] = params
        if attachments:
            body["attachments"] = []
            for file in attachments:
                with open(file, "rb") as f:
                    content_base64 = base64.b64encode(f.read()).decode("utf-8")
                body["attachments"].append(
                    {
                        "filename": _os.path.basename(file),
                        "content_base64": content_base64,
                    }
                )

        url = f"{self.url}/email_template/"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, json=body, headers=headers, timeout=30.0)

        try:
            response = self._refresh_token_and_retry(make_request)

            logging.info(
                f"IA Portal --> send_email_template --> End Time: {datetime.now()}"
            )

            response.raise_for_status()

            return response.text, response.status_code

        except requests.exceptions.RequestException as e:
            print(f"Error making HTTP request: {str(e)}")
            logging.error(f"Error making HTTP request: {str(e)}")
            raise

    def render_email_template(
        self,
        template: str,
        to: str = None,
        cc: str = None,
        bcc: str = None,
        params: dict[str, any] = None,
    ) -> RenderedEmailResponse:
        """
        Render an email template and return the processed email object without sending it.

        Args:
            template: The name of the email template asset to use.
            to: Comma-separated list of recipient email addresses. Optional if configured in template.
            cc: Comma-separated list of CC email addresses. Optional if configured in template.
            bcc: Comma-separated list of BCC email addresses. Optional if configured in template.
            params: Dictionary of template parameters to substitute in the email.

        Returns:
            RenderedEmailResponse with fields: to (list), cc (list), bcc (list), subject (str), body (str)
        """
        body = {"template": template}
        if to is not None:
            body["to"] = to
        if cc is not None:
            body["cc"] = cc
        if bcc is not None:
            body["bcc"] = bcc
        if params is not None:
            body["params"] = params

        url = f"{self.url}/email_template/render"

        def make_request():
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            return _http_session.post(url, json=body, headers=headers, timeout=30.0)

        try:
            response = self._refresh_token_and_retry(make_request)
            response.raise_for_status()
            return RenderedEmailResponse.from_dict(response.json())
        except requests.exceptions.RequestException as e:
            logging.error(f"Error making HTTP request: {str(e)}")
            raise

    def upload_robot_package(self, robot_package_name: str, robot_package_path: str):
        """
        .. deprecated::
            This function is deprecated and should not be used in new automations.

        Upload a robot package zip file to the portal.

        Args:
            robot_package_name (str): The name to register the package under.
            robot_package_path (str): The local file path to the robot package zip file.
        """
        url = f"{self.url}/upload-robot-package/?name={robot_package_name}"

        print(f"Uploading robot package to {url}")

        def make_request():
            files = [
                (
                    "file",
                    ("robot.zip", open(robot_package_path, "rb"), "application/zip"),
                )
            ]
            headers = {"Authorization": f"Bearer {self.token}"}
            return _http_session.post(url, headers=headers, data={}, files=files)

        response = self._refresh_token_and_retry(make_request)

        print(response.text)
