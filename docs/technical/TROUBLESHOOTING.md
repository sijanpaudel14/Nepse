# 🔧 Troubleshooting Guide
## NEPSE AI Trading System - Common Issues & Solutions

---

## 📋 Table of Contents

1. [Installation Issues](#installation-issues)
2. [API & Data Fetching](#api--data-fetching)
3. [Scoring & Analysis](#scoring--analysis)
4. [Auto Logger Issues](#auto-logger-issues)
5. [Portfolio Tracking](#portfolio-tracking)
6. [Performance Problems](#performance-problems)
7. [Error Messages Decoded](#error-messages-decoded)

---

## 🔨 Installation Issues

### Problem: `ModuleNotFoundError: No module named 'pandas'`

**Cause:** Dependencies not installed

**Solution:**
```bash
pip install -r requirements.txt
# or
pip install pandas pandas-ta loguru pydantic requests httpx
```

### Problem: `ImportError: cannot import name 'NepseFetcher'`

**Cause:** Wrong Python path or module structure

**Solution:**
```bash
# Run from project root
cd /path/to/Nepse

# Set PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH

# Or run with python -m
python -m nepse_ai_trading.tools.paper_trader --scan
```

### Problem: Playwright installation fails

**Cause:** Missing system dependencies

**Solution:**
```bash
# Install playwright (optional, only for news scraping)
pip install playwright
playwright install chromium

# If it fails, skip news features
python paper_trader.py --scan  # Works without playwright
```

---

## 🌐 API & Data Fetching

### Problem: `❌ Smart Money Flow - Timeout (>5min)`

**Cause:** Smart money analysis makes 60+ API calls for all stocks

**Solution 1** - Use sector filtering:
```bash
python paper_trader.py --smart-money --sector=hydro  # Much faster
```

**Solution 2** - Increase timeout in auto_logger.py:
```python
# Line 72-86: Timeout detection
timeouts = {
    "--smart-money": 600,  # Increase from 420 to 600 seconds
}
```

**Solution 3** - Run during off-peak hours (avoid 11am-3pm NEPSE hours)

### Problem: `ValueError: could not convert string to float: '10,00,000'`

**Cause:** Old code using unsafe type conversions

**Status:** ✅ FIXED in latest version

**Verification:**
```python
# Should now use safe conversion:
# sharehub_api.py lines 746-803: _safe_int() and _safe_float()
```

### Problem: `AttributeError: 'str' object has no attribute 'get'`

**Cause:** Bulk deals API returns paginated dict, code expects flat list

**Status:** ✅ FIXED in latest version (lines 1526-1530 in sharehub_api.py)

### Problem: `No data available for stock XXXX`

**Possible Causes:**
1. Stock is suspended
2. API is down
3. Symbol is incorrect
4. Recent IPO (< 14 days data)

**Solution:**
```bash
# Verify symbol
python paper_trader.py --analyze NABIL  # Correct
python paper_trader.py --analyze NABL   # Wrong! ❌

# Check if stock is trading
# Visit nepseAlpha.com or merolagani.com to verify

# Try with different case
python paper_trader.py --analyze nabil  # Auto-converts to uppercase
```

### Problem: `Dividend history showing 0.00%` but company declared dividends

**Cause:** Attribute name mismatch (cash_dividend vs cash_pct)

**Status:** ✅ FIXED in latest version

**Verification:** Dividends should now show correctly in --analyze reports

### Problem: `Net flow is always Rs. 0.0Cr`

**Cause:** Broker trading is a closed system (every buy has a sell)

**Status:** ✅ FIXED - Now uses top 10 buyers vs top 10 sellers

**How it works now:**
```python
# OLD (wrong):
net_flow = sum(all_brokers.net_amount)  # Always 0

# NEW (correct):
inflow = sum(top_10_buyers.net_amount where > 0)
outflow = abs(sum(top_10_sellers.net_amount where < 0))
net_flow = inflow - outflow
```

---

## 📊 Scoring & Analysis

### Problem: `Stock scores 85 but classified as VETO`

**Cause:** 2+ veto reasons override score

**Expected Behavior:**
```
Score >= 70 + 0 vetos    → GOOD
Score >= 70 + 1 veto     → RISKY
Score >= 70 + 2+ vetos   → VETO
Score < 70               → NOT_QUALIFIED
```

**Status:** Working as intended (conservative risk management)

**To override:** Comment out veto checks in paper_trader.py lines 520-556

### Problem: `RSI unavailable` for stocks with sufficient data

**Cause:** RSI logic bug - if RSI=0, neither condition triggers

**Status:** ✅ FIXED in latest version

**What changed:**
```python
# OLD (buggy):
if rsi > 70:
    veto()
elif 0 < rsi < 40:  # RSI=0 skips this!
    veto()

# NEW (fixed):
if rsi is None or rsi <= 0:
    veto("RSI unavailable")
elif rsi > 70:
    veto("overbought")
elif rsi < 40:
    veto("below momentum zone")
```

### Problem: `14D VWAP unavailable` even when data exists

**Cause:** Logic bug - condition check fails → always adds veto

**Status:** ✅ FIXED in latest version

**What changed:**
```python
# OLD (buggy):
if vwap_14d and vwap_14d > 0 and current_price > 0:
    calculate_premium()
else:
    veto("VWAP unavailable")  # Always fires!

# NEW (fixed):
vwap_available = False
if vwap_14d is not None and vwap_14d > 0:
    vwap_available = True

if vwap_available and current_price > 0:
    calculate_premium()
elif not vwap_available:
    veto("VWAP unavailable")  # Only when truly unavailable
```

### Problem: `PBV = 0.00 for stocks with book value < 1`

**Cause:** PBV logic error (book_value >= 1.0 threshold)

**Status:** ✅ FIXED in latest version

**What changed:**
```python
# OLD (wrong):
pbv = ltp / book_value if book_value >= 1.0 else 0  # Sets PBV=0!

# NEW (correct):
if book_value > 0:
    pbv = ltp / book_value
else:
    pbv = None  # Can't calculate, not 0
```

### Problem: `EPS showing 0.00 for profitable companies`

**Possible Causes:**
1. Quarterly data not annualized
2. API returning wrong fiscal year
3. Paid-up capital missing

**Check:**
```bash
# View raw fundamentals
python paper_trader.py --analyze NABIL --full

# Look for:
# - eps_annualized (should be non-zero)
# - fiscal_year (should be recent)
# - net_profit (should match expectations)
```

**Manual Fix:**
```python
# In sharehub_api.py, _calculate_annualized_eps()
# Adjust multipliers if needed (lines 768-863)
```

---

## ⏰ Auto Logger Issues

### Problem: `❌ Momentum Scan - Timeout (>2min)`

**Cause:** Scanning 600+ stocks takes 5-7 minutes, not 2 minutes

**Solution:** Increase timeout in auto_market_logger.py:
```python
# Line 76-77:
timeouts = {
    "--scan": 600,  # Change from 420 to 600 seconds (10 min)
}
```

### Problem: Auto logger creates empty markdown files

**Cause:** Command failed but error not caught

**Debug:**
```bash
# Run commands manually to see actual error
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum

# Check last 50 lines for errors
tail -50 market_logs/YYYY-MM-DD_HHMM/03_momentum_scan.md
```

### Problem: Missing broker intelligence reports (05b, 05c, 05d, 05e)

**Cause:** Broker intelligence not integrated in auto logger

**Status:** ✅ FIXED in latest version (Phase 2 lines 234-268)

**Verify:**
```bash
# Should generate 4 broker intel reports:
ls market_logs/YYYY-MM-DD_HHMM/05*.md

# Expected output:
# 05_smart_money.md
# 05b_broker_intel_all.md
# 05c_broker_intel_hydro.md
# 05d_broker_intel_banks.md
# 05e_broker_intel_finance.md
```

### Problem: `DeprecationWarning: Use 'content=<...>' to upload raw bytes`

**Cause:** HTTPX library deprecation (18+ warnings)

**Status:** ✅ FIXED in latest version

**What changed:**
```python
# paper_trader.py lines 28-31: Warning filter added
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
```

---

## 💼 Portfolio Tracking

### Problem: `Portfolio shows 0 positions` after buying stocks

**Cause:** Portfolio not initialized in SQLite

**Solution:**
```bash
# Initialize portfolio table
python paper_trader.py --action=status

# Buy stocks properly
python paper_trader.py --action=buy --symbol=NABIL --price=1234.50
```

### Problem: `P&L calculation incorrect`

**Check:**
1. Entry price recorded correctly?
2. Current LTP fetched successfully?
3. Exit signals generated?

**Debug:**
```bash
# View portfolio details
python paper_trader.py --portfolio

# Check SQLite directly
sqlite3 paper_trader.db "SELECT * FROM portfolio_holdings;"
```

### Problem: `Exit signal not generated` for losing position

**Cause:** Exit logic only triggers on:
- Score drops below 60
- 2+ new veto reasons appear
- Manual stop-loss (not yet implemented)

**Feature Request:** Add configurable stop-loss % (e.g., -10%)

---

## ⚡ Performance Problems

### Problem: `Full scan takes 30+ minutes`

**Normal:** Scanning 600+ stocks with 400-day history takes time

**Speed up:**
```bash
# Option 1: Quick mode (top 50 stocks only)
python paper_trader.py --scan --quick --strategy=momentum

# Option 2: Sector filtering
python paper_trader.py --scan --sector=hydro --strategy=momentum

# Option 3: Parallel processing (future enhancement)
```

### Problem: `High memory usage (>4GB)`

**Cause:** Loading 400 days × 600 stocks = 240,000 rows in memory

**Solutions:**
1. Use quick mode (reduces to 50 stocks)
2. Clear pandas cache between stocks
3. Upgrade RAM (recommended: 8GB+)

### Problem: `API rate limiting errors`

**Cause:** Making too many requests too fast

**Solution:**
```python
# Add delays in data_fetcher.py:
import time
time.sleep(0.2)  # 200ms delay between requests
```

---

## 🚨 Error Messages Decoded

### `KeyError: 'total_quantity'`

**File:** bulk_deal_analyzer.py line 489

**Status:** ✅ FIXED - Now uses `activity['summary'].total_deals`

### `ValueError: The truth value of a DataFrame is ambiguous`

**File:** sector_rotation.py line 233 (old code)

**Status:** ✅ FIXED - Now uses `.empty` check

**Prevention:** Always use:
```python
if df.empty:  # Correct
if not df:    # Wrong! Causes error
```

### `TypeError: 'NoneType' object is not iterable`

**Common Cause:** API returned null instead of list

**Status:** ✅ FIXED in sharehub_api.py line 900:
```python
# OLD:
values = record.get("values", [])  # Can be null!

# NEW:
values = record.get("values") or []  # Converts null to []
```

### `AttributeError: 'BulkDealAnalyzer' object has no attribute 'format_market_report'`

**File:** bulk_deal_analyzer.py line 502

**Cause:** Method name typo

**Fix:** Changed to `format_report()` (correct method name)

### `ImportError: cannot import name 'get_composite_score_report'`

**File:** paper_trader.py line 3583

**Cause:** Function not exported from module

**Solution:**
```python
# In intelligence/technical_composite.py, add:
def get_composite_score_report(symbol):
    # Implementation
    pass

# Or comment out unused import in paper_trader.py
```

---

## 🆘 Still Having Issues?

### 1. Enable Debug Logging

```python
# In any script, add at top:
from loguru import logger
logger.remove()
logger.add("debug.log", level="DEBUG")
```

### 2. Check System Requirements

- Python 3.10+
- 8GB RAM (16GB recommended)
- Stable internet connection
- Ubuntu/Debian/macOS/Windows

### 3. Verify Data Availability

```bash
# Test basic API connectivity
python -c "
from nepse_ai_trading.data.data_fetcher import NepseFetcher
fetcher = NepseFetcher()
data = fetcher.fetch_live_market()
print(f'Fetched {len(data)} stocks')
"
```

### 4. Clean Reinstall

```bash
# Remove old installation
pip uninstall -y pandas pandas-ta loguru pydantic

# Clear cache
rm -rf __pycache__ nepse_ai_trading/__pycache__

# Reinstall
pip install -r requirements.txt
```

### 5. Report Bugs

**Include:**
- Error message (full traceback)
- Command used
- Python version (`python --version`)
- OS details
- Steps to reproduce

**Where:**
- GitHub Issues (if public repo)
- Or email developer

---

## 📅 Historical Analysis Mode

### Using Historical Analysis

The `--date` parameter allows backtesting by analyzing stocks as of a specific historical date:

```bash
python paper_trader.py --analyze AVYAN --date=2026-03-16
```

**What happens:**
- Price data is truncated to data on or before the specified date
- Technical indicators (RSI, EMA, VWAP, ATR) are calculated only on historical data
- The score reflects what the system would have shown on that date

### Known Limitation: Broker Data

⚠️ **Broker analysis data cannot be fetched historically.** The ShareHub API only supports `duration` parameters (1D, 1W, 1M), not specific date ranges.

**Impact:**
- Broker/Institutional pillar scores use current broker positions
- For true historical backtesting, interpret broker scores with caution
- Price-based indicators (RSI, EMA, VWAP) ARE calculated historically

### Historical Analysis Best Practices

1. **Use for price-based analysis:** RSI, EMA, VWAP, ATR are accurate
2. **Verify with known events:** Test on dates where you know the outcome
3. **Compare with current analysis:** Run both to see how indicators changed

---

## 📚 Additional Resources

- [Architecture Guide](ARCHITECTURE.md) - System design details
- [Audit Report](COMPREHENSIVE_AUDIT_REPORT.md) - Known bugs & fixes
- [User Guide](../guides/USER_GUIDE.md) - Command reference
- [Quick Start](../guides/QUICK_START.md) - Getting started

---

**Last Updated:** 2026-03-24  
**Version:** 1.0.1
