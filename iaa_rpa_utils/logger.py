import logging
from time import perf_counter


class _MaxLevelFilter(logging.Filter):
    """Allow records up to (and including) max_level."""
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


def setup_logger(name: str | None = None, level: str = "INFO") -> logging.Logger:
    """
    Configure a logger that propagates to the root logger.
    Screen display and file writing are handled by the framework (Sema4ai/Robocorp).
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a (possibly already configured) logger by name."""
    return logging.getLogger(name)


class ProcessLogger:
    """Context manager for timing & success/failure logs."""
    def __init__(self, process_name: str, logger: logging.Logger | None = None):
        self.process_name = process_name
        self.logger = logger or logging.getLogger(__name__)
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = perf_counter()
        self.logger.info("Starting: %s", self.process_name)
        return self

    def __exit__(self, exc_type, exc, tb):
        dt = perf_counter() - self._t0
        if exc_type is None:
            self.logger.info("Completed: %s (%.2fs)", self.process_name, dt)
        else:
            self.logger.error("Failed: %s (%.2fs) — %s", self.process_name, dt, exc)
        return False  # don't suppress exceptions
