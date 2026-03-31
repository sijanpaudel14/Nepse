# NEPSE AI Quantitative Trading System 🚀

🤖 A production-grade, AI-powered quantitative trading system for Nepal Stock Exchange (NEPSE).

## 🎯 Features

### Composite Signal Score (CSS) Engine — NEW

- 📊 **6-Component Scoring** — Trend + Momentum + Volume + Volatility + Operator + Fundamental
- 🎯 **3 Trading Profiles** — Short-term, Swing, Investment (different weight sets)
- 📉 **Signal Freshness Decay** — Stale data automatically penalized (0.8^days)
- 🔬 **22 Quantitative Indicators** — MEIS (Minimal Effective Indicator Set) in one call
- 🕵️ **Operator Cycle Detection** — 14-21 day pump/dump pattern recognition

### Trading Intelligence

- 📊 **5 Swing Trading Strategies** — Golden Cross, Volume Breakout, RSI Divergence, Support Bounce
- 🧠 **AI-Powered Analysis** — GPT-4o-mini validates signals and analyzes news sentiment
- 📰 **News Scraping** — Automatic collection from ShareSansar & Merolagani
- ⚡ **Real-time Screening** — Parallel analysis of all NEPSE stocks

### Fundamental Analysis

- 📈 **Sector-Specific Valuations** — PE/PBV benchmarks per NEPSE sector (no more blanket PE<15)
- 🏦 **Broker Intelligence** — 30/60/90 day broker profile tracking
- 🕸️ **Syndicate Detection** — Cross-broker coordination algorithm
- 📊 **Floorsheet HHI** — Concentration tracking per stock
- 🏛️ **NRB Macro Scoring** — Interbank rate, CCD ratio, inflation impact

### Risk Management — Hard Enforcement

- 🛡️ **8-Gate Pre-Trade Check** — Daily loss, drawdown, position limits, sector caps (ENFORCED, not advisory)
- 📉 **ATR Dynamic Stops** — Entry - 2×ATR, progressive trailing (tightens with profit)
- 💰 **Quarter-Kelly Sizing** — Conservative Kelly criterion for NEPSE's thin markets
- 💾 **Position Persistence** — Positions survive restarts via SQLite storage
- 🚨 **Circuit Breaker Proximity** — CSS penalty when stock nears ±10% circuit limit
- ⏰ **T+2 Settlement Aware** — Blocks premature exits

### Institutional-Grade Backtesting

- 📈 **CSS Backtesting** — Test CSS signals with realistic NEPSE costs
- 🔄 **Walk-Forward Validation** — 6-month train / 2-month test rolling windows
- 🎲 **Monte Carlo Testing** — Statistical significance with p-values
- ⚖️ **Strategy Comparison** — All strategies + CSS profiles ranked side-by-side
- 💸 **Realistic Cost Model** — 0.36% broker + 0.015% SEBON + Rs.25 DP + volume slippage

### Market Intelligence

- 🌡️ **Market Breadth History** — Persisted A/D data with multi-day divergence detection
- 🏭 **Sector Rotation** — Dampened extrapolation with seasonal calendar
- 💰 **Smart Money Tracking** — Institutional flow scaled by stock turnover
- 📊 **Market Regime Detection** — BULL/BEAR/PANIC automatic classification

### Notifications & Interface

- 📲 **Telegram Alerts** — Real-time trading signals with fundamentals
- 📧 **Email Notifications** — Daily summaries and important alerts
- 🖥️ **Web Dashboard** — Modern dark-mode UI with live data
- 📡 **REST API** — Full FastAPI backend with OpenAPI docs

## 🏗️ Architecture

```
nepse_ai_trading/
├── core/               # Config, database, logging, exceptions
├── data/               # NEPSE API integration & data cleaning (bulk upserts)
├── analysis/           # Technical + Fundamental + CSS scoring
│   ├── strategies/     # Individual TA strategy implementations
│   ├── quant_indicators.py  # MEIS — 22 indicators, one call
│   ├── signal_scorer.py     # CSS — 6-component composite scoring
│   ├── fundamentals.py      # PE, PB, ROE, Broker analysis
│   ├── corporate_actions.py # Dividends, bonus, rights
│   └── financial_reports.py # Q1-Q4 report scraping
├── backtesting/        # CSS backtest, walk-forward, Monte Carlo, comparison
├── risk/               # ATR stops, portfolio risk engine, position persistence
│   ├── atr_stops.py         # Dynamic ATR stops + progressive trailing
│   ├── portfolio_risk_engine.py  # 8-gate pre-trade check (ENFORCED)
│   ├── position_sizer.py   # Quarter-Kelly + alternatives
│   └── portfolio_manager.py # Position tracking
├── intelligence/       # News, AI, brokers, syndicate, macro, breadth
│   ├── broker_profiles.py   # 30/60/90 day broker tracking
│   ├── syndicate_detector.py    # Cross-broker coordination
│   ├── floorsheet_tracker.py    # HHI concentration
│   ├── macro_engine.py      # NRB macro scoring
│   ├── market_breadth.py    # Breadth history + divergence
│   ├── operator_cycle.py    # Pump/dump cycle detection
│   └── ...                  # News, AI, sentiment, sector rotation
├── notifications/      # Telegram & email integration
├── api/                # FastAPI backend
├── web/                # Dashboard templates & static files
├── scheduler/          # APScheduler for automated runs
└── main.py             # CLI orchestrator
```

## 🚀 Quick Start

### Installation

```bash
# Clone and navigate
cd nepse_ai_trading

# Create virtual environment (Python 3.11+)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for news scraping)
playwright install chromium

# Copy and edit environment file
cp .env.example .env
nano .env  # Add your API keys
```

### Configuration

Edit `.env` with your credentials:

```env
# Required
OPENAI_API_KEY=sk-your-key-here
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Optional: ShareHub protected endpoints (broker analysis/accumulation)
SHAREHUB_AUTH_TOKEN=your-sharehub-bearer-token
SHAREHUB_AUTH_COOKIES=route=...; SRVGROUP=common; _clck=...; _ga=...; _gcl_au=...; _ga_13E8FKZMQ2=...; _clsk=...

# Risk Parameters (defaults)
RISK_PER_TRADE=0.02      # 2% risk per trade
MAX_POSITIONS=5          # Max concurrent positions
MIN_PRICE=200            # Min stock price filter
TARGET_PROFIT=0.10       # 10% target
STOP_LOSS=0.05           # 5% stop loss
```

### Usage

```bash
# Run full analysis pipeline (fetch → screen → analyze → notify)
python main.py

# Fetch market data only
python main.py --fetch-only

# Run screener only (uses existing data)
python main.py --screen-only

# Dry run (no notifications)
python main.py --dry-run

# Start the web dashboard
uvicorn api.main:app --reload
# Open http://localhost:8000

# Run with scheduler (automated daily runs)
python main.py --schedule
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

## 📊 Trading Strategies

| Strategy            | Entry Signal                     | Confirmation                 |
| ------------------- | -------------------------------- | ---------------------------- |
| **Golden Cross**    | EMA(9) crosses above EMA(21)     | RSI 50-65, Volume > 1.5x avg |
| **Volume Breakout** | Volume > 3x 50-day avg           | Price breaks 20-day high     |
| **RSI Divergence**  | Price lower low + RSI higher low | RSI crosses above 30         |
| **Support Bounce**  | Price touches support level      | Bullish rejection candle     |

## 💰 Risk Management Rules (ENFORCED)

| Rule             | Setting                | Enforcement                                   |
| ---------------- | ---------------------- | --------------------------------------------- |
| Risk per trade   | 2% max (Quarter-Kelly) | Pre-trade check blocks oversized trades       |
| Max positions    | 5                      | Pre-trade check blocks new entries            |
| Sector limit     | 30%                    | Pre-trade check blocks sector concentration   |
| Min price        | Rs. 200                | Filtered in screening                         |
| Daily loss limit | 3%                     | All trading blocked until next day            |
| Max drawdown     | 20%                    | System halt, manual review required           |
| Stop-loss        | ATR-based              | Dynamic: Entry - 2×ATR, trails progressively  |
| T+2 settlement   | 3 day hold             | Cannot sell within 3 trading days of purchase |
| Circuit breaker  | ±10% daily             | CSS penalty when stock nears limit            |

## 📡 API Endpoints

### Market Data

| Endpoint                  | Method | Description                    |
| ------------------------- | ------ | ------------------------------ |
| `/api/market/summary`     | GET    | NEPSE index and market breadth |
| `/api/market/live`        | GET    | Live prices for all stocks     |
| `/api/market/top-gainers` | GET    | Top gaining stocks             |
| `/api/market/top-losers`  | GET    | Top losing stocks              |
| `/api/market/sectors`     | GET    | Sector-wise performance        |

### Stock Data

| Endpoint                       | Method | Description                  |
| ------------------------------ | ------ | ---------------------------- |
| `/api/stocks`                  | GET    | List all stocks with filters |
| `/api/stocks/{symbol}`         | GET    | Stock details                |
| `/api/stocks/{symbol}/history` | GET    | Price history                |

### Fundamental Analysis (NEW!)

| Endpoint                             | Method | Description                       |
| ------------------------------------ | ------ | --------------------------------- |
| `/api/fundamentals/{symbol}`         | GET    | PE, PB, ROE, EPS, valuation score |
| `/api/fundamentals/{symbol}/brokers` | GET    | Broker buy/sell analysis          |
| `/api/fundamentals/{symbol}/depth`   | GET    | Market depth & order book         |
| `/api/analysis/{symbol}`             | GET    | Comprehensive TA + FA analysis    |
| `/api/screen/fundamentals`           | GET    | Screen by fundamental criteria    |

### Trading Signals

| Endpoint            | Method | Description             |
| ------------------- | ------ | ----------------------- |
| `/api/signals`      | GET    | Today's trading signals |
| `/api/signals/scan` | POST   | Trigger market scan     |

### Portfolio & Backtest

| Endpoint                   | Method | Description                   |
| -------------------------- | ------ | ----------------------------- |
| `/api/portfolio`           | GET    | Portfolio positions and P&L   |
| `/api/portfolio/positions` | GET    | Current positions             |
| `/api/backtest`            | POST   | Run strategy backtest         |
| `/docs`                    | GET    | Interactive API documentation |

## 🛠️ Technology Stack

| Component     | Technology                      |
| ------------- | ------------------------------- |
| Language      | Python 3.11+                    |
| Data          | pandas, numpy, pandas-ta        |
| NEPSE API     | NepseUnofficialApi              |
| Database      | SQLite (dev), PostgreSQL (prod) |
| Web Framework | FastAPI                         |
| AI            | OpenAI GPT-4o-mini              |
| Scraping      | Playwright                      |
| Notifications | Telegram Bot API, SMTP          |
| Scheduler     | APScheduler                     |
| Deployment    | Docker                          |

## ⚠️ Important NEPSE Realities

1. **T+2 Settlement** - Day trading is impossible. This system is for swing trading only.

2. **Manual Execution** - NEPSE TMS has NO API. You must manually execute trades. The bot sends alerts, you take action.

3. **Slippage Risk** - In fast-moving markets, your actual fill price may differ from the signal price.

4. **Adjusted Prices** - Use adjusted close prices for backtesting to account for bonus/right shares.

## 📈 Millionaire Roadmap

1. **Paper Trade** - Run the system for 2-3 months without real money
2. **Start Small** - Begin with only 10% of intended capital
3. **Track Everything** - Log all trades, learn from losses
4. **Compound** - 3% monthly = 42% yearly. Rs. 500K → Rs. 7.1M in 5 years
5. **Iterate** - Continuously improve strategies based on results

## ⚖️ Disclaimer

⚠️ **THIS IS NOT FINANCIAL ADVICE**

- Trading involves substantial risk of loss
- Past performance does not guarantee future results
- The NEPSE API is unofficial and may break anytime
- Always verify signals with your own analysis
- Only trade money you can afford to lose

## 📄 License

MIT License - Use at your own risk.

---

Built with ❤️ for the NEPSE trading community
