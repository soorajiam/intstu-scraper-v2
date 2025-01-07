"""Link extraction and validation functionality."""

import logging
from typing import Set, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .url import is_valid_url, is_likely_download_url

logger = logging.getLogger(__name__)

class LinkHandler:
    """Handles link extraction and validation."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.seen_links: Set[str] = set()

    async def process_links(self, html_content: str) -> List[str]:
        """
        Extract all links from HTML content and validate them.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            List[str]: List of valid links
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            all_links = []
            
            # Extract all links from anchor tags
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                # Skip empty or non-HTTP links
                if not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                    continue

                # Convert relative to absolute URLs
                try:
                    absolute_url = urljoin(self.base_url, href)
                except Exception as e:
                    logger.error(f"Error resolving URL {href}: {e}")
                    continue

                # Basic URL validation
                try:
                    parsed = urlparse(absolute_url)
                    if not all([parsed.scheme, parsed.netloc]):
                        continue
                    if parsed.scheme not in ['http', 'https']:
                        continue
                except Exception:
                    continue

                # Skip if already seen
                if absolute_url in self.seen_links:
                    continue

                # Skip download URLs
                if await is_likely_download_url(absolute_url):
                    continue

                # Add to collection
                self.seen_links.add(absolute_url)
                all_links.append(absolute_url)

            logger.info(f"Extracted {len(all_links)} valid links")
            return all_links

        except Exception as e:
            logger.error(f"Error extracting links: {e}", exc_info=True)
            return [] 