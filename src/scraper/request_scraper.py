"""
Basic request-based scraper implementation using the requests library.
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional
from fake_useragent import UserAgent

from src.scraper.base import BaseScraper, ScrapedContent
from src.content.cleaner import clean_html_content
from src.utils.url import is_valid_url, is_likely_download_url
from src.utils.constants import JS_REQUIRED_INDICATORS

logger = logging.getLogger(__name__)

class RequestScraper(BaseScraper):
    """
    Simple scraper implementation using the requests library.
    Suitable for basic static web pages.
    """

    def __init__(self):
        """Initialize the request scraper with default settings."""
        self.user_agent = UserAgent()
        self.session = requests.Session()
        self.timeout = 10

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
            
        # Try a HEAD request to check content type
        try:
            headers = {'User-Agent': self.user_agent.random}
            response = self.session.head(url, timeout=5, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()
            
            return 'text/html' in content_type
        except:
            return False

    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from the given URL using requests.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
        """
        try:
            headers = {
                'User-Agent': self.user_agent.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
            }
            
            response = self.session.get(
                url, 
                headers=headers, 
                timeout=self.timeout,
                verify=False
            )
            response.raise_for_status()
            
            # Check content length
            if len(response.text.strip()) < 100:
                return ScrapedContent(
                    url=url,
                    content="",
                    title="",
                    status="error",
                    error="Page content too short"
                )

            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
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
            content = await clean_html_content(str(soup))
            
            if not content.strip():
                return ScrapedContent(
                    url=url,
                    content="",
                    title=title,
                    status="error",
                    error="No content after cleaning"
                )

            return ScrapedContent(
                url=url,
                content=content,
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
        self.session.close() 