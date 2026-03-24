# 🚀 NEPSE AI Trading Engine

**Advanced AI-Powered Trading System for Nepal Stock Exchange (NEPSE)**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Production](https://img.shields.io/badge/status-production-green.svg)](https://github.com)

---

## 📖 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Usage Examples](#usage-examples)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Trading Philosophy](#trading-philosophy)
- [Project Structure](#project-structure)

---

## Overview

The **NEPSE AI Trading Engine** is a production-ready, automated trading system designed specifically for the Nepal Stock Exchange (NEPSE). It combines technical analysis, fundamental screening, broker intelligence, and AI-powered insights to help traders make informed decisions in NEPSE's unique market environment.

### Why This System?

NEPSE has characteristics that differ from developed markets:
- **T+2 Settlement** - No day trading possible
- **High Manipulation** - Operator-controlled pumps and dumps
- **Limited Liquidity** - Small-cap stocks dominate
- **Retail-Heavy** - 80%+ retail investors

This system is built to **detect manipulation early**, **follow institutional money**, and **exit before dumps**.

---

## Key Features

### 🕵️ Broker Intelligence
- **Aggressive Holdings Detection** - Catch operator accumulation before pumps
- **Favourite Broker Tracking** - Filter out one-day pump traps
- **Risk Level Analysis** - Know when brokers are ready to dump
- **Sector-Wise Scanning** - Deep analysis of Hydro, Banks, Finance sectors

### 💰 Institutional Flow Tracking
- **Smart Money Analysis** - Track top 10 institutional buyers/sellers
- **Bulk Deal Monitoring** - Detect large insider trades (>1Cr or 10K+ shares)
- **Distribution Risk Detection** - Identify when operators are taking profits

### 📊 Market Intelligence
- **Sector Rotation** - Identify which sectors are leading
- **Market Breadth Heatmap** - See % of stocks green/red by sector
- **Quant Positioning** - Measure market overbought/oversold conditions

### 🎯 Stock Screening
- **Momentum Strategy** - Technical + Fundamental + Broker scoring (0-100)
- **Dual-Timeframe Validation** - 1M baseline + 1W fine-tune
- **Risk Classification** - GOOD / RISKY / WATCH categories
- **Portfolio Management** - Automated position sizing (9% max per stock)

### 🤖 Automated Analysis
- **Auto Market Logger** - Daily 25-30 min automated analysis
- **12+ Intelligence Reports** - Market positioning, heatmap, sector rotation, smart money, bulk deals, broker intelligence (4 sectors), momentum scan, portfolio review
- **Markdown Logs** - All reports saved with timestamps

### 📱 AI & News Integration
- **OpenAI Analysis** - GPT-4 powered stock verdicts
- **News Scraping** - Automated ShareSansar/Merolagani news collection
- **Telegram Alerts** - Real-time notifications for trade signals

---

## Quick Start

### 1. Clone & Install

```bash
git clone <repository-url>
cd Nepse
pip install -r requirements.txt
```

### 2. Configure API Keys

Create `.env` file:
```bash
SHAREHUB_USERNAME=your_username
SHAREHUB_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run Your First Scan

```bash
# Quick momentum scan
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum

# Deep stock analysis
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL

# Broker intelligence (operator detection)
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=hydro

# Automated daily analysis (25-30 min)
python nepse_ai_trading/tools/auto_market_logger.py --now
```

---

## Documentation

### 📚 User Guides (Start Here)
- **[Quick Start Guide](docs/guides/QUICK_START.md)** - Get started in 5 minutes
- **[User Guide](docs/guides/USER_GUIDE.md)** - Complete user manual
- **[Auto Logger Guide](docs/guides/AUTO_LOGGER_GUIDE.md)** - Automated analysis setup
- **[Broker Intelligence Guide](docs/guides/BROKER_INTELLIGENCE_GUIDE.md)** - Operator detection explained
- **[Telegram Guide](docs/guides/TELEGRAM_GUIDE.md)** - Alert setup

### 🎯 Feature Documentation
- **[Command Reference Card](docs/features/COMMAND_REFERENCE_CARD.md)** - All commands explained
- **[Advanced Features Guide](docs/features/ADVANCED_FEATURES_GUIDE.md)** - Deep dive into all features
- **[Feature Overview](docs/features/OVERVIEW.MD)** - High-level feature list

### 🔧 Technical Documentation
- **[API Documentation](docs/api/NEPSE_unofficial_API.md)** - NEPSE API reference
- **[Bug Fixes Session](docs/technical/FINAL_BUG_FIXES_SESSION.md)** - Latest fixes
- **[Product Documentation](docs/technical/PRODUCT_DOCUMENTATION.md)** - System architecture

### 📦 Archive
- **[Archive Folder](docs/archive/)** - Historical documentation and session notes

---

## Usage Examples

### Morning Routine (Before Market Opens - 11:00 AM)

```bash
# 1. Run automated analysis
python nepse_ai_trading/tools/auto_market_logger.py --now

# Wait 25-30 minutes, then review outputs in market_logs/
cd market_logs/latest/

# 2. Check market overview
cat 01_market_positioning.md
cat 02_market_heatmap.md
cat 03_sector_rotation.md

# 3. Review institutional activity
cat 04_smart_money_flow.md
cat 05_bulk_deals.md
cat 05b_broker_intelligence_all.md
cat 05c_broker_intelligence_hydro.md

# 4. Find trading opportunities
cat 06_momentum_scan.md

# 5. Check portfolio
cat 07_portfolio_review.md
```

### Individual Commands

```bash
# Market Overview
python nepse_ai_trading/tools/paper_trader.py --positioning
python nepse_ai_trading/tools/paper_trader.py --heatmap
python nepse_ai_trading/tools/paper_trader.py --sector-rotation

# Smart Money
python nepse_ai_trading/tools/paper_trader.py --smart-money
python nepse_ai_trading/tools/paper_trader.py --smart-money --sector=hydro
python nepse_ai_trading/tools/paper_trader.py --bulk-deals

# Broker Intelligence
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=hydro
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=bank

# Stock Analysis
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL
python nepse_ai_trading/tools/paper_trader.py --order-flow NABIL

# Portfolio
python nepse_ai_trading/tools/paper_trader.py --portfolio
python nepse_ai_trading/tools/paper_trader.py --buy-picks NGPL API GVL
python nepse_ai_trading/tools/paper_trader.py --sell NGPL
```

---

## System Requirements

### Python
- **Version:** Python 3.12 or higher
- **Virtual Environment:** Recommended (venv or conda)

### Dependencies
- pandas >= 2.0.0
- pandas-ta >= 0.3.14b
- playwright >= 1.40.0
- openai >= 1.0.0
- python-telegram-bot >= 20.0
- loguru >= 0.7.0
- httpx >= 0.24.0
- pydantic >= 2.0.0

### Hardware
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 1GB for data and logs
- **Network:** Stable internet for API calls

### API Accounts Required
1. **ShareHub Nepal** - For broker/fundamental data ([ShareHub](https://sharehubnepal.com))
2. **OpenAI** - For AI analysis (optional) ([OpenAI](https://openai.com))
3. **Telegram Bot** - For alerts (optional) ([BotFather](https://t.me/botfather))

---

## Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd Nepse
```

### Step 2: Create Virtual Environment

```bash
# Using venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# OR using conda
conda create -n nepse python=3.12
conda activate nepse
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Step 4: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your preferred editor
```

### Step 5: Verify Installation

```bash
# Test basic command
python nepse_ai_trading/tools/paper_trader.py --positioning

# If successful, you're ready!
```

---

## Trading Philosophy

This system follows a **Swing Trading** approach optimized for NEPSE's T+2 settlement:

### Core Principles

1. **Better Miss Than Lose**
   - Only trade high-conviction setups
   - Skip marginal opportunities
   - Capital preservation > FOMO

2. **Follow Smart Money**
   - Track institutional buyers (top 10)
   - Monitor broker accumulation patterns
   - Detect distribution before dumps

3. **Multi-Timeframe Validation**
   - 1-month baseline (trend)
   - 1-week fine-tune (entry)
   - Hard veto on contradictory signals

4. **Risk Management First**
   - Max 9% per position
   - Max 7-day holding period
   - 3 exit triggers (target/stop/time)

5. **Operator Awareness**
   - 60%+ of NEPSE volume is manipulated
   - Enter Week 2 (accumulation), exit Week 3 (peak)
   - Avoid Week 4 (dump phase)

### Expected Performance

| Metric | Target |
|--------|--------|
| Win Rate | 60-70% |
| Avg Win | +10-15% |
| Avg Loss | -5% |
| Risk:Reward | >2:1 |
| Max Drawdown | <15% |
| Holding Period | 3-7 days |

**Disclaimer:** These are backtested targets, not guarantees. Always use stop losses and proper position sizing.

---

## Project Structure

```
Nepse/
├── nepse_ai_trading/           # Main package
│   ├── tools/                  # CLI tools
│   │   ├── paper_trader.py     # Main trading engine
│   │   └── auto_market_logger.py  # Automated analysis
│   ├── intelligence/           # Intelligence modules
│   │   ├── broker_intelligence.py
│   │   ├── smart_money_tracker.py
│   │   ├── bulk_deal_analyzer.py
│   │   ├── sector_rotation.py
│   │   └── ...
│   ├── data/                   # Data fetchers
│   │   ├── fetcher.py
│   │   └── sharehub_api.py
│   └── ...
│
├── docs/                       # Documentation
│   ├── guides/                 # User guides
│   ├── features/               # Feature docs
│   ├── api/                    # API reference
│   ├── technical/              # Technical docs
│   └── archive/                # Historical docs
│
├── market_logs/                # Daily analysis logs
├── .env                        # Configuration (not in git)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Contributing

This is a personal trading system. If you find bugs or have suggestions:

1. Check existing issues
2. Create detailed bug report
3. Suggest improvements with use cases

---

## License

MIT License - See LICENSE file for details.

---

## Disclaimer

**IMPORTANT:** This software is for educational and research purposes only.

- Not financial advice
- No guarantees of profit
- Trading involves risk of loss
- NEPSE is highly manipulated
- Always do your own research
- Never invest more than you can afford to lose

**The authors are not responsible for any financial losses incurred using this system.**

---

## Support

- **Documentation:** See `docs/` folder
- **Issues:** Create GitHub issue
- **Questions:** Check guides first

---

## Changelog

### v1.0.0 (2026-03-24)
- ✅ Broker Intelligence System
- ✅ Smart Money Tracker
- ✅ Bulk Deal Analyzer
- ✅ Sector Rotation Analysis
- ✅ Auto Market Logger (12+ reports)
- ✅ Portfolio Management
- ✅ Comprehensive Documentation

---

**Built with ❤️ for NEPSE traders**

*Last Updated: 2026-03-24*
