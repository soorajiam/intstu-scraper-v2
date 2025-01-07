"""
Base scraper class defining the interface for all scraper implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Set
from bs4 import BeautifulSoup

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
        html: Optional[str]: Raw HTML before cleaning
    """
    url: str
    content: str
    title: str
    status: str
    error: str = ""
    html: Optional[str] = None

class BaseScraper(ABC):
    """
    Abstract base class for all scraper implementations.
    Defines the interface and common functionality.
    """

    def __init__(self):
        """Initialize base scraper."""
        self.resource_cost = 1.0  # Base resource cost, higher means more intensive
        
    @abstractmethod
    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from the given URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent: Scraped content and metadata
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the scraper."""
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
        
    async def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title from BeautifulSoup object."""
        try:
            # Try meta title first
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content'].strip()
                
            # Try regular title
            if soup.title and soup.title.string:
                return soup.title.string.strip()
                
            # Try h1
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)
                
        except Exception:
            pass
            
        return ""
        
    async def should_retry(self, error: Exception) -> bool:
        """
        Check if scraping should be retried based on error.
        
        Args:
            error: Exception that occurred
            
        Returns:
            bool: True if should retry
        """
        # Check for common retryable errors
        retryable_messages = [
            'timeout', 
            'connection reset',
            'too many requests',
            'server error',
            'gateway timeout',
            'service unavailable'
        ]
        
        error_str = str(error).lower()
        return any(msg in error_str for msg in retryable_messages) 