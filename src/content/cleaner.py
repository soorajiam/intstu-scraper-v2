"""
Content cleaning and processing functionality.
Handles HTML cleaning, content extraction, and markdown conversion.
"""

import re
import logging
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import Set
from dataclasses import dataclass

from .patterns import (
    HIDDEN_STYLE_PATTERN,
    CLUTTER_CLASS_PATTERN,
    JS_ERROR_PATTERN,
    HIDDEN_CLASSES,
    UNWANTED_ELEMENTS,
    CLUTTER_CLASSES,
    CONTENT_CLASSES
)

logger = logging.getLogger(__name__)

@dataclass
class CleaningStats:
    """Statistics about the cleaning process."""
    initial_length: int
    removed_elements: int
    final_length: int
    processing_time: float

class ContentCleaner:
    """
    Handles cleaning and processing of HTML content.
    Removes unwanted elements, converts to markdown, and ensures quality output.
    """

    def __init__(self):
        """Initialize the content cleaner."""
        self.soup = None
        self.removed_count = 0

    async def clean_html_content(self, html_content: str) -> str:
        """
        Clean HTML content by removing unwanted elements and converting to markdown.
        
        Args:
            html_content: Raw HTML content to clean
            
        Returns:
            str: Cleaned and converted markdown content
        """
        if not html_content:
            logger.warning("Received empty HTML content")
            return ""
            
        try:
            # Parse HTML
            self.soup = BeautifulSoup(html_content, 'html.parser')
            initial_text_length = len(self.soup.get_text(strip=True))
            
            # Remove unwanted elements
            await self._remove_unwanted_elements()
            await self._remove_hidden_elements()
            await self._remove_clutter()
            await self._remove_empty_elements()
            
            # Convert to markdown
            markdown_content = await self._convert_to_markdown()
            
            # Clean up markdown
            cleaned_markdown = await self._clean_markdown(markdown_content)
            
            final_length = len(cleaned_markdown)
            logger.info(
                f"Content cleaning stats - "
                f"Initial: {initial_text_length} chars, "
                f"Final: {final_length} chars, "
                f"Removed: {self.removed_count} elements"
            )
            
            return cleaned_markdown
            
        except Exception as e:
            logger.error(f"Error cleaning content: {e}")
            return ""
        finally:
            self.soup = None
            self.removed_count = 0

    async def _remove_unwanted_elements(self) -> None:
        """Remove elements with unwanted tags."""
        for tag in UNWANTED_ELEMENTS:
            for element in self.soup.find_all(tag):
                element.decompose()
                self.removed_count += 1

    async def _remove_hidden_elements(self) -> None:
        """Remove hidden elements based on styles and classes."""
        # Remove elements with hidden styles
        for element in self.soup.find_all(style=HIDDEN_STYLE_PATTERN):
            element.decompose()
            self.removed_count += 1
            
        # Remove elements with hidden classes
        for class_name in HIDDEN_CLASSES:
            for element in self.soup.find_all(class_=class_name):
                element.decompose()
                self.removed_count += 1

    async def _remove_clutter(self) -> None:
        """Remove clutter elements like ads, social media, etc."""
        for element in self.soup.find_all(class_=CLUTTER_CLASS_PATTERN):
            element.decompose()
            self.removed_count += 1
            
        for class_name in CLUTTER_CLASSES:
            for element in self.soup.find_all(class_=class_name):
                element.decompose()
                self.removed_count += 1

    async def _remove_empty_elements(self) -> None:
        """Remove elements with no meaningful content."""
        for element in self.soup.find_all():
            if not element.get_text(strip=True) and element.name not in ['img', 'br', 'hr']:
                element.decompose()
                self.removed_count += 1

    async def _convert_to_markdown(self) -> str:
        """Convert cleaned HTML to markdown."""
        try:
            return md(str(self.soup), heading_style="ATX", bullets="-")
        except Exception as e:
            logger.error(f"Markdown conversion failed: {e}")
            return ""

    async def _clean_markdown(self, content: str) -> str:
        """
        Clean and format markdown content.
        
        Args:
            content: Raw markdown content
            
        Returns:
            str: Cleaned markdown content
        """
        if not content:
            return ""
            
        lines = content.split('\n')
        valid_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Keep lines that are:
            # - Headers (# Header)
            # - List items (- item or 1. item)
            # - Have meaningful content (>3 chars)
            # - Tables (| column |)
            if (len(stripped) > 3 or 
                re.match(r'^#{1,6}\s', stripped) or  # Headers
                re.match(r'^[-*+]\s', stripped) or   # List items
                re.match(r'^\d+\.\s', stripped) or   # Numbered lists
                re.match(r'^\|.*\|$', stripped)):    # Tables
                valid_lines.append(line)
                
        # Join lines and clean up excessive newlines
        result = '\n'.join(valid_lines)
        result = re.sub(r'(\n\s*){3,}', '\n\n', result).strip()
        
        return result

# Create singleton instance
content_cleaner = ContentCleaner()

async def clean_html_content(html_content: str) -> str:
    """
    Public interface for cleaning HTML content.
    
    Args:
        html_content: Raw HTML content to clean
        
    Returns:
        str: Cleaned markdown content
    """
    return await content_cleaner.clean_html_content(html_content) 