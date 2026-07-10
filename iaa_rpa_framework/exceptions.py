class RPABusinessException(Exception):
    def __init__(self, message, record_data=None):
        super().__init__(message)
        self.record_data = record_data


class RPASystemException(Exception):
    def __init__(self, message, record_data=None):
        super().__init__(message)
        self.record_data = record_data


class InitialisationError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        base_msg = super().__str__()
        if self.error_code:
            base_msg += f" (Error Code: {self.error_code})"
        return base_msg


class ConfigAPILoadException(InitialisationError):
    """Raised when error occurs while loading config from API"""

    pass


class ConfigYamlLoadException(InitialisationError):
    """Raised when error occurs while loading config from YAML file"""

    pass


class IntialiseApplicationsException(InitialisationError):
    """Raised when error occurs while initialising applications"""

    pass
