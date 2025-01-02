"""
Asynchronous HTTP scraper implementation using aiohttp.
"""

import aiohttp
from bs4 import BeautifulSoup
import logging
from typing import Optional
from fake_useragent import UserAgent
from http import HTTPStatus

from .base import BaseScraper, ScrapedContent
from ..content.cleaner import clean_html_content
from ..utils.url import is_valid_url, is_likely_download_url
from ..utils.constants import JS_REQUIRED_INDICATORS

logger = logging.getLogger(__name__)

class AiohttpScraper(BaseScraper):
    """
    Asynchronous scraper implementation using aiohttp.
    More efficient than requests for multiple URLs.
    """

    def __init__(self):
        """Initialize the aiohttp scraper."""
        self.user_agent = UserAgent()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def is_suitable(self, url: str) -> bool:
        """
        Check if this scraper is suitable for the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL is valid and not likely to require JavaScript
        """
        if not await is_valid_url(url) or await is_likely_download_url(url):
            return False
            
        # Try a HEAD request
        try:
            await self._ensure_session()
            headers = {'User-Agent': self.user_agent.random}
            async with self.session.head(url, headers=headers, allow_redirects=True) as response:
                content_type = response.headers.get('content-type', '').lower()
                return 'text/html' in content_type
        except:
            return False

    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from the given URL using aiohttp.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
        """
        try:
            await self._ensure_session()
            
            headers = {
                'User-Agent': self.user_agent.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != HTTPStatus.OK:
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error=f"HTTP {response.status}"
                    )
                
                content = await response.text()
                
                # Check content length
                if len(content.strip()) < 100:
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error="Page content too short"
                    )

                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Check for JavaScript requirements
                if self._requires_javascript(soup):
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error="Page requires JavaScript"
                    )

                # Get title
                title = soup.title.string if soup.title else ""
                
                # Clean and extract content
                cleaned_content = await clean_html_content(str(soup))
                
                if not cleaned_content.strip():
                    return ScrapedContent(
                        url=url,
                        content="",
                        title=title,
                        status="error",
                        error="No content after cleaning"
                    )

                return ScrapedContent(
                    url=url,
                    content=cleaned_content,
                    title=title,
                    status="success"
                )

        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return ScrapedContent(
                url=url,
                content="",
                title="",
                status="error",
                error=str(e)
            )

    def _requires_javascript(self, soup: BeautifulSoup) -> bool:
        """Check if page appears to require JavaScript."""
        text = soup.get_text().lower()
        return any(indicator in text for indicator in JS_REQUIRED_INDICATORS)

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None 