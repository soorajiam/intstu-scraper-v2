"""
Main scraper orchestration module.
Coordinates different scraper implementations and handles the scraping workflow.
"""

import asyncio
import logging
from typing import List, Optional
import gc
from urllib.parse import urlparse

from src.scraper.base import BaseScraper, ScrapedContent
from src.scraper.request_scraper import RequestScraper
from src.scraper.aiohttp_scraper import AiohttpScraper
from src.scraper.playwright_scraper import PlaywrightScraper
from src.api.client import api_client
from src.api.models import ScrapedLink
from src.utils.link_handler import LinkHandler
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ScraperOrchestrator:
    """
    Coordinates multiple scraper implementations and manages the scraping workflow.
    Implements a tiered scraping approach, trying simpler scrapers first.
    """

    def __init__(self, session: str, worker_id: str, institution_id: Optional[str] = None):
        """Initialize the scraper orchestrator."""
        self.session = session
        self.worker_id = worker_id
        self.institution_id = institution_id
        
        # Initialize scrapers in order of complexity/resource usage
        self.scrapers: List[BaseScraper] = [
            RequestScraper(),    # Simplest, fastest
            AiohttpScraper(),    # More capable
            PlaywrightScraper()  # Most powerful, resource-heavy
        ]
        
        self.stopped = False
        self.link_handler = None
        
        # Set session ID in API client
        api_client.session_id = session

    async def process_url(self, url: str) -> bool:
        """Process a single URL through the tiered scraping system."""
        # Initialize link handler for this URL
        self.link_handler = LinkHandler(url)
        
        for scraper in self.scrapers:
            try:
                logger.info(f"Trying {scraper.__class__.__name__} for {url}")
                
                if not await scraper.is_suitable(url):
                    logger.debug(f"{scraper.__class__.__name__} not suitable for {url}")
                    continue
                    
                result = await scraper.scrape(url)
                
                # Always try to extract links if we have HTML, regardless of content extraction success
                if result.html:
                    try:
                        # Extract all links from the raw HTML
                        new_links = await self.link_handler.process_links(result.html)
                        
                        if new_links:
                            # Save links to API
                            if await api_client.save_new_links(new_links):
                                logger.info(f"Successfully saved {len(new_links)} new links")
                            else:
                                logger.error("Failed to save new links")
                        else:
                            logger.debug("No new links found")
                            
                    except Exception as e:
                        logger.error(f"Error processing links: {e}", exc_info=True)
                
                # If content extraction was successful, save the content
                if result.status == "success" and result.content:
                    logger.info(f"Successfully scraped {url} with {scraper.__class__.__name__}")
                    await self._save_result(result)
                    return True
                else:
                    logger.warning(f"{scraper.__class__.__name__} failed: {result.error}")
                    
            except Exception as e:
                logger.error(f"Error in {scraper.__class__.__name__} for {url}: {str(e)}", 
                            exc_info=True)
            continue
        
        return False

    async def _save_result(self, result: ScrapedContent) -> None:
        """Save scraping result to API."""
        try:
            link = ScrapedLink(
                link=result.url,
                session=self.session,
                status=result.status,
                error=result.error,
                content=result.content,
                title=result.title
            )
            await api_client.save_scraped_link(link)
        except Exception as e:
            logger.error(f"Error saving result: {e}")

    async def run(self) -> None:
        """Main scraping loop."""
        logger.info(f"Starting scraper worker {self.worker_id}")
        
        try:
            # Ensure API client is initialized with session
            await api_client.start_session(self.session)
            
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