"""
Intelligence module for NEPSE AI Trading Bot.
Handles news scraping, sentiment analysis, AI integration,
broker profiling, syndicate detection, macro scoring, and market breadth.
"""

from .news_scraper import NewsScraper, scrape_news_for_stock
from .ai_advisor import AIAdvisor, get_ai_verdict
from .signal_aggregator import SignalAggregator, FinalSignal
from .broker_profiles import build_broker_profiles, BrokerProfile, StockBrokerSummary
from .syndicate_detector import detect_syndicate, SyndicateSignal
from .floorsheet_tracker import analyze_floorsheet_concentration, compute_hhi, ConcentrationResult
from .macro_engine import compute_macro_score, MacroScore

__all__ = [
    "NewsScraper",
    "scrape_news_for_stock",
    "AIAdvisor",
    "get_ai_verdict",
    "SignalAggregator",
    "FinalSignal",
    # Phase 5 additions
    "build_broker_profiles",
    "BrokerProfile",
    "StockBrokerSummary",
    "detect_syndicate",
    "SyndicateSignal",
    "analyze_floorsheet_concentration",
    "compute_hhi",
    "ConcentrationResult",
    "compute_macro_score",
    "MacroScore",
]
