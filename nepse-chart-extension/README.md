# NEPSE Chart Analyzer — Chrome Extension + FastAPI Backend

Automatically analyzes NEPSE stock charts on ShareHub. Detects candlestick patterns, volume anomalies (operator activity), and provides BUY/SELL signals — **no chart-reading knowledge required**.

## Directory Structure

```
nepse-chart-extension/
├── backend/
│   ├── main.py              # FastAPI server — pattern detection, indicators, scoring
│   └── requirements.txt     # Python dependencies
├── extension/
│   ├── manifest.json         # Chrome Extension Manifest V3
│   ├── background.js         # Service worker (badge updates)
│   ├── content_script.js     # Bridge: inject.js ↔ backend ↔ Shadow DOM UI
│   ├── inject.js             # Main-world fetch/XHR interceptor
│   ├── styles.css            # Shadow DOM styles for the floating widget
│   └── icons/                # Extension icons (create 16/48/128px PNGs)
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
└── README.md
```

## How It Works

```
ShareHub chart loads → fetch("candle-chart/history?symbol=NICA&resolution=1D")
        ↓
inject.js intercepts the response (clones it, doesn't block ShareHub)
        ↓
window.postMessage → content_script.js
        ↓
POST to http://localhost:8000/analyze
        ↓
FastAPI: pandas-ta pattern scan + RSI + ATR + volume analysis + scoring
        ↓
JSON response → content_script.js renders Shadow DOM widget on the page
```

## Quick Start

### 1. Start the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Verify: open http://localhost:8000/health — should return `{"status": "ok"}`.

### 2. Load the Extension

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** → select the `extension/` folder
4. You should see the "NEPSE Chart Analyzer" extension

### 3. Use It

1. Go to **sharehubnepal.com** and open any stock chart
2. The extension **automatically** intercepts chart data as it loads
3. A floating widget appears at bottom-right with the analysis
4. Change timeframe or stock → widget updates automatically

## Extension Icons

You need to create 3 PNG icon files in `extension/icons/`:

- `icon16.png` (16×16)
- `icon48.png` (48×48)
- `icon128.png` (128×128)

Use any chart/stock icon. The extension will work without icons but Chrome will show a default placeholder.

## API Reference

### POST /analyze

**Request:**

```json
{
  "metadata": {
    "symbol": "NICA",
    "resolution": "1D",
    "countback": "300",
    "isAdjust": "false"
  },
  "data": [
    {"time": 1711324800, "open": 850, "high": 870, "low": 845, "close": 865, "volume": 50000},
    ...
  ]
}
```

**Response:**

```json
{
  "symbol": "NICA",
  "resolution": "1D",
  "verdict": "BUY",
  "confidence": 72,
  "pattern_detected": "Engulfing",
  "patterns": [
    {
      "name": "Engulfing",
      "direction": "Bullish",
      "bar_index": 0,
      "strength": 100
    }
  ],
  "operator_activity": false,
  "volume_ratio": 1.35,
  "current_price": 865.0,
  "suggested_sl": 838.5,
  "suggested_target": 918.0,
  "risk_reward_ratio": 2.0,
  "rsi_14": 42.5,
  "atr_14": 13.25,
  "ema_10": 855.0,
  "ema_30": 840.0,
  "macd_signal": "Bullish",
  "bb_pct_b": 0.35,
  "trend": "UPTREND",
  "trend_strength": 28.5,
  "warnings": ["NEPSE T+2 settlement: minimum 3 trading days hold"]
}
```
