Here is the comprehensive, step-by-step System Architecture and Technical Requirement Document. Since you are highly skilled in Python and automation but lack share market knowledge, this document bridges that gap. It defines the exact financial formulas (Technical Analysis) and the software architecture. 

You can copy and paste this entire guide directly into GitHub Copilot, ChatGPT, or Claude as your "Master Prompt" to generate the code file by file.

***

# 🤖 MASTER PROMPT FOR GITHUB COPILOT
**Context for AI Assistant:** I am building a personal, automated swing-trading bot for the Nepal Stock Exchange (NEPSE). I want to write this in Python. The bot will fetch daily market data, perform strict technical analysis to find short-term stock breakouts, scrape recent news for those specific stocks, and use OpenAI to give me a final trading recommendation via Telegram. Generate the code modularly based on the steps below.

## 📂 Project Structure
Ask Copilot to create the following file structure:
```text
nepse_ai_bot/
│── main.py                 # The orchestrator script
│── requirements.txt        # Python dependencies
│── data_fetcher.py         # Handles NepseUnofficialAPI and database
│── technical_analyzer.py   # Handles pandas-ta math and screening
│── news_scraper.py         # Playwright script for ShareSansar/Merolagani
│── ai_advisor.py           # OpenAI API integration
└── notifier.py             # Telegram bot integration
```

***

## 🛠️ Step 1: Dependencies (`requirements.txt`)
**Prompt Copilot:** "Generate a `requirements.txt` with the following libraries: `requests`, `pandas`, `pandas-ta`, `playwright`, `openai`, `python-telegram-bot`, `python-dotenv`, and `sqlite3`."

***

## 📊 Step 2: Data Extraction (`data_fetcher.py`)
**Prompt Copilot:** "Write a Python script that uses `NepseUnofficialAPI` (via HTTP requests to the open GitHub repo endpoints) to fetch the daily closing data for all NEPSE companies. The data must include: Symbol, Open, High, Low, Close, and Volume (OHLCV). Save this data into a local SQLite database (`nepse_data.db`)."

*Financial Context for You:* OHLCV is the foundation of all trading. 
* **Open/Close:** The price at the start and end of the day.
* **High/Low:** The maximum and minimum price of the day.
* **Volume:** How many shares were traded. High volume means big investors are buying.

***

## 📈 Step 3: Technical Analysis Engine (`technical_analyzer.py`)
**Prompt Copilot:** "Write a script using `pandas` and `pandas-ta` that pulls the last 60 days of data from the SQLite database and applies the following swing-trading conditions. Return a list of stock symbols that pass ALL of these rules:
1. **Trend Rule:** Calculate the 9-day EMA (Exponential Moving Average) and 21-day EMA. The 9-day EMA must have crossed ABOVE the 21-day EMA today or yesterday (Golden Cross).
2. **Momentum Rule:** Calculate the 14-day RSI (Relative Strength Index). The RSI must be between 50 and 65 (bullish momentum, but not overbought).
3. **Volume Rule:** The trading volume today must be at least 150% higher than the 20-day Average Volume.
4. **Price Rule:** The Closing price must be greater than Rs. 200 (to avoid penny stock manipulation)."

*Financial Context for You:* 
* **EMA (Exponential Moving Average):** A line showing the average price. When a short-term average (9-day) crosses above a longer-term average (21-day), it signals a new upward trend is starting.
* **RSI (Relative Strength Index):** A score from 0 to 100. Below 30 means the stock is "oversold" (cheap). Above 70 means "overbought" (too expensive). 50-65 is the sweet spot where a stock is rising safely.

***

## 📰 Step 4: News Scraping (`news_scraper.py`)
**Prompt Copilot:** "For the list of filtered stock symbols returned by the `technical_analyzer.py`, use Playwright to navigate to `sharesansar.com` or `merolagani.com`. Search for the stock symbol and scrape the text of the top 3 most recent news headlines or company announcements. Return this as a dictionary: `{ 'SYMBOL': 'News text...' }`."

*Financial Context for You:* Technical analysis tells us *what* is happening (price is going up). News tells us *why* (e.g., the company just announced a 15% dividend). We need the "why" to confirm the math isn't a fake pump.

***

## 🧠 Step 5: OpenAI Integration (`ai_advisor.py`)
**Prompt Copilot:** "Write a script that takes the filtered stocks, their technical indicators (RSI, EMA, Volume spike percentage), and the scraped news text. Pass this to the OpenAI API (GPT-4o-mini) using the following System Prompt:
*'You are an expert NEPSE swing trader. I am giving you a stock that just triggered a technical buy signal. Analyze the provided technical data and the recent news. Tell me if this is a strong buy, a risky buy, or a false breakout. Provide a 3-sentence summary, a suggested Entry Price, a Target Price (10% gain), and a Stop Loss (-5% loss).'* Return the AI's response."

*Financial Context for You:* 
* **Target Price:** Where you plan to sell for a profit.
* **Stop Loss:** A strictly calculated price where you automatically sell at a minor loss (e.g., -5%) if the AI/Math was wrong, protecting your main capital.

***

## 📲 Step 6: Telegram Notification (`notifier.py`)
**Prompt Copilot:** "Write a script using `python-telegram-bot` that takes the final OpenAI analysis and sends it to my personal Telegram chat ID. Format the message with emojis for readability (e.g., 🟢 Symbol, 📈 Technicals, 📰 News, 🤖 AI Verdict)."

***

## ⚙️ Step 7: Main Orchestrator (`main.py`)
**Prompt Copilot:** "Create a `main.py` that imports all the above modules and runs them in sequence: `fetch_data()` -> `analyze_technicals()` -> `scrape_news(filtered_stocks)` -> `get_ai_verdict()` -> `send_telegram_alert()`. Wrap everything in a `try/except` block for error handling."

***
