"""
Custom exceptions for NEPSE AI Trading Bot.
Centralized exception handling for better error management.
"""


class NepseAIException(Exception):
    """Base exception for all NEPSE AI Trading Bot errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NepseAPIError(NepseAIException):
    """
    Raised when NEPSE API calls fail.
    Common causes: API down, rate limiting, network issues.
    """
    pass


class DataValidationError(NepseAIException):
    """
    Raised when data fails validation.
    Common causes: Malformed NEPSE data, missing fields, wrong types.
    """
    pass


class InsufficientDataError(NepseAIException):
    """
    Raised when not enough historical data for analysis.
    Example: Need 60 days of data but only have 30.
    """
    pass


class StrategyError(NepseAIException):
    """
    Raised when a trading strategy encounters an error.
    Common causes: Invalid parameters, calculation failures.
    """
    pass


class ScraperError(NepseAIException):
    """
    Raised when web scraping fails.
    Common causes: Site structure changed, blocked, timeout.
    """
    pass


class AIAdvisorError(NepseAIException):
    """
    Raised when OpenAI integration fails.
    Common causes: API key invalid, rate limit, model unavailable.
    """
    pass


class NotificationError(NepseAIException):
    """
    Raised when sending notifications fails.
    Common causes: Invalid token, network issues.
    """
    pass


class RiskLimitExceeded(NepseAIException):
    """
    Raised when a trade would exceed risk limits.
    Example: Max positions reached, drawdown limit hit.
    """
    pass


class BacktestError(NepseAIException):
    """
    Raised when backtesting encounters an error.
    Common causes: Invalid date range, missing data.
    """
    pass
