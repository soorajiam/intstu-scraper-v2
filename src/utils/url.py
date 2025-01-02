"""
URL validation and processing utilities.
"""

import logging
from urllib.parse import urlparse
import socket
import os
from typing import Optional

from .constants import SKIP_EXTENSIONS, DOWNLOAD_PATTERNS

logger = logging.getLogger(__name__)

async def is_valid_url(url: str) -> bool:
    """
    Check if URL is valid and well-formed.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if URL is valid
    """
    try:
        parsed = urlparse(url)
        
        # Check basic URL structure
        if not bool(parsed.netloc) or not parsed.scheme:
            return False
            
        # Verify scheme
        if parsed.scheme not in ['http', 'https']:
            return False
            
        # Try to resolve domain
        try:
            socket.gethostbyname(parsed.netloc)
        except socket.gaierror:
            logger.warning(f"Could not resolve domain: {parsed.netloc}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error validating URL {url}: {e}")
        return False

async def is_likely_download_url(url: str) -> bool:
    """
    Check if URL likely points to a downloadable file.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if URL likely points to a download
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check file extension
        ext = os.path.splitext(path)[1]
        if ext in SKIP_EXTENSIONS:
            logger.debug(f"Skipping file download URL: {url}")
            return True
            
        # Check for download patterns
        if any(pattern in url.lower() for pattern in DOWNLOAD_PATTERNS):
            logger.debug(f"Skipping probable download URL: {url}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking download URL {url}: {e}")
        return True  # Err on the side of caution

def truncate_url(url: str, max_length: int = 100) -> str:
    """
    Truncate URL for logging purposes.
    
    Args:
        url: URL to truncate
        max_length: Maximum length
        
    Returns:
        str: Truncated URL
    """
    if len(url) <= max_length:
        return url
    return url[:max_length] + "..." 