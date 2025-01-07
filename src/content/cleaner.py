"""
Content cleaning and processing functionality.
Handles HTML cleaning, content extraction, and markdown conversion.
"""

import re
import logging
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import Set, Optional
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
    """Cleans and processes HTML content."""
    
    def __init__(self):
        """Initialize the content cleaner."""
        self.min_content_length = 100
        self.content_elements = {
            'p': 1,
            'article': 2,
            'main': 2,
            'section': 1.5,
            'div': 0.5,
            'h1': 2,
            'h2': 2,
            'h3': 1.5,
            'h4': 1,
            'h5': 1,
            'h6': 1,
            'ul': 1,
            'ol': 1,
            'table': 1.5,
            'pre': 1.5,
            'code': 1.5
        }

    async def clean_html_content(self, html_content: str) -> str:
        """
        Clean HTML content and convert to markdown.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            str: Cleaned markdown content
        """
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            self._remove_unwanted_elements(soup)
            
            # Find best content container
            best_element = self._find_content_container(soup)
            if not best_element:
                return ""
                
            # Convert to markdown
            markdown = self._convert_to_markdown(str(best_element))
            
            # Clean markdown
            cleaned = self._clean_markdown(markdown)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning content: {e}")
            return ""

    def _find_content_container(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the element containing the main content."""
        candidates = []
        
        # First look for common content identifiers
        content_selectors = [
            'main', 'article', '#main-content', '.main-content', '#content', '.content',
            '[role="main"]', '.page-content', '.entry-content', '.article-content',
            '#primary', '.primary', '#main', '.main', '.post-content',
            'div[class*="content"]', 'div[id*="content"]',
            'div[class*="main"]', 'div[id*="main"]'
        ]
        
        # Try each selector
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                score = self._calculate_content_score(element)
                if score > 0:
                    candidates.append((score, element))
        
        # If no content found with selectors, try semantic elements
        if not candidates:
            for tag in ['article', 'main', 'div', 'section']:
                elements = soup.find_all(tag)
                for element in elements:
                    score = self._calculate_content_score(element)
                    if score > 0:
                        candidates.append((score, element))
        
        # If still no candidates, try the body
        if not candidates and soup.body:
            score = self._calculate_content_score(soup.body)
            if score > 0:
                candidates.append((score, soup.body))
            
        if not candidates:
            return None
            
        # Return element with highest score
        return max(candidates, key=lambda x: x[0])[1]

    def _calculate_content_score(self, element) -> float:
        """Calculate content value score for an element."""
        if not element:
            return 0
            
        score = 0
        text = element.get_text(strip=True)
        
        # Base score from text length
        if len(text) < self.min_content_length:
            return 0
        score += len(text) / 50
        
        # Score from content elements
        for child in element.find_all(True):
            if child.name in self.content_elements:
                score += self.content_elements[child.name]
                
                # Extra points for semantic elements
                if child.name in ['article', 'main', 'section']:
                    score *= 1.2
                    
                # Extra points for headings with meaningful text
                if child.name.startswith('h') and len(child.get_text(strip=True)) > 10:
                    score += 3
                    
                # Extra points for substantial paragraphs
                if child.name == 'p' and len(child.get_text(strip=True)) > 20:
                    score += 2
                    
                # Points for lists with multiple items
                if child.name in ['ul', 'ol']:
                    items = child.find_all('li')
                    if items:
                        score += len(items) * 0.5
                        
                # Points for tables with data
                if child.name == 'table':
                    rows = child.find_all('tr')
                    if rows:
                        score += len(rows) * 0.5
                        
                # Points for code blocks
                if child.name in ['pre', 'code']:
                    score += 3
                    
        # Check for content-related classes/IDs
        classes = element.get('class', [])
        element_id = element.get('id', '')
        
        content_terms = ['content', 'article', 'post', 'entry', 'text', 'body', 'main']
        for term in content_terms:
            if any(term in cls.lower() for cls in classes) or term in element_id.lower():
                score *= 1.5
                
        # Penalize for too many links
        links = element.find_all('a')
        if links:
            link_text = sum(len(link.get_text(strip=True)) for link in links)
            if link_text / len(text) > 0.6:  # More than 60% links
                score *= 0.5
                
        # Penalize elements with ads/tracking classes
        if any(c for c in classes if 'ad' in c.lower() or 'track' in c.lower()):
            score *= 0.3
            
        return score

    def _clean_markdown(self, content: str) -> str:
        """Clean and format markdown content."""
        if not content:
            return ""
            
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Keep headers, lists, and substantial text
            if (line.startswith('#') or
                line.startswith('-') or
                line.startswith('*') or
                line.startswith('1.') or
                len(line) > 20):
                lines.append(line)
                
        return '\n\n'.join(lines)

    def _convert_to_markdown(self, content: str) -> str:
        """Convert HTML to markdown while preserving structure."""
        # Configure markdownify options
        md_options = {
            'heading_style': 'ATX',  # Use # style headings
            'bullets': '-',          # Use - for unordered lists
            'autolinks': True,
            'code_language': '',     # Don't add language tags to code blocks
            'default_title': True,   # Use alt text as image titles
            'escape_asterisks': True,
            'escape_underscores': True,
            'heading_style': 'ATX',
            'strip': None,           # Don't strip any tags by default
            'wrap': True,            # Wrap lines
            'convert': [             # Only convert these tags
                'p', 'div', 'span',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li',
                'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'img', 'hr',
                'br',
                'b', 'strong', 'i', 'em', 'a',
                'pre', 'code',
                'blockquote',
                'section', 'article', 'main',
                'dl', 'dt', 'dd',
                'figure', 'figcaption'
            ]
        }
        
        try:
            # Convert to markdown
            markdown = md(content, **md_options)
            
            # Clean up markdown
            lines = []
            in_table = False
            in_list = False
            
            for line in markdown.split('\n'):
                line = line.strip()
                if line:
                    # Preserve table structure
                    if '|' in line:
                        if not in_table and '-|-' not in line:
                            # Add table header separator if missing
                            col_count = line.count('|') + 1
                            lines.append('|' + '|'.join(['-' * 3] * col_count) + '|')
                        in_table = True
                        lines.append(line)
                    # Preserve list structure
                    elif line.startswith(('- ', '* ', '1. ')):
                        in_list = True
                        lines.append(line)
                    # Keep headers and substantial text
                    elif (line.startswith('#') or
                          len(line) > 20 or
                          line.startswith('```') or
                          line.startswith('> ')):
                        if in_table or in_list:
                            lines.append('')  # Add spacing after tables/lists
                            in_table = False
                            in_list = False
                        lines.append(line)
                else:
                    # Add spacing between sections
                    if lines and not lines[-1] == '':
                        lines.append('')
                    in_table = False
                    in_list = False
                        
            return '\n'.join(lines)
            
        except Exception as e:
            logger.error(f"Error converting to markdown: {e}", exc_info=True)
            # Fallback to basic text extraction if markdown conversion fails
            soup = BeautifulSoup(content, 'html.parser')
            return soup.get_text(separator='\n\n', strip=True)

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove unwanted elements from the soup."""
        # Remove script and style elements
        for tag in soup.find_all(['script', 'style', 'iframe', 'noscript']):
            tag.decompose()
        
        # Remove navigation elements but be less aggressive
        nav_elements = ['nav', 'header', 'footer']
        for tag in nav_elements:
            for element in soup.find_all(tag):
                # Keep if it might contain main content
                if not self._is_navigation_element(element):
                    continue
                element.decompose()
        
        # Remove elements with unwanted classes/ids
        unwanted_patterns = [
            'nav', 'menu', 'sidebar', 'footer', 'header', 
            'banner', 'social', 'share', 'widget', 'cookie',
            'popup', 'modal', 'advertisement', 'ad-'
        ]
        
        for pattern in unwanted_patterns:
            for element in soup.find_all(class_=lambda x: x and pattern in x.lower()):
                if not self._might_contain_content(element):
                    element.decompose()
            for element in soup.find_all(id=lambda x: x and pattern in x.lower()):
                if not self._might_contain_content(element):
                    element.decompose()

    def _is_navigation_element(self, element) -> bool:
        """Check if an element is likely a navigation element."""
        # Check if element contains significant content
        text_length = len(element.get_text(strip=True))
        if text_length > 500:  # Don't remove elements with substantial text
            return False
            
        # Check for navigation-related classes
        classes = element.get('class', [])
        nav_terms = ['nav', 'menu', 'breadcrumb', 'pagination']
        if any(term in cls.lower() for cls in classes for term in nav_terms):
            return True
            
        # Check link density
        links = element.find_all('a')
        if links:
            text_length = len(element.get_text(strip=True))
            link_text_length = sum(len(link.get_text(strip=True)) for link in links)
            if link_text_length / text_length > 0.8:  # 80% of text is links
                return True
                
        return False

    def _might_contain_content(self, element) -> bool:
        """Check if an element might contain main content."""
        # Check text length
        text = element.get_text(strip=True)
        if len(text) > 200:  # Don't remove elements with substantial text
            return True
            
        # Check for content-related classes
        classes = element.get('class', [])
        content_terms = ['content', 'article', 'post', 'entry', 'text', 'body']
        if any(term in cls.lower() for cls in classes for term in content_terms):
            return True
            
        # Check for headings with content
        headings = element.find_all(['h1', 'h2', 'h3'])
        if any(len(h.get_text(strip=True)) > 20 for h in headings):
            return True
            
        return False

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