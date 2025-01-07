"""
Basic request-based scraper implementation using the requests library.
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional
from fake_useragent import UserAgent
import time
import asyncio

from src.scraper.base import BaseScraper, ScrapedContent
from src.content.cleaner import clean_html_content
from src.utils.url import is_valid_url, is_likely_download_url
from src.utils.constants import JS_REQUIRED_INDICATORS

logger = logging.getLogger(__name__)

class RequestScraper(BaseScraper):
    """
    Simple scraper implementation using the requests library.
    First tier scraper - fastest but least capable.
    """

    def __init__(self):
        """Initialize the request scraper."""
        super().__init__()
        self.resource_cost = 1.0  # Lowest resource cost
        self.user_agent = UserAgent()
        self.session = requests.Session()
        self.timeout = 10
        self.max_retries = 2
        self.retry_delay = 1

    async def is_suitable(self, url: str) -> bool:
        """Check if this scraper is suitable for the URL."""
        if not await is_valid_url(url) or await is_likely_download_url(url):
            return False
            
        # Try a HEAD request to check content type
        try:
            headers = {'User-Agent': self.user_agent.random}
            response = self.session.head(
                url, 
                timeout=5, 
                allow_redirects=True,
                verify=False
            )
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not 'text/html' in content_type:
                return False
                
            # Check response code
            if response.status_code != 200:
                return False
                
            return True
            
        except:
            return False

    async def scrape(self, url: str) -> ScrapedContent:
        """Scrape content using requests."""
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
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
                    verify=False  # Keep verify=False but suppress warnings
                )
                response.raise_for_status()
                
                html_content = response.text
                
                # Quick check for very short content
                if len(html_content.strip()) < 100:
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error="Page content too short"
                    )

                try:
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
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
                    title = await self.extract_title(soup)
                    
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
                        status="success",
                        html=html_content
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing content: {e}", exc_info=True)
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error=f"Content processing error: {str(e)}"
                    )

            except Exception as e:
                last_error = e
                if await self.should_retry(e):
                    retries += 1
                    if retries <= self.max_retries:
                        await asyncio.sleep(self.retry_delay * retries)
                        continue
                break

        return ScrapedContent(
            url=url,
            content="",
            title="",
            status="error",
            error=str(last_error)
        )

    def _requires_javascript(self, soup: BeautifulSoup) -> bool:
        """Check if page appears to require JavaScript."""
        text = soup.get_text().lower()
        return any(indicator in text for indicator in JS_REQUIRED_INDICATORS)

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            self.session.close() 