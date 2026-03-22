"""
NEPSE Data Fetcher using the official NepseUnofficialApi library.

This uses the actual library from: https://github.com/basic-bgnr/NepseUnofficialApi
which deciphers NEPSE's authentication to access real-time data.

INSTALLATION:
    pip install git+https://github.com/basic-bgnr/NepseUnofficialApi

IMPORTANT: 
- NEPSE's SSL certificate has issues. We disable TLS verification.
- This is production-grade - uses the same endpoints as nepalstock.com
"""

import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any
import pandas as pd
from loguru import logger

from core.config import settings
from core.exceptions import NepseAPIError, DataValidationError
from core.database import SessionLocal, Stock, DailyPrice, MarketData
from data.schemas import StockData, PriceData, MarketDataSchema
from data.data_cleaner import clean_price_data, parse_nepse_number

# Import the REAL NepseUnofficialApi
try:
    from nepse import Nepse
    NEPSE_API_AVAILABLE = True
except ImportError:
    NEPSE_API_AVAILABLE = False
    logger.warning(
        "NepseUnofficialApi not installed! "
        "Run: pip install git+https://github.com/basic-bgnr/NepseUnofficialApi"
    )


class NepseFetcher:
    """
    Fetches data from NEPSE using the NepseUnofficialApi library.
    
    This library deciphers NEPSE's authentication and provides
    direct access to nepalstock.com APIs - the same data brokers use.
    """
    
    def __init__(self):
        """
        Initialize the NEPSE API client.
        """
        if not NEPSE_API_AVAILABLE:
            raise ImportError(
                "NepseUnofficialApi required. Install with: "
                "pip install git+https://github.com/basic-bgnr/NepseUnofficialApi"
            )
        
        self.nepse = Nepse()
        # Disable TLS verification (NEPSE has SSL certificate issues)
        self.nepse.setTLSVerification(False)
        
        logger.info("NepseFetcher initialized with official NepseUnofficialApi")
    
    def fetch_company_list(self) -> List[StockData]:
        """
        Fetch list of all NEPSE-listed companies.
        
        Returns:
            List of StockData objects
        """
        logger.info("Fetching company list from NEPSE...")
        
        try:
            companies = self.nepse.getCompanyList()
            
            stocks = []
            for company in companies:
                try:
                    stock = StockData(
                        symbol=company.get("symbol", ""),
                        name=company.get("securityName", company.get("companyName", "")),
                        sector=company.get("sectorName", ""),
                        listed_shares=parse_nepse_number(company.get("listedShares")),
                        market_cap=parse_nepse_number(company.get("marketCapitalization")),
                    )
                    if stock.symbol:
                        stocks.append(stock)
                except Exception as e:
                    logger.debug(f"Failed to parse company: {e}")
                    continue
            
            logger.info(f"Fetched {len(stocks)} companies from NEPSE")
            return stocks
            
        except Exception as e:
            logger.error(f"Failed to fetch company list: {e}")
            raise NepseAPIError(f"Company list fetch failed: {e}")
    
    def fetch_live_market(self) -> pd.DataFrame:
        """
        Fetch today's live market data for all stocks.
        
        This is the real-time data from NEPSE trading floor.
        
        Returns:
            DataFrame with today's OHLCV data
        """
        logger.info("Fetching live market data from NEPSE...")
        
        try:
            live_data = self.nepse.getLiveMarket()
            
            if not live_data:
                logger.warning("No live market data received")
                return pd.DataFrame()
            
            # Convert to DataFrame
            records = []
            for item in live_data:
                records.append({
                    "symbol": item.get("symbol", ""),
                    "date": date.today(),
                    "open": parse_nepse_number(item.get("openPrice")),
                    "high": parse_nepse_number(item.get("highPrice")),
                    "low": parse_nepse_number(item.get("lowPrice")),
                    "close": parse_nepse_number(item.get("lastTradedPrice", item.get("ltp"))),
                    "volume": parse_nepse_number(item.get("totalTradedQuantity", item.get("totalTradeQuantity"))),
                    "turnover": parse_nepse_number(item.get("totalTradedValue", item.get("turnover"))),
                    "trades": item.get("totalTrades"),
                })
            
            df = pd.DataFrame(records)
            df = df.dropna(subset=["symbol", "close"])
            
            logger.info(f"Fetched live data for {len(df)} stocks")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch live market: {e}")
            raise NepseAPIError(f"Live market fetch failed: {e}")
    
    def fetch_price_history(self, symbol: str, days: int = None) -> pd.DataFrame:
        """
        Fetch historical price data for a specific stock.
        
        Uses getCompanyPriceVolumeHistory(symbol, start_date, end_date) which 
        directly accepts symbol string (library handles ID lookup internally).
        
        Args:
            symbol: Stock symbol (e.g., "NABIL", "NICA")
            days: Number of days of history (default from settings)
            
        Returns:
            DataFrame with historical OHLCV data
        """
        symbol = symbol.upper().strip()
        days = days or settings.lookback_days
        
        logger.info(f"Fetching {days}-day history for {symbol}...")
        
        try:
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Use the correct method from NepseUnofficialApi
            # getCompanyPriceVolumeHistory(symbol, start_date, end_date) -> returns {"content": [...]}
            response = self.nepse.getCompanyPriceVolumeHistory(symbol, start_date, end_date)
            
            # Response can be list directly or dict with "content" key
            if isinstance(response, dict):
                history = response.get("content", [])
            else:
                history = response if response else []
            
            # NEPSE API quirk: Range query often misses today's data due to caching lag
            # Fetch today explicitly and merge if missing
            today_response = self.nepse.getCompanyPriceVolumeHistory(symbol, end_date, end_date)
            if isinstance(today_response, dict):
                today_data = today_response.get("content", [])
            else:
                today_data = today_response if today_response else []
            
            # Merge today's data if not already present
            if today_data:
                today_date_str = str(end_date)
                existing_dates = {item.get("businessDate") for item in history}
                for td in today_data:
                    if td.get("businessDate") not in existing_dates:
                        history.append(td)
                        logger.debug(f"Added today's data ({td.get('businessDate')}) for {symbol}")
            
            if not history:
                logger.warning(f"No history for {symbol}")
                return pd.DataFrame()
            
            records = []
            for item in history:
                records.append({
                    "symbol": symbol,
                    "date": item.get("businessDate", ""),
                    "open": parse_nepse_number(item.get("openPrice")),
                    "high": parse_nepse_number(item.get("highPrice")),
                    "low": parse_nepse_number(item.get("lowPrice")),
                    "close": parse_nepse_number(item.get("closePrice", item.get("lastTradedPrice"))),
                    "volume": parse_nepse_number(item.get("totalTradedQuantity")),
                    "turnover": parse_nepse_number(item.get("totalTradedValue")),
                })
            
            df = pd.DataFrame(records)
            
            # Parse dates
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.sort_values("date")
            
            logger.info(f"Fetched {len(df)} days of history for {symbol}")
            return df.reset_index(drop=True)
            
        except KeyError as e:
            logger.warning(f"Symbol not found in NEPSE: {symbol}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to fetch history for {symbol}: {e}")
            raise NepseAPIError(f"Price history fetch failed: {e}")

    def safe_fetch_data(self, symbol: str, days: int = 60, min_rows: int = 14) -> pd.DataFrame:
        """
        Fetch and validate OHLCV safely for indicator/scoring pipelines.

        Handles common NEPSE issues:
        - insufficient rows for indicators
        - string/invalid numeric values
        - missing OHLC fields
        - zero-volume days and malformed OHLC relationships
        """
        symbol = symbol.upper().strip()
        required_cols = ["date", "open", "high", "low", "close", "volume"]

        def _validate(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return pd.DataFrame(columns=required_cols)

            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"{symbol}: missing required column '{col}' in price history")
                    return pd.DataFrame(columns=required_cols)

            cleaned = df.copy()
            cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce").dt.date
            for col in ["open", "high", "low", "close", "volume"]:
                cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

            # Keep rows with at least close; backfill missing OHLC from close.
            cleaned = cleaned.dropna(subset=["close"])
            cleaned["open"] = cleaned["open"].fillna(cleaned["close"])
            cleaned["high"] = cleaned["high"].fillna(cleaned["close"])
            cleaned["low"] = cleaned["low"].fillna(cleaned["close"])
            cleaned["volume"] = cleaned["volume"].fillna(0).clip(lower=0)

            # Repair OHLC relationships where APIs return broken values.
            cleaned["high"] = cleaned[["high", "open", "close", "low"]].max(axis=1)
            cleaned["low"] = cleaned[["low", "open", "close", "high"]].min(axis=1)

            cleaned = cleaned.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
            return cleaned.reset_index(drop=True)

        try:
            df = _validate(self.fetch_price_history(symbol, days=days))
            if len(df) >= min_rows:
                return df

            fallback_days = max(days * 2, min_rows + 10)
            logger.warning(
                f"{symbol}: only {len(df)} rows from {days} days, retrying with {fallback_days} days for indicator safety"
            )
            fallback_df = _validate(self.fetch_price_history(symbol, days=fallback_days))

            if len(fallback_df) < min_rows:
                logger.warning(
                    f"{symbol}: insufficient validated rows ({len(fallback_df)} < {min_rows}); returning best-effort data"
                )
            return fallback_df
        except Exception as e:
            logger.error(f"safe_fetch_data failed for {symbol}: {e}")
            return pd.DataFrame(columns=required_cols)
    
    def fetch_index_history(self, days: int = 60) -> pd.DataFrame:
        """
        Fetch NEPSE Index historical data for market regime analysis.
        
        Used to determine if market is in Bull or Bear mode by comparing
        current index value to its 50-day EMA.
        
        Args:
            days: Number of days of history to fetch (default 60 for EMA 50)
        
        Returns:
            DataFrame with columns: date, close
        """
        logger.info(f"Fetching {days}-day NEPSE Index history...")
        
        try:
            # Try to get index history from NEPSE API
            # Using getDailyNepseIndexGraph() which returns [[timestamp, value], ...]
            index_data = self.nepse.getDailyNepseIndexGraph()
            
            if not index_data or len(index_data) == 0:
                logger.warning("No index history available, using market summary")
                return pd.DataFrame()
            
            # Convert to DataFrame with explicit columns
            df = pd.DataFrame(index_data, columns=['timestamp', 'close'])
            
            # Convert timestamp to date
            df['date'] = pd.to_datetime(df['timestamp'], unit='s').dt.date
            
            # Clean and sort
            df = df[['date', 'close']].dropna()
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df = df.dropna()
            df = df.sort_values('date').tail(days)
            
            logger.info(f"Fetched {len(df)} days of NEPSE Index history")
            return df.reset_index(drop=True)
            
        except Exception as e:
            logger.warning(f"Failed to fetch index history: {e}")
            # Fallback: Try to construct from current day data
            try:
                current_index = self.nepse.getNepseIndex()
                if current_index:
                    for idx in current_index:
                        if idx.get('index') == 'NEPSE Index' or 'NEPSE' in str(idx.get('index', '')):
                            value = float(idx.get('currentValue', 0))
                            if value > 0:
                                return pd.DataFrame({
                                    'date': [pd.Timestamp.now().date()],
                                    'close': [value]
                                })
            except:
                pass
            return pd.DataFrame()

    def fetch_sector_indices(self) -> Dict[str, float]:
        """
        Fetch current percentage change for all sectors.
        Used for Sector Trend Bonus.
        
        Returns:
            Dictionary of { "Sector Name": percentage_change }
            Example: { "Hydropower": 2.5, "Banking": -0.5 }
        """
        logger.info("Fetching sector indices (sub-indices)...")
        
        try:
            # This calls the endpoint that returns all sub-indices status
            sub_indices = self.nepse.getNepseSubIndices()
            
            sector_map = {}
            if not sub_indices:
                logger.warning("Sector indices returned empty")
                return {}
                
            # Parse response
            # Expected format: List of dicts with 'index', 'change', 'percentChange' or similar
            # Example: [{'index': 'Banking', 'currentValue': 1160.2, 'change': -5.1, 'perChange': -0.44}, ...]
            for item in sub_indices:
                try:
                    name = item.get("index", "")
                    # Ensure percent change is float
                    # Note: API usually returns 'perChange' or 'percentChange'
                    pct_change = parse_nepse_number(item.get("perChange", item.get("percentChange", 0)))
                    if name:
                        sector_map[name] = pct_change
                except (ValueError, TypeError):
                    continue
            
            logger.info(f"✅ Fetched trends for {len(sector_map)} sectors")
            return sector_map
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch sector indices: {e}")
            return {}
    
    def fetch_market_summary(self) -> MarketDataSchema:
        """
        Fetch overall market summary (NEPSE index, breadth).
        
        Returns:
            MarketDataSchema with market data
        """
        logger.info("Fetching market summary...")
        
        try:
            # Get NEPSE index
            index_data = self.nepse.getNepseIndex()
            
            # Get market status
            market_status = self.nepse.isNepseOpen()
            
            # Parse index data
            nepse_index = None
            nepse_change = None
            nepse_change_pct = None
            
            if index_data:
                for idx in index_data:
                    if "NEPSE" in idx.get("index", "").upper():
                        nepse_index = parse_nepse_number(idx.get("currentValue"))
                        nepse_change = parse_nepse_number(idx.get("change"))
                        nepse_change_pct = parse_nepse_number(idx.get("perChange"))
                        break
            
            # Get market breadth from live data
            live_data = self.nepse.getLiveMarket()
            advances = sum(1 for s in live_data if parse_nepse_number(s.get("percentageChange", 0)) > 0)
            declines = sum(1 for s in live_data if parse_nepse_number(s.get("percentageChange", 0)) < 0)
            unchanged = len(live_data) - advances - declines
            
            market_data = MarketDataSchema(
                date=date.today(),
                nepse_index=nepse_index,
                nepse_change=nepse_change,
                nepse_change_pct=nepse_change_pct,
                advances=advances,
                declines=declines,
                unchanged=unchanged,
            )
            
            logger.info(f"Market: NEPSE {nepse_index} ({nepse_change_pct}%)")
            logger.info(f"Breadth: {advances}↑ {declines}↓ {unchanged}→")
            
            return market_data
            
        except Exception as e:
            logger.error(f"Failed to fetch market summary: {e}")
            return MarketDataSchema(date=date.today())
    
    def fetch_top_gainers(self, limit: int = 10) -> pd.DataFrame:
        """Fetch top gaining stocks today."""
        try:
            gainers = self.nepse.getTopGainers()
            return self._convert_top_list(gainers, limit)
        except Exception as e:
            logger.error(f"Failed to fetch top gainers: {e}")
            return pd.DataFrame()
    
    def fetch_top_losers(self, limit: int = 10) -> pd.DataFrame:
        """Fetch top losing stocks today."""
        try:
            losers = self.nepse.getTopLosers()
            return self._convert_top_list(losers, limit)
        except Exception as e:
            logger.error(f"Failed to fetch top losers: {e}")
            return pd.DataFrame()
    
    def fetch_top_volume(self, limit: int = 10) -> pd.DataFrame:
        """Fetch stocks with highest volume today."""
        try:
            volume = self.nepse.getTopTenTradeScrips()
            return self._convert_top_list(volume, limit)
        except Exception as e:
            logger.error(f"Failed to fetch top volume: {e}")
            return pd.DataFrame()
    
    def fetch_top_turnover(self, limit: int = 10) -> pd.DataFrame:
        """Fetch stocks with highest turnover today."""
        try:
            turnover = self.nepse.getTopTenTurnoverScrips()
            return self._convert_top_list(turnover, limit)
        except Exception as e:
            logger.error(f"Failed to fetch top turnover: {e}")
            return pd.DataFrame()
    
    def fetch_sector_summary(self) -> pd.DataFrame:
        """
        Fetch sector-wise performance summary.
        
        Uses getSectorScrips() to get stocks grouped by sector,
        then aggregates from live market data.
        """
        try:
            # Get sector-scrip mapping
            sector_scrips = self.nepse.getSectorScrips()
            
            # Get live market for aggregation
            live_data = self.nepse.getLiveMarket()
            live_dict = {item.get("symbol"): item for item in live_data}
            
            records = []
            for sector, symbols in sector_scrips.items():
                sector_volume = 0
                sector_turnover = 0
                sector_trades = 0
                
                for sym in symbols:
                    if sym in live_dict:
                        item = live_dict[sym]
                        sector_volume += parse_nepse_number(item.get("totalTradedQuantity", 0)) or 0
                        sector_turnover += parse_nepse_number(item.get("totalTradedValue", item.get("turnover", 0))) or 0
                        sector_trades += item.get("totalTrades", 0) or 0
                
                records.append({
                    "sector": sector,
                    "stock_count": len(symbols),
                    "volume": sector_volume,
                    "turnover": sector_turnover,
                    "trades": sector_trades,
                })
            
            return pd.DataFrame(records)
            
        except Exception as e:
            logger.error(f"Failed to fetch sector summary: {e}")
            return pd.DataFrame()
    
    def fetch_floorsheet(self, symbol: str = None) -> pd.DataFrame:
        """
        Fetch floorsheet (all transactions) for today.
        
        This is detailed trade-by-trade data - very powerful for analysis!
        
        Args:
            symbol: Optional - filter for specific stock
            
        Returns:
            DataFrame with all transactions
        """
        logger.info("Fetching floorsheet (this may take a moment)...")
        
        try:
            if symbol:
                floorsheet = self.nepse.getFloorSheetOf(symbol.upper())
            else:
                floorsheet = self.nepse.getFloorSheet()
            
            if not floorsheet:
                return pd.DataFrame()
            
            df = pd.DataFrame(floorsheet)
            logger.info(f"Fetched {len(df)} floorsheet entries")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch floorsheet: {e}")
            return pd.DataFrame()
    
    def fetch_company_details(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch detailed company information.
        
        Returns:
            Dict with company details (market cap, EPS, PE, etc.)
        """
        symbol = symbol.upper().strip()
        logger.info(f"Fetching company details for {symbol}...")
        
        try:
            details = self.nepse.getCompanyDetails(symbol)
            return details if details else {}
        except Exception as e:
            logger.error(f"Failed to fetch company details for {symbol}: {e}")
            return {}
    
    def fetch_market_depth(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch market depth (buy/sell orders) for a stock.
        
        This shows pending orders at different price levels - 
        extremely useful for gauging supply/demand!
        
        Returns:
            Dict with bid/ask levels
        """
        symbol = symbol.upper().strip()
        
        try:
            depth = self.nepse.getSymbolMarketDepth(symbol)
            return depth if depth else {}
        except Exception as e:
            logger.debug(f"No market depth for {symbol}: {e}")
            return {}
    
    def fetch_supply_demand(self) -> Dict[str, Any]:
        """Fetch overall market supply/demand data."""
        try:
            return self.nepse.getSupplyDemand()
        except Exception as e:
            logger.error(f"Failed to fetch supply/demand: {e}")
            return {}
    
    def fetch_sector_indices(self) -> pd.DataFrame:
        """
        Fetch all sector sub-indices (Banking, Hydropower, etc.)
        
        Returns:
            DataFrame with sector index values and changes
        """
        try:
            indices = self.nepse.getNepseSubIndices()
            
            if not indices:
                return pd.DataFrame()
            
            records = []
            for idx in indices:
                records.append({
                    "index": idx.get("index", ""),
                    "current_value": parse_nepse_number(idx.get("currentValue")),
                    "change": parse_nepse_number(idx.get("change")),
                    "change_pct": parse_nepse_number(idx.get("perChange")),
                    "high": parse_nepse_number(idx.get("highValue")),
                    "low": parse_nepse_number(idx.get("lowValue")),
                })
            
            return pd.DataFrame(records)
            
        except Exception as e:
            logger.error(f"Failed to fetch sector indices: {e}")
            return pd.DataFrame()
    
    def fetch_daily_index_graph(self) -> List[Dict]:
        """Fetch NEPSE index intraday price graph data."""
        try:
            return self.nepse.getDailyNepseIndexGraph() or []
        except Exception as e:
            logger.error(f"Failed to fetch index graph: {e}")
            return []
    
    def fetch_scrip_price_graph(self, symbol: str) -> List[Dict]:
        """
        Fetch intraday price graph for a specific stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of intraday price points
        """
        try:
            return self.nepse.getDailyScripPriceGraph(symbol.upper()) or []
        except Exception as e:
            logger.debug(f"No price graph for {symbol}: {e}")
            return []
    
    def _convert_top_list(self, data: List, limit: int) -> pd.DataFrame:
        """Convert top lists to DataFrame."""
        if not data:
            return pd.DataFrame()
        
        records = []
        for item in data[:limit]:
            records.append({
                "symbol": item.get("symbol", ""),
                "ltp": parse_nepse_number(item.get("lastTradedPrice", item.get("ltp"))),
                "change": parse_nepse_number(item.get("pointChange")),
                "change_pct": parse_nepse_number(item.get("percentageChange")),
                "volume": parse_nepse_number(item.get("totalTradedQuantity")),
                "turnover": parse_nepse_number(item.get("turnover")),
            })
        
        return pd.DataFrame(records)
    
    def is_market_open(self) -> bool:
        """Check if NEPSE market is currently open."""
        try:
            return self.nepse.isNepseOpen()
        except:
            return False


def save_prices_to_db(df: pd.DataFrame) -> int:
    """
    Save price data to database.
    
    Args:
        df: DataFrame with price data
        
    Returns:
        Number of records saved
    """
    if df.empty:
        return 0
    
    db = SessionLocal()
    saved_count = 0
    
    try:
        for _, row in df.iterrows():
            symbol = row.get("symbol", "")
            if not symbol:
                continue
            
            # Get or create stock
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                stock = Stock(symbol=symbol)
                db.add(stock)
                db.flush()
            
            trade_date = row.get("date", date.today())
            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
            
            # Check if price already exists
            existing = db.query(DailyPrice).filter(
                DailyPrice.stock_id == stock.id,
                DailyPrice.date == trade_date
            ).first()
            
            price_data = {
                "open": row.get("open", 0) or 0,
                "high": row.get("high", 0) or 0,
                "low": row.get("low", 0) or 0,
                "close": row.get("close", 0) or 0,
                "volume": row.get("volume", 0) or 0,
                "turnover": row.get("turnover"),
                "trades": row.get("trades"),
            }
            
            if existing:
                for key, value in price_data.items():
                    setattr(existing, key, value)
            else:
                price = DailyPrice(
                    stock_id=stock.id,
                    date=trade_date,
                    **price_data
                )
                db.add(price)
                saved_count += 1
        
        db.commit()
        logger.info(f"Saved {saved_count} new price records to database")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving prices: {e}")
        raise
        
    finally:
        db.close()
    
    return saved_count


def fetch_all_stocks() -> List[StockData]:
    """Convenience function to fetch all stocks."""
    fetcher = NepseFetcher()
    return fetcher.fetch_company_list()


def fetch_stock_history(symbol: str, days: int = None) -> pd.DataFrame:
    """Convenience function to fetch stock history."""
    fetcher = NepseFetcher()
    return fetcher.fetch_price_history(symbol, days)


def fetch_and_save_today() -> int:
    """
    Fetch today's prices and save to database.
    
    Returns:
        Number of records saved
    """
    fetcher = NepseFetcher()
    df = fetcher.fetch_live_market()
    return save_prices_to_db(df)


def load_historical_csv(filepath: str) -> pd.DataFrame:
    """
    Load historical data from a CSV file.
    Use this as a fallback when API is down.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        Cleaned DataFrame
    """
    logger.info(f"Loading historical data from {filepath}")
    
    df = pd.read_csv(filepath)
    df = clean_price_data(df)
    
    logger.info(f"Loaded {len(df)} records from CSV")
    return df
