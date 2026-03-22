"""
Data module for NEPSE AI Trading Bot.
Handles data fetching, cleaning, and storage.
"""

from data.fetcher import NepseFetcher, fetch_all_stocks, fetch_stock_history
from data.data_cleaner import clean_price_data, parse_nepse_number
from data.schemas import StockData, PriceData, MarketDataSchema

__all__ = [
    "NepseFetcher",
    "fetch_all_stocks",
    "fetch_stock_history",
    "clean_price_data",
    "parse_nepse_number",
    "StockData",
    "PriceData",
    "MarketDataSchema",
]
