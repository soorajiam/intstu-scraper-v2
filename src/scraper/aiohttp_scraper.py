"""
Asynchronous HTTP scraper implementation using aiohttp.
Second tier scraper with better performance than requests.
"""

import aiohttp
from bs4 import BeautifulSoup
import logging
from typing import Optional
from fake_useragent import UserAgent
import asyncio
from http import HTTPStatus

from src.scraper.base import BaseScraper, ScrapedContent
from src.content.cleaner import clean_html_content
from src.utils.url import is_valid_url, is_likely_download_url
from src.utils.constants import JS_REQUIRED_INDICATORS

logger = logging.getLogger(__name__)

class AiohttpScraper(BaseScraper):
    """
    Asynchronous scraper using aiohttp.
    Second tier scraper - better performance than requests.
    """

    def __init__(self):
        """Initialize the aiohttp scraper."""
        super().__init__()
        self.resource_cost = 2.0  # Medium resource cost
        self.user_agent = UserAgent()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.max_retries = 3
        self.retry_delay = 1

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def is_suitable(self, url: str) -> bool:
        """Check if this scraper is suitable for the URL."""
        if not await is_valid_url(url) or await is_likely_download_url(url):
            return False
            
        # Try a HEAD request
        try:
            await self._ensure_session()
            headers = {'User-Agent': self.user_agent.random}
            
            async with self.session.head(
                url, 
                headers=headers, 
                allow_redirects=True,
                ssl=False
            ) as response:
                # Check status code
                if response.status != HTTPStatus.OK:
                    return False
                    
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not 'text/html' in content_type:
                    return False
                    
                return True
                
        except Exception as e:
            logger.debug(f"URL not suitable for aiohttp: {e}")
            return False

    async def scrape(self, url: str) -> ScrapedContent:
        """Scrape content using aiohttp."""
        await self._ensure_session()
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
                
                async with self.session.get(url, headers=headers, ssl=False) as response:
                    if response.status != 200:
                        return ScrapedContent(
                            url=url,
                            content="",
                            title="",
                            status="error",
                            error=f"HTTP {response.status}"
                        )
                    
                    html_content = await response.text()
                    
                    try:
                        # Parse with BeautifulSoup
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Get title
                        title = await self.extract_title(soup)
                        
                        # Clean and extract content
                        content = await clean_html_content(str(soup))
                        
                        if not content.strip():
                            logger.warning(f"No content extracted from {url}")
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
                        logger.error(f"Error processing content from {url}: {e}", exc_info=True)
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
            await self.session.close()
            self.session = None 