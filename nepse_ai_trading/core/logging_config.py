"""
Logging configuration using Loguru.
Provides consistent logging across all modules.
"""

import sys
from pathlib import Path
from loguru import logger
from core.config import settings


def setup_logging():
    """
    Configure Loguru for the application.
    Logs to both console and file with rotation.
    """
    # Remove default handler
    logger.remove()
    
    # Console logging with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    
    # File logging with rotation
    log_path = Path(settings.log_file)
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="10 MB",  # Rotate when file reaches 10MB
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress rotated files
        serialize=False,
    )
    
    # Add special handler for trading signals (separate file)
    signals_log = log_path.parent / "trading_signals.log"
    logger.add(
        signals_log,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        filter=lambda record: "signal" in record["extra"],
        rotation="1 week",
        retention="30 days",
    )
    
    logger.info(f"Logging initialized. Level: {settings.log_level}")
    return logger


# Export configured logger
def get_logger(name: str = None):
    """Get a logger instance, optionally with a specific name."""
    if name:
        return logger.bind(name=name)
    return logger
