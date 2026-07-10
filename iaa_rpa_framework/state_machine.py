import os
import logging
import csv
from typing import Optional, List, Dict, Any, Type, Union, overload
from statemachine import StateMachine, State
from datetime import datetime

from .orchestrator import Orchestrator, DEFAULT_TOKEN_PIPE_NAME
from .assets import Asset, AssetT

from .common import ExecuteProcessFunction, create_processlog_subfolder
from .initialisation import (
    read_csv_to_dicts,
    backup_transaction_list,
    InitialiseApplications,
)
from .config import Config
from .config_table import ConfigTable
from .exceptions import (
    RPABusinessException,
    RPASystemException,
    InitialisationError,
    ConfigAPILoadException,
    ConfigYamlLoadException,
)

# Configure logging
logger = logging.getLogger(__name__)


def str_to_bool(value):
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "t", "yes", "y", "1")
        return bool(value)
    except Exception as e:
        logger.error(f"Failed to convert value to boolean: {e}")
        raise InitialisationError(f"Cannot convert {value} to boolean: {e}") from e


class RPAStateMachine(StateMachine):
    "RPA Framework State Machine"

    # States
    Initialisation = State(
        initial=True, enter="InitialiseProcess", name="Initilisation"
    )
    GetTransactionData = State(enter="RetrieveData", name="GetTransactionData")
    ProcessTransaction = State(enter="MainProcess", name="ProcessTransactions")
    EndProcess = State(final=True, enter="EndProcessTasks", name="EndProcess")

    # Transitions/Events
    InitSuccessful = Initialisation.to(GetTransactionData)
    InitFailed = Initialisation.to(EndProcess)

    FoundNewTransaction = GetTransactionData.to(ProcessTransaction)
    RetryTransaction = GetTransactionData.to(ProcessTransaction)
    FoundNoData = GetTransactionData.to(EndProcess)

    SystemException = ProcessTransaction.to(Initialisation)
    SystemExceptionMaxRetries = ProcessTransaction.to(EndProcess)
    BusinessException = ProcessTransaction.to(GetTransactionData)
    ProcessSuccess = ProcessTransaction.to(GetTransactionData)

    def __init__(
        self,
        orchestrator_url: str,
        job_id: str,
        config_type: str = "iaaorchestrator",
        config_file_path: Optional[str] = None,
        keyfile: Optional[str] = None,
    ):
        """
        Initialize the RPA State Machine.

        Args:
            orchestrator_url: The base URL of the orchestrator API
            job_id: The job ID for this execution (required, enables automatic token refresh)
            config_type: Configuration type ("iaaorchestrator" or "json")
            config_file_path: Path to config file (for "json" config_type)
            keyfile: Path to the private key file for asset decryption
        """
        # Agent Config
        self.job_id: str = job_id
        self.config_type: str = config_type
        self.config_file_path: Optional[str] = config_file_path
        self.orchestrator_url: str = orchestrator_url
        self.PrivateKeyFile: str = keyfile

        # Transaction Info
        self.current_record: int = 0
        self.total_processed: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.warning_count: int = 0
        self.transaction_data: Optional[List[Dict[str, Any]]] = None
        self.transaction_item: Optional[Dict[str, Any]] = None
        self.retry_count: int = 0
        self.number_of_retry_attempts: int = 0
        self.start_time: datetime = datetime.now()  # Log start time

        self.UseLocalTransactionsList: bool = False
        self.UseRobotDataQueue: bool = False
        self.UseCustomDataQueueFunction: bool = False
        self.initialisation_abort: bool = False
        self.initialisation_exception: Optional[Exception] = None
        self.cancel_requested: bool = False
        self.SystemExceptionCount: int = 0

        # Initialize orchestrator with pipe-based token refresh
        logger.info(
            f"Initializing orchestrator with token pipe: {DEFAULT_TOKEN_PIPE_NAME}"
        )
        self.orchestrator = Orchestrator(
            orchestrator_url=orchestrator_url, job_id=job_id
        )
        self.is_initialised: bool = False
        self.initialised_apps: Dict[str, Any] = (
            {}
        )  # Dictionary to store initialized application objects
        logger.info(f"Process started at {self.start_time}")
        super().__init__()

    # Wrappers to interact with the orchestrator
    @overload
    def get_asset(self, asset_name: str) -> str: ...

    @overload
    def get_asset(self, asset_name: str, asset_type: Type[AssetT]) -> AssetT: ...

    def get_asset(
        self, asset_name: str, asset_type: Optional[Type[AssetT]] = None
    ) -> Union[str, AssetT]:
        """
        Retrieve an asset from the orchestrator.

        Args:
            asset_name: The name of the asset to retrieve
            asset_type: Optional asset type class for typed retrieval.
                        If provided, returns an instance of that type.
                        If not provided, returns the raw decrypted string.

        Returns:
            If asset_type is provided: An instance of the specified asset type
            If asset_type is None: The raw decrypted asset string

        Examples:
            # Untyped retrieval (returns raw string)
            raw_value = agent.get_asset("MyAsset")

            # Typed retrieval (returns LoginCredential)
            from iaa_rpa_framework import LoginCredential
            cred = agent.get_asset("MyLogin", LoginCredential)
            print(cred.username)
            print(cred.password)

            # Typed retrieval (returns DatabaseCredential)
            from iaa_rpa_framework import DatabaseCredential
            db = agent.get_asset("MyDb", DatabaseCredential)
            print(db.hostname)
        """
        print(
            f"Getting asset {asset_name} from orchestrator with keyfile: {self.PrivateKeyFile}"
        )
        logger.info(f"Getting asset {asset_name} from orchestrator")
        if self.PrivateKeyFile is None:
            raise ValueError(
                "PrivateKeyFile is required for get_asset but was not provided"
            )
        raw_value = self.orchestrator.get_asset(asset_name, self.PrivateKeyFile)
        logger.info(f"Got asset: {asset_name}")
        if asset_type is None:
            return raw_value
        else:
            return asset_type.from_json(raw_value)

    def get_queue_items(
        self,
        filter: Optional[Dict[str, Any]] = None,
        queue_name: Optional[str] = None,
        redact: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve items from a data queue.

        Abstracts the job ID automatically. By default queries the queue associated
        with the current job. Optionally target a specific queue by name.

        Args:
            filter: Optional field-level filter dict with 'conditions' (list) and
                    'logic' ("AND"/"OR"). Example::

                        {
                            "conditions": [
                                {"field": "status", "operator": "equals", "value": "pending"}
                            ],
                            "logic": "AND"
                        }

            queue_name: Name of the queue to query. Defaults to the queue
                        associated with the current job.
            redact: Apply redaction to sensitive fields. Defaults to True.

        Returns:
            list: Matching queue items, or None if the queue does not exist.
        """
        if queue_name is not None:
            return self.orchestrator.get_queue_items_by_queue_name(
                queue_name, filter, redact
            )
        else:
            return self.orchestrator.get_queue_items_by_job(self.job_id, filter, redact)

    def push_item_to_queue(self, item_id, item: dict, queueName=None):
        if queueName is None:
            return self.orchestrator.put_item_by_job(self.job_id, item_id, item)
        else:
            return self.orchestrator.put_item_by_queue_name(queueName, item_id, item)

    def update_queue_item(self, item):
        return self.orchestrator.update_data_queue_item(item)

    def get_config_table(self, tablename: str) -> ConfigTable | None:
        return self.orchestrator.get_config_table(tablename)

    def InitialiseProcess(self):
        logger.info("----- Initilising Process ---------------")

        try:

            if not self.is_initialised:

                # Init All Settings
                if self.config_type == "iaaorchestrator":
                    Config.load_config_from_api(self.orchestrator, self.job_id)
                elif self.config_type == "json":
                    Config.load_config_from_file(self.config_file_path)

                # Check Balance
                if self.orchestrator.get_credits():
                    logger.info("Funds Available")
                else:
                    logger.error("Not enough funds available to run process")
                    raise Exception("Not enough funds available to run process")

                self.UseLocalTransactionsList = str_to_bool(
                    Config.get("UseLocalTransactionList", False)
                )
                self.UseRobotDataQueue = str_to_bool(
                    Config.get("UseRobotDataQueue", False)
                )
                self.UseCustomDataQueueFunction = str_to_bool(
                    Config.get("UseCustomDataQueueFunction", False)
                )
                # self.transaction_data = []  # Will store all processed transactions for reporting
                self.total_processed = 0
                self.success_count = 0
                self.failed_count = 0

                # Log the configuration for debugging
                logger.info(
                    f"UseLocalTransactionList: {self.UseLocalTransactionsList} (type: {type(self.UseLocalTransactionsList)})"
                )
                logger.info(
                    f"UseRobotDataQueue: {self.UseRobotDataQueue} (type: {type(self.UseRobotDataQueue)})"
                )

                if self.UseLocalTransactionsList:
                    # Scenario 1: Local transaction list processing logic
                    if Config.get("TransactionListFile", None) is not None:
                        backup_transaction_list(
                            Config.get("TransactionListFile", None),
                            Config.get("TransactionListFileBackupFolder", None),
                        )
                        self.transaction_data = read_csv_to_dicts(
                            Config.get("TransactionListFile", None)
                        )
                    else:
                        raise Exception(
                            "UseLocalTransactionList is True and Client List not found in the configuration"
                        )

                    logger.info(
                        f"Found {len(self.transaction_data)} records in client list"
                    )
                elif not self.UseRobotDataQueue:
                    # Scenario 2: External function to get ALL records at once
                    try:
                        get_data_function_name = Config.get("GetDataFunction", None)

                        if get_data_function_name:
                            self.transaction_data = ExecuteProcessFunction(
                                get_data_function_name, self
                            )

                            if not self.transaction_data:
                                logger.warning(
                                    "No records returned from external get data function"
                                )
                                self.transaction_data = []
                            elif not isinstance(self.transaction_data, list):
                                logger.warning(
                                    f"External data function returned non-list type: {type(self.transaction_data)}"
                                )
                                if isinstance(self.transaction_data, dict):
                                    self.transaction_data = [
                                        self.transaction_data
                                    ]  # Convert single dict to list
                                else:
                                    self.transaction_data = []

                            logger.info(
                                f"Retrieved {len(self.transaction_data)} records from external get data function"
                            )
                        else:
                            raise InitialisationError(
                                "GetDataFunction not provided in the configuration",
                                error_code="CFGINIT-001",
                            )

                    except Exception as e:
                        logger.error(
                            f"Error retrieving data from external get data function: {e.__class__.__name__}:{e}"
                        )
                        self.transaction_data = []
                        self.InitFailed()
                else:
                    # Scenario 3: IAA Robot Data Queue - we'll get records one by one
                    logger.info("Using IAA Robot Data Queue for transaction data")
                    if self.transaction_data is None:
                        self.transaction_data = []

                self.number_of_retry_attempts = int(Config.get("RetryAttempts", 0))

                self.is_initialised = True

            else:
                logger.info(
                    "State Machine is already initialised - Likely recovering from a System Exception"
                )

            # Kill All Processes
            try:
                logger.info("Attempting to kill applications")
                ExecuteProcessFunction(
                    Config.get("KillAllProcessFunction", None),
                    initialised_apps=self.initialised_apps,
                )
            except Exception as e:
                logger.error("Error Killing applications: ", e)

            # Get number of transaction items
            data_count = len(self.transaction_data)

            # Get pending items in queue
            if self.UseRobotDataQueue:
                if Config.get("DataQueueName", None) is not None:
                    counts = self.orchestrator.get_queue_item_count_by_queue_name(
                        Config.get("DataQueueName")
                    )
                    data_count = counts["pending"] if counts else 0
                else:
                    counts = self.orchestrator.get_queue_item_count(self.job_id)
                    data_count = counts["pending"] if counts else 0

            logger.info(f"{data_count} items available for processing")

            init_function_name = Config.get("InitApplicationsFunction", None)

            # Only initialise if data exists
            if init_function_name and (
                data_count > 0 or self.transaction_item is not None
            ):
                self.initialised_apps = ExecuteProcessFunction(init_function_name, self)
            else:
                logger.info(
                    "No transaction or queue data found, skipping initialisation of applications"
                )
                self.initialised_apps = {}

            # Mark InitSuccessful
            self.InitSuccessful()

        except ConfigAPILoadException as e:
            logger.error(
                f"Initialisation Failed: {e.__class__.__name__}:{e}, Check the Token Authenication"
            )
            self.InitFailed()
        except ConfigYamlLoadException as e:
            logger.error(
                f"Initialisation Failed: {e.__class__.__name__}:{e}, Check the YAML file"
            )
            self.InitFailed()
        except InitialisationError as e:
            logger.error(f"Initialisation Failed: {e.__class__.__name__}:{e}")
            self.InitFailed(e)
        except Exception as e:
            logger.error(f"Initialisation Failed: {e.__class__.__name__}:{e}")
            self.InitFailed(e)

    def _check_cancel_signal(self) -> bool:
        """Poll the agent's token pipe to check if a graceful cancel has been requested."""
        try:
            return self.orchestrator.check_cancel_signal(self.job_id)
        except Exception:
            return False

    def RetrieveData(self):
        logger.info("Begin RetrieveData")

        if self._check_cancel_signal():
            logger.warning(
                "Cancel signal received. Aborting after current transaction and proceeding to EndProcess."
            )
            self.cancel_requested = True
            self.FoundNoData()
            return

        if self.UseRobotDataQueue:
            # Scenario 3: IAA Robot Data Queue - get one record at a time
            try:
                # If we're retrying the current transaction
                if (
                    self.transaction_item is not None
                    and self.retry_count <= self.number_of_retry_attempts
                ):
                    logger.info(
                        f"Retrying transaction, attempt {self.retry_count} of {self.number_of_retry_attempts}"
                    )
                    self.RetryTransaction()
                    return

                if self.UseCustomDataQueueFunction:

                    get_data_function_name = Config.get("GetDataFunction", None)

                    if get_data_function_name:
                        next_item = ExecuteProcessFunction(get_data_function_name, self)
                    else:
                        raise Exception(
                            "GetDataFunction not provided in the configuration"
                        )
                else:
                    # Stanadard IAA Data Queue Function
                    if Config.get("DataQueueName", None) is not None:
                        next_item = self.orchestrator.get_next_item_by_queue_name(
                            Config.get("DataQueueName")
                        )
                    else:
                        next_item = self.orchestrator.get_next_queue_item(self.job_id)
                        # raise Exception("DataQueueName not provided in the configuration")

                if next_item:
                    # Ensure next_item is a dictionary, not a list
                    if isinstance(next_item, list):
                        if len(next_item) > 0:
                            self.transaction_item = next_item[
                                0
                            ]  # Use first item if it's a list
                            logger.info(
                                f"Retrieved item is a list, using first element"
                            )
                        else:
                            logger.info("Retrieved empty list from queue")
                            self.transaction_item = None
                            self.FoundNoData()
                            return
                    else:
                        self.transaction_item = next_item

                    # Final check to ensure transaction_item is a dictionary
                    if not isinstance(self.transaction_item, dict):
                        logger.error(
                            f"Retrieved item is not a dictionary: {type(self.transaction_item)}"
                        )
                        self.transaction_item = None
                        self.FoundNoData()
                        return

                    self.retry_count = 0
                    self.SystemExceptionCount = 0
                    logger.info(f"Retrieved new transaction from IAA Robot Data Queue")
                    self.FoundNewTransaction()
                else:
                    logger.info("No more items in the IAA Robot Data Queue")
                    self.transaction_item = None
                    self.FoundNoData()

            except Exception as e:
                if str(e) == "GetDataFunction not provided in the configuration":
                    logger.error("Configuration error: GetDataFunction not provided")
                    self.transaction_item = None
                    # self.SystemException(e)
                    self.FoundNoData()
                else:
                    logger.error(
                        f"Error retrieving data from IAA Robot Data Queue: {e.__class__.__name__}:{e}"
                    )
                    self.transaction_item = None
                    self.FoundNoData()
        else:
            # Scenarios 1 & 2: Process from pre-loaded transaction_data list
            if self.transaction_item is not None:
                self.RetryTransaction()
            elif self.current_record <= len(self.transaction_data) - 1:
                self.transaction_item = self.transaction_data[self.current_record]
                # Ensure transaction_item is a dictionary
                if not isinstance(self.transaction_item, dict):
                    logger.error(
                        f"Transaction item at index {self.current_record} is not a dictionary: {type(self.transaction_item)}"
                    )
                    self.current_record += 1
                    self.RetrieveData()  # Try the next record
                    return

                self.retry_count = 0
                self.SystemExceptionCount = 0
                self.FoundNewTransaction()
            else:
                self.transaction_item = None
                self.FoundNoData()

    def MainProcess(self):
        if self.retry_count <= self.number_of_retry_attempts:
            try:
                # logger.debug(f"Trying to process Transaction! {self.current_record}")
                # logger.debug(self.transaction_item)

                process_data_function_name = Config.get("ProcessDataFunction", None)

                if process_data_function_name:
                    self.transaction_item = ExecuteProcessFunction(
                        process_data_function_name, self.transaction_item, self
                    )
                else:
                    raise Exception(
                        "Process function name not provided in the configuration"
                    )

                self.ProcessSuccess()

            except RPABusinessException as e:
                logger.error(
                    f"Business Exception occurred - {e.__class__.__name__}: {e}"
                )
                self.BusinessException(e, e.record_data)
            except RPASystemException as e:
                self.SystemExceptionCount += 1
                if all(
                    [
                        self.retry_count >= self.number_of_retry_attempts,
                        self.SystemExceptionCount >= self.number_of_retry_attempts,
                    ]
                ):
                    logger.error(
                        f"System Exception occurred - {e.__class__.__name__}: {e}"
                    )
                    self.SystemExceptionMaxRetries(e, e.record_data)
                else:
                    logger.error(
                        f"System Exception occurred - {e.__class__.__name__}: {e}"
                    )
                    self.SystemException(e, e.record_data)
            except Exception as e:
                self.SystemExceptionCount += 1
                if all(
                    [
                        self.retry_count >= self.number_of_retry_attempts,
                        self.SystemExceptionCount >= self.number_of_retry_attempts,
                    ]
                ):
                    logger.error(f"Error occurred - {e.__class__.__name__}: {e}")
                    self.SystemExceptionMaxRetries(e, self.transaction_item)
                else:
                    logger.error(f"Error occurred - {e.__class__.__name__}: {e}")
                    self.SystemException(e, self.transaction_item)
            finally:
                self.retry_count += 1
        else:
            logger.error("Hit maximum retries for this record")
            self.BusinessException(
                RPABusinessException(
                    "Hit maximum retries for this record", self.transaction_item
                )
            )

    def EndProcessTasks(self):

        logger.info("------ Trying to End Process ------------")

        if not self.initialisation_abort:

            # Close All Applications
            try:
                logger.info("Attempting to close applications")
                ExecuteProcessFunction(
                    Config.get("CloseAllProcessFunction", None),
                    initialised_apps=self.initialised_apps,
                )
            except Exception as e:
                logger.error("Error Closing applications: ", e)

            # Calculate statistics
            if not self.UseLocalTransactionsList:
                if self.transaction_data is None:
                    total_records_count = self.total_processed
                    success_records_count = self.success_count
                    failed_records_count = self.failed_count
                    warning_records_count = self.warning_count
                else:
                    (
                        total_records_count,
                        success_records_count,
                        failed_records_count,
                        warning_records_count,
                        success_records,
                        failed_records,
                        warning_records,
                    ) = self.getRecordcounts()
            else:
                # Original logic for local client list
                (
                    total_records_count,
                    success_records_count,
                    failed_records_count,
                    warning_records_count,
                    success_records,
                    failed_records,
                    warning_records,
                ) = self.getRecordcounts()

            logger.info(f"Total records processed: {total_records_count}")
            logger.info(f"Total successful records: {success_records_count}")
            logger.info(f"Total failed records: {failed_records_count}")
            logger.info(f"Total warning records: {warning_records_count}")

            # For local client list, update the source file with remaining records
            if self.UseLocalTransactionsList and total_records_count > 0:
                client_list_path = Config.get("TransactionListFile", None)
                if not client_list_path:
                    client_list_path = Config.get(
                        "TransactionNotProcessedFile",
                        "./Transactions_not_processed.csv",
                    )
                    if not os.path.exists(client_list_path):
                        # Create the file and write headers if it does not exist
                        if self.transaction_data and len(self.transaction_data) > 0:
                            fieldnames = self.transaction_data[0].keys()
                            with open(
                                client_list_path, mode="w", newline="", encoding="utf-8"
                            ) as csvfile:
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                writer.writeheader()
                if self.transaction_data:
                    fieldnames = self.transaction_data[0].keys()
                    with open(
                        client_list_path, mode="w", newline="", encoding="utf-8"
                    ) as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for record in self.transaction_data:
                            if record.get("status") != "success":
                                record["status"] = ""
                                record["comment"] = ""
                                writer.writerow(record)
                    logger.info(
                        f"Client list updated with remaining records: {client_list_path}"
                    )
                else:
                    logger.info("No remaining records to write to client list.")

            # Get End Time
            end_time, total_time, total_time_minutes, timespan_string = (
                self.calc_end_time(self.start_time)
            )

            print("Calling Finish Job Endpoint")

            self.orchestrator.finish_job(
                self.job_id,
                total_records_count,
                success_records_count,
                failed_records_count,
            )

            # Process log and End Of Process
            if Config.get("ProcessLogFolder", None) is not None:
                self.log_file_path = self.write_process_log_file(
                    end_time,
                    success_records_count,
                    failed_records_count + warning_records_count,
                    total_records_count,
                    total_time_minutes,
                )
            else:
                self.log_file_path = None

            endofprocess_func_name = Config.get("EndofProcessFunction", None)

            if endofprocess_func_name:
                self.transaction_item = ExecuteProcessFunction(
                    endofprocess_func_name, self
                )
            else:
                logger.warning(
                    "End of Process Function not provided in the configuration - Skipping"
                )

        else:
            logger.error("Initialisation Failed, skipping End Process Tasks")
            # raise Exception("Initialisation Failed")
            end_time, total_time, total_time_minutes, timespan_string = (
                self.calc_end_time(self.start_time)
            )

        logger.info(
            f"Total runtime: {total_time}, Total runtime in minutes: {total_time_minutes:.2f}"
        )

    def calc_end_time(self, start_time):

        # Convert total_time_minutes to a proper TimeSpan format
        def minutes_to_timespan_string(minutes):
            """Convert minutes to a TimeSpan string format (hh:mm:ss)"""
            total_seconds = int(minutes * 60)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        end_time = datetime.now()
        logger.info(f"Process ended at {end_time}")
        total_time = end_time - start_time
        total_time_minutes = total_time.total_seconds() / 60
        timespan_string = minutes_to_timespan_string(total_time_minutes)
        return end_time, total_time, total_time_minutes, timespan_string

    def on_FoundNewTransaction(self):
        if not self.UseRobotDataQueue and self.transaction_data is not None:
            logger.info(
                f"Getting Next Record - {(self.current_record +1)} of {len(self.transaction_data)}"
            )
        else:
            logger.info(f"Getting Next Record - {(self.current_record +1)}")

    def on_RetryTransaction(self):
        logger.info(
            f"Attempting Retry Number {self.retry_count} of {self.number_of_retry_attempts} for current record"
        )

    def on_FoundNoData(self):
        logger.info("No more records found to process")

    def on_SystemException(self, exception, record_data=None):
        logger.error(
            f"System Exception occurred - {exception.__class__.__name__}: {exception}"
        )

    def on_SystemExceptionMaxRetries(self, exception, record_data=None):
        logger.error(
            f"Hit maximum System Exception retries on record {self.current_record}, Ending Process. "
        )
        if record_data is not None:
            self.transaction_item = record_data

        # Update the transaction status with the exception
        error_message = f"{exception.__class__.__name__}: {str(exception)}"

        self.update_transaction_status("failed", error_message)

        # For IAA Robot Data Queue processing, track statistics and store the processed item
        if self.UseRobotDataQueue:
            self.total_processed += 1
            self.failed_count += 1
            # Store a copy of the transaction item for reporting
            self.transaction_data.append(self.transaction_item.copy())
        else:
            self.current_record += 1

        self.transaction_item = None

    def on_InitFailed(self, exception=None):
        # logger.error("Initialisation Failed")
        self.initialisation_exception = exception

        if not exception:
            self.initialisation_abort = True

    def on_ProcessSuccess(self):
        logger.info("Transaction processed successfully")

        # For IAA Robot Data Queue processing, track statistics and store the processed item
        if self.UseRobotDataQueue:
            # Update the transaction status
            self.update_transaction_status("success")
            self.total_processed += 1
            self.success_count += 1
            # Store a copy of the transaction item for reporting
            self.transaction_data.append(self.transaction_item.copy())
        else:
            # Update the transaction status
            self.update_transaction_status(status="success")
            self.current_record += 1

        self.transaction_item = None

    def on_BusinessException(self, exception, record_data=None):
        if record_data is not None:
            self.transaction_item = record_data

        # if self.retry_count > self.number_of_retry_attempts:  - Don't retry
        # logger.info('Maximum retries reached, marking transaction as failed')
        # Update the transaction status with the exception
        error_message = f"{exception.__class__.__name__}: {str(exception)}"

        # Update Transaction Status - No Return Value
        self.update_transaction_status("warning", error_message)

        # For IAA Robot Data Queue processing, track statistics and store the processed item
        if self.UseRobotDataQueue:
            should_retry = str_to_bool(Config.get("BusinessExceptionRetry", True))
            has_retries_left = self.retry_count < self.number_of_retry_attempts

            # Only count as processed when we're done retrying
            if not should_retry or not has_retries_left:
                self.total_processed += 1
                self.failed_count += 1
                # Store a copy of the transaction item for reporting
                if self.transaction_item is not None:
                    self.transaction_data.append(self.transaction_item.copy())
                self.transaction_item = None
                self.retry_count = 0
            # else: keep transaction_item set so it will be retried
        else:
            self.current_record += 1
            self.transaction_item = None

    def getRecordcounts(self):
        if self.transaction_data is not None:
            total_records_count = len(self.transaction_data)
            success_records = [
                record
                for record in self.transaction_data
                if record.get("status") in ["success", "completed"]
            ]
            success_records_count = len(success_records)
            failed_records = [
                record
                for record in self.transaction_data
                if record.get("status") in ["Failed", "failed"]
            ]
            failed_records_count = len(failed_records)
            warning_records = [
                record
                for record in self.transaction_data
                if record.get("status") == "warning"
            ]
            warning_records_count = len(warning_records)

        else:
            total_records_count = 0
            success_records_count = 0
            failed_records_count = 0
            warning_records_count = 0
            success_records = []
            failed_records = []
            warning_records = []

        return (
            total_records_count,
            success_records_count,
            failed_records_count,
            warning_records_count,
            success_records,
            failed_records,
            warning_records,
        )

    def update_transaction_status(self, status=None, comment=None):
        """
        Updates the status and comment of the current transaction item.

        Args:

            status (str): The status to set for the transaction item.
            comment: Optional comment or error message.
        """

        if self.UseRobotDataQueue:
            # Assume Process a single record from the data queue so update status of the current item and the logfile.
            self.transaction_item["status"] = status
            self.transaction_item["comment"] = str(comment) if comment else ""

            # update DataQueueItem
            self.orchestrator.update_data_queue_item(self.transaction_item)

            # Write/append the current transaction item to the file
            transaction_log_file = Config.get("TransactionLogFile", None)
            if transaction_log_file:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(transaction_log_file), exist_ok=True)
                # Ensure the file exists before appending
                open(transaction_log_file, "a").close()

                with open(
                    transaction_log_file, mode="a", newline="", encoding="utf-8"
                ) as logfile:
                    # Add Date and Time as the first two fields
                    fieldnames = ["Date", "Time"] + list(self.transaction_item.keys())
                    writer = csv.DictWriter(logfile, fieldnames=fieldnames)
                    if logfile.tell() == 0:  # Check if file is empty to write header
                        writer.writeheader()
                    # Add current date and time to the record
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    current_time = datetime.now().strftime("%H:%M:%S")
                    record = {"Date": current_date, "Time": current_time}
                    record.update(self.transaction_item)
                    writer.writerow(record)
                logger.info(
                    f"Transaction item appended to log file: {transaction_log_file}"
                )
            else:
                logger.warning("Transaction log file path not found in config.")

        else:
            self.transaction_data[self.current_record]["status"] = status
            self.transaction_data[self.current_record]["comment"] = (
                str(comment) if comment else ""
            )

    def write_process_log_file(
        self, end_time, success_records, failed_records, total_records, minutes_spent
    ):
        """
        Writes the process log details to a specified log file.

        Args:

            config (dict): The configuration dictionary.
            start_time (datetime): The start time of the process.
            end_time (datetime): The end time of the process.
            success_records (int): The total number of successful records.
            failed_records (int): The total number of failed records.
            total_records (int): The total number of records processed.
            minutes_spent (float): The total minutes spent on the process.
        """
        # Ensure the file exists before appending

        process_name = Config.get("ProcessName", None)
        client_name = Config.get("ClientName", None)
        client_code = Config.get("ClientCode", None)
        subscription_code = Config.get("SubscriptionCode", None)
        process_type = Config.get("ProcessType", None)
        log_file_path = (
            create_processlog_subfolder(Config.get("ProcessLogFolder", None))
            + "/"
            + "ProcessLog_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".csv"
        )

        if not os.path.exists(log_file_path):
            open(log_file_path, "a").close()
        with open(log_file_path, mode="a", newline="", encoding="utf-8") as logfile:
            fieldnames = [
                "Date",
                "Client Name",
                "Client Code",
                "Process Name",
                "Start Time",
                "End Time",
                "Success Records",
                "Failed Records",
                "Total Records",
                "Minutes Spent",
                "Subscription Code",
                "Process Type",
            ]
            writer = csv.DictWriter(logfile, fieldnames=fieldnames)
            if logfile.tell() == 0:  # Check if file is empty to write header
                writer.writeheader()
            # Prepare the log record
            current_date = datetime.now().strftime("%Y-%m-%d")
            record = {
                "Date": current_date,
                "Client Name": client_name,
                "Client Code": client_code,
                "Process Name": process_name,
                "Start Time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "End Time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Success Records": success_records,
                "Failed Records": failed_records,
                "Total Records": total_records,
                "Minutes Spent": minutes_spent,
                "Subscription Code": subscription_code,
                "Process Type": process_type,
            }
            writer.writerow(record)
        logger.info(f"Process log entry appended to log file: {log_file_path}")
        return log_file_path


# [Copy the entire RPAStateMachine class from tasks.py]
