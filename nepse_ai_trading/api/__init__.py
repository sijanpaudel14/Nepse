"""
API Module - FastAPI Web Interface.

Provides:
- RESTful API endpoints for market data, signals, portfolio
- Web dashboard (HTML/JS frontend)
- OpenAPI documentation at /docs

Start the server with:
    uvicorn api.main:app --reload
"""

from .main import app

__all__ = ["app"]
