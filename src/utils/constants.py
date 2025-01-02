"""
Shared constants used throughout the scraper application.
"""

from typing import List, Set

# Browser configuration
BROWSER_LAUNCH_ARGS: List[str] = [
    '--disable-blink-features=AutomationControlled',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disable-site-isolation-trials',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--enable-gpu-rasterization',
    '--enable-gpu-compositing',
    '--enable-gpu'
]

# Timeouts (in milliseconds)
PAGE_LOAD_TIMEOUT: int = 60000      # 60 seconds for page load
NETWORK_IDLE_TIMEOUT: int = 30000   # 30 seconds for network idle
DOM_CONTENT_TIMEOUT: int = 30000    # 30 seconds for DOM content
SELECTOR_TIMEOUT: int = 10000       # 10 seconds for selectors

# JavaScript detection patterns
JS_REQUIRED_INDICATORS: Set[str] = {
    # Protection systems
    'captcha',
    'cloudflare',
    'security check',
    'ddos protection',
    'bot protection',
    'human verification',
    'robot verification',
    'browser verification',
    'browser check',
    
    # JavaScript requirements
    'please enable javascript',
    'javascript is required',
    'javascript is disabled',
    'js is required',
    'enable js',
    'enable javascript',
    
    # Loading states
    'loading...',
    'please wait',
    'loading content',
    'loading page',
    'checking your browser',
    'initializing',
    'connecting',
    
    # Access issues
    'access denied',
    'blocked',
    'forbidden',
    '403 forbidden',
    'unauthorized',
    '401 unauthorized',
    
    # Empty content indicators
    'no content available',
    'content not found',
    'page not available',
    
    # Dynamic content markers
    'fetching data',
    'loading data',
    'retrieving content',
    
    # Error states
    'error loading',
    'failed to load',
    'connection error',
    
    # SPA indicators
    'single page application',
    'react root',
    'vue root',
    'angular root',
    'app root',
    
    # Common dynamic content containers
    'data-react-app',
    'data-vue-app',
    'ng-app',
    'ember-app'
}

# API Configuration
MAX_LOG_LENGTH: int = 10000  # Maximum length for log messages

# File extensions to skip
SKIP_EXTENSIONS: Set[str] = {
    # Documents
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.odt', '.ods', '.odp',
    # Archives
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg',
    '.webp',
    # Audio/Video
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.wav',
    '.ogg',
    # Other
    '.exe', '.dmg', '.pkg', '.iso', '.csv', '.xml', '.json',
    '.rss',
    # Web formats
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot'
}

# Download patterns to skip
DOWNLOAD_PATTERNS: List[str] = [
    '/download/',
    '/downloads/',
    '/dl/',
    '/document/',
    '/documents/',
    '/file/',
    '/files/',
    '/attachment/',
    '/attachments/',
    '/export/',
    '/print/'
] 