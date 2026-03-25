"""
Sector-Specific Configuration for NEPSE Trading.

Different sectors in NEPSE have different momentum characteristics:
- Hydro: Operator-driven, fast pumps (7 days)
- Banking: Macro trends, institutional (14 days)
- Manufacturing: Fundamental-driven, slow (21 days)

All periods are in TRADING DAYS (excluding Friday/Saturday).
"""

from typing import Optional
from core.config import settings


def get_momentum_period(sector: Optional[str]) -> int:
    """
    Get sector-specific momentum lookback period (in TRADING DAYS).
    
    Args:
        sector: Sector name (case-insensitive)
        
    Returns:
        Number of trading days to look back for momentum calculation
        
    Examples:
        >>> get_momentum_period("Hydro")
        7
        >>> get_momentum_period("banking")
        14
        >>> get_momentum_period("Unknown Sector")
        10  # default
    """
    if not sector:
        return settings.momentum_default
    
    # Normalize sector name (lowercase, strip whitespace)
    sector_lower = sector.strip().lower()
    
    # Map sector to config setting
    # NOTE: NEPSE uses "Hydro Power" (with space), so handle both
    sector_map = {
        "hydro": settings.momentum_hydro,
        "hydro power": settings.momentum_hydro,  # NEPSE official name
        "hydropower": settings.momentum_hydro,
        "banking": settings.momentum_banking,
        "commercial banking": settings.momentum_banking,
        "commercial banks": settings.momentum_banking,
        "microfinance": settings.momentum_microfinance,
        "micro finance": settings.momentum_microfinance,
        "development bank": settings.momentum_dev_bank,
        "development banks": settings.momentum_dev_bank,
        "dev bank": settings.momentum_dev_bank,
        "finance": settings.momentum_finance,
        "finance company": settings.momentum_finance,
        "finance companies": settings.momentum_finance,
        "insurance": settings.momentum_insurance,
        "life insurance": settings.momentum_insurance,
        "non life insurance": settings.momentum_insurance,
        "non-life insurance": settings.momentum_insurance,
        "general insurance": settings.momentum_insurance,
        "manufacturing": settings.momentum_manufacturing,
        "production": settings.momentum_manufacturing,
        "manufacturing & processing": settings.momentum_manufacturing,
    }
    
    return sector_map.get(sector_lower, settings.momentum_default)


def get_sector_characteristics(sector: Optional[str]) -> dict:
    """
    Get detailed sector trading characteristics.
    
    Args:
        sector: Sector name
        
    Returns:
        Dict with momentum_days, description, and risk_profile
    """
    sector_lower = sector.strip().lower() if sector else "unknown"
    
    characteristics = {
        "hydro": {
            "momentum_days": settings.momentum_hydro,
            "description": "Fast operator-driven pumps",
            "risk_profile": "HIGH",
            "typical_hold": "5-10 days",
            "liquidity": "HIGH",
        },
        "banking": {
            "momentum_days": settings.momentum_banking,
            "description": "Macro trend followers",
            "risk_profile": "LOW",
            "typical_hold": "10-20 days",
            "liquidity": "VERY HIGH",
        },
        "microfinance": {
            "momentum_days": settings.momentum_microfinance,
            "description": "Credit cycle dependent",
            "risk_profile": "MEDIUM",
            "typical_hold": "7-15 days",
            "liquidity": "MEDIUM",
        },
        "development bank": {
            "momentum_days": settings.momentum_dev_bank,
            "description": "Medium-term institutional",
            "risk_profile": "MEDIUM",
            "typical_hold": "10-18 days",
            "liquidity": "MEDIUM",
        },
        "finance": {
            "momentum_days": settings.momentum_finance,
            "description": "Similar to microfinance",
            "risk_profile": "MEDIUM",
            "typical_hold": "7-15 days",
            "liquidity": "MEDIUM",
        },
        "insurance": {
            "momentum_days": settings.momentum_insurance,
            "description": "Long macro trends",
            "risk_profile": "LOW",
            "typical_hold": "15-30 days",
            "liquidity": "LOW",
        },
        "manufacturing": {
            "momentum_days": settings.momentum_manufacturing,
            "description": "Fundamental-driven (slowest)",
            "risk_profile": "MEDIUM",
            "typical_hold": "20-40 days",
            "liquidity": "LOW",
        },
    }
    
    # Find matching sector (case-insensitive, partial match)
    for key, value in characteristics.items():
        if key in sector_lower:
            return value
    
    # Default characteristics
    return {
        "momentum_days": settings.momentum_default,
        "description": "Standard momentum analysis",
        "risk_profile": "MEDIUM",
        "typical_hold": "10-15 days",
        "liquidity": "MEDIUM",
    }


# Quick reference constants
FAST_SECTORS = ["hydro", "hydropower"]
SLOW_SECTORS = ["manufacturing", "production", "insurance"]
LIQUID_SECTORS = ["banking", "commercial banking"]
