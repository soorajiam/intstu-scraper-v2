"""
Data models for API requests and responses.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class NextUrlResponse:
    """Response model for next URL endpoint."""
    link: str
    institution_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ScrapedLink:
    """Model for scraped link data."""
    link: str
    session: str
    status: str
    error: str = ""
    content: str = ""
    title: str = ""

@dataclass
class NewLinks:
    """Model for new discovered links."""
    links: List[str]

@dataclass
class ApiError(Exception):
    """Custom exception for API errors."""
    status_code: int
    message: str
    response_text: str = ""

    def __str__(self) -> str:
        return f"API Error ({self.status_code}): {self.message}" 