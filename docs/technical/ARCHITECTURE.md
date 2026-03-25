# 🏗️ NEPSE AI Trading System - Architecture

## System Overview

The NEPSE AI Trading System is a comprehensive, production-ready algorithmic trading platform designed specifically for the Nepal Stock Exchange (NEPSE). It combines technical analysis, fundamental analysis, smart money tracking, and AI-driven insights to generate actionable trading signals.

---

## 🎯 Design Philosophy

1. **Swing Trading Focus** - Designed for T+2 settlement (no day trading)
2. **Multi-Strategy** - Value + Momentum + Smart Money combined
3. **Risk-First** - Hard veto gates prevent bad entries
4. **Production-Ready** - Bulletproof error handling, logging, validation
5. **NEPSE-Specific** - Handles market manipulation, thin liquidity, penny stocks

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface Layer                       │
│                  (paper_trader.py)                          │
│  Commands: --scan, --analyze, --portfolio, --bulk-deals    │
└────────────┬────────────────────────────────────────────────┘
             │
             ├───► Auto Logger (Scheduler)
             │     • Runs 12+ intelligence modules
             │     • Generates timestamped markdown reports
             │     • 25-30 min full market scan
             │
┌────────────▼────────────────────────────────────────────────┐
│                   Core Trading Engine                        │
│              (MasterStockScreener)                          │
│  • 4-Pillar Scoring (Technical/Broker/Fundamental/Unlock)  │
│  • Dual-Timeframe Validation (1M + 1W)                     │
│  • Classification: GOOD/RISKY/WATCH/VETO                   │
└────┬────────────────────────────┬─────────────┬─────────────┘
     │                            │             │
┌────▼─────────┐    ┌────────────▼──────┐  ┌──▼──────────────┐
│ Data Layer   │    │ Intelligence Layer│  │  Output Layer   │
├──────────────┤    ├───────────────────┤  ├─────────────────┤
│• NepseFetcher│    │• Smart Money      │  │• Markdown       │
│• ShareHubAPI │    │• Bulk Deals       │  │• JSON           │
│• Price OHLCV │    │• Manipulation     │  │• Telegram       │
│• Broker Data │    │• Sector Rotation  │  │• SQLite         │
│• Fundamentals│    │• Dividend Forecast│  │• Console        │
└──────────────┘    │• Order Flow       │  └─────────────────┘
                    │• Tech Composite   │
                    │• Earnings Track   │
                    │• Broker Intel     │
                    └───────────────────┘
```

---

## 🔧 Module Breakdown

### 1. **Data Layer** (`nepse_ai_trading/data/`)

**Purpose:** Fetch and normalize data from multiple NEPSE APIs

**Key Files:**
- `data_fetcher.py` - NepseFetcher class (official NEPSE API)
- `sharehub_api.py` - ShareHubAPI wrapper (fundamentals, broker data)
- `nepse_unofficial_api.py` - Fallback unofficial API

**Data Sources:**
- Live market data (OHLCV, LTP, volume)
- Historical price data (up to 400 days)
- Broker transaction data (1D, 1W, 1M timeframes)
- Fundamental data (EPS, ROE, PE, PBV, dividends)
- Corporate actions (dividends, bonus, rights)
- Bulk deals and insider transactions

**Error Handling:**
- Retry logic with exponential backoff
- Fallback to alternative APIs
- Safe type conversion (handles Indian number format: "10,00,000")
- Null/None propagation protection

---

### 2. **Core Trading Engine** (`nepse_ai_trading/analysis/`)

**Purpose:** Score and classify stocks using multi-factor analysis

**Key Files:**
- `master_screener.py` - Main screening engine (2700+ lines)
- `indicators.py` - Technical indicator calculations
- `settings.py` - Strategy parameters and thresholds

**Scoring System (4 Pillars):**

| Pillar | Weight | Components |
|--------|--------|------------|
| **1. Technical** | 40% | RSI, EMA Cross, Volume Spike, ATR, MACD |
| **2. Broker/Institutional** | 30% | 1M Net Holdings, 1W Net Holdings, Smart Money |
| **3. Fundamental** | 10% | EPS, ROE, PE, PBV, Dividends |
| **4. Unlock Risk** | 20% | Days to unlock, MF lock penalty |

**Classification Logic:**
```
Score ≥ 80 + No Vetos       → GOOD (3-5% position)
Score 70-79 + ≤1 Veto       → RISKY (1-2% position)
Score 60-69                 → WATCH (monitor only)
Score < 60 or 2+ Vetos      → VETO (paper trade only)
```

**Hard Veto Gates:**
- RSI > 70 (overbought)
- EPS ≤ 0 (loss-making)
- ROE ≤ 0 (negative returns)
- VWAP premium > 10% (overextended)
- 1M broker distribution (selling pressure)
- Recent dump day detected

---

### 3. **Intelligence Modules** (`nepse_ai_trading/intelligence/`)

**Purpose:** Provide specialized analysis beyond basic screening

**Modules:**

1. **Smart Money Tracker** (`smart_money_tracker.py`)
   - Tracks institutional buying/selling (top 10 brokers)
   - Net flow calculation (inflow - outflow)
   - Concentration score (0-100)
   - Signals: STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL

2. **Broker Intelligence** (`broker_intelligence.py`)
   - Aggressive holdings score (0-100)
   - Stockwise broker table (top 3 per stock)
   - Favourite broker detection (sustained multi-day buying)
   - Risk level (LOW/MED/HIGH/CRITICAL based on profit %)

3. **Bulk Deal Analyzer** (`bulk_deal_analyzer.py`)
   - Detects promoter exit risk
   - Identifies institutional accumulation
   - Flags wash trades (same broker buy/sell)
   - Market-wide bulk deal trends

4. **Manipulation Detector** (`manipulation_detector.py`)
   - Pump & dump detection
   - Wash trading patterns
   - Artificial volume spikes
   - Price manipulation flags

5. **Sector Rotation** (`sector_rotation.py`)
   - Identifies hot/cold sectors
   - Momentum scoring across sectors
   - Seasonal rotation patterns
   - Sector-specific opportunities

6. **Dividend Forecaster** (`dividend_forecaster.py`)
   - Predicts dividend declarations
   - Historical dividend patterns
   - Yield forecasting

7. **Earnings Tracker** (`earnings_tracker.py`)
   - Quarterly earnings monitoring
   - EPS trend analysis
   - Earnings surprise detection

8. **Order Flow** (`order_flow.py`)
   - Bid/ask spread analysis
   - Order book imbalances
   - Market depth metrics

9. **Technical Composite** (`technical_composite.py`)
   - Multi-timeframe RSI
   - Bollinger Bands squeeze
   - MACD divergence
   - Composite strength score

---

### 4. **Tools Layer** (`nepse_ai_trading/tools/`)

**Purpose:** User-facing CLI and automation

**Key Files:**

1. **paper_trader.py** (3800+ lines)
   - Main CLI entry point
   - Commands: --scan, --analyze, --portfolio, --buy, --skip
   - Portfolio tracking (P&L, exit signals)
   - Recommendation management
   - **NEW:** Historical analysis with `--date` parameter

2. **auto_market_logger.py** (500+ lines)
   - Automated market intelligence runner
   - Runs during NEPSE hours (11am-3pm)
   - Generates 12+ markdown reports
   - Phase 1: Pre-market (6 modules, 10-12 min)
   - Phase 2: Market hours (6 modules, 15-18 min)

**Auto Logger Outputs:**
```
market_logs/YYYY-MM-DD_HHMM/
├── 01_market_overview.md        # Market breadth, top movers
├── 02_manipulation_alerts.md    # Pump/dump detection
├── 03_momentum_scan.md          # GOOD/RISKY/WATCH stocks
├── 04_portfolio_review.md       # P&L + exit signals
├── 05_smart_money.md            # Institutional flow
├── 05b_broker_intel_all.md      # All sectors broker analysis
├── 05c_broker_intel_hydro.md    # Hydro sector brokers
├── 05d_broker_intel_banks.md    # Banking sector brokers
├── 05e_broker_intel_finance.md  # Finance sector brokers
├── 06_bulk_deals.md             # Insider activity
├── 07_sector_rotation.md        # Hot/cold sectors
└── 08_dividend_forecast.md      # Upcoming dividends
```

---

## 🔄 Data Flow

### Full Scan Workflow:

```
1. CLI: python paper_trader.py --scan --strategy=momentum
   ↓
2. MasterStockScreener initialized
   ↓
3. Fetch live market data (all stocks)
   ↓
4. For each stock (600+ stocks):
   ├─► Fetch 400-day OHLCV history
   ├─► Calculate technical indicators (RSI, EMA, MACD, etc.)
   ├─► Fetch broker data (1D, 1W, 1M)
   ├─► Fetch fundamentals (ShareHub)
   ├─► Calculate 4-pillar score
   ├─► Run dual-timeframe validation
   └─► Classify as GOOD/RISKY/WATCH/VETO
   ↓
5. Filter and rank results
   ↓
6. Generate markdown output
   ↓
7. Optional: Save to SQLite portfolio DB
```

### Single Stock Analysis Workflow:

```
1. CLI: python paper_trader.py --analyze NABIL --date=2026-03-16
   ↓
2. Parse historical date (if provided)
   ↓
3. Fetch price history up to that date
   ↓
4. Filter data: only use records ≤ historical_date
   ↓
5. Run BOTH strategies (value + momentum)
   ├─► Score with 4-pillar system
   ├─► Calculate indicators from historical data
   └─► Fetch broker data (if available for that period)
   ↓
6. Generate comprehensive report:
   ├─► Scores (value vs momentum)
   ├─► Risk analysis
   ├─► Support/resistance levels
   ├─► Entry/exit points
   ├─► Position sizing guidance
   └─► Veto reasons (if any)
```

---

## 🛡️ Error Handling & Resilience

### API Failures:
- Primary API timeout → Retry 3x with backoff
- Retry fails → Try fallback API
- All APIs fail → Log error, continue with remaining stocks

### Data Quality:
- Missing OHLCV → Skip indicator calculation, use fallback
- Zero volume days → VWAP returns None (validated)
- Insufficient data (< 14 days) → RSI returns None
- NaN propagation → Early detection with `pd.notna()` checks

### Type Safety:
- **NEW:** Safe conversion helpers (`_safe_int`, `_safe_float`)
- Handles comma-formatted numbers ("10,00,000")
- Validates before division (avoid division by zero)
- None/null checks before iteration

### Database:
- SQLite for portfolio tracking
- Atomic transactions
- Schema validation on startup
- Automatic backups (not yet implemented)

---

## 🔍 Key Algorithms

### 1. Dual-Timeframe Validation

```python
# Rule 1: 1-Month Baseline
if net_1m <= 0:
    VETO("No accumulation in last month")

# Rule 2: 1-Week Fine-Tune
if net_1m > 0 and net_1w < 0:
    VETO("Recent distribution despite 1M accumulation")

# Rule 3: Technical Gates
if RSI > 70:
    VETO("Overbought")

# Rule 4: Fundamental Gates
if EPS <= 0:
    VETO("Loss-making company")
```

### 2. Smart Money Net Flow

```python
# NOT: sum(all_brokers.net_amount)  # Always = 0 (closed system)
# INSTEAD:
top_10_buyers = sorted(brokers, key=lambda x: x.net_amount, reverse=True)[:10]
inflow = sum(b.net_amount for b in top_10_buyers if b.net_amount > 0)

top_10_sellers = sorted(brokers, key=lambda x: x.net_amount)[:10]
outflow = abs(sum(b.net_amount for b in top_10_sellers if b.net_amount < 0))

net_flow = inflow - outflow
```

### 3. Aggressive Broker Score (0-100)

```python
score = 0

# Concentration (0-30 pts)
if top3_broker_pct > 50:
    score += 30
elif top3_broker_pct > 30:
    score += 20

# Net Amount (0-25 pts)
if total_net_buying > 1_000_000:  # 1Cr NPR
    score += 15

# Acceleration (0-20 pts)
if today_buy > 1.5 * avg_1w_buy:
    score += 20

# Conviction (0-25 pts)
if net_1w > net_1d * 1.5:  # Sustained multi-day buying
    score += 25  # FAVOURITE ⭐

return min(100, score)
```

---

## 📦 Dependencies

**Core Libraries:**
- `pandas` - Data manipulation
- `pandas-ta` - Technical indicators
- `requests` / `httpx` - API calls
- `loguru` - Structured logging
- `pydantic` - Data validation

**Optional:**
- `playwright` - News scraping
- `openai` - AI analysis
- `python-telegram-bot` - Notifications
- `matplotlib` / `plotly` - Charting (future)

---

## 🔐 Security & API Keys

**Required Environment Variables:**
```bash
# Optional (for AI features)
OPENAI_API_KEY=sk-...

# Optional (for notifications)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

**API Rate Limits:**
- NEPSE Official API: ~10 req/sec
- ShareHub API: ~5 req/sec
- Unofficial API: No known limits

---

## 🚀 Performance Optimizations

1. **Parallel Processing**
   - Multiple explore agents run in parallel
   - Independent scans can run concurrently

2. **Data Caching**
   - In-memory cache for company details
   - SQLite for portfolio state
   - Historical data cached per session

3. **Smart Filtering**
   - Quick mode: Top 50 stocks only (5x faster)
   - Sector filtering: Reduces API calls by 80%
   - Single-symbol mode: Skips market-wide fetch

4. **Lazy Loading**
   - Indicators calculated only when needed
   - News scraping only with --with-news
   - AI analysis only with --with-ai

---

## 📈 Future Enhancements

1. **Database Layer**
   - PostgreSQL for multi-user support
   - Time-series database for tick data
   - Daily broker snapshot tracking

2. **Backtesting Engine**
   - Historical performance simulation
   - Strategy parameter optimization
   - Walk-forward validation

3. **Real-time Monitoring**
   - WebSocket integration for live prices
   - Alert system for entry/exit signals
   - Mobile app (React Native)

4. **Machine Learning**
   - Price prediction models (LSTM)
   - Sentiment analysis from news
   - Pattern recognition (chart patterns)

5. **Portfolio Optimization**
   - Modern Portfolio Theory (MPT)
   - Risk-adjusted position sizing
   - Correlation analysis

---

## 🐛 Known Limitations

1. **Data Availability**
   - Broker data sometimes missing (API issues)
   - Historical data limited to ~2 years
   - Corporate actions not always updated

2. **Market Specifics**
   - NEPSE-only (not scalable to other markets)
   - T+2 settlement (no intraday strategies)
   - Thin liquidity (slippage not modeled)

3. **Technical**
   - No real-time streaming data
   - Manual portfolio entry (no brokerage integration)
   - SQLite limits (single-user)

---

## 📚 Code Quality Standards

1. **Documentation**
   - Docstrings for all public methods
   - Inline comments for complex logic
   - README for each module

2. **Error Handling**
   - Try-except blocks for all API calls
   - Graceful degradation (fallbacks)
   - Structured logging with context

3. **Testing** (Future)
   - Unit tests for core algorithms
   - Integration tests for API clients
   - End-to-end tests for workflows

4. **Logging**
   - INFO: Key workflow steps
   - WARNING: Recoverable errors
   - ERROR: Failures that need attention
   - DEBUG: Detailed troubleshooting info

---

**Version:** 1.0.0  
**Last Updated:** 2026-03-24  
**Total Lines of Code:** 216,640  
**Total Python Modules:** 6,568
