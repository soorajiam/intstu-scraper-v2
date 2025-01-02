"""
API client for interacting with the scraping API.
Handles authentication, rate limiting, and data transfer.
"""

import aiohttp
import logging
import asyncio
from typing import Optional, Dict, Any, List
import os
from datetime import datetime
import time
from urllib.parse import urlparse
import random

from .models import NextUrlResponse, ScrapedLink, NewLinks, ApiError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ApiClient:
    """
    Client for interacting with the scraping API.
    Handles authentication, rate limiting, and all API operations.
    """

    def __init__(self):
        """Initialize the API client with configuration from environment."""
        self.base_url = os.getenv('API_BASE_URL')
        self.api_token = os.getenv('API_TOKEN')
        self.user_id = os.getenv('USER_ID')
        
        if not all([self.base_url, self.api_token, self.user_id]):
            raise ValueError("API_BASE_URL, API_TOKEN, and USER_ID must be set")
            
        self.headers = {
            'bearer': self.api_token,
            'user-id': self.user_id,
            'Content-Type': 'application/json'
        }
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = datetime.min

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def exponential_sleep(self, attempt: int, max_delay: int = 300) -> None:
        """Sleep with exponential backoff."""
        delay = min(2 ** attempt, max_delay)
        jitter = random.uniform(0, 0.1 * delay)
        total_delay = delay + jitter
        logger.info(f"⏰ Rate limited. Waiting {total_delay:.1f} seconds before retry (attempt {attempt + 1})")
        await asyncio.sleep(total_delay)

    async def check_connection(self) -> bool:
        """Check if the API server is accessible."""
        try:
            await self._ensure_session()
            async with self.session.get(
                f'{self.base_url}/institutes/scraper/links/next/',
                params={'session': 'connection_test'},
                timeout=5,
                ssl=False
            ) as response:
                if response.status not in (200, 204, 401, 403):
                    logger.error(f"❌ API connection check failed with status {response.status}")
                    return False
                return True
        except aiohttp.ClientConnectorError as e:
            logger.error(f"❌ Cannot connect to API server: {e}")
            logger.error(f"🔍 Please ensure:")
            logger.error(f"1️⃣ Your API server is running at {self.base_url}")
            logger.error(f"2️⃣ The port {urlparse(self.base_url).port} is correct and open")
            logger.error(f"3️⃣ If running locally, the server is bound to {urlparse(self.base_url).hostname}")
            return False
        except aiohttp.ClientSSLError as e:
            logger.error(f"🔒 SSL Error connecting to API: {e}")
            logger.error("💡 If using localhost, try using http:// instead of https://")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking API connection: {e}")
            return False

    async def _handle_api_error(self, response: aiohttp.ClientResponse, context: str) -> None:
        """
        Handle API error responses with detailed logging.
        
        Args:
            response: API response
            context: Context of the API call for logging
        """
        try:
            error_text = await response.text()
            
            # Try to extract error message from HTML
            if error_text.startswith('<!DOCTYPE html>') or error_text.startswith('<html'):
                # Extract title content which usually contains the error in Django debug pages
                import re
                title_match = re.search(r'<title>(.*?)</title>', error_text, re.DOTALL)
                if title_match:
                    error_message = title_match.group(1).strip()
                    # Clean up the error message
                    error_message = re.sub(r'\s+at\s+/\w+.*$', '', error_message)  # Remove the URL path
                    error_message = error_message.strip()
                else:
                    error_message = "HTML error page received"
            else:
                try:
                    # Try to parse as JSON
                    error_data = await response.json()
                    error_message = error_data.get('message', error_data.get('error', error_text))
                except:
                    # If not JSON, use text directly
                    error_message = error_text

            # Clean up and truncate the message
            error_message = error_message.strip()
            if len(error_message) > 1000:
                error_message = error_message[:1000] + "..."

            if response.status == 500:
                logger.error(f"❌ API Server Error (500) in {context}: {error_message}")
            else:
                logger.error(f"❌ API Error ({response.status}) in {context}: {error_message}")

        except Exception as e:
            logger.error(f"❌ Failed to read error response: {e}")

    async def get_next_url(self, session: str, institution_id: Optional[str] = None) -> Optional[NextUrlResponse]:
        """Get next URL to scrape from the API."""
        max_retries = 5
        attempt = 0
        
        while attempt < max_retries:
            try:
                await self._ensure_session()

                if institution_id:
                    params = {
                        'session': session,
                        'institution_id': institution_id
                    }
                else:
                    params = {
                        'session': session,
                    }
                params = {k: v for k, v in params.items() if v is not None}
                
                logger.info(f"🎯 Requesting next URL with params: {params}")
                
                start_time = time.time()
                async with self.session.get(
                    f'{self.base_url}/institutes/scraper/links/next/',
                    params=params,
                    timeout=30,
                    ssl=False
                ) as response:
                    end_time = time.time()
                    logger.info(f"⏱️ GET NEXT URL responded in {end_time - start_time:.4f} seconds")
                    
                    response_text = await response.text()
                    
                    if response.status == 204:
                        logger.info("📭 No more URLs to process (204 status)")
                        await asyncio.sleep(10)
                        continue
                        
                    if response.status == 429:  # Rate limited
                        logger.warning("⏰ Rate limit reached")
                        await self.exponential_sleep(attempt)
                        attempt += 1
                        continue
                        
                    if response.status != 200:
                        try:
                            error_data = await response.json()
                            if 'data' in error_data and 'error' in error_data['data']:
                                error_msg = error_data['data']['error']
                            else:
                                error_msg = error_data.get('detail', response_text)
                        except:
                            if response_text.startswith('<!DOCTYPE html>') or response_text.startswith('<html'):
                                import re
                                error_match = re.search(r'<pre class="exception_value">(.*?)</pre>', response_text, re.DOTALL)
                                if error_match:
                                    error_msg = error_match.group(1).strip()
                                else:
                                    title_match = re.search(r'<title>(.*?)</title>', response_text, re.DOTALL)
                                    error_msg = title_match.group(1).strip() if title_match else response_text
                            else:
                                error_msg = response_text.strip()

                        logger.error(f"❌ API Error ({response.status}): {error_msg}")
                        await asyncio.sleep(5)
                        attempt += 1
                        continue
                        
                    try:
                        data = await response.json()
                        if data and 'data' in data and data['data'].get('link'):
                            return NextUrlResponse(
                                link=data['data']['link'],
                                institution_id=data['data'].get('institution_id'),
                                metadata=data['data'].get('metadata', {})
                            )
                        logger.warning(f"Invalid or empty response data: {data}")
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"❌ Error parsing response JSON: {e}")
                        await asyncio.sleep(5)
                        
            except Exception as e:
                logger.error(f"❌ Error getting next URL: {str(e)}")
                
            attempt += 1
            await asyncio.sleep(5)
            
        logger.error("🔄 Max retries reached when getting next URL")
        await asyncio.sleep(30)
        return None

    async def save_scraped_link(self, link: ScrapedLink) -> bool:
        """Save the results of checking a link."""
        try:
            await self._ensure_session()
            
            payload = {
                'link': link.link,
                'session_id': link.session,
                'status': link.status,
                'error': link.error or None,
                'content': link.content or None,
                'title': link.title or None
            }
            
            start_time = time.time()
            async with self.session.post(
                f'{self.base_url}/institutes/scraper/links/check/',
                json=payload,
                ssl=False
            ) as response:
                end_time = time.time()
                logger.info(f"⏱️ Saving scraped page responded in {end_time - start_time:.4f} seconds")
                
                if response.status != 200:
                    response_text = await response.text()
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('message', error_data.get('error', response_text))
                    except:
                        error_msg = response_text.strip()
                    logger.error(f"❌ API Error ({response.status}): {error_msg}")
                    return False
                    
                return True
                
        except Exception as e:
            logger.error(f"❌ Error saving link check: {e}")
            return False

    async def save_new_links(self, links: List[str]) -> bool:
        """Save newly discovered links to the API."""
        if not links:
            return True
            
        try:
            await self._ensure_session()
            
            payload = {
                'links': list(set(links))
            }
            
            logger.info(f"💾 Adding {len(links)} new links to collection")
            
            start_time = time.time()
            async with self.session.post(
                f'{self.base_url}/institutes/scraper/links/add/',
                json=payload,
                ssl=False
            ) as response:
                end_time = time.time()
                logger.info(f"⏱️ SAVE NEW LINKS responded in {end_time - start_time:.4f} seconds")
                
                if response.status == 500:
                    await self._handle_api_error(response, "save_new_links")
                    return False
                    
                return response.status == 200
                
        except Exception as e:
            logger.error(f"❌ Error saving new links: {e}")
            return False

    async def close(self) -> None:
        """Close the API client and cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None

# Create singleton instance
api_client = ApiClient() 