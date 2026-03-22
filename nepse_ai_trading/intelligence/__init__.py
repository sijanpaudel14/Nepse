"""
Intelligence module for NEPSE AI Trading Bot.
Handles news scraping, sentiment analysis, and AI integration.
"""

from intelligence.news_scraper import NewsScraper, scrape_news_for_stock
from intelligence.ai_advisor import AIAdvisor, get_ai_verdict
from intelligence.signal_aggregator import SignalAggregator, FinalSignal

__all__ = [
    "NewsScraper",
    "scrape_news_for_stock",
    "AIAdvisor",
    "get_ai_verdict",
    "SignalAggregator",
    "FinalSignal",
]
