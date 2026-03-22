"""
ShareHub Nepal API Integration.

ShareHub provides comprehensive NEPSE data including:
- Fundamental data (PE, EPS, PBV, ROE, ROA, Book Value)
- Dividend history
- Right share history
- Price change summary
- Technical ratings (RSI, MACD, ADX signals)
- Broker analysis (requires auth)
- Floor sheet analysis
- Bulk transactions

API AVAILABILITY:
================
FREE (No Auth Required):
✅ Fundamental Values - PE, EPS, ROE, ROA, Book Value, NPL, etc.
✅ Dividend History - Cash, Bonus, Total dividends
✅ Right Share History - Past right share issues
✅ Price Change Summary - 3D, 7D, 30D, 90D, 180D, 52W returns
✅ Technical Ratings - RSI, MACD, ADX, CCI signals
✅ Price History - Historical OHLCV data
✅ Announcements - Company announcements
✅ Stock News - Recent news articles

REQUIRES AUTH (Bearer Token):
🔒 Broker Analysis - Top buyers/sellers
🔒 Broker Accumulation - Holdings by broker
🔒 Bulk Transactions detail

MILLIONAIRE INSIGHT:
ShareHub is the ONLY free source for fundamental data in Nepal!
NEPSE API doesn't provide PE/EPS/ROE - ShareHub does.
"""

import json
from json import JSONDecodeError
import os
import requests
import time
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from loguru import logger

# Load .env from current or parent directories
def _load_env():
    """Load .env file from current directory or parent directories."""
    try:
        from dotenv import load_dotenv
        current = Path.cwd()
        for _ in range(4):  # Check up to 3 parent levels
            env_path = current / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"Loaded .env from {env_path}")
                return
            parent = current.parent
            if parent == current:
                break
            current = parent
        # Fallback - try default
        load_dotenv()
    except ImportError:
        pass  # dotenv not installed, rely on system env vars

_load_env()

from data.data_cleaner import parse_nepse_number


@dataclass
class ShareHubFundamentals:
    """Fundamental data from ShareHub."""
    symbol: str
    fiscal_year: str = ""
    quarter: str = ""

    # Valuation
    eps: float = 0.0                    # Earnings Per Share
    eps_annualized: float = 0.0         # Annualized EPS
    book_value: float = 0.0             # Net Worth / Book Value per share
    pe_ratio: float = 0.0               # Price to Earnings (calculated)
    pbv: float = 0.0                    # Price to Book Value (calculated)

    # Profitability
    roe: float = 0.0                    # Return on Equity %
    roa: float = 0.0                    # Return on Assets %
    net_profit: float = 0.0             # Net Profit
    operating_profit: float = 0.0

    # Banking specific
    npl: float = 0.0                    # Non-Performing Loan %
    cd_ratio: float = 0.0               # Credit to Deposit ratio
    base_rate: float = 0.0
    interest_spread: float = 0.0
    cost_of_fund: float = 0.0
    capital_adequacy: float = 0.0       # Capital Fund to RWA

    # Capital
    paid_up_capital: float = 0.0
    reserve: float = 0.0
    retained_earnings: float = 0.0
    total_equity: float = 0.0
    total_assets: float = 0.0

    # Dividend
    dps: float = 0.0                    # Dividend Per Share

    # Loans (for banks)
    loan: float = 0.0
    deposit: float = 0.0

    def calculate_pe(self, ltp: float) -> float:
        """Calculate PE ratio given current price using annualized EPS."""
        # Use annualized EPS for accurate PE (quarterly EPS would give inflated PE)
        eps_to_use = self.eps_annualized if self.eps_annualized != 0 else self.eps
        if eps_to_use != 0:  # Allow negative EPS to show negative PE
            self.pe_ratio = round(ltp / eps_to_use, 2)
        return self.pe_ratio

    def calculate_pbv(self, ltp: float) -> float:
        """Calculate PBV given current price."""
        if self.book_value > 0:
            self.pbv = round(ltp / self.book_value, 2)
        return self.pbv


@dataclass
class PromoterUnlock:
    """
    🔴 CRITICAL: Share lock-in data (Promoter & Mutual Fund).

    WHY THIS MATTERS:
    =================
    When locked shares unlock, holders can SELL:
    - More supply → Price drops
    - Smart money exits BEFORE unlock date

    TYPES:
    ======
    1. MutualFund (type=1): Mutual funds holding IPO shares
       - They are PROFIT-DRIVEN - will sell to book profits!
       - Usually sell within weeks of unlock

    2. Promoter (type=2): Company promoters/founders
       - May hold for strategic reasons
       - But often sell portion for liquidity

    TRADING RULE:
    - remainingDays < 30 → ⚠️ CAUTION
    - remainingDays < 7  → 🔴 AVOID
    - Just unlocked     → 🚨 HIGH RISK
    - Mutual Fund unlock → Extra caution (they WILL sell!)
    """
    symbol: str
    name: str
    type: str  # MutualFund, Promoter, etc.
    total_listed_shares: int
    total_shares: int
    locked_shares: int
    allotment_date: Optional[date] = None
    lock_in_end_date: Optional[date] = None
    remaining_days: int = 0

    @property
    def is_mutual_fund(self) -> bool:
        """Check if this is a mutual fund unlock."""
        return "mutual" in self.type.lower() if self.type else False

    @property
    def unlock_risk_level(self) -> str:
        """Get risk level based on remaining days and type."""
        # Mutual funds are MORE likely to sell, so higher risk
        mf_multiplier = " (MF - HIGH SELL RISK)" if self.is_mutual_fund else ""

        if self.remaining_days <= 0:
            return f"🚨 JUST UNLOCKED - HIGH RISK{mf_multiplier}"
        elif self.remaining_days <= 7:
            return f"🔴 UNLOCKING SOON - AVOID{mf_multiplier}"
        elif self.remaining_days <= 30:
            return f"🟠 UNLOCK APPROACHING - CAUTION{mf_multiplier}"
        elif self.remaining_days <= 90:
            return f"🟡 MONITOR{mf_multiplier}"
        else:
            return "🟢 SAFE"

    @property
    def locked_percentage(self) -> float:
        """Get percentage of shares still locked."""
        if self.total_listed_shares > 0:
            return (self.locked_shares / self.total_listed_shares) * 100
        return 0.0

    @property
    def risk_score(self) -> int:
        """
        Calculate numeric risk score (0-100).
        Higher = more risky.
        """
        score = 0

        # Time-based risk
        if self.remaining_days <= 0:
            score += 50  # Already unlocked
        elif self.remaining_days <= 7:
            score += 40
        elif self.remaining_days <= 14:
            score += 30
        elif self.remaining_days <= 30:
            score += 20
        elif self.remaining_days <= 60:
            score += 10

        # Mutual Fund = higher sell probability
        if self.is_mutual_fund:
            score += 15

        # High locked percentage = bigger impact
        if self.locked_percentage > 5:
            score += 20
        elif self.locked_percentage > 2:
            score += 10
        elif self.locked_percentage > 1:
            score += 5

        return min(100, score)


@dataclass
class DividendRecord:
    """Single dividend record."""
    symbol: str
    fiscal_year: str
    bonus_pct: float = 0.0
    cash_pct: float = 0.0
    total_pct: float = 0.0
    announcement_date: Optional[date] = None
    book_closure_date: Optional[date] = None
    status: str = ""


@dataclass
class TechnicalRating:
    """Technical indicator rating."""
    name: str
    value: float
    action: str  # BUY, SELL, NEUTRAL


@dataclass
class TechnicalAnalysis:
    """Complete technical analysis from ShareHub."""
    symbol: str
    date: date

    # Oscillator ratings
    oscillators: List[TechnicalRating] = field(default_factory=list)
    oscillator_summary: str = ""  # BUY, SELL, NEUTRAL

    # Moving average ratings
    moving_averages: List[TechnicalRating] = field(default_factory=list)
    ma_summary: str = ""

    # Overall
    overall_rating: str = ""


@dataclass
class PriceChangeSummary:
    """Price change over different periods."""
    symbol: str
    change_3d: float = 0.0
    change_3d_pct: float = 0.0
    change_7d: float = 0.0
    change_7d_pct: float = 0.0
    change_30d: float = 0.0
    change_30d_pct: float = 0.0
    change_90d: float = 0.0
    change_90d_pct: float = 0.0
    change_180d: float = 0.0
    change_180d_pct: float = 0.0
    change_52w: float = 0.0
    change_52w_pct: float = 0.0


@dataclass
class BrokerData:
    """Broker transaction data (requires auth)."""
    broker_code: str
    broker_name: str
    buy_quantity: int = 0
    sell_quantity: int = 0
    buy_amount: float = 0.0
    sell_amount: float = 0.0
    net_quantity: int = 0
    net_amount: float = 0.0


@dataclass
class BrokerAnalysisResponse:
    """
    Complete broker analysis response with metadata.
    
    Contains:
    - date_range: e.g., "2026-02-22 to 2026-03-22 (16 days)"
    - total_amount: Total traded amount in the period
    - total_quantity: Total traded quantity in the period
    - total_transactions: Number of transactions
    - brokers: List of BrokerData for each broker
    """
    date_range: str
    total_amount: float
    total_quantity: int
    total_transactions: int
    brokers: List[BrokerData] = field(default_factory=list)


class ShareHubAPI:
    """
    ShareHub Nepal API Client.

    Usage:
        api = ShareHubAPI()

        # Get fundamentals (FREE)
        fundamentals = api.get_fundamentals("NABIL")
        print(f"EPS: {fundamentals.eps}, ROE: {fundamentals.roe}%")

        # Get dividend history (FREE)
        dividends = api.get_dividend_history("NABIL")

        # Get technical ratings (FREE)
        technicals = api.get_technical_ratings("NABIL")

        # For broker analysis (REQUIRES AUTH):
        api.set_auth_token("your-bearer-token")
        brokers = api.get_broker_analysis("NABIL")
    """

    BASE_URL = "https://sharehubnepal.com"
    NEWS_URL = "https://arthakendra.com"

    # Fallback cookies captured from authenticated browser session.
    DEFAULT_AUTH_COOKIES = {
        "route": "b72262511a87f31a78023c410c1effb1",
        "SRVGROUP": "common",
        "_clck": "1cbrido%5E2%5Eg4j%5E0%5E2271",
        "_ga": "GA1.1.1869738471.1774087286",
        "_gcl_au": "1.1.1837741703.1774087286",
        "_ga_13E8FKZMQ2": "GS2.1.s1774087285$o1$g1$t1774092186$j60$l0$h0",
        "_clsk": "1upn43%5E1774092187941%5E74%5E1%5El.clarity.ms%2Fcollect",
    }

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
    ]

    def __init__(self, auth_token: str = None, auth_cookies: Dict[str, str] = None):
        """
        Initialize ShareHub API client.

        Args:
            auth_token: Optional Bearer token for authenticated endpoints.
            auth_cookies: Optional cookie map for authenticated endpoints.
        """
        env_token = os.getenv("SHAREHUB_AUTH_TOKEN")
        self.auth_token = auth_token or env_token
        self.auth_cookies = auth_cookies or self._load_auth_cookies_from_env(
        ) or self.DEFAULT_AUTH_COOKIES.copy()
        self.session = requests.Session()

        # Stealth Mode tracking
        self._request_count = 0
        self._current_ua = random.choice(self.USER_AGENTS)
        self._last_request_time = 0

        # Token expiry tracking
        self._token_expiry: Optional[datetime] = None
        self._firebase_api_key = os.getenv(
            "FIREBASE_API_KEY", "AIzaSyCIxrLiH2x_p8IoS7wJhpWS1_thnvKLIUI")

        # Default headers
        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "user-agent": self._current_ua,
        })

        # Default cookies
        self.session.cookies.update({
            "route": "b72262511a87f31a78023c410c1effb1",
            "SRVGROUP": "common",
        })

        if self.auth_token:
            self.set_auth_token(self.auth_token)
            self._parse_token_expiry()

    def _parse_token_expiry(self):
        """Parse JWT token to get expiry time."""
        if not self.auth_token:
            return
        try:
            import base64
            # JWT format: header.payload.signature
            parts = self.auth_token.split(".")
            if len(parts) >= 2:
                # Add padding if needed
                payload = parts[1]
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += "=" * padding
                decoded = base64.urlsafe_b64decode(payload)
                data = json.loads(decoded)
                exp = data.get("exp")
                if exp:
                    self._token_expiry = datetime.fromtimestamp(exp)
                    logger.debug(f"Token expires at: {self._token_expiry}")
        except Exception as e:
            logger.debug(f"Could not parse token expiry: {e}")

    def is_token_valid(self) -> bool:
        """Check if current token is still valid."""
        if not self.auth_token:
            return False
        if not self._token_expiry:
            return True  # Can't verify, assume valid
        # Add 1 minute buffer
        return datetime.now() < (self._token_expiry - timedelta(minutes=1))

    def refresh_token_with_firebase(
        self,
        email: str = None,
        password: str = None,
    ) -> Optional[str]:
        """
        🔑 REFRESH AUTH TOKEN using Firebase.

        ShareHub uses Firebase Authentication. To get a fresh token:
        1. Authenticate with Firebase using email/password
        2. Get ID token from Firebase
        3. Exchange for ShareHub token

        Set environment variables:
        - SHAREHUB_EMAIL: Your ShareHub login email
        - SHAREHUB_PASSWORD: Your ShareHub password
        - FIREBASE_API_KEY: Firebase API key (default provided)

        Returns:
            New auth token or None if failed
        """
        email = email or os.getenv("SHAREHUB_EMAIL")
        password = password or os.getenv("SHAREHUB_PASSWORD")

        if not email or not password:
            logger.error("Email and password required for token refresh!")
            logger.info(
                "Set SHAREHUB_EMAIL and SHAREHUB_PASSWORD environment variables")
            return None

        try:
            # Step 1: Authenticate with Firebase
            firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self._firebase_api_key}"

            firebase_resp = requests.post(
                firebase_url,
                json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True,
                },
                timeout=15,
            )
            firebase_resp.raise_for_status()
            firebase_data = firebase_resp.json()

            id_token = firebase_data.get("idToken")
            if not id_token:
                logger.error("No idToken in Firebase response")
                return None

            logger.info("✅ Firebase authentication successful")

            # Step 2: Exchange Firebase token for ShareHub token
            sharehub_auth_url = f"{self.BASE_URL}/users/api/v1/authenticate/firebase"

            sharehub_resp = requests.post(
                sharehub_auth_url,
                json={"accessToken": id_token},
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                timeout=15,
            )
            sharehub_resp.raise_for_status()
            sharehub_data = sharehub_resp.json()

            if sharehub_data.get("success"):
                new_token = sharehub_data.get("data", {}).get("accessToken")
                if new_token:
                    self.set_auth_token(new_token)
                    self._parse_token_expiry()
                    logger.info("✅ ShareHub token refreshed successfully!")
                    logger.info(f"   Token expires at: {self._token_expiry}")
                    return new_token

            logger.error(
                f"ShareHub auth failed: {sharehub_data.get('message')}")
            return None

        except requests.RequestException as e:
            logger.error(f"Token refresh failed: {e}")
            return None

    def login(self) -> bool:
        """
        🔐 Login to ShareHub using Email/Password to get a fresh token.
        Uses the endpoint provided by the user: /account/api/v1/auth/login/email
        """
        email = os.getenv("SHAREHUB_EMAIL")
        password = os.getenv("SHAREHUB_PASSWORD")
        
        if not email or not password:
            logger.warning("⚠️ SHAREHUB_EMAIL or SHAREHUB_PASSWORD not set. Cannot auto-login.")
            return False
            
        logger.info(f"🔐 Logging into ShareHub as {email}...")
        
        url = "https://sharehubnepal.com/account/api/v1/auth/login/email"
        
        payload = {
            "email": email,
            "password": password
        }
        
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://sharehubnepal.com",
            "referer": "https://sharehubnepal.com/",
            "user-agent": self._current_ua,
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        
        try:
            # First request to get the token
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                token = None
                
                # Check nested data structure first (most likely based on error logs)
                if isinstance(data.get("data"), dict):
                    token = data.get("data", {}).get("token") or data.get("data", {}).get("accessToken")
                
                # Fallback to top level
                if not token:
                    token = data.get("token") or data.get("accessToken")
                
                if token:
                    self.set_auth_token(token)
                    self._parse_token_expiry()
                    
                    # Also update session headers with the new token and fetch metadata
                    self.session.headers.update(headers)
                    self.session.headers["authorization"] = f"Bearer {token}"
                    
                    logger.info("✅ ShareHub Login Successful! Token refreshed.")
                    return True
                else:
                    logger.error(f"❌ Login failed: No token in response. Keys: {list(data.keys())}")
                    if "data" in data and isinstance(data["data"], dict):
                        logger.error(f"   Data keys: {list(data['data'].keys())}")
                    elif "data" in data:
                        logger.error(f"   Data content: {str(data['data'])[:200]}")
            else:
                logger.error(f"❌ Login failed with status {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Login exception: {e}")
            
        return False

    def ensure_valid_token(self) -> bool:
        """
        Ensure we have a valid token, refreshing if needed.

        Returns:
            True if token is valid/refreshed, False otherwise
        """
        if self.is_token_valid():
            return True

        logger.warning("🔄 Token expired or invalid. Attempting auto-login...")
        return self.login()

    @staticmethod
    def _parse_cookie_header(cookie_header: str) -> Dict[str, str]:
        """Parse a browser-style cookie header string into a dict."""
        cookies = {}
        for chunk in cookie_header.split(";"):
            part = chunk.strip()
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key:
                cookies[key] = value.strip()
        return cookies

    def _load_auth_cookies_from_env(self) -> Optional[Dict[str, str]]:
        """Load auth cookies from env, supporting JSON dict or cookie-header format."""
        raw_json = os.getenv("SHAREHUB_AUTH_COOKIES_JSON", "").strip()
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
                logger.warning(
                    "SHAREHUB_AUTH_COOKIES_JSON must be a JSON object.")
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in SHAREHUB_AUTH_COOKIES_JSON.")

        raw_header = os.getenv("SHAREHUB_AUTH_COOKIES", "").strip()
        if raw_header:
            parsed = self._parse_cookie_header(raw_header)
            if parsed:
                return parsed
            logger.warning("Could not parse SHAREHUB_AUTH_COOKIES.")

        return None

    def set_auth_token(self, token: str):
        """Set authentication token for protected endpoints."""
        self.auth_token = token
        self.session.headers["authorization"] = f"Bearer {token}"

    def set_auth_cookies(self, cookies: Dict[str, str]):
        """Set authentication cookies for protected endpoints."""
        self.auth_cookies = cookies or {}

    def _rotate_identity(self):
        """Rotate User-Agent and clear session to avoid detection."""
        self._current_ua = random.choice(self.USER_AGENTS)
        self.session.headers.update({"user-agent": self._current_ua})
        self.session.cookies.clear()
        # Re-add essential cookies if needed
        self.session.cookies.update({
            "route": "b72262511a87f31a78023c410c1effb1",
            "SRVGROUP": "common",
        })
        logger.debug(f"🕵️ STEALTH MODE: Rotated Identity (UA: {self._current_ua[:30]}...)")

    def _get(
        self,
        url: str,
        params: Dict = None,
        referer: str = None,
        use_auth_context: bool = False,
    ) -> Dict:
        """Make GET request with Stealth Mode."""
        
        # 1. Anti-Bot Sleep (Random 0.5s - 1.5s delay)
        # Only sleep if we've made requests recently to avoid startup lag
        if self._request_count > 0:
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)
            
        # 2. Identity Rotation (Every 15 requests)
        self._request_count += 1
        if self._request_count % 15 == 0:
            self._rotate_identity()

        headers = {}
        if referer:
            headers["referer"] = referer

        # Inject current random UA into headers
        headers["user-agent"] = self._current_ua

        if use_auth_context:
            headers.update({
                "accept-language": "en-US,en;q=0.9,en-GB;q=0.8",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            })

        request_cookies = self.auth_cookies if use_auth_context else None

        try:
            resp = self.session.get(
                url,
                params=params,
                headers=headers,
                cookies=request_cookies,
                timeout=15,
            )
            
            # 🔄 AUTO-LOGIN HANDLER
            if resp.status_code == 401 and use_auth_context:
                logger.warning(f"⚠️ Auth token expired (401). Attempting re-login for {url}")
                if self.login():
                    # Retry with new token
                    headers["authorization"] = f"Bearer {self.auth_token}"
                    resp = self.session.get(
                        url,
                        params=params,
                        headers=headers,
                        cookies=self.auth_cookies,
                        timeout=15,
                    )
            
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"ShareHub API error: {e}")
            return {}

    # ==================== FREE ENDPOINTS ====================

    def _to_decimal_number(self, value: Any, default: Decimal = Decimal("0")) -> Decimal:
        """Parse API numeric values to Decimal safely for financial math."""
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            # str() avoids binary float artifacts in Decimal constructor.
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return default
        if isinstance(value, str):
            parsed = parse_nepse_number(value)
            if parsed is None:
                return default
            try:
                return Decimal(str(parsed))
            except InvalidOperation:
                return default
        return default

    def _calculate_annualized_eps(self, quarter: str, net_profit: Any, paidup_capital: Any) -> float:
        """
        Manually calculate Annualized EPS from raw financial data.
        
        This is more reliable than using the pre-calculated eps/eps_a from NEPSE APIs
        which are sometimes incorrect.
        
        Args:
            quarter: The quarter string (e.g., "q1", "q2", "q3", "q4")
            net_profit: Net profit for the period (in Rs.)
            paidup_capital: Paid-up capital (in Rs.)
            
        Returns:
            Annualized EPS rounded to 2 decimal places
            
        Logic:
            1. shares = paidup_capital / 100 (Nepal par value is always Rs. 100)
            2. base_eps = net_profit / shares
            3. Annualize based on quarter:
               - q1: base_eps * 4 (1 quarter -> 4 quarters)
               - q2: base_eps * 2 (2 quarters -> 4 quarters)
               - q3: base_eps * (4/3) (3 quarters -> 4 quarters)
               - q4: base_eps * 1 (already full year)
        """
        net_profit_d = self._to_decimal_number(net_profit)
        paidup_capital_d = self._to_decimal_number(paidup_capital)

        # Guard against invalid inputs
        if paidup_capital_d <= 0:
            return 0.0
        if net_profit_d == 0:
            return 0.0
            
        # Calculate number of shares (par value = Rs. 100 in Nepal)
        shares = paidup_capital_d / Decimal("100")
        
        if shares <= 0:
            return 0.0
            
        # Calculate base EPS for the period
        base_eps = net_profit_d / shares
        
        # Annualization multipliers based on quarter
        quarter_multipliers = {
            "q1": Decimal("4"),      # 1 quarter -> 4 quarters
            "q2": Decimal("2"),      # 2 quarters -> 4 quarters
            "q3": Decimal("1.3333333333333333333333333333"),  # 4/3
            "q4": Decimal("1"),      # Already full year
        }
        
        # Normalize quarter string (handle "Q1", "Q2", etc.)
        quarter_normalized = str(quarter).lower().strip()
        
        # Get multiplier (default to 1.0 if quarter not recognized)
        multiplier = quarter_multipliers.get(quarter_normalized, Decimal("1"))
        
        # Calculate annualized EPS
        annualized_eps = base_eps * multiplier
        
        return float(annualized_eps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def get_fundamentals(self, symbol: str) -> ShareHubFundamentals:
        """
        Get fundamental data for a stock.

        This is the GOLD endpoint - gives PE, EPS, ROE, Book Value!

        Args:
            symbol: Stock symbol

        Returns:
            ShareHubFundamentals with all metrics
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/fundamental/values/{symbol}"
        referer = f"{self.BASE_URL}/company/{symbol}/fundamental-analysis"

        result = ShareHubFundamentals(symbol=symbol)

        data = self._get(url, referer=referer)

        if not data.get("success") or not data.get("data"):
            logger.warning(f"No fundamental data for {symbol}")
            return result

        # Get first (most recent) record
        records = data["data"]
        if isinstance(records, list) and len(records) > 0:
            record = records[0]
        else:
            return result

        result.fiscal_year = record.get("fiscalYear", "")
        result.quarter = record.get("quarter", "")

        # Parse values array
        values = record.get("values", [])
        values_dict = {v["key"]: v["value"]
                       for v in values if v.get("value") is not None}

        # Map to our fields
        result.eps = float(self._to_decimal_number(values_dict.get("eps", 0)))
        result.eps_annualized = float(self._to_decimal_number(values_dict.get("eps_a", 0)))
        result.book_value = float(self._to_decimal_number(values_dict.get("net_worth", 0)))
        result.roe = float(self._to_decimal_number(values_dict.get("roe", 0)))
        result.roa = float(self._to_decimal_number(values_dict.get("roa", 0)))
        result.net_profit = float(self._to_decimal_number(values_dict.get("net_profit", 0)))
        result.operating_profit = float(self._to_decimal_number(values_dict.get("operating_profit", 0)))
        result.dps = float(self._to_decimal_number(values_dict.get("dps", 0)))

        # Banking specific
        result.npl = float(self._to_decimal_number(values_dict.get("npl", 0)))
        result.cd_ratio = float(self._to_decimal_number(values_dict.get("cd_ratio", 0)))
        result.base_rate = float(self._to_decimal_number(values_dict.get("base_rate", 0)))
        result.interest_spread = float(self._to_decimal_number(values_dict.get("interest_spread", 0)))
        result.cost_of_fund = float(self._to_decimal_number(values_dict.get("cost_of_fund", 0)))
        result.capital_adequacy = float(self._to_decimal_number(values_dict.get(
            "capital_fund_to_rwa", 0)))

        # Capital
        result.paid_up_capital = float(self._to_decimal_number(values_dict.get("paidup_capital", 0)))
        result.reserve = float(self._to_decimal_number(values_dict.get("reserve", 0)))
        result.retained_earnings = float(self._to_decimal_number(values_dict.get("retained_earning", 0)))
        result.total_equity = float(self._to_decimal_number(values_dict.get("total_equity", 0)))
        result.total_assets = float(self._to_decimal_number(values_dict.get("total_assets", 0)))

        # Loans
        result.loan = float(self._to_decimal_number(values_dict.get("loan", 0)))
        result.deposit = float(self._to_decimal_number(values_dict.get("deposit", 0)))
        
        # ===== MANUAL EPS CALCULATION (More reliable than API values) =====
        # NEPSE APIs sometimes have incorrect eps/eps_a values
        # Calculate annualized EPS from raw financials for accuracy
        calculated_annualized_eps = self._calculate_annualized_eps(
            quarter=result.quarter,
            net_profit=result.net_profit,
            paidup_capital=result.paid_up_capital
        )
        
        # Use calculated EPS if it's valid, otherwise fall back to API value
        if calculated_annualized_eps > 0:
            result.eps_annualized = calculated_annualized_eps
            # Also update base EPS to be consistent (for quarterly reporting)
            if result.quarter.lower() == "q1":
                result.eps = round(calculated_annualized_eps / 4, 2)
            elif result.quarter.lower() == "q2":
                result.eps = round(calculated_annualized_eps / 2, 2)
            elif result.quarter.lower() == "q3":
                result.eps = round(calculated_annualized_eps * 3 / 4, 2)
            else:  # q4 or full year
                result.eps = calculated_annualized_eps
                
            logger.debug(f"{symbol}: Calculated Annualized EPS = {calculated_annualized_eps} (Q: {result.quarter})")

        logger.info(
            f"Fetched fundamentals for {symbol}: EPS={result.eps}, Annualized={result.eps_annualized}, ROE={result.roe}%")

        return result

    def get_dividend_history(self, symbol: str, limit: int = 10) -> List[DividendRecord]:
        """
        Get dividend history for a stock.

        Args:
            symbol: Stock symbol
            limit: Number of records to fetch

        Returns:
            List of DividendRecord objects
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/dividend"
        params = {"symbol": symbol, "limit": str(limit)}
        referer = f"{self.BASE_URL}/company/{symbol}/dividend-history"

        data = self._get(url, params=params, referer=referer)

        if not data.get("success"):
            return []

        records = []
        content = data.get("data", {}).get("content", [])

        for item in content:
            record = DividendRecord(
                symbol=symbol,
                fiscal_year=item.get("fiscalYear", ""),
                bonus_pct=item.get("bonus", 0) or 0,
                cash_pct=item.get("cash", 0) or 0,
                total_pct=item.get("total", 0) or 0,
                status=item.get("status", ""),
            )

            # Parse dates with proper exception handling
            if item.get("announcementDate"):
                try:
                    record.announcement_date = datetime.fromisoformat(
                        item["announcementDate"].replace("Z", "")
                    ).date()
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse announcementDate: {item.get('announcementDate')}: {e}")

            if item.get("bookClosureDate"):
                try:
                    record.book_closure_date = datetime.fromisoformat(
                        item["bookClosureDate"].replace("Z", "")
                    ).date()
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse bookClosureDate: {item.get('bookClosureDate')}: {e}")

            records.append(record)

        logger.info(f"Fetched {len(records)} dividend records for {symbol}")
        return records

    def get_price_change_summary(self, symbol: str) -> PriceChangeSummary:
        """
        Get price change summary over different periods.

        Returns 3D, 7D, 30D, 90D, 180D, 52W returns.
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/price-history/change-summary/{symbol}"
        referer = f"{self.BASE_URL}/company/{symbol}"

        result = PriceChangeSummary(symbol=symbol)
        data = self._get(url, referer=referer)

        if not data.get("success"):
            return result

        for item in data.get("data", []):
            name = item.get("name", "")
            change = item.get("change", 0) or 0
            change_pct = item.get("changePercent", 0) or 0

            if "3 Days" in name:
                result.change_3d = change
                result.change_3d_pct = change_pct
            elif "7 Days" in name:
                result.change_7d = change
                result.change_7d_pct = change_pct
            elif "30 Days" in name:
                result.change_30d = change
                result.change_30d_pct = change_pct
            elif "90 Days" in name:
                result.change_90d = change
                result.change_90d_pct = change_pct
            elif "180 Days" in name:
                result.change_180d = change
                result.change_180d_pct = change_pct
            elif "52 Weeks" in name:
                result.change_52w = change
                result.change_52w_pct = change_pct

        return result

    def get_technical_ratings(self, symbol: str) -> TechnicalAnalysis:
        """
        Get technical indicator ratings.

        Returns RSI, MACD, ADX, CCI signals with BUY/SELL/NEUTRAL ratings.
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/ps/technical-ratings"
        params = {"symbol": symbol}
        referer = f"{self.BASE_URL}/company/{symbol}/technical-analysis"

        result = TechnicalAnalysis(symbol=symbol, date=date.today())
        data = self._get(
            url,
            params=params,
            referer=referer,
            use_auth_context=bool(self.auth_token),
        )

        if not data.get("success"):
            return result

        content = data.get("data", {}).get("content", {})

        # Parse oscillators (RSI, MACD, ADX, CCI)
        osc_data = content.get("oscillatorRating", {})
        for rating in osc_data.get("ratings", []):
            result.oscillators.append(TechnicalRating(
                name=rating.get("name", ""),
                value=rating.get("value", 0) or 0,
                action=rating.get("action", "NEUTRAL"),
            ))
        result.oscillator_summary = osc_data.get("summary", "NEUTRAL")

        # Parse moving averages
        ma_data = content.get("movingAverageRating", {})
        for rating in ma_data.get("ratings", []):
            result.moving_averages.append(TechnicalRating(
                name=rating.get("name", ""),
                value=rating.get("value", 0) or 0,
                action=rating.get("action", "NEUTRAL"),
            ))
        result.ma_summary = ma_data.get("summary", "NEUTRAL")

        # Overall summary
        summary = content.get("summaryRating", {})
        result.overall_rating = summary.get("summary", "NEUTRAL")

        return result

    def get_right_share_history(self, symbol: str) -> List[Dict]:
        """Get right share history."""
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/public-offering"
        params = {"For": "2", "Type": "2", "pageSize": "10", "symbol": symbol}
        referer = f"{self.BASE_URL}/company/{symbol}/right-share-history"

        data = self._get(url, params=params, referer=referer)

        if not data.get("success"):
            return []

        return data.get("data", {}).get("content", [])

    def get_announcements(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get company announcements."""
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/announcement"
        params = {"symbol": symbol, "Size": str(limit), "Page": "1"}
        referer = f"{self.BASE_URL}/company/{symbol}/announcements"

        data = self._get(
            url,
            params=params,
            referer=referer,
        )

        if not data.get("success"):
            return []

        return data.get("data", {}).get("content", [])

    def get_price_history(
        self,
        symbol: str,
        from_date: date = None,
        to_date: date = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get price history.

        Args:
            symbol: Stock symbol
            from_date: Start date
            to_date: End date
            limit: Max records
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/price-history"

        params = {"symbol": symbol, "pageSize": str(limit)}

        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        referer = f"{self.BASE_URL}/company/{symbol}/price-history"

        data = self._get(
            url,
            params=params,
            referer=referer,
        )

        if not data.get("success"):
            return []

        return data.get("data", {}).get("content", [])

    def get_stock_news(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get recent news for a stock."""
        symbol = symbol.upper()
        url = f"{self.NEWS_URL}/api/v1/news/sharehub/stock-news"
        params = {"limit": str(limit), "companySymbol": symbol}

        headers = {
            "origin": self.BASE_URL,
            "referer": self.BASE_URL,
        }

        try:
            resp = self.session.get(
                url, params=params, headers=headers, timeout=15)
            return resp.json() if resp.status_code == 200 else []
        except (requests.RequestException, ValueError, JSONDecodeError) as e:
            logger.debug(f"Failed to fetch news for {symbol}: {e}")
            return []

    def get_daily_graph(self, symbol: str) -> Dict:
        """
        Get daily graph data (intraday price movements).

        This endpoint provides:
        - Intraday price ticks
        - Open, High, Low, Close
        - Volume throughout the day
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/live/api/v1/daily-graph/company/{symbol}"
        referer = f"{self.BASE_URL}/company/{symbol}"

        data = self._get(url, referer=referer)

        if not data.get("success"):
            return {}

        return data.get("data", {})

    def get_complete_overview(self, symbol: str) -> Dict:
        """
        Get COMPLETE stock overview combining all data sources.

        This matches what ShareHub shows on their company overview page:
        - General Information (Market Cap, Face Value, 52W High/Low, etc.)
        - Performance Value (1Y Yield, EPS, PE, Book Value, PBV)
        - Change Summary (3D, 7D, 30D, 90D, 180D, 52W returns)
        - Ownership Structure
        - Last Dividend
        - Last Right Share

        Returns a comprehensive dictionary for display/analysis.
        """
        symbol = symbol.upper()
        logger.info(f"Fetching complete overview for {symbol}...")

        overview = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }

        # 1. Get fundamentals (EPS, ROE, Book Value, etc.)
        fundamentals = self.get_fundamentals(symbol)
        overview["fundamentals"] = {
            "eps": fundamentals.eps,
            "eps_annualized": fundamentals.eps_annualized,
            "book_value": fundamentals.book_value,
            "roe": fundamentals.roe,
            "roa": fundamentals.roa,
            "dps": fundamentals.dps,
            "fiscal_year": fundamentals.fiscal_year,
            "quarter": fundamentals.quarter,
        }

        # Banking-specific metrics
        if fundamentals.npl > 0:
            overview["fundamentals"]["banking"] = {
                "npl": fundamentals.npl,
                "cd_ratio": fundamentals.cd_ratio,
                "base_rate": fundamentals.base_rate,
                "capital_adequacy": fundamentals.capital_adequacy,
            }

        # 2. Get price change summary
        price_changes = self.get_price_change_summary(symbol)
        overview["change_summary"] = {
            "3d": {"change": price_changes.change_3d, "pct": price_changes.change_3d_pct},
            "7d": {"change": price_changes.change_7d, "pct": price_changes.change_7d_pct},
            "30d": {"change": price_changes.change_30d, "pct": price_changes.change_30d_pct},
            "90d": {"change": price_changes.change_90d, "pct": price_changes.change_90d_pct},
            "180d": {"change": price_changes.change_180d, "pct": price_changes.change_180d_pct},
            "52w": {"change": price_changes.change_52w, "pct": price_changes.change_52w_pct},
        }
        overview["1_year_yield"] = price_changes.change_52w_pct

        # 3. Get dividend history (for last dividend)
        dividends = self.get_dividend_history(symbol, limit=3)
        if dividends:
            last_div = dividends[0]
            overview["last_dividend"] = {
                "fiscal_year": last_div.fiscal_year,
                "cash_pct": last_div.cash_pct,
                "bonus_pct": last_div.bonus_pct,
                "total_pct": last_div.total_pct,
                "announcement_date": str(last_div.announcement_date) if last_div.announcement_date else None,
                "book_closure_date": str(last_div.book_closure_date) if last_div.book_closure_date else None,
            }
        else:
            overview["last_dividend"] = None

        # 4. Get right share history
        right_shares = self.get_right_share_history(symbol)
        if right_shares:
            last_right = right_shares[0]
            overview["last_right_share"] = {
                "fiscal_year": last_right.get("fiscalYear", ""),
                "ratio": last_right.get("ratio", ""),
                "price_per_share": last_right.get("pricePerShare", 0),
                "opening_date": last_right.get("openingDate", ""),
                "closing_date": last_right.get("closingDate", ""),
            }
        else:
            overview["last_right_share"] = None

        # 5. Get technical ratings
        tech = self.get_technical_ratings(symbol)
        overview["technical"] = {
            "oscillator_summary": tech.oscillator_summary,
            "ma_summary": tech.ma_summary,
            "overall_rating": tech.overall_rating,
            "oscillators": [{"name": o.name, "value": o.value, "action": o.action} for o in tech.oscillators],
            "moving_averages": [{"name": m.name, "value": m.value, "action": m.action} for m in tech.moving_averages],
        }

        # 6. Get announcements
        announcements = self.get_announcements(symbol, limit=5)
        overview["announcements"] = [
            {
                "title": a.get("title", ""),
                "date": a.get("publishedDate", ""),
                "type": a.get("type", ""),
            }
            for a in announcements
        ]

        # 7. Get news
        news = self.get_stock_news(symbol, limit=5)
        overview["news"] = [
            {
                "title": n.get("title", ""),
                "url": n.get("url", ""),
                "date": n.get("publishedAt", ""),
            }
            for n in news
        ]

        logger.info(f"Complete overview for {symbol} ready")
        return overview

    # ==================== AUTHENTICATED ENDPOINTS ====================

    def get_broker_analysis(
        self,
        symbol: str,
        duration: str = "1D"
    ) -> List[BrokerData]:
        """
        Get broker-wise analysis (TOP BUYERS/SELLERS).

        REQUIRES AUTHENTICATION TOKEN!

        Args:
            symbol: Stock symbol
            duration: "1D", "1W", "1M", "3M", "6M", "1Y"

        Returns:
            List of BrokerData showing top buyers/sellers
        """
        # Ensure we have a valid token (auto-login if needed)
        self.ensure_valid_token()
        
        if not self.auth_token:
            logger.warning("Auth token required for broker analysis (Login failed)!")
            return []

        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/floorsheet-analysis/stockwise-broker-analysis/{symbol}"
        params = {"duration": duration}
        referer = f"{self.BASE_URL}/company/{symbol}/broker-analysis"

        data = self._get(
            url,
            params=params,
            referer=referer,
            use_auth_context=True,
        )

        if not data:
            return []

        # Parse broker data - handle nested response structure
        # API returns: {"success": true, "data": {"brokerAnalysisData": [...]}}
        broker_list = []
        if isinstance(data, dict):
            # New API structure with nested data
            broker_list = data.get("brokerAnalysisData", [])
            if not broker_list and "data" in data:
                broker_list = data.get("data", {}).get("brokerAnalysisData", [])
        elif isinstance(data, list):
            broker_list = data
        
        brokers = []
        for item in broker_list:
            # Handle both old and new field names
            broker_code = item.get("brokerCode") or item.get("brokerId", "")
            broker_name = item.get("brokerName") or item.get("name", "")
            
            # Calculate net if not provided
            buy_qty = int(item.get("buyQty") or item.get("buyQuantity", 0) or 0)
            sell_qty = int(item.get("sellQty") or item.get("sellQuantity", 0) or 0)
            buy_amt = float(item.get("buyAmt") or item.get("buyAmount", 0) or 0)
            sell_amt = float(item.get("sellAmt") or item.get("sellAmount", 0) or 0)
            net_qty = int(item.get("netQty") or item.get("netQuantity", buy_qty - sell_qty) or 0)
            net_amt = float(item.get("netAmt") or item.get("netAmount", buy_amt - sell_amt) or 0)
            
            brokers.append(BrokerData(
                broker_code=str(broker_code),
                broker_name=broker_name,
                buy_quantity=buy_qty,
                sell_quantity=sell_qty,
                buy_amount=buy_amt,
                sell_amount=sell_amt,
                net_quantity=net_qty,
                net_amount=net_amt,
            ))

        return brokers

    def get_broker_analysis_full(
        self,
        symbol: str,
        duration: str = "1D"
    ) -> Optional[BrokerAnalysisResponse]:
        """
        Get broker-wise analysis with full metadata (date range, totals).

        REQUIRES AUTHENTICATION TOKEN!

        Args:
            symbol: Stock symbol
            duration: "1D", "1W", "1M", "3M", "6M", "1Y"

        Returns:
            BrokerAnalysisResponse with date_range, totals, and broker list
            
        Example:
            response = api.get_broker_analysis_full("SSHL", duration="1M")
            print(f"Date Range: {response.date_range}")
            print(f"Total Qty: {response.total_quantity:,}")
            for broker in response.brokers[:5]:
                print(f"  {broker.broker_name}: Net {broker.net_quantity:,}")
        """
        self.ensure_valid_token()
        
        if not self.auth_token:
            logger.warning("Auth token required for broker analysis (Login failed)!")
            return None

        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/floorsheet-analysis/stockwise-broker-analysis/{symbol}"
        params = {"duration": duration}
        referer = f"{self.BASE_URL}/company/{symbol}/broker-analysis"

        response_data = self._get(
            url,
            params=params,
            referer=referer,
            use_auth_context=True,
        )

        if not response_data:
            return None

        # Extract metadata from response
        inner_data = response_data.get("data", {}) if isinstance(response_data, dict) else {}
        
        date_range = inner_data.get("date", "Unknown")
        total_amount = float(inner_data.get("totalAmount", 0) or 0)
        total_quantity = int(inner_data.get("totalQuantity", 0) or 0)
        total_transactions = int(inner_data.get("totalTransactions", 0) or 0)
        
        # Parse broker list
        broker_list = inner_data.get("brokerAnalysisData", [])
        if not broker_list and "brokerAnalysisData" in response_data:
            broker_list = response_data.get("brokerAnalysisData", [])
        
        brokers = []
        for item in broker_list:
            broker_code = item.get("brokerCode") or item.get("brokerId", "")
            broker_name = item.get("brokerName") or item.get("name", "")
            
            buy_qty = int(item.get("buyQty") or item.get("buyQuantity", 0) or 0)
            sell_qty = int(item.get("sellQty") or item.get("sellQuantity", 0) or 0)
            buy_amt = float(item.get("buyAmt") or item.get("buyAmount", 0) or 0)
            sell_amt = float(item.get("sellAmt") or item.get("sellAmount", 0) or 0)
            net_qty = int(item.get("netQty") or item.get("netQuantity", buy_qty - sell_qty) or 0)
            net_amt = float(item.get("netAmt") or item.get("netAmount", buy_amt - sell_amt) or 0)
            
            brokers.append(BrokerData(
                broker_code=str(broker_code),
                broker_name=broker_name,
                buy_quantity=buy_qty,
                sell_quantity=sell_qty,
                buy_amount=buy_amt,
                sell_amount=sell_amt,
                net_quantity=net_qty,
                net_amount=net_amt,
            ))

        return BrokerAnalysisResponse(
            date_range=date_range,
            total_amount=total_amount,
            total_quantity=total_quantity,
            total_transactions=total_transactions,
            brokers=brokers
        )

    def get_broker_accumulation(
        self,
        symbol: str,
        duration: str = "1D"
    ) -> List[Dict]:
        """
        Get broker accumulation data (WHO IS HOLDING).

        REQUIRES AUTHENTICATION TOKEN!
        """
        # Ensure we have a valid token (auto-login if needed)
        self.ensure_valid_token()

        if not self.auth_token:
            logger.warning("Auth token required for broker accumulation (Login failed)!")
            return []

        symbol = symbol.upper()
        url = f"{self.BASE_URL}/data/api/v1/floorsheet-analysis/broker-accumulation"
        params = {"symbol": symbol, "duration": duration}
        referer = f"{self.BASE_URL}/company/{symbol}/broker-analysis/accumulation"

        data = self._get(
            url,
            params=params,
            referer=referer,
            use_auth_context=True,
        )
        return data if isinstance(data, list) else []

    def get_bulk_transactions(
        self,
        symbol: str,
        min_quantity: int = 3000
    ) -> List[Dict]:
        """
        Get bulk transactions (large trades).

        Args:
            symbol: Stock symbol
            min_quantity: Minimum quantity to qualify as bulk
        """
        symbol = symbol.upper()
        url = f"{self.BASE_URL}/live/api/v1/floorsheet/bulk-transactions"
        params = {
            "pageSize": "20",
            "MinimumQuantity": str(min_quantity),
            "symbol": symbol
        }
        referer = f"{self.BASE_URL}/company/{symbol}/bulk-transactions"

        data = self._get(url, params=params, referer=referer)

        if not data.get("success"):
            return []

        return data.get("data", [])

    def get_player_favorites(self) -> List[Dict]:
        """
        🎯 MILLIONAIRE ENDPOINT - Player Favorites (What Big Players Are Doing)!

        This is GOLD for swing trading! Shows:
        - Which stocks have heavy BUYER activity vs SELLER activity
        - "winner" = Who's dominating (Buyer/Seller)
        - "winnerWeight" = How dominant they are (%)

        TRADING RULES:
        ===============
        • winnerWeight > 55% BUYER → BIG MONEY loading up → BULLISH 🟢
        • winnerWeight > 55% SELLER → SMART MONEY exiting → BEARISH 🔴
        • winnerWeight < 55% → No clear direction → NEUTRAL ⚪

        Returns:
            List of dicts with:
            - symbol: Stock symbol
            - buyAmount/sellAmount: Total Rs. traded
            - buyQuantity/sellQuantity: Total shares traded
            - buyTransactions/sellTransactions: Number of trades
            - winner: "Buyer" or "Seller"
            - winnerWeight: Percentage (higher = more dominant)
        """
        url = f"{self.BASE_URL}/live/api/v1/floorsheet/bulk-transactions/player-fav"
        referer = f"{self.BASE_URL}/analysis/player-choices"

        data = self._get(url, referer=referer)

        if not data.get("success"):
            return []

        content = data.get("data", {}).get("content", [])
        logger.info(
            f"Fetched {len(content)} player favorites (buyer/seller dominance)")
        return content

    def get_player_favorites_by_symbol(self) -> Dict[str, Dict]:
        """
        Get player favorites indexed by symbol for quick lookup.

        Returns:
            Dict mapping symbol -> player favorite data
        """
        favorites = self.get_player_favorites()
        return {item["symbol"]: item for item in favorites}

    def get_buyer_dominated_stocks(self, min_weight: float = 55.0) -> List[Dict]:
        """
        🟢 Get stocks where BUYERS are dominating (bullish signal).

        Args:
            min_weight: Minimum winner weight to consider dominant (default 55%)

        Returns:
            List of stocks with strong buyer activity
        """
        favorites = self.get_player_favorites()
        buyers = [
            f for f in favorites
            if f.get("winner") == "Buyer" and f.get("winnerWeight", 0) >= min_weight
        ]
        # Sort by weight descending
        buyers.sort(key=lambda x: x.get("winnerWeight", 0), reverse=True)
        return buyers

    def get_seller_dominated_stocks(self, min_weight: float = 55.0) -> List[Dict]:
        """
        🔴 Get stocks where SELLERS are dominating (bearish signal - AVOID!)

        Args:
            min_weight: Minimum winner weight to consider dominant (default 55%)

        Returns:
            List of stocks with strong seller activity (to avoid!)
        """
        favorites = self.get_player_favorites()
        sellers = [
            f for f in favorites
            if f.get("winner") == "Seller" and f.get("winnerWeight", 0) >= min_weight
        ]
        # Sort by weight descending
        sellers.sort(key=lambda x: x.get("winnerWeight", 0), reverse=True)
        return sellers

    def get_broker_aggressive_holdings(
        self,
        duration: str = "1D",
        equity_only: bool = True,
    ) -> List[Dict]:
        """
        🎯 MILLIONAIRE ENDPOINT - Get broker aggressive holdings!

        This shows which stocks are being ACCUMULATED by big brokers.
        When top 3 brokers hold >50% of recent trades, it signals
        institutional interest = potential price rise!

        REQUIRES AUTHENTICATION TOKEN!

        Args:
            duration: "1D", "2D", "3D", "5D", "7D", "1W", "1M", "3M", "6M", "1Y"
            equity_only: Only show equity stocks (not mutual funds)

        Returns:
            List of stocks with broker accumulation data:
            - symbol, name
            - totalInvolvedBrokers: Number of brokers trading
            - topThreeBrokersHoldingPercentage: % held by top 3 (higher = more concentrated)
            - holdQuantity: Total quantity being held
            - publicTradePercentage: % of public shares traded
            - change, changePercentage, ltp: Price data
            - topBrokers: List of top 3 brokers with their holdings
        """
        if not self.auth_token:
            logger.warning(
                "Auth token required for broker aggressive holdings!")
            return []

        url = f"{self.BASE_URL}/data/api/v1/floorsheet-analysis/broker-aggressive-holdings"
        params = {
            "EquityOnly": "true" if equity_only else "false",
            "duration": duration,
        }
        referer = f"{self.BASE_URL}/broker/broker-aggressive-holdings"

        data = self._get(
            url,
            params=params,
            referer=referer,
            use_auth_context=True,
        )

        if not data.get("success"):
            return []

        content = data.get("data", {}).get("content", [])
        logger.info(
            f"Fetched {len(content)} broker aggressive holdings for {duration}")
        return content

    def get_top_accumulated_stocks(
        self,
        duration: str = "1D",
        min_holding_pct: float = 50.0,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get stocks with highest broker accumulation.

        Filters for stocks where top 3 brokers hold more than min_holding_pct.
        These are potential big-money plays!

        Args:
            duration: Time period ("1D", "1W", "1M", etc.)
            min_holding_pct: Minimum holding % by top 3 brokers
            limit: Maximum results

        Returns:
            List of accumulated stocks sorted by holding percentage
        """
        holdings = self.get_broker_aggressive_holdings(duration=duration)

        # Filter by holding percentage
        accumulated = [
            h for h in holdings
            if h.get("topThreeBrokersHoldingPercentage", 0) >= min_holding_pct
        ]

        # Sort by holding percentage (descending)
        accumulated.sort(
            key=lambda x: x.get("topThreeBrokersHoldingPercentage", 0),
            reverse=True
        )

        return accumulated[:limit]

    def get_promoter_unlock_data(
        self,
        lock_type: int = 1,
        size: int = 100,
    ) -> List[PromoterUnlock]:
        """
        🔴 CRITICAL: Get promoter share unlock schedule.

        WHY THIS IS IMPORTANT:
        ======================
        When promoter shares unlock, they can FLOOD the market with supply:
        - Promoters often sell to take profits
        - Increased supply → Price DROP
        - Smart traders EXIT before unlock dates!

        TRADING RULES:
        1. remainingDays < 7  → 🔴 AVOID completely
        2. remainingDays < 30 → ⚠️ Don't buy, consider selling
        3. Just unlocked      → 🚨 Watch for selling pressure

        Args:
            lock_type: 1 = MutualFund, 2 = Promoter (different unlock rules)
            size: Number of results

        Returns:
            List of PromoterUnlock objects sorted by remaining days
        """
        url = f"{self.BASE_URL}/data/api/v1/lock-in-period"
        params = {
            "size": str(size),
            "type": str(lock_type),
        }
        referer = f"{self.BASE_URL}/investment/promoter-unlock"

        data = self._get(url, params=params, referer=referer)

        if not data.get("success"):
            return []

        content = data.get("data", {}).get("content", [])

        unlocks = []
        for item in content:
            try:
                allotment_date = None
                lock_end_date = None

                if item.get("allotmentDate"):
                    allotment_date = datetime.fromisoformat(
                        item["allotmentDate"].replace("Z", "+00:00")
                    ).date()

                if item.get("lockInEndDate"):
                    lock_end_date = datetime.fromisoformat(
                        item["lockInEndDate"].replace("Z", "+00:00")
                    ).date()

                unlocks.append(PromoterUnlock(
                    symbol=item.get("symbol", ""),
                    name=item.get("name", ""),
                    type=item.get("type", ""),
                    total_listed_shares=item.get("totalListedShares", 0),
                    total_shares=item.get("totalShares", 0),
                    locked_shares=item.get("lockedShares", 0),
                    allotment_date=allotment_date,
                    lock_in_end_date=lock_end_date,
                    remaining_days=item.get("remainingDays", 0),
                ))
            except Exception as e:
                logger.debug(f"Error parsing unlock data: {e}")
                continue

        # Sort by remaining days (closest unlock first)
        unlocks.sort(key=lambda x: x.remaining_days)

        logger.info(
            f"Fetched {len(unlocks)} {'MutualFund' if lock_type == 1 else 'Promoter'} unlock records")
        return unlocks

    def get_all_unlock_risks(self, days_threshold: int = 60) -> Dict[str, List[PromoterUnlock]]:
        """
        🔴 Get ALL unlock risks (Mutual Fund + Promoter).

        Returns a dict with:
        - mutual_fund: List of MF unlocks
        - promoter: List of Promoter unlocks  
        - combined: All unlocks sorted by risk

        WHY BOTH MATTER:
        ================
        Mutual Fund: WILL sell to book profits (high probability)
        Promoter: MAY sell for liquidity (medium probability)

        If BOTH unlock around same time → DOUBLE TROUBLE! 🚨
        """
        # Type 0 = Promoter (3-year lock), Type 1 = MutualFund (6-month lock)
        mf_unlocks = self.get_promoter_unlock_data(lock_type=1)
        promoter_unlocks = self.get_promoter_unlock_data(lock_type=0)

        # Filter to threshold
        mf_risky = [u for u in mf_unlocks if 0 <
                    u.remaining_days <= days_threshold]
        promoter_risky = [u for u in promoter_unlocks if 0 <
                          u.remaining_days <= days_threshold]

        # Combined and sorted by risk score
        combined = mf_risky + promoter_risky
        combined.sort(key=lambda x: x.risk_score, reverse=True)

        return {
            "mutual_fund": mf_risky,
            "promoter": promoter_risky,
            "combined": combined,
            "summary": {
                "mf_count": len(mf_risky),
                "promoter_count": len(promoter_risky),
                "total_risky": len(combined),
            }
        }

    def get_stocks_to_avoid(self, days_threshold: int = 30) -> List[PromoterUnlock]:
        """
        🔴 Get stocks to AVOID due to upcoming unlock (MF + Promoter).

        These stocks have shares unlocking soon, which typically
        leads to selling pressure and price drops.

        Args:
            days_threshold: Avoid stocks with unlock within this many days

        Returns:
            List of stocks to avoid, sorted by risk score (highest first)
        """
        all_unlocks = self.get_promoter_unlock_data(lock_type=1)  # MutualFund
        all_unlocks.extend(self.get_promoter_unlock_data(
            lock_type=0))  # Promoter (type 0!)

        # Filter stocks unlocking soon (only future unlocks)
        to_avoid = [u for u in all_unlocks if 0 <
                    u.remaining_days <= days_threshold]

        # Sort by risk score (highest risk first)
        to_avoid.sort(key=lambda x: x.risk_score, reverse=True)

        return to_avoid

    def check_promoter_risk(self, symbol: str) -> Optional[PromoterUnlock]:
        """
        Check if a specific stock has promoter unlock risk.

        Args:
            symbol: Stock symbol to check

        Returns:
            PromoterUnlock object if stock has upcoming unlock, None otherwise
        """
        symbol = symbol.upper()

        # Check both types
        for lock_type in [1, 2]:
            unlocks = self.get_promoter_unlock_data(lock_type=lock_type)
            for u in unlocks:
                if u.symbol == symbol:
                    return u

        return None

    def get_symbol_unlock_risk(self, symbol: str) -> Dict:
        """
        Get complete unlock risk analysis for a symbol.

        Checks BOTH Mutual Fund AND Promoter unlocks.
        """
        symbol = symbol.upper()

        mf_unlocks = self.get_promoter_unlock_data(lock_type=1)
        promoter_unlocks = self.get_promoter_unlock_data(lock_type=2)

        mf_risk = next((u for u in mf_unlocks if u.symbol == symbol), None)
        promoter_risk = next(
            (u for u in promoter_unlocks if u.symbol == symbol), None)

        total_risk_score = 0
        risks = []

        if mf_risk and mf_risk.remaining_days > 0:
            total_risk_score += mf_risk.risk_score
            risks.append({
                "type": "MutualFund",
                "remaining_days": mf_risk.remaining_days,
                "locked_shares": mf_risk.locked_shares,
                "locked_pct": mf_risk.locked_percentage,
                "risk_level": mf_risk.unlock_risk_level,
                "risk_score": mf_risk.risk_score,
            })

        if promoter_risk and promoter_risk.remaining_days > 0:
            total_risk_score += promoter_risk.risk_score
            risks.append({
                "type": "Promoter",
                "remaining_days": promoter_risk.remaining_days,
                "locked_shares": promoter_risk.locked_shares,
                "locked_pct": promoter_risk.locked_percentage,
                "risk_level": promoter_risk.unlock_risk_level,
                "risk_score": promoter_risk.risk_score,
            })

        return {
            "symbol": symbol,
            "has_unlock_risk": len(risks) > 0,
            "total_risk_score": total_risk_score,
            "risk_summary": "🚨 DOUBLE UNLOCK RISK!" if len(risks) > 1 else (
                "⚠️ UNLOCK RISK" if len(risks) == 1 else "✅ NO UNLOCK RISK"
            ),
            "risks": risks,
        }


@dataclass
class BrokerAccumulatedStock:
    """Stock being accumulated by brokers."""
    symbol: str
    name: str
    ltp: float
    change_pct: float
    total_involved_brokers: int
    top_three_holding_pct: float
    hold_quantity: int
    public_trade_pct: float
    top_brokers: List[Dict]

    @property
    def accumulation_signal(self) -> str:
        """Get accumulation signal strength."""
        if self.top_three_holding_pct >= 80:
            return "🔴 EXTREME ACCUMULATION"
        elif self.top_three_holding_pct >= 60:
            return "🟠 STRONG ACCUMULATION"
        elif self.top_three_holding_pct >= 40:
            return "🟡 MODERATE ACCUMULATION"
        else:
            return "🟢 NORMAL DISTRIBUTION"

    # =========================================================================
    # EXACT TURNOVER FROM DAILY GRAPH (FREE API)
    # =========================================================================
    
    def get_daily_turnover(self, symbol: str) -> float:
        """
        📊 Get EXACT turnover for a stock from daily trade graph.
        
        Turnover = sum of (contractQuantity × contractRate) for ALL trades today.
        This is more accurate than volume × LTP which can be misleading.
        
        FREE API - NO AUTH REQUIRED!
        
        Args:
            symbol: Stock symbol (e.g., "ADBL")
            
        Returns:
            Exact turnover in NPR (0 if failed)
        """
        url = f"{self.BASE_URL}/live/api/v1/daily-graph/company/{symbol.upper()}"
        referer = f"{self.BASE_URL}/company/{symbol.upper()}"
        
        try:
            data = self._get(url, referer=referer)
            
            if not data or not isinstance(data, list):
                return 0.0
            
            # Sum of (quantity × rate) for each trade
            total_turnover = sum(
                float(trade.get("contractQuantity", 0)) * float(trade.get("contractRate", 0))
                for trade in data
            )
            
            return total_turnover
            
        except Exception as e:
            logger.debug(f"Failed to get turnover for {symbol}: {e}")
            return 0.0
    
    def get_bulk_turnover(self, symbols: List[str]) -> Dict[str, float]:
        """
        📊 Get exact turnover for multiple stocks.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict mapping symbol -> turnover
        """
        turnovers = {}
        for symbol in symbols:
            turnovers[symbol] = self.get_daily_turnover(symbol)
        return turnovers


# Convenience functions

def get_fundamentals(symbol: str) -> ShareHubFundamentals:
    """Quick function to get fundamentals."""
    api = ShareHubAPI()
    return api.get_fundamentals(symbol)


def get_dividends(symbol: str, limit: int = 10) -> List[DividendRecord]:
    """Quick function to get dividend history."""
    api = ShareHubAPI()
    return api.get_dividend_history(symbol, limit)


def get_technical_signals(symbol: str) -> TechnicalAnalysis:
    """Quick function to get technical ratings."""
    api = ShareHubAPI()
    return api.get_technical_ratings(symbol)


def get_broker_accumulated_stocks(auth_token: str, duration: str = "1D") -> List[BrokerAccumulatedStock]:
    """
    Quick function to get broker accumulated stocks.

    Usage:
        stocks = get_broker_accumulated_stocks("your-bearer-token", "1D")
        for s in stocks:
            print(f"{s.symbol}: {s.top_three_holding_pct}% held by top 3")
    """
    api = ShareHubAPI(auth_token=auth_token)
    holdings = api.get_broker_aggressive_holdings(duration=duration)

    return [
        BrokerAccumulatedStock(
            symbol=h.get("symbol", ""),
            name=h.get("name", ""),
            ltp=h.get("ltp", 0),
            change_pct=h.get("changePercentage", 0),
            total_involved_brokers=h.get("totalInvolvedBrokers", 0),
            top_three_holding_pct=h.get("topThreeBrokersHoldingPercentage", 0),
            hold_quantity=h.get("holdQuantity", 0),
            public_trade_pct=h.get("publicTradePercentage", 0),
            top_brokers=h.get("topBrokers", []),
        )
        for h in holdings
    ]


# Standalone helper for getting price history with OPEN price
def get_price_history_with_open(symbol: str, days: int = 10) -> Optional[List[Dict]]:
    """
    🚨 GET PRICE HISTORY WITH OPEN PRICE FROM SHAREHUB
    
    CRITICAL: NEPSE API does NOT provide open price, but ShareHub does!
    This is essential for detecting pump-and-dump scenarios where operators
    pump the open price and dump throughout the day.
    
    Args:
        symbol: Stock symbol (e.g., "BARUN")
        days: Number of days to fetch (default: 10)
    
    Returns:
        List of dicts with keys: date, open, high, low, close, volume
        Returns None if API fails
    
    Example:
        data = get_price_history_with_open("BARUN", days=7)
        if data:
            today = data[0]  # Latest data first
            open_price = today["open"]
            close_price = today["close"]
    """
    try:
        url = f"https://sharehubnepal.com/data/api/v1/price-history?pageSize={days}&symbol={symbol}"
        response = requests.get(url, headers={"accept": "application/json"}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("content"):
                content = data["data"]["content"]
                return [
                    {
                        "date": item["date"],
                        "open": float(item["open"]) if item.get("open") else None,
                        "high": float(item["high"]) if item.get("high") else None,
                        "low": float(item["low"]) if item.get("low") else None,
                        "close": float(item["close"]) if item.get("close") else None,
                        "volume": float(item["volume"]) if item.get("volume") else None,
                    }
                    for item in content
                ]
        logger.warning(f"Failed to fetch ShareHub price history for {symbol}: {response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching ShareHub price history for {symbol}: {e}")
        return None
