# 📊 Sector-Aware Momentum Analysis

## Overview

The NEPSE AI Trading Bot now uses **sector-specific momentum lookback periods** to improve entry date prediction accuracy. Different sectors in NEPSE have fundamentally different price movement characteristics, and this update reflects that reality.

## Why Sector-Specific Momentum?

In NEPSE, different sectors behave differently:

| Sector | Characteristics | Momentum Period |
|--------|----------------|-----------------|
| **Hydro Power** | Fast operator-driven pumps, high volatility | **7 days** |
| **Commercial Banks** | Macro trend followers, institutional money | **14 days** |
| **Development Banks** | Medium-term institutional flows | **12 days** |
| **Microfinance** | Credit cycle dependent | **10 days** |
| **Finance Companies** | Similar to microfinance | **10 days** |
| **Insurance** | Long macro trends, low liquidity | **14 days** |
| **Manufacturing** | Fundamental-driven, slowest movers | **21 days** |
| **Default** | For other/unknown sectors | **10 days** |

## How It Works

### 1. Configuration (`core/config.py`)

```python
# Sector-specific momentum periods (trading days, excluding Fri/Sat)
momentum_hydro: int = 7
momentum_banking: int = 14
momentum_microfinance: int = 10
momentum_dev_bank: int = 12
momentum_finance: int = 10
momentum_insurance: int = 14
momentum_manufacturing: int = 21
momentum_default: int = 10
```

### 2. Sector Detection (`core/sector_config.py`)

```python
from core.sector_config import get_momentum_period

# Automatically maps NEPSE sector names
momentum_days = get_momentum_period("Hydro Power")  # Returns 7
momentum_days = get_momentum_period("Commercial Banks")  # Returns 14
```

### 3. Entry Date Prediction (`analysis/technical_signal_engine.py`)

The `_predict_entry_date()` function now:
1. Accepts a `sector` parameter
2. Gets sector-specific momentum period
3. Uses that period to calculate recent price trend
4. Predicts when price will reach entry zone based on sector characteristics

```python
# Old (hardcoded 10 days for all sectors)
recent = df.tail(10)

# New (sector-aware)
momentum_days = get_momentum_period(sector)  # 7, 14, or 21 depending on sector
recent = df.tail(momentum_days)
```

## Trading Days vs Calendar Days

**IMPORTANT:** All momentum periods are in **TRADING DAYS** (not calendar days).

- NEPSE trading days: Sunday, Monday, Tuesday, Wednesday, Thursday (5 days/week)
- Closed: Friday, Saturday
- 7 trading days = ~10 calendar days
- 14 trading days = ~20 calendar days
- Pandas `.tail(7)` correctly uses trading days (rows), not calendar days

## Example: KKHC (Hydro Power)

```python
# KKHC is in "Hydro Power" sector
# Old system: Used 10-day momentum (too slow for hydro pumps)
# New system: Uses 7-day momentum (matches fast operator cycles)

Signal:
  LTP: Rs. 290
  Entry Zone: Rs. 284 (2.1% pullback expected)
  Momentum: 7-day average shows -0.3% daily change
  Prediction: 3-5 days to reach entry zone
```

## Impact on Trading Signals

### Hydro Stocks (7 days)
- **Faster detection** of operator pump cycles
- Entry predictions react to **last week's movement**
- Better for stocks with 2-3 week pump patterns

### Banking Stocks (14 days)
- **Smoother momentum** based on macro trends
- Less sensitive to daily noise
- Better for institutional accumulation detection

### Manufacturing (21 days)
- **Longest lookback** for fundamental-driven moves
- Filters out short-term volatility
- Entry predictions based on monthly trends

## Configuration

You can adjust these periods in `core/config.py`:

```python
from core.config import settings

# View current settings
print(settings.momentum_hydro)  # 7

# Modify if needed (requires restart)
settings.momentum_hydro = 5  # Make hydro even faster
```

## Testing

```bash
# Test sector detection
python -c "
from core.sector_config import get_momentum_period
print(get_momentum_period('Hydro Power'))  # 7
print(get_momentum_period('Commercial Banks'))  # 14
"

# Test with real signal
python -m tools.paper_trader --signal KKHC
# Will automatically use 7-day momentum for Hydro Power
```

## Technical Details

### Files Modified

1. **`core/config.py`** - Added sector momentum configuration
2. **`core/sector_config.py`** - New helper module for sector logic
3. **`analysis/technical_signal_engine.py`** - Updated entry prediction to use sector
4. **`tools/paper_trader.py`** - Pass sector to signal generation

### Backward Compatibility

- ✅ If sector is `None` or unknown, defaults to 10 days
- ✅ All existing code works without changes
- ✅ Sector parameter is optional in all functions

## Future Enhancements

Potential improvements:
1. **Dynamic period adjustment** based on market volatility
2. **Sector-specific target percentages** (Hydro targets vs Banking targets)
3. **Volume thresholds** per sector (Hydro needs higher volume confirmation)
4. **Hold duration** estimates per sector characteristics

## References

- User request: "Make scanner sector-aware with different momentum lookbacks"
- NEPSE trading calendar: 5 days/week (Sun-Thu)
- Momentum analysis: Uses `pandas.DataFrame.tail()` for last N bars
- Entry prediction: `analysis/technical_signal_engine.py:1650`

---
**Implementation Date:** 2026-03-25  
**Version:** 2.1.0  
**Status:** ✅ Production Ready
