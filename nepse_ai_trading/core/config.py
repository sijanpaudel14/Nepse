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
    
    # Broker commission (NEPSE standard — 0.36% per side as of 2025)
    broker_commission_pct: float = 0.0036  # 0.36%
    
    # SEBON fee
    sebon_fee_pct: float = 0.00015  # 0.015%
    
    # DP charge (per transaction)
    dp_charge: float = 25.0  # Rs. 25 per transaction
    
    # Total transaction costs (used for position closing calculations)
    total_transaction_cost_pct: float = 0.00375  # 0.36% broker + 0.015% SEBON
    
    # ============ NEPSE MARKET CONSTANTS ============
    # NEPSE trading days/year (~230, Sun-Thu minus holidays)
    nepse_trading_days_per_year: int = 230
    # Risk-free rate from NRB T-bill (updated periodically)
    risk_free_rate: float = 0.055  # 5.5% as of early 2026
    
    # Maximum risk per trade as percentage (for portfolio manager)
    max_risk_per_trade_pct: float = 2.0  # 2% maximum risk per trade
    
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
    
    # ============ SECTOR-SPECIFIC MOMENTUM (TRADING DAYS) ============
    # Different sectors have different momentum characteristics in NEPSE
    # Note: These are TRADING DAYS (excluding Friday/Saturday holidays)
    momentum_hydro: int = 7           # Fast operator-driven pumps
    momentum_banking: int = 14        # Macro trend followers
    momentum_microfinance: int = 10   # Credit cycle dependent
    momentum_dev_bank: int = 12       # Medium-term institutional
    momentum_finance: int = 10        # Similar to microfinance
    momentum_insurance: int = 14      # Long macro trends
    momentum_manufacturing: int = 21  # Fundamental-driven (slowest)
    momentum_default: int = 10        # Default for other sectors
    
    # ============ API SETTINGS ============
    # SECURITY: JWT secret MUST be set via environment variable.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_secret_key: str = ""  # Empty = app will generate random key on startup (non-persistent)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ============ SECTOR PE BENCHMARKS ============
    # Sector-specific valuation thresholds (replaces blanket PE < 15)
    sector_pe_medians: dict = {
        "Commercial Banks": 22,
        "Development Banks": 18,
        "Finance": 16,
        "Life Insurance": 30,
        "Non Life Insurance": 25,
        "Hydro Power": 35,
        "Manufacturing And Processing": 20,
        "Hotels And Tourism": 25,
        "Trading": 18,
        "Microfinance": 15,
        "Investment": 20,
        "Others": 20,
    }
    sector_pbv_medians: dict = {
        "Commercial Banks": 1.5,
        "Development Banks": 1.2,
        "Finance": 1.0,
        "Life Insurance": 3.0,
        "Non Life Insurance": 2.0,
        "Hydro Power": 3.0,
        "Manufacturing And Processing": 1.5,
        "Hotels And Tourism": 2.0,
        "Trading": 1.0,
        "Microfinance": 1.5,
        "Investment": 1.5,
        "Others": 1.5,
    }
    
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
    s = Settings()
    # SECURITY: If JWT secret is empty, generate a random one (non-persistent across restarts)
    if not s.jwt_secret_key or s.jwt_secret_key == "change-this-in-production":
        import secrets
        import warnings
        s.jwt_secret_key = secrets.token_urlsafe(64)
        warnings.warn(
            "JWT_SECRET_KEY not set in environment! Using random key. "
            "Tokens will be invalidated on restart. "
            "Set JWT_SECRET_KEY in .env for production.",
            RuntimeWarning,
            stacklevel=2,
        )
    return s


# Global settings instance for convenience
settings = get_settings()
