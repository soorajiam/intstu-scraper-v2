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
        self.session = None
        self.session_id = None  # Will be set when starting a scraping session
        
        if not all([self.base_url, self.api_token, self.user_id]):
            raise ValueError("Missing required environment variables")
            
        # # Ensure proper token format
        # if not self.api_token.startswith('Token '):
        #     self.api_token = f'Token {self.api_token}'
            
        self.headers = {
            'bearer': self.api_token,
            'user-id': str(self.user_id),
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
        Extracts error messages from both JSON responses and Django debug pages.
        
        Args:
            response: API response
            context: Context of the API call for logging
        """
        try:
            error_text = await response.text()
            error_message = None
            error_details = []
            
            # Try to parse Django debug page
            if error_text.startswith('<!DOCTYPE html>') or error_text.startswith('<html'):
                import re
                
                # Extract detailed error information
                debug_sections = {
                    'Exception Type': r'<th>Exception Type:</th>\s*<td>([^<]+)</td>',
                    'Exception Value': r'<th>Exception Value:</th>\s*<td><pre>([^<]+)</pre>',
                    'Exception Location': r'<th>Exception Location:</th>\s*<td>([^<]+)</td>',
                    'Python Path': r'<th>Python Path:</th>\s*<td>([^<]+)</td>',
                    'Request Method': r'<th>Request Method:</th>\s*<td>([^<]+)</td>',
                    'Request URL': r'<th>Request URL:</th>\s*<td>([^<]+)</td>',
                    'Django Version': r'<th>Django Version:</th>\s*<td>([^<]+)</td>',
                    'Request Headers': r'<th>Request Headers:</th>\s*<td>([^<]+)</td>'
                }
                
                for section, pattern in debug_sections.items():
                    match = re.search(pattern, error_text, re.DOTALL)
                    if match:
                        value = match.group(1).strip()
                        error_details.append(f"{section}: {value}")
                
                # Try to get traceback
                traceback_match = re.search(r'<div class="commands"><pre>([^<]+)</pre>', error_text, re.DOTALL)
                if traceback_match:
                    error_details.append("\nTraceback:")
                    error_details.append(traceback_match.group(1).strip())
                
                # Get the main error message
                error_patterns = [
                    r'<pre class="exception_value">([^<]+)</pre>',
                    r'<title>([^<]+)</title>',
                    r'<div id="summary">\s*<h1>([^<]+)</h1>'
                ]
                
                for pattern in error_patterns:
                    match = re.search(pattern, error_text, re.DOTALL)
                    if match:
                        error_message = match.group(1).strip()
                        break
                
                if not error_message:
                    error_message = "Django debug page received (could not extract specific error)"
                
                # Save the full debug page
                debug_log_path = f"log/django_debug_{int(time.time())}.html"
                os.makedirs("log", exist_ok=True)
                with open(debug_log_path, "w") as f:
                    f.write(error_text)
                error_details.append(f"\nFull debug page saved to: {debug_log_path}")
                
            else:
                # Try to parse as JSON
                try:
                    error_data = await response.json()
                    error_message = error_data.get('message') or error_data.get('error') or error_text
                except:
                    error_message = error_text.strip()

            # Clean up and format the error message
            if error_message:
                error_message = re.sub(r'\s+', ' ', error_message)  # Normalize whitespace
                error_message = error_message.strip()

            # Log the error with context and status code
            if response.status == 500:
                logger.error(f"""
❌ API Server Error (500) in {context}
Status: {response.status}
URL: {response.url}
Error: {error_message}
Headers: {dict(response.headers)}
Detailed Error Information:
{'='*50}
{chr(10).join(error_details)}
{'='*50}
""")
            else:
                logger.error(f"""
❌ API Error in {context}
Status: {response.status}
URL: {response.url}
Error: {error_message}
Headers: {dict(response.headers)}
Detailed Error Information:
{'='*50}
{chr(10).join(error_details)}
{'='*50}
""")

        except Exception as e:
            logger.error(f"Failed to process error response: {e}")
            logger.error(f"Original response status: {response.status}")
            logger.error(f"Original response headers: {dict(response.headers)}")
            try:
                logger.error(f"Response text: {await response.text()}")
            except:
                pass

    async def get_next_url(self, session: str, institution_id: Optional[str] = None) -> Optional[NextUrlResponse]:
        """Get next URL to scrape from the API."""
        max_retries = 5
        attempt = 0
        
        while attempt < max_retries:
            try:
                await self._ensure_session()

                params = {'session': session}
                if institution_id:
                    params['institution_id'] = institution_id
                
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
                    
                    if response.status == 429:  # Rate limited
                        logger.warning("⏰ Rate limit reached")
                        await self.exponential_sleep(attempt)
                        attempt += 1
                        continue
                    
                    if response.status == 204:  # No content
                        logger.info("📭 No more URLs to process (204 status)")
                        # Add longer sleep for no content to prevent hammering
                        await asyncio.sleep(10)
                        return None
                        
                    if response.status == 400:
                        response_text = await response.text()
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('error', response_text)
                            
                            # Handle specific error cases
                            if "invalid institution" in error_msg.lower():
                                logger.error(f"Invalid institution ID: {institution_id}")
                                return None
                                
                            logger.error(f"API Error: {error_msg}")
                            
                        except:
                            logger.error(f"API Error: {response_text}")
                            
                        await asyncio.sleep(5)
                        attempt += 1
                        continue
                    
                    if response.status != 200:
                        await self._handle_api_error(response, "get_next_url")
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
        await asyncio.sleep(30)  # Longer sleep after max retries
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
                
                if response.status == 429:  # Rate limited
                    logger.warning("Rate limit reached, backing off...")
                    await self.exponential_sleep(0)  # Start with first attempt
                    return False
                
                if response.status == 400:
                    response_text = await response.text()
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('error', response_text)
                        
                        # Handle specific error cases
                        if "link not found" in error_msg.lower():
                            logger.warning(f"Link not found in database: {link.link}")
                            return False
                            
                        if "invalid session" in error_msg.lower():
                            logger.error("Invalid session ID")
                            return False
                            
                        logger.error(f"API Error: {error_msg}")
                        return False
                        
                    except:
                        logger.error(f"API Error: {response_text}")
                        return False
                
                if response.status not in (200, 201):
                    await self._handle_api_error(response, "save_scraped_link")
                    return False
                
                # Parse successful response
                try:
                    response_data = await response.json()
                    if response_data.get('message') == 'Link check saved successfully':
                        logger.info("Successfully saved link check result")
                        return True
                except Exception as e:
                    logger.error(f"Error parsing success response: {e}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving link check: {e}")
            return False

    async def save_new_links(self, links: List[str]) -> bool:
        """Save newly discovered links to the API."""
        if not links:
            return True
        
        try:
            await self._ensure_session()
            
            payload = {
                'links': list(set(links))  # Remove duplicates
            }
            
            logger.info(f"Saving {len(links)} new links to API")
            
            async with self.session.post(
                f'{self.base_url}/institutes/scraper/links/add/',
                json=payload,
                ssl=False
            ) as response:
                if response.status == 429:  # Rate limited
                    logger.warning("Rate limit reached, backing off...")
                    await self.exponential_sleep(0)  # Start with first attempt
                    return False
                    
                if response.status == 400:
                    response_text = await response.text()
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('error', response_text)
                        
                        # Handle case where all links exist
                        if "all provided links already exist" in error_msg.lower():
                            logger.info("All links already exist in database")
                            return True
                            
                        # Handle case where no matching institutions found
                        if "no matching institutions found" in error_msg.lower():
                            logger.warning("No matching institutions for provided links")
                            return True
                            
                        logger.error(f"API Error: {error_msg}")
                        return False
                        
                    except:
                        logger.error(f"API Error: {response_text}")
                        return False
                
                if response.status not in (200, 201):
                    response_text = await response.text()
                    logger.error(f"Failed to save links: HTTP {response.status} - {response_text}")
                    return False
                
                # Parse successful response
                try:
                    response_data = await response.json()
                    if 'links' in response_data:
                        saved_count = len(response_data['links'])
                        logger.info(f"Successfully saved {saved_count} new links")
                        return True
                except Exception as e:
                    logger.error(f"Error parsing success response: {e}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving links to API: {e}", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the API client and cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None

    async def start_session(self, session_id: str) -> None:
        """Start a new scraping session."""
        self.session_id = session_id

# Create singleton instance
api_client = ApiClient() 