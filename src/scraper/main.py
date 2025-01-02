"""
Main scraper orchestration module.
Coordinates different scraper implementations and handles the scraping workflow.
"""

import asyncio
import logging
import argparse
from typing import List, Optional
import gc

from src.scraper.base import BaseScraper, ScrapedContent
from src.scraper.request_scraper import RequestScraper
from src.scraper.aiohttp_scraper import AiohttpScraper
from src.scraper.playwright_scraper import PlaywrightScraper
from src.api.client import api_client
from src.api.models import ScrapedLink
from src.utils.logging import setup_logging, get_logger
from src.utils.url import is_valid_url

logger = get_logger(__name__)

class ScraperOrchestrator:
    """
    Coordinates multiple scraper implementations and manages the scraping workflow.
    Implements a tiered scraping approach, trying simpler scrapers first.
    """

    def __init__(self, session: str, worker_id: str, institution_id: Optional[str] = None):
        """
        Initialize the scraper orchestrator.
        
        Args:
            session: Scraping session ID
            worker_id: Unique worker identifier
            institution_id: Optional institution ID filter
        """
        self.session = session
        self.worker_id = worker_id
        self.institution_id = institution_id
        
        # Initialize scrapers in order of complexity
        self.scrapers: List[BaseScraper] = [
            RequestScraper(),
            AiohttpScraper(),
            PlaywrightScraper()
        ]
        
        self.stopped = False

    async def _try_scraper(self, scraper: BaseScraper, url: str) -> Optional[ScrapedContent]:
        """
        Try scraping with a specific scraper implementation.
        
        Args:
            scraper: Scraper to use
            url: URL to scrape
            
        Returns:
            Optional[ScrapedContent]: Scraped content if successful
        """
        try:
            if not await scraper.is_suitable(url):
                return None
                
            logger.info(f"Trying {scraper.__class__.__name__} for {url}")
            return await scraper.scrape(url)
            
        except Exception as e:
            logger.error(f"Error with {scraper.__class__.__name__}: {e}")
            return None

    async def _save_result(self, content: ScrapedContent) -> None:
        """
        Save scraped content to the API.
        
        Args:
            content: Scraped content to save
        """
        try:
            link = ScrapedLink(
                link=content.url,
                session=self.session,
                status=content.status,
                error=content.error,
                content=content.content,
                title=content.title
            )
            
            await api_client.save_scraped_link(link)
            
        except Exception as e:
            logger.error(f"Error saving result: {e}")

    async def process_url(self, url: str) -> bool:
        """
        Process a single URL using available scrapers.
        
        Args:
            url: URL to process
            
        Returns:
            bool: True if processing was successful
        """
        if not await is_valid_url(url):
            logger.warning(f"Invalid URL: {url}")
            await self._save_result(ScrapedContent(
                url=url,
                content="",
                title="",
                status="error",
                error="Invalid URL"
            ))
            return True

        # Try each scraper in order until one succeeds
        for scraper in self.scrapers:
            try:
                if result := await self._try_scraper(scraper, url):
                    await self._save_result(result)
                    
                    # If content was successfully extracted, we're done
                    if result.status == "success" and result.content.strip():
                        return True
                        
            except Exception as e:
                logger.error(f"Error with scraper {scraper.__class__.__name__}: {e}")
                continue

        # If all scrapers failed, save error
        await self._save_result(ScrapedContent(
            url=url,
            content="",
            title="",
            status="error",
            error="All scrapers failed"
        ))
        return True

    async def run(self) -> None:
        """Main scraping loop."""
        logger.info(f"Starting scraper worker {self.worker_id}")
        
        try:
            while not self.stopped:
                # Get next URL from API
                next_url = await api_client.get_next_url(
                    session=self.session,
                    institution_id=self.institution_id
                )
                
                if not next_url:
                    logger.info("No more URLs to process")
                    await asyncio.sleep(10)
                    continue

                # Process URL
                try:
                    await self.process_url(next_url.link)
                except Exception as e:
                    logger.error(f"Error processing URL {next_url.link}: {e}")
                finally:
                    gc.collect()

                # Brief pause between URLs
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Fatal error in scraper: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources."""
        for scraper in self.scrapers:
            try:
                await scraper.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up scraper: {e}")

        try:
            await api_client.close()
        except Exception as e:
            logger.error(f"Error closing API client: {e}")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Web scraper worker')
    parser.add_argument('--session', type=str, required=True,
                      help='Session ID for the scraping run')
    parser.add_argument('--worker-id', type=str, required=True,
                      help='Unique worker identifier')
    parser.add_argument('--workers', type=int, default=5,
                      help='Number of concurrent workers')
    parser.add_argument('--max-memory', type=float, default=80,
                      help='Maximum memory usage percentage')
    parser.add_argument('--max-temp', type=float, default=75,
                      help='Maximum CPU temperature')
    parser.add_argument('--institution-id', type=str,
                      help='Institution ID for filtering URLs')
    return parser.parse_args()

async def main():
    """Main entry point."""
    args = parse_arguments()
    setup_logging()
    
    orchestrator = ScraperOrchestrator(
        session=args.session,
        worker_id=args.worker_id,
        institution_id=args.institution_id
    )
    
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 