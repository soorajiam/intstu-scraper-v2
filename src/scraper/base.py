"""
Base scraper class defining the interface for all scraper implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ScrapedContent:
    """
    Data class representing scraped content.
    
    Attributes:
        url (str): URL that was scraped
        content (str): Extracted content
        title (str): Page title
        status (str): Scraping status (success/error)
        error (str): Error message if any
    """
    url: str
    content: str
    title: str
    status: str
    error: str = ""

class BaseScraper(ABC):
    """
    Abstract base class for all scraper implementations.
    
    This class defines the interface that all scrapers must implement.
    """

    @abstractmethod
    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from the given URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
            
        Raises:
            ValueError: If URL is invalid
            Exception: If scraping fails
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up any resources used by the scraper.
        """
        pass

    @abstractmethod
    async def is_suitable(self, url: str) -> bool:
        """
        Check if this scraper is suitable for the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if this scraper can handle the URL
        """
        pass 