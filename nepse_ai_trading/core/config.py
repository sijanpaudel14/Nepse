"""
Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated here.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env file - check current directory and parent directories
def _find_env_file() -> Optional[str]:
    """Find .env file in current directory or parent directories."""
    current = Path.cwd()
    # Check current and up to 3 parent levels
    for _ in range(4):
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent
    return ".env"  # Fallback to default


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses .env file if present, otherwise falls back to system env vars.
    """
    
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ============ DATABASE ============
    database_url: str = "sqlite:///./nepse_data.db"
    
    # ============ OPENAI ============
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # ============ TELEGRAM ============
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # ============ EMAIL ============
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    
    # ============ TRADING PARAMETERS ============
    # Risk per trade as decimal (0.02 = 2%)
    risk_per_trade: float = 0.02
    # Maximum concurrent positions
    max_positions: int = 5
    # Minimum stock price to consider (filters penny stocks)
    min_price: float = 200.0
    # Target profit percentage
    target_profit: float = 0.10
    # Stop loss percentage
    stop_loss: float = 0.05
    
    # ============ NEPSE EXECUTION REALITIES ============
    # NEPSE TMS has NO API - all trades are manual!
    # These settings model the reality of manual execution:
    
    # Slippage: Price difference between signal and actual execution
    # In illiquid NEPSE stocks, expect 1-2% slippage during volatile times
    slippage_pct: float = 0.015  # 1.5% default slippage
    
    # Broker commission (NEPSE standard)
    broker_commission_pct: float = 0.004  # 0.4%
    
    # SEBON fee
    sebon_fee_pct: float = 0.00015  # 0.015%
    
    # DP charge (per transaction)
    dp_charge: float = 25.0  # Rs. 25 per transaction
    
    # ============ TECHNICAL ANALYSIS DEFAULTS ============
    # EMA periods for trend detection
    ema_short: int = 9
    ema_long: int = 21
    # RSI period
    rsi_period: int = 14
    # RSI thresholds for momentum filter
    rsi_min: float = 50.0
    rsi_max: float = 65.0
    # Volume spike multiplier (1.5 = 150% of average)
    volume_spike_multiplier: float = 1.5
    # Volume average period
    volume_avg_period: int = 20
    # Days of historical data to fetch
    lookback_days: int = 60
    
    # ============ API SETTINGS ============
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ============ LOGGING ============
    log_level: str = "INFO"
    log_file: str = "nepse_bot.log"
    
    # ============ SCHEDULER ============
    analysis_time: str = "10:30"
    scheduler_enabled: bool = True
    
    # ============ NEPSE API ============
    # Base URL for NEPSE Unofficial API
    nepse_api_base_url: str = "https://nepse-data-api.herokuapp.com/api"
    # Fallback endpoints
    nepse_api_timeout: int = 30
    nepse_api_retries: int = 3
    
    # ============ SHAREHUB ============
    sharehub_auth_token: str = ""
    
    @property
    def is_configured(self) -> bool:
        """Check if essential API keys are configured."""
        return bool(self.openai_api_key and self.telegram_bot_token)
    
    @property
    def database_is_sqlite(self) -> bool:
        """Check if using SQLite (for async handling)."""
        return self.database_url.startswith("sqlite")


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance. 
    Call this function to get settings throughout the app.
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()
