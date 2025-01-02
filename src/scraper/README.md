# Scraper Module Documentation

## Overview

The scraper module implements a multi-tiered approach to web scraping, using three different strategies with increasing complexity and capability. This design ensures optimal resource usage while maintaining high success rates.

## Architecture

### Base Scraper

The `BaseScraper` abstract class defines the interface that all scraper implementations must follow: 