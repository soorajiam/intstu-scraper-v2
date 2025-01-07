# Web Scraper with Tiered Architecture

A robust web scraping system that implements a tiered approach to content extraction, with automatic fallback mechanisms and intelligent content cleaning.

## Features

- **Tiered Scraping Architecture**
  - Request-based scraping (Tier 1)
  - Async HTTP scraping (Tier 2)
  - Full browser automation (Tier 3)
  
- **Intelligent Content Processing**
  - Semantic structure preservation
  - Navigation/clutter removal
  - Markdown conversion
  - Table and list retention
  
- **Link Discovery and Validation**
  - Automatic link extraction
  - URL validation and normalization
  - Filter unwanted content types
  - Duplicate detection
  
- **Anti-Detection Measures**
  - Cloudflare bypass
  - Rate limiting
  - User-agent rotation
  - Request retry handling

## Installation

### Using Docker (Recommended)

1. Clone the repository: 