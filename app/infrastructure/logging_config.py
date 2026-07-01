import sys
from pathlib import Path

from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/app.log",
    rotation: str = "10 MB",
    retention: str = "1 month",
    compression: str = "zip",
) -> None:
    """Configures the loguru logger to write to both stdout and a rolling log file.

    Args:
        log_level: The threshold logging level (e.g. DEBUG, INFO, WARNING, ERROR).
        log_file: The path to the log file to write logs to.
        rotation: Trigger criteria for rolling a new file (e.g. size in MB, or time).
        retention: Clean-up window for stale log files (e.g. '1 month').
        compression: The archival compression algorithm for rolled logs (e.g. 'zip').
    """
    # Remove default handler
    logger.remove()

    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to current working directory log location if write permissions fail
        log_file = "app.log"
        log_path = Path(log_file)

    # Standard log format matching premium commercial systems
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Console Handler (Stdout)
    if sys.stdout is not None:
        logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # File Handler
    try:
        logger.add(
            str(log_path),
            format=log_format,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe async logging queue
        )
    except Exception:
        pass

    logger.info("Logging initialized successfully (Level: {}, File: {})", log_level, log_file)
