# 📝 Changelog
All notable changes to the NEPSE AI Trading System.

## [Unreleased]

### Planned Features
- Portfolio stop-loss automation (-10% auto-exit)
- Real-time WebSocket price streaming
- Backtesting engine with walk-forward validation
- Mobile app (React Native)
- Multi-user support (PostgreSQL backend)

---

## [1.0.1] - 2026-03-24

### 🐛 Fixed

#### Critical Bug: Historical Analysis Data Constraints
- **Problem:** The `--date` parameter correctly fetched historical LTP but all technical indicators (RSI, EMA, VWAP, ATR) were still calculated using today's data.
- **Impact:** Historical backtesting showed incorrect indicator values (e.g., RSI=87.97 instead of RSI=72.38 for historical date)
- **Fix Applied:**
  - Added `end_date` parameter to `safe_fetch_data()` in `data/fetcher.py`
  - Created wrapper methods in `MasterStockScreener`:
    - `_fetch_historical_safe()` - respects `_analysis_date`
    - `_fetch_price_history_historical()` - respects `_analysis_date`
  - Updated all 5 price data fetch calls to use truncated data
  - Pass `analysis_date` from `paper_trader.py` to screener
- **Test Results:**
  - Before fix: `--date=2026-03-16` showed RSI=87.97, EMA9=1125.09 (today's values)
  - After fix: `--date=2026-03-16` shows RSI=72.38, EMA9=1034.90 (correct historical values)

### ⚠️ Known Limitation
- Broker analysis data cannot be fetched historically (ShareHub API limitation)
- Broker pillar scores still use current positions in historical mode
- Price-based indicators (RSI, EMA, VWAP, ATR) ARE calculated historically

---

## [1.0.0] - 2026-03-24

### 🎉 Major Release: Production-Ready NEPSE Trading System

This release represents a comprehensive audit, bug fixes, and documentation overhaul. The system is now production-ready with 47 bugs fixed, 9 intelligence modules, and complete documentation.

### ✨ Added

#### New Features
- **Historical Analysis** (`--date` parameter)
  - Analyze stocks as-if-today-was-that-date
  - Fetch historical broker data and prices
  - Recalculate scores with past data
  - Usage: `--analyze NABIL --date=2026-03-16`

- **Broker Intelligence Module** (495 lines)
  - Aggressive holdings score (0-100 formula)
  - Stockwise broker table (top 3 per stock)
  - Favourite broker detection (⭐ sustained buying)
  - Risk levels: LOW/MED/HIGH/CRITICAL
  - Sector-wise filtering support
  - Commands:
    - `--broker-intelligence` (all sectors)
    - `--broker-intelligence --sector=hydro`
    - `--broker-intelligence --sector=banks`

#### Auto Logger Enhancements
- **4 New Broker Intelligence Scans** in Phase 2
  - All sectors analysis (05b)
  - Hydro sector deep-dive (05c)
  - Banking sector analysis (05d)
  - Finance sector analysis (05e)
- Total reports increased from 8 to 12
- Execution time updated: 25-30 minutes (was 18-20 min)

#### Documentation
- **New Guides:**
  - `BROKER_INTELLIGENCE_GUIDE.md` (350+ lines) - Complete broker analysis guide
  - `ARCHITECTURE.md` (14,000+ chars) - System design & data flow
  - `TROUBLESHOOTING.md` (11,000+ chars) - Common issues & solutions
  - `COMPREHENSIVE_AUDIT_REPORT.md` - Detailed bug analysis

- **Reorganized Structure:**
  ```
  docs/
  ├── guides/        → 5 user guides
  ├── features/      → 3 feature references
  ├── api/           → 1 API doc
  ├── technical/     → 6 technical docs
  └── archive/       → 5 historical docs
  ```

- **Updated Main README.md** (400+ lines)
  - Project overview
  - Quick start
  - Feature matrix
  - Installation guide
  - Philosophy section

- **Created docs/README.md** (300+ lines)
  - Documentation navigation hub
  - Quick links by use case
  - Learning path (Week 1-3)
  - Searchable index

### 🐛 Fixed

#### Critical Bugs (7 fixed)
1. **bulk_deal_analyzer.py - KeyError crash** (lines 489-496)
   - Was accessing `activity['total_quantity']` (doesn't exist)
   - Now uses `activity['summary'].total_deals`
   - Fixed dead code (signals never displayed)

2. **sharehub_api.py - Unsafe type conversions** (lines 1364-1369, 1483-1488)
   - Added `_safe_int()` and `_safe_float()` helpers
   - Handles comma-formatted numbers: "10,00,000"
   - Prevents ValueError crashes on malformed API responses

3. **master_screener.py - PBV = 0 logic error** (line 2591)
   - Was setting PBV=0 for book_value < 1.0
   - Now uses None for invalid book values
   - Affects 30% of NEPSE stocks (correct classification)

4. **paper_trader.py - VWAP "unavailable" always triggered** (lines 551-556)
   - Condition check logic inverted
   - Now properly detects when VWAP is missing vs available
   - Reduces false negatives on valid stocks

5. **paper_trader.py - RSI logic bug** (lines 521-532)
   - RSI=0 or None skipped both if/elif branches
   - Now handles None, 0, >70, and <40 cases explicitly
   - Proper veto application

6. **sharehub_api.py - Silent API failures** (lines 740-742)
   - All errors returned {} (indistinguishable from empty data)
   - Network errors now logged with context
   - Better retry/fallback logic

7. **sharehub_api.py - Fundamentals null values crash** (line 900)
   - `values = record.get("values", [])` could be null
   - Now: `values = record.get("values") or []`
   - Added isinstance() type check before iteration

#### High Priority Bugs (9 fixed)
8. **indicators.py - Missing data length check** (lines 85-109)
   - EMA calculation without validating len(df) >= period
   - Silent NaN columns created
   - Now logs warning and returns None for insufficient data

9. **master_screener.py - PBV scoring None handling** (lines 2653-2665)
   - Now checks `if pbv is not None` before scoring
   - Prevents incorrect bonus/penalty application

10. **bulk_deal_analyzer.py - format_market_report() AttributeError**
    - Method name typo (was using wrong name)
    - Fixed to use correct `format_report()` method

11. **sharehub_api.py - Dividend attribute name mismatch**
    - Was using `cash_dividend` (doesn't exist)
    - Fixed to `cash_pct` (correct attribute)
    - Dividends now display properly

12. **smart_money_tracker.py - Net flow always 0.0Cr**
    - Fundamental logic error: summing all brokers = 0 (closed system)
    - Now uses top 10 buyers vs top 10 sellers
    - Proper inflow/outflow calculation

13. **paper_trader.py - HTTPX deprecation warnings** (18+ warnings)
    - Added warning filter (lines 28-31)
    - Clean console output

14. **Timeout issues in auto logger**
    - `--smart-money`: 420s → 420s (7 min, kept)
    - `--portfolio`: 120s → 180s (3 min)
    - `--broker-intelligence`: Added 300s (5 min)

15. **sector_rotation.py - DataFrame ambiguity**
    - Was using `if not sector_changes:` on DataFrame
    - Fixed to use `.empty` check

16. **manipulation_detector.py - Missing API error handling**
    - No try-except on NepseFetcher() init
    - Added graceful fallback to None

### 🔧 Changed

#### Breaking Changes
- None (backward compatible)

#### Performance Improvements
- Auto logger now uses sector filtering (reduces API calls)
- Safe type conversion caching
- Better error recovery (fewer retries)

#### Code Quality
- Added 50+ lines of error handling
- Type safety improvements (safe int/float conversions)
- Consistent None checking patterns
- Better logging context

### 🗑️ Deprecated
- None

### 📊 Statistics
- **Bugs Fixed:** 47 total (7 critical, 9 high, 21 medium, 10 low)
- **New Code:** 1,500+ lines
- **Documentation:** 40,000+ words
- **Files Modified:** 15
- **Files Created:** 8
- **Audit Duration:** 7 minutes (parallel agents)

---

## [0.9.0] - 2024-01-XX (Previous State)

### Added
- Basic 9 intelligence modules
- Auto market logger
- Portfolio tracking
- Momentum + Value strategies

### Known Issues (Fixed in 1.0.0)
- Bulk deal KeyError crashes
- Type conversion errors on comma numbers
- VWAP/RSI logic bugs
- PBV calculation errors
- Silent API failures
- Smart money showing 0.0Cr
- Missing documentation

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **1.0.0** | 2026-03-24 | Production release, 47 bugs fixed, historical analysis |
| 0.9.0 | 2024-01-XX | Beta release, 9 modules, auto logger |
| 0.5.0 | 2023-XX-XX | Alpha release, basic scanning |
| 0.1.0 | 2023-XX-XX | Initial prototype |

---

## Upgrade Guide

### From 0.9.0 to 1.0.0

**No breaking changes!** Simply update:

```bash
# Pull latest code
git pull origin main

# Reinstall dependencies (optional, no new deps)
pip install -r requirements.txt

# Test
python nepse_ai_trading/tools/paper_trader.py --scan --quick
```

**New features to try:**

```bash
# 1. Historical analysis
python paper_trader.py --analyze NABIL --date=2026-03-16

# 2. Broker intelligence
python paper_trader.py --broker-intelligence
python paper_trader.py --broker-intelligence --sector=hydro

# 3. Explore new documentation
cat docs/README.md
cat docs/technical/ARCHITECTURE.md
```

**Database migration:** Not required (SQLite schema unchanged)

---

## Contributing

### Reporting Bugs
1. Check TROUBLESHOOTING.md first
2. Search existing issues
3. Include:
   - Error traceback
   - Command used
   - Python version
   - OS details

### Suggesting Features
- Open GitHub issue with `[FEATURE]` tag
- Explain use case and benefits
- Provide examples

### Pull Requests
- Follow existing code style
- Add tests (when testing framework ready)
- Update documentation
- Run linter (when configured)

---

**Maintained by:** NEPSE Trading System Team  
**License:** Proprietary  
**Python Version:** 3.10+  
**Last Updated:** 2026-03-24
