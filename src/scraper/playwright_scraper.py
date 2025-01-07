"""
Playwright-based scraper implementation for JavaScript-heavy and dynamic websites.
Final tier scraper with full browser capabilities.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from fake_useragent import UserAgent
import gc
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper, ScrapedContent
from src.content.cleaner import clean_html_content
from src.utils.url import is_valid_url, is_likely_download_url
from src.utils.constants import (
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
    Final tier scraper - most capable but resource intensive.
    """

    def __init__(self):
        """Initialize the Playwright scraper."""
        super().__init__()
        self.resource_cost = 5.0  # Highest resource cost
        self.user_agent = UserAgent()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.max_retries = 2
        self.retry_delay = 2

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
        """Configure page settings and event handlers."""
        if not self.page:
            return

        # Set timeouts
        self.page.set_default_timeout(PAGE_LOAD_TIMEOUT)
        self.page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT)

        # Set up error handling
        self.page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))
        self.page.on("crash", lambda: logger.error("Page crashed"))
        self.page.on("console", lambda msg: logger.debug(f"Console {msg.type}: {msg.text}"))

        # Block unnecessary resources
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}", 
            lambda route: route.abort())

    async def is_suitable(self, url: str) -> bool:
        """Check if this scraper is suitable for the URL."""
        # Playwright is our last resort, so accept most URLs
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

    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content using Playwright.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
        """
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                await self._ensure_browser()
                
                # Navigate to page
                await self.page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                
                # Handle Cloudflare
                if not await self._handle_cloudflare():
                    return ScrapedContent(
                        url=url,
                        content="",
                        title="",
                        status="error",
                        error="Failed to bypass protection"
                    )

                # Wait for content to load
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=DOM_CONTENT_TIMEOUT)
                    await self.page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT)
                except PlaywrightTimeoutError:
                    logger.warning("Timeout waiting for page load - continuing anyway")

                # Get page content
                html_content = await self.page.content()
                
                # Parse with BeautifulSoup for content extraction
                soup = BeautifulSoup(html_content, 'html.parser')
                
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
                last_error = e
                if await self.should_retry(e):
                    retries += 1
                    if retries <= self.max_retries:
                        await asyncio.sleep(self.retry_delay * retries)
                        # Reset page on retry
                        if self.page:
                            await self.page.close()
                            self.page = None
                        continue
                break

        return ScrapedContent(
            url=url,
            content="",
            title="",
            status="error",
            error=str(last_error)
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