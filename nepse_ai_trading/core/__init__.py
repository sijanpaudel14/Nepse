"""
Core module for NEPSE AI Trading Bot.
Contains configuration, database, and common utilities.
"""

from .config import settings
from .database import get_db, init_db
from .exceptions import (
    NepseAPIError,
    DataValidationError,
    StrategyError,
    InsufficientDataError,
)

__all__ = [
    "settings",
    "get_db",
    "init_db",
    "NepseAPIError",
    "DataValidationError",
    "StrategyError",
    "InsufficientDataError",
]
