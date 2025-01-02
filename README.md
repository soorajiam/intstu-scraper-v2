# Dockerized Web Scraper

A robust, scalable web scraping system with multi-tiered scraping strategies and Docker support.

## Features

- **Multi-tiered Scraping**: Uses multiple scraping strategies (requests, aiohttp, Playwright) for optimal content extraction
- **Docker Support**: Fully containerized for consistent deployment
- **Resource Management**: Monitors system resources (CPU, memory) to prevent overload
- **Scalable**: Supports multiple worker processes
- **Error Handling**: Comprehensive error handling and recovery mechanisms
- **Logging**: Detailed logging with rotation support
- **API Integration**: Built-in API client for data storage and retrieval

## Architecture

The system consists of several key components:

1. **Worker Manager**: Orchestrates multiple scraper workers
2. **Scraper Workers**: Individual scraping processes with three-tiered approach:
   - Basic Request Scraper (for simple static pages)
   - Aiohttp Scraper (for async HTTP requests)
   - Playwright Scraper (for JavaScript-heavy pages)
3. **Content Processing**: Cleans and converts HTML to markdown
4. **API Client**: Handles communication with external API

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- API credentials (see Configuration section)

## Quick Start

1. Clone the repository: 