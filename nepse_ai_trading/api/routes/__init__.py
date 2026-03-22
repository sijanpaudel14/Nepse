"""
API Routes for NEPSE AI Trading Bot.

This module contains all FastAPI route handlers organized by feature area.
"""

from api.routes.analysis import router as analysis_router
from api.routes.stocks import router as stocks_router
from api.routes.signals import router as signals_router

__all__ = [
    "analysis_router",
    "stocks_router", 
    "signals_router",
]
