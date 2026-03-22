"""
News Scraper for NEPSE stocks.

Scrapes news from ShareSansar and Merolagani using Playwright.
Playwright is used because these sites use JavaScript rendering.

IMPORTANT: These sites may change their structure. Update selectors as needed.
"""

import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = Any  # Type hint fallback when Playwright not installed
    Page = Any
    logger.warning("Playwright not installed. News scraping will be disabled.")

from core.config import settings
from core.exceptions import ScraperError


@dataclass
class NewsItem:
    """Represents a news article."""
    title: str
    url: str
    date: Optional[str] = None
    source: str = ""
    snippet: str = ""


class NewsScraper:
    """
    Async news scraper for NEPSE stocks.
    
    Uses Playwright to handle JavaScript-rendered content.
    """
    
    # News source configurations
    SOURCES = {
        "sharesansar": {
            "base_url": "https://www.sharesansar.com",
            "search_url": "https://www.sharesansar.com/company/{symbol}",
            "news_selector": ".news-list .news-item, .company-news-item",
            "title_selector": "h3 a, .title a",
            "date_selector": ".date, .news-date",
        },
        "merolagani": {
            "base_url": "https://merolagani.com",
            "search_url": "https://merolagani.com/CompanyDetail.aspx?symbol={symbol}",
            "news_selector": ".media-news, .news-item",
            "title_selector": "h4 a, .media-heading a",
            "date_selector": ".text-muted",
        },
    }
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize scraper.
        
        Args:
            headless: Run browser in headless mode
            timeout: Page load timeout in ms
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required for news scraping. Run: pip install playwright && playwright install")
        
        self.headless = headless
        self.timeout = timeout
        self._browser: Optional[Browser] = None # type: ignore
        self._playwright = None
        self._news_cache: List[NewsItem] = []  # Cache for latest market news
        self._cache_time: Optional[datetime] = None

    
    async def _get_browser(self) -> Browser: # type: ignore
        """Get or create browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        return self._browser
    
    async def _close_browser(self):
        """Close browser instance."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.debug(f"Browser close ignored: {e}")
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug(f"Playwright stop ignored: {e}")
            self._playwright = None
    
    async def close(self):
        """Public method to clean up resources."""
        await self._close_browser()

    def _clean_text(self, text: str) -> str:
        """
        Clean text to prevent OpenAI token burnout.
        1. Remove extra whitespace/newlines.
        2. Remove potential HTML artifacts.
        3. Remove non-printable characters.
        4. Truncate if excessively long.
        """
        if not text:
            return ""
        
        cleaned = text
        
        # 0. Strip HTML tags (extra safety)
        if '<' in cleaned and '>' in cleaned:
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            
        # 1. Replace newlines/tabs with space and strip ends
        cleaned = " ".join(cleaned.split())
        
        # 2. Basic HTML entity check (inner_text handles most tags, but entities might remain)
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        
        # 3. Remove generic site suffixes if present (optional but good for AI context)
        # e.g., " | ShareSansar", " - Merolagani"
        
        return cleaned[:300] # Hard limit on title length just in case

    async def _scrape_market_news(self, limit: int = 50) -> List[NewsItem]:
        """
        🚀 BATCH SCRAPE: Scrape latest news from all sources ONCE.
        
        Sources:
        1. ShareSansar Main Page
        2. Merolagani Main Page (Breaking News)
        3. Merolagani NewsList (with Load More)
        
        Args:
            limit: Max articles to fetch per source
            
        Returns:
            List of all NewsItems found
            
        Note: This method now populates self._news_cache directly.
        """
        # Skip if already cached recently
        if self._news_cache and len(self._news_cache) > 0:
            logger.info(f"📰 Using cached news ({len(self._news_cache)} items)")
            return self._news_cache
            
        logger.info("📰 Batch scraping latest market news (Stealth & Optimized)...")
        all_news = []
        browser = await self._get_browser()
        page = await browser.new_page()
        
        # 1. ShareSansar News
        try:
            url = "https://www.sharesansar.com/news-page"
            logger.debug(f"   Visiting {url}...")
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            articles = await page.query_selector_all('a[href*="/newsdetail/"]')
            count = 0
            for article in articles:
                if count >= limit: break
                try:
                    text = await article.inner_text()
                    text = self._clean_text(text)
                    href = await article.get_attribute("href")
                    
                    if text and len(text) > 10:
                        if href and not href.startswith("http"):
                            href = "https://www.sharesansar.com" + href
                        
                        all_news.append(NewsItem(
                            title=text,
                            url=href or "",
                            date=datetime.now().strftime("%Y-%m-%d"),
                            source="ShareSansar"
                        ))
                        count += 1
                except Exception: pass
            logger.info(f"   ✅ Found {count} headlines from ShareSansar")
            
        except Exception as e:
            logger.warning(f"   ⚠️ ShareSansar batch scrape failed: {e}")

        # 2. Merolagani Main Page (All News with NewsDetail links)
        try:
            url = "https://merolagani.com"
            logger.debug(f"   Visiting {url} (Homepage)...")
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Use the working selector that finds NewsDetail links
            # This captures sliders, breaking news, featured, and all visible news
            articles = await page.query_selector_all('a[href*="NewsDetail"]')
            count = 0
            seen_titles = set()  # Deduplicate
            
            for article in articles:
                if count >= 50: break  # Get up to 50 from homepage
                try:
                    text = await article.inner_text()
                    text = self._clean_text(text)
                    href = await article.get_attribute("href")
                    
                    # Skip if too short or already seen
                    if not text or len(text) < 10 or text in seen_titles:
                        continue
                        
                    seen_titles.add(text)
                    
                    if href and not href.startswith("http"):
                        href = "https://merolagani.com/" + href.lstrip("/")
                    
                    all_news.append(NewsItem(
                        title=text,
                        url=href or "",
                        date=datetime.now().strftime("%Y-%m-%d"),
                        source="Merolagani"
                    ))
                    count += 1
                except Exception: pass
            logger.info(f"   ✅ Found {count} headlines from Merolagani Home")
            
        except Exception as e:
            logger.warning(f"   ⚠️ Merolagani Home scrape failed: {e}")

        # 3. Merolagani News List (With Load More)
        try:
            url = "https://merolagani.com/NewsList.aspx"
            logger.debug(f"   Visiting {url} (List)...")
            await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # CLICK LOAD MORE 12 TIMES (Requested: 10-12 times)
            # Each click loads ~10 news items. 12 clicks = 120+ items.
            load_more_clicks = 12
            for i in range(load_more_clicks):
                try:
                    # Updated selector: btn btn-primary btn-block with "Load More" text
                    load_more_btn = await page.query_selector('a.btn-primary:has-text("Load More"), a.btn:has-text("Load More")')
                    
                    if load_more_btn:
                        is_visible = await load_more_btn.is_visible()
                        if is_visible:
                            # Scroll button into view first
                            await load_more_btn.scroll_into_view_if_needed()
                            logger.debug(f"      Clicking Load More ({i+1}/{load_more_clicks})...")
                            await load_more_btn.click()
                            # Wait for AJAX to load new items
                            await asyncio.sleep(1.5)
                            # Scroll to top so more news loads above
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        else:
                            logger.debug(f"      Load More not visible, stopping at {i} clicks")
                            break
                    else:
                        logger.debug(f"      Load More button not found, stopping at {i} clicks")
                        break
                except Exception as e:
                    logger.debug(f"      Load More click failed: {e}")
                    break
            
            # Scrape ALL news items after loading more
            articles = await page.query_selector_all('a[href*="NewsDetail"]')
            count = 0
            seen_titles = set(n.title for n in all_news)  # Already seen from homepage
            
            for article in articles:
                if count >= 150: break  # Get up to 150 from list
                try:
                    text = await article.inner_text()
                    text = self._clean_text(text)
                    href = await article.get_attribute("href")
                    
                    # Skip if too short or already seen
                    if not text or len(text) < 10 or text in seen_titles:
                        continue
                    
                    seen_titles.add(text)

                    if href and not href.startswith("http"):
                        href = "https://merolagani.com/" + href.lstrip("/")
                    
                    all_news.append(NewsItem(
                        title=text,
                        url=href or "",
                        date=datetime.now().strftime("%Y-%m-%d"),
                        source="Merolagani (List)"
                    ))
                    count += 1
                except Exception: pass
            logger.info(f"   ✅ Found {count} headlines from Merolagani List (after {load_more_clicks} Load More clicks)")
            
        except Exception as e:
            logger.warning(f"   ⚠️ Merolagani List scrape failed: {e}")
            
        await page.close()
        
        # Cache the results for subsequent calls
        self._news_cache = all_news
        self._cache_time = datetime.now()
        logger.info(f"📰 Total cached news: {len(self._news_cache)} items")
        
        return all_news

    async def scrape_sharesansar(self, symbol: str, limit: int = 3) -> List[NewsItem]:
        """
        Scrape news from ShareSansar.
        
        Strategy: Visit the main news page and search for articles mentioning the stock symbol.
        This is more reliable than company-specific pages which may not have news sections.
        
        Args:
            symbol: Stock symbol
            limit: Max articles to fetch
            
        Returns:
            List of NewsItems
        """
        news = []
        browser = await self._get_browser()
        page = await browser.new_page()
        
        # Try the main news page first
        news_url = "https://www.sharesansar.com/news-page"
        
        try:
            logger.debug(f"Scraping ShareSansar news page for {symbol}: {news_url}")
            await page.goto(news_url, timeout=self.timeout, wait_until="domcontentloaded")
            
            # Wait for content to load
            await asyncio.sleep(2)
            
            # Find all news article links
            articles = await page.query_selector_all('a[href*="/newsdetail/"]')
            
            for article in articles:
                if len(news) >= limit:
                    break
                    
                try:
                    text = await article.inner_text()
                    href = await article.get_attribute("href")
                    
                    # Check if this article mentions our stock symbol
                    # Also check for company name matches (e.g., NMB -> "NMB Bank")
                    symbol_upper = symbol.upper()
                    text_upper = text.upper()
                    
                    if symbol_upper in text_upper or f"{symbol_upper} " in text_upper:
                        # Make URL absolute
                        if href and not href.startswith("http"):
                            href = "https://www.sharesansar.com" + href
                        
                        news.append(NewsItem(
                            title=text.strip()[:150],
                            url=href or "",
                            date=None,
                            source="ShareSansar",
                            snippet="",
                        ))
                        logger.debug(f"Found news for {symbol}: {text[:50]}...")
                        
                except Exception as e:
                    logger.debug(f"Error parsing article: {e}")
                    continue
            
            # If no symbol-specific news found, try the company page as fallback
            if not news:
                company_url = f"https://www.sharesansar.com/company/{symbol.upper()}"
                logger.debug(f"No news on main page, trying company page: {company_url}")
                await page.goto(company_url, timeout=self.timeout, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # Look for any news links on the company page
                news_links = await page.query_selector_all('a[href*="news"], a[href*="announcement"]')
                for link in news_links[:limit]:
                    try:
                        text = await link.inner_text()
                        href = await link.get_attribute("href")
                        if text.strip() and len(text.strip()) > 20:
                            if href and not href.startswith("http"):
                                href = "https://www.sharesansar.com" + href
                            news.append(NewsItem(
                                title=text.strip()[:150],
                                url=href or "",
                                source="ShareSansar",
                            ))
                    except:
                        continue
            
        except PlaywrightTimeout:
            logger.warning(f"Timeout scraping ShareSansar for {symbol}")
        except Exception as e:
            logger.error(f"Error scraping ShareSansar: {e}")
        finally:
            await page.close()
        
        logger.info(f"Scraped {len(news)} news from ShareSansar for {symbol}")
        return news
    
    async def scrape_merolagani(self, symbol: str, limit: int = 3) -> List[NewsItem]:
        """
        Scrape news from Merolagani.
        
        Strategy: Visit the Merolagani news page and search for stock-related news.
        
        Args:
            symbol: Stock symbol
            limit: Max articles to fetch
            
        Returns:
            List of NewsItems
        """
        news = []
        browser = await self._get_browser()
        page = await browser.new_page()
        
        # Try Merolagani's news section
        news_url = "https://merolagani.com/NewsList.aspx"
        
        try:
            logger.debug(f"Scraping Merolagani news for {symbol}: {news_url}")
            await page.goto(news_url, timeout=self.timeout, wait_until="domcontentloaded")
            
            await asyncio.sleep(2)  # Merolagani is slow
            
            # Find all news links
            news_links = await page.query_selector_all('a[href*="NewsDetail"], .media-heading a, h4 a')
            
            symbol_upper = symbol.upper()
            
            for link in news_links:
                if len(news) >= limit:
                    break
                    
                try:
                    text = await link.inner_text()
                    href = await link.get_attribute("href")
                    
                    # Check if mentions our symbol
                    if symbol_upper in text.upper():
                        if href and not href.startswith("http"):
                            href = "https://merolagani.com/" + href.lstrip("/")
                        
                        news.append(NewsItem(
                            title=text.strip()[:150],
                            url=href or "",
                            source="Merolagani",
                        ))
                        logger.debug(f"Found Merolagani news for {symbol}: {text[:50]}...")
                        
                except Exception as e:
                    logger.debug(f"Error parsing Merolagani item: {e}")
                    continue
            
            # If no news found, try the company detail page
            if not news:
                company_url = f"https://merolagani.com/CompanyDetail.aspx?symbol={symbol.upper()}"
                logger.debug(f"No news found, trying company page: {company_url}")
                await page.goto(company_url, timeout=self.timeout, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # Look for news/announcement sections on company page
                news_section = await page.query_selector_all('.news-item, .media-body, [id*="news"] a')
                for item in news_section[:limit]:
                    try:
                        text = await item.inner_text()
                        if text.strip() and len(text.strip()) > 20:
                            news.append(NewsItem(
                                title=text.strip()[:150],
                                url=company_url,
                                source="Merolagani",
                            ))
                    except:
                        continue
            
        except PlaywrightTimeout:
            logger.warning(f"Timeout scraping Merolagani for {symbol}")
        except Exception as e:
            logger.error(f"Error scraping Merolagani: {e}")
        finally:
            await page.close()
        
        logger.info(f"Scraped {len(news)} news from Merolagani for {symbol}")
        return news
    
    async def scrape_all_sources(self, symbol: str, limit: int = 3) -> List[NewsItem]:
        """
        Scrape news from all sources (Optimized).
        
        Uses a batch fetching strategy:
        1. First call fetches global market news from main pages.
        2. Subsequent calls filter from this cache.
        3. This avoids visiting 50+ individual company pages.
        
        Args:
            symbol: Stock symbol
            limit: Max articles per source
            
        Returns:
            Combined list of NewsItems
        """
        # 1. Populate cache if empty
        if not self._news_cache:
            self._news_cache = await self._scrape_market_news()
        
        # 2. Filter from cache
        symbol_upper = symbol.upper()
        filtered_news = []
        
        for item in self._news_cache:
            # Simple heuristic: Check if symbol is in title
            # In production, we'd want smarter NLP or full company name matching
            if symbol_upper in item.title.upper().split():
                filtered_news.append(item)
            # Also check for common variations or if symbol is a substring but distinct
            elif f" {symbol_upper} " in f" {item.title.upper()} ":
                filtered_news.append(item)
                
        # 3. If cache yielded results, return them
        if filtered_news:
            logger.info(f"✅ Found {len(filtered_news)} cached news for {symbol}")
            return filtered_news[:limit]
            
        # 4. FALLBACK: If specific stock not in headlines, try direct company page
        # Only do this if we really need to (e.g. for top picks)
        # But to be safe and robust, let's just return empty for now to save time,
        # unless it's a very specific request.
        # The user explicitly asked to "fetch exactly once".
        
        logger.debug(f"No headline news found for {symbol} in batch scrape.")
        return []
            
    def format_news_for_ai(self, news: List[NewsItem]) -> str:
        """
        Format news for AI analysis.
        
        Args:
            news: List of NewsItems
            
        Returns:
            Formatted string for AI prompt
        """
        if not news:
            return "No recent news found for this stock."
        
        lines = []
        for i, item in enumerate(news, 1):
            line = f"{i}. [{item.source}] {item.title}"
            if item.date:
                line += f" ({item.date})"
            if item.snippet:
                line += f"\n   {item.snippet}"
            lines.append(line)
        
        return "\n".join(lines)


def scrape_news_for_stock(symbol: str, limit: int = 3, headless: bool = True) -> List[NewsItem]:
    """
    Convenience function to scrape news synchronously.
    
    Args:
        symbol: Stock symbol
        limit: Max articles per source
        headless: Run browser in headless mode (default True)
        
    Returns:
        List of NewsItems
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright not available, returning empty news")
        return []
    
    scraper = NewsScraper(headless=headless)
    return asyncio.run(scraper.scrape_all_sources(symbol, limit))
