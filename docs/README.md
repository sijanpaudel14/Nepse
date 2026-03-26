# 📚 NEPSE Trading Engine - Documentation Hub

Welcome to the documentation center for the NEPSE AI Trading Engine.

---

## 🚀 Quick Navigation

### 👤 User Guides (Start Here!)

Perfect for traders new to the system:

- **[Quick Start Guide](guides/QUICK_START.md)** - Get up and running in 5 minutes
- **[User Guide](guides/USER_GUIDE.md)** - Complete step-by-step manual
- **[Auto Logger Guide](guides/AUTO_LOGGER_GUIDE.md)** - Automated daily analysis setup
- **[Broker Intelligence Guide](guides/BROKER_INTELLIGENCE_GUIDE.md)** - Operator detection explained (350+ lines)
- **[Telegram Guide](guides/TELEGRAM_GUIDE.md)** - Set up real-time alerts

### 🆕 Position Management Tools

Help your friends decide what to do with their holdings:

- **[IPO Exit Analyzer](ipo-exit-analyzer/)** - When to sell newly listed IPOs (< 30 days) 🆕
- **[Position Advisor](position-advisor/)** - Hold or sell existing positions (any age) 🆕

**Start with:** Quick Start Guide → User Guide → Auto Logger Guide

---

### 🎯 Feature Documentation

Deep dives into system capabilities:

- **[Command Reference Card](features/COMMAND_REFERENCE_CARD.md)** - All 17+ commands with examples
- **[Advanced Features Guide](features/ADVANCED_FEATURES_GUIDE.md)** - Complete feature walkthrough
- **[Technical Signal Engine v2.0](features/TECHNICAL_SIGNAL_ENGINE_V2.md)** - NEPSE-optimized entry/exit timing 🆕
- **[Feature Overview](features/OVERVIEW.MD)** - High-level capabilities list

**Best for:** Understanding what each command does and when to use it

---

### 🔧 Technical Documentation

For developers and advanced users:

- **[API Documentation](api/NEPSE_unofficial_API.md)** - NEPSE API reference and endpoints
- **[Technical Analysis Periods Audit](technical/TECHNICAL_ANALYSIS_PERIODS_AUDIT.md)** - Lookback period optimization 🆕
- **[Bug Fixes Session](technical/FINAL_BUG_FIXES_SESSION.md)** - Latest 6 critical bug fixes
- **[Timeout Fixes](technical/TIMEOUT_FIXES_COMPLETE.md)** - Timeout troubleshooting guide
- **[Product Documentation](technical/PRODUCT_DOCUMENTATION.md)** - System architecture and design

**Best for:** Debugging, extending, or understanding the codebase

---

### 📦 Archive

Historical documentation and session notes:

- **[Advanced Features Complete](archive/ADVANCED_FEATURES_COMPLETE.md)** - Feature implementation history
- **[Comprehensive Product Complete](archive/COMPREHENSIVE_PRODUCT_COMPLETE.md)** - Product evolution
- **[Legacy Docs](archive/)** - Historical documentation

**Best for:** Understanding how features evolved

---

## 📖 Documentation by Use Case

### I want to...

#### 🏁 Get Started Quickly
1. [Quick Start Guide](guides/QUICK_START.md)
2. [Command Reference Card](features/COMMAND_REFERENCE_CARD.md)

#### 📊 Run Daily Analysis
1. [Auto Logger Guide](guides/AUTO_LOGGER_GUIDE.md)
2. [Broker Intelligence Guide](guides/BROKER_INTELLIGENCE_GUIDE.md)

#### 🕵️ Detect Market Manipulation
1. [Broker Intelligence Guide](guides/BROKER_INTELLIGENCE_GUIDE.md) (⭐ Start here)
2. [Smart Money section in User Guide](guides/USER_GUIDE.md)

#### 💰 Track Institutional Money
1. [Advanced Features Guide](features/ADVANCED_FEATURES_GUIDE.md) - Smart Money section
2. [Command Reference Card](features/COMMAND_REFERENCE_CARD.md) - `--smart-money` command

#### 🎯 Find Entry/Exit Timing 🆕
1. [Technical Signal Engine v2.0](features/TECHNICAL_SIGNAL_ENGINE_V2.md) (⭐ Start here)
2. [Command Reference Card](features/COMMAND_REFERENCE_CARD.md) - `--signal` command

#### 🏦 Decide Hold or Sell Existing Position 🆕
1. [Position Advisor](position-advisor/) - For stocks bought weeks/months ago (⭐ Start here)
2. [IPO Exit Analyzer](ipo-exit-analyzer/) - For newly listed IPOs (< 30 days)

#### 💹 Calculate Price Targets 🆕
1. [Command Reference Card](features/COMMAND_REFERENCE_CARD.md) - `--price-targets` command
2. [Technical Signal Engine v2.0](features/TECHNICAL_SIGNAL_ENGINE_V2.md)

#### 🔔 Set Up Alerts
1. [Telegram Guide](guides/TELEGRAM_GUIDE.md)
2. [Auto Logger Guide](guides/AUTO_LOGGER_GUIDE.md) - Scheduling section

#### 🐛 Fix Problems
1. [Bug Fixes Session](technical/FINAL_BUG_FIXES_SESSION.md)
2. [Timeout Fixes](technical/TIMEOUT_FIXES_COMPLETE.md)

#### 🛠️ Understand the Code
1. [Product Documentation](technical/PRODUCT_DOCUMENTATION.md)
2. [API Documentation](api/NEPSE_unofficial_API.md)

---

## 🎓 Learning Path

### Beginner (Week 1)
```
Day 1: Quick Start Guide
Day 2: User Guide (Part 1: Setup)
Day 3: User Guide (Part 2: Basic Commands)
Day 4: Command Reference Card
Day 5: Auto Logger Guide
Day 6-7: Practice with real market data
```

### Intermediate (Week 2)
```
Day 1-2: Broker Intelligence Guide
Day 3-4: Advanced Features Guide
Day 5: Telegram Guide (alerts setup)
Day 6-7: Combine all features in daily workflow
```

### Advanced (Week 3+)
```
- Customize strategies
- Build custom filters
- Read technical documentation
- Contribute improvements
```

---

## 📋 Command Quick Reference

### Market Overview
```bash
--positioning      # Market overbought/oversold
--heatmap          # Sector breadth analysis
--sector-rotation  # Which sectors are hot
```

### Smart Money
```bash
--smart-money      # Institutional flow (all sectors)
--smart-money --sector=hydro  # Sector-specific
--bulk-deals       # Large insider trades
```

### Broker Intelligence 🆕
```bash
--broker-intelligence              # All sectors
--broker-intelligence --sector=hydro    # Hydro sector
--broker-intelligence --sector=bank     # Banks sector
--broker-intelligence --sector=finance  # Finance sector
```

### Stock Analysis
```bash
--analyze SYMBOL        # Complete stock report
--tech-score SYMBOL     # Multi-timeframe technical score
--order-flow SYMBOL     # Buy/sell pressure analysis
--signal SYMBOL         # Entry/exit timing with Wyckoff phases 🆕
--price-targets SYMBOL   # Multi-level price targets 🆕
--calendar              # Daily top picks calendar (next 30 days) 🆕
--calendar-days 30      # Lookahead window (default 30)
--calendar-max-stocks 0 # 0=all stocks (default), N=cap universe
```

### Position Management 🆕
```bash
--ipo-exit SYMBOL                           # IPO exit analysis (< 30 days)
--hold-or-sell SYMBOL --buy-price 500        # Position advisor
--hold-or-sell SYMBOL --buy-price 500 --buy-date 2026-01-01  # With date
```

### Calendar Filters (also works with `--calendar`)
```bash
--sector=all|hydro|bank|finance|...
--max-price=600
--quick                 # fast mode
```

### Portfolio
```bash
--portfolio           # Current portfolio status
--buy-picks [SYMBOLS] # Buy specific stocks
--sell SYMBOL         # Sell a position
```

### Automation
```bash
python tools/auto_market_logger.py --now  # Run full analysis
python tools/auto_market_logger.py --schedule  # Schedule daily
```

---

## 🔥 Most Popular Docs

Based on usage and importance:

1. **[Technical Signal Engine v2.0](features/TECHNICAL_SIGNAL_ENGINE_V2.md)** ⭐⭐⭐⭐⭐ 🆕
   - Entry/exit timing automation
   - 16 chart patterns + Wyckoff phases
   - NEPSE-optimized (75-80% accuracy)
   - Beats manual chart reading

2. **[Position Advisor](position-advisor/)** ⭐⭐⭐⭐⭐ 🆕
   - Hold or sell existing positions
   - Health score (0-100) with verdicts
   - Holding period awareness (1 week to 1 year)
   - Help your friends decide

3. **[IPO Exit Analyzer](ipo-exit-analyzer/)** ⭐⭐⭐⭐⭐ 🆕
   - When to sell newly listed IPOs
   - Volume + Broker flow analysis
   - 5 exit signals with scoring
   - Perfect for first 30 days

4. **[Broker Intelligence Guide](guides/BROKER_INTELLIGENCE_GUIDE.md)** ⭐⭐⭐⭐⭐
   - Operator detection
   - 350+ lines
   - Trading strategies included

3. **[Auto Logger Guide](guides/AUTO_LOGGER_GUIDE.md)** ⭐⭐⭐⭐⭐
   - Automated analysis
   - 25-30 min daily routine
   - 12+ intelligence reports

4. **[Command Reference Card](features/COMMAND_REFERENCE_CARD.md)** ⭐⭐⭐⭐
   - All commands in one place
   - Copy-paste ready
   - Daily workflow examples

5. **[Quick Start Guide](guides/QUICK_START.md)** ⭐⭐⭐⭐
   - 5-minute setup
   - First scan walkthrough

6. **[User Guide](guides/USER_GUIDE.md)** ⭐⭐⭐
   - Complete manual
   - Step-by-step instructions

---

## 🆘 Getting Help

### Where to Look

1. **Check this README first** - Quick navigation
2. **Read Quick Start** - Common setup issues
3. **Search Command Reference** - Command usage
4. **Check Bug Fixes** - Known issues

### Common Issues

| Problem | Solution |
|---------|----------|
| "ShareHub API error 401" | Check credentials in `.env` |
| "Timeout error" | See [Timeout Fixes](technical/TIMEOUT_FIXES_COMPLETE.md) |
| "No broker data" | Stock may be delisted/dormant |
| "Scan returns 0 stocks" | Market may be in distribution phase |
| "Auto logger won't start" | Check Python version (need 3.12+) |

---

## 📊 Documentation Stats

- **Total Docs:** 26 markdown files (+6 new) 🆕
- **Total Lines:** ~10,500+ lines  
- **Guides:** 5
- **Position Management:** 2 (NEW) 🆕
- **Features:** 4 (+1 new) 🆕
- **Technical:** 6 (+3 new) 🆕
- **Archive:** 5
- **API:** 1

---

## 🔄 Recently Updated

- **2026-03-26:** Position Advisor (NEW - Hold or sell existing positions) 🆕
- **2026-03-26:** IPO Exit Analyzer (NEW - When to sell newly listed IPOs) 🆕
- **2026-03-26:** NEPSE-specific fixes (Stop loss 5%, RSI exit 60, real-time LTP) 🆕
- **2026-03-26:** Comprehensive Audit (57 fixes - lookahead bias, crash guards, execution realism) 🆕
- **2026-03-25:** Technical Signal Engine v2.0 (NEW - NEPSE-optimized entry/exit timing) 🆕
- **2026-03-25:** Price Target Analyzer (NEW - Multi-level targets with risk assessment) 🆕
- **2026-03-25:** Technical Analysis Periods Audit (NEW - Lookback optimization) 🆕
- **2026-03-24:** Broker Intelligence Guide (NEW - 350+ lines)
- **2026-03-24:** Auto Logger Guide (Updated with broker intelligence)
- **2026-03-24:** Command Reference Card (Added broker intelligence examples)
- **2026-03-24:** Bug Fixes Session (6 critical bugs fixed)
- **2026-03-24:** Documentation reorganized into docs/ folder

---

## 🗂️ File Organization

```
docs/
├── README.md                    # This file
│
├── guides/                      # User-facing guides
│   ├── QUICK_START.md
│   ├── USER_GUIDE.md
│   ├── AUTO_LOGGER_GUIDE.md
│   ├── TELEGRAM_GUIDE.md
│   └── BROKER_INTELLIGENCE_GUIDE.md
│
├── ipo-exit-analyzer/           # 🆕 IPO exit timing
│   ├── README.md
│   ├── IPO_EXIT_GUIDE.md
│   └── BROKER_FLOW_EXPLAINED.md
│
├── position-advisor/            # 🆕 Hold or sell advisor
│   ├── README.md
│   └── POSITION_ADVISOR_GUIDE.md
│
├── features/                    # Feature documentation
│   ├── ADVANCED_FEATURES_GUIDE.md
│   ├── COMMAND_REFERENCE_CARD.md
│   ├── TECHNICAL_SIGNAL_ENGINE_V2.md  # 🆕
│   └── OVERVIEW.MD
│
├── api/                         # API reference
│   └── NEPSE_unofficial_API.md
│
├── technical/                   # Technical docs
│   ├── AUDIT_FIXES_SUMMARY.md   # 🆕 57 audit fixes
│   ├── TECHNICAL_ANALYSIS_PERIODS_AUDIT.md  # 🆕
│   ├── FINAL_BUG_FIXES_SESSION.md
│   ├── TIMEOUT_FIXES_COMPLETE.md
│   ├── PRODUCT_DOCUMENTATION.md
│   ├── ARCHITECTURE.md
│   ├── COMPREHENSIVE_AUDIT_REPORT.md
│   └── TROUBLESHOOTING.md
│
└── archive/                     # Historical docs
    ├── ADVANCED_FEATURES_COMPLETE.md
    ├── COMPREHENSIVE_PRODUCT_COMPLETE.md
    ├── final_documentation.md
    ├── instruction.md
    └── markdown.md
```

---

## 💡 Pro Tips

1. **Bookmark these pages:**
   - Command Reference Card (daily use)
   - Broker Intelligence Guide (before buying stocks)
   - Auto Logger Guide (automation setup)

2. **Print these:**
   - Command Reference Card
   - Broker Intelligence scoring guide

3. **Read daily:**
   - Auto logger outputs in `market_logs/latest/`

4. **Master these first:**
   - `--scan` (momentum screening)
   - `--analyze SYMBOL` (stock deep dive)
   - `--signal SYMBOL` (entry/exit timing) 🆕
   - `--price-targets SYMBOL` (profit targets) 🆕
   - `--hold-or-sell SYMBOL --buy-price 500` (position advisor) 🆕
   - `--ipo-exit SYMBOL` (IPO exit timing) 🆕
   - `--broker-intelligence --sector=hydro` (operator detection)

---

## 🎯 Next Steps

1. **New User?** 
   - Start with [Quick Start Guide](guides/QUICK_START.md)

2. **Setting Up Automation?**
   - Read [Auto Logger Guide](guides/AUTO_LOGGER_GUIDE.md)

3. **Want to Detect Pumps?**
   - Study [Broker Intelligence Guide](guides/BROKER_INTELLIGENCE_GUIDE.md)

4. **Friend Asks "Should I Sell?"** 🆕
   - Use [Position Advisor](position-advisor/) (get their buy price)
   - Or [IPO Exit Analyzer](ipo-exit-analyzer/) (if newly listed)

5. **Building Custom Strategy?**
   - Check [Technical Documentation](technical/)

---

**Happy Trading! 🚀**

*Documentation maintained by NEPSE AI Trading Engine Team*  
*Last Updated: 2026-03-26*
