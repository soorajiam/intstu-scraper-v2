"""
Playwright-based scraper implementation for JavaScript-heavy and dynamic websites.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from fake_useragent import UserAgent
import gc

from .base import BaseScraper, ScrapedContent
from ..content.cleaner import clean_html_content
from ..utils.url import is_valid_url, is_likely_download_url
from ..utils.constants import (
    BROWSER_LAUNCH_ARGS,
    PAGE_LOAD_TIMEOUT,
    NETWORK_IDLE_TIMEOUT,
    DOM_CONTENT_TIMEOUT,
    SELECTOR_TIMEOUT
)

logger = logging.getLogger(__name__)

class PlaywrightScraper(BaseScraper):
    """
    Advanced scraper using Playwright for JavaScript-heavy websites.
    Handles dynamic content, SPAs, and complex web applications.
    """

    def __init__(self):
        """Initialize the Playwright scraper."""
        self.user_agent = UserAgent()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def _ensure_browser(self) -> None:
        """
        Ensure browser is initialized and running.
        
        Raises:
            RuntimeError: If browser initialization fails
        """
        if not self.playwright:
            self.playwright = await async_playwright().start()

        if not self.browser:
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=BROWSER_LAUNCH_ARGS,
                    chromium_sandbox=False
                )
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                raise RuntimeError(f"Browser launch failed: {e}")

        if not self.page:
            try:
                context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent=self.user_agent.random,
                    ignore_https_errors=True
                )
                self.page = await context.new_page()
                await self._configure_page()
            except Exception as e:
                logger.error(f"Failed to create page: {e}")
                raise RuntimeError(f"Page creation failed: {e}")

    async def _configure_page(self) -> None:
        """Configure page settings and timeouts."""
        if not self.page:
            return

        self.page.set_default_timeout(PAGE_LOAD_TIMEOUT)
        self.page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

        # Set up error handling
        self.page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))
        self.page.on("crash", lambda: logger.error("Page crashed"))

        # Optional: Handle other events
        self.page.on("console", lambda msg: logger.debug(f"Console {msg.type}: {msg.text}"))

    async def is_suitable(self, url: str) -> bool:
        """
        Check if this scraper is suitable for the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL is valid and might require JavaScript
        """
        # Playwright is our most capable scraper, so we accept most URLs
        if not await is_valid_url(url) or await is_likely_download_url(url):
            return False
        return True

    async def _handle_cloudflare(self) -> bool:
        """
        Handle Cloudflare protection pages.
        
        Returns:
            bool: True if successfully bypassed or no Cloudflare
        """
        try:
            # Check for Cloudflare elements
            cloudflare_selectors = [
                "div[class*='cf-browser-verification']",
                "#challenge-form",
                "div[class*='cf-challenge']",
                "iframe[src*='challenges.cloudflare.com']"
            ]

            for selector in cloudflare_selectors:
                try:
                    if await self.page.wait_for_selector(selector, timeout=5000):
                        logger.info("Detected Cloudflare challenge")
                        
                        # Wait for challenge to process
                        await self.page.wait_for_load_state("networkidle", timeout=30000)
                        
                        # Check if we're past Cloudflare
                        content = await self.page.content()
                        if not any(cf_text in content.lower() for cf_text in [
                            "checking if the site connection is secure",
                            "please wait while we verify",
                            "please stand by, while we are checking"
                        ]):
                            return True
                except PlaywrightTimeoutError:
                    continue

            return True  # No Cloudflare detected
            
        except Exception as e:
            logger.error(f"Error handling Cloudflare: {e}")
            return False

    async def _extract_content(self) -> tuple[str, str]:
        """
        Extract content and title from the page.
        
        Returns:
            tuple[str, str]: (content, title)
        """
        try:
            # Wait for content to load
            await self.page.wait_for_load_state("domcontentloaded", timeout=DOM_CONTENT_TIMEOUT)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
            except PlaywrightTimeoutError:
                logger.warning("Network idle timeout - continuing anyway")

            # Get page title
            title = await self.page.title()

            # Try to get main content
            content_selectors = [
                'main', 'article', '#main-content', '.main-content',
                '.content', '#content', '[role="main"]'
            ]

            html_content = ""
            for selector in content_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=SELECTOR_TIMEOUT)
                    if element:
                        html_content = await element.inner_html()
                        if html_content.strip():
                            break
                except PlaywrightTimeoutError:
                    continue

            # If no content found with selectors, get full body
            if not html_content.strip():
                html_content = await self.page.content()

            # Clean and process content
            cleaned_content = await clean_html_content(html_content)
            return cleaned_content, title

        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            raise

    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from the given URL using Playwright.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
        """
        try:
            await self._ensure_browser()
            
            # Navigate to page
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            except PlaywrightTimeoutError:
                return ScrapedContent(
                    url=url,
                    content="",
                    title="",
                    status="error",
                    error="Page load timeout"
                )

            # Handle Cloudflare
            if not await self._handle_cloudflare():
                return ScrapedContent(
                    url=url,
                    content="",
                    title="",
                    status="error",
                    error="Failed to bypass protection"
                )

            # Extract content
            content, title = await self._extract_content()
            
            if not content.strip():
                return ScrapedContent(
                    url=url,
                    content="",
                    title=title,
                    status="error",
                    error="No content extracted"
                )

            return ScrapedContent(
                url=url,
                content=content,
                title=title,
                status="success"
            )

        except PlaywrightError as e:
            logger.error(f"Playwright error: {e}")
            return ScrapedContent(
                url=url,
                content="",
                title="",
                status="error",
                error=f"Playwright error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedContent(
                url=url,
                content="",
                title="",
                status="error",
                error=str(e)
            )

    async def cleanup(self) -> None:
        """Clean up Playwright resources."""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            gc.collect() 