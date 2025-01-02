"""
Logging configuration and utilities.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from typing import Optional

def setup_logging(
    debug: bool = False,
    log_dir: str = "log",
    filename: str = "scraper.log"
) -> logging.Logger:
    """
    Configure logging with file and console handlers.
    
    Args:
        debug: Enable debug logging
        log_dir: Directory for log files
        filename: Log filename
        
    Returns:
        logging.Logger: Configured logger
    """
    # Create logger
    logger = logging.getLogger('webscraper')
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # File Handler - detailed logging
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, filename),
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    
    # Console Handler - minimal logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(f"webscraper.{name}")

def log_memory_usage(logger: logging.Logger) -> None:
    """
    Log current memory usage statistics.
    
    Args:
        logger: Logger instance to use
    """
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        
        logger.info(
            f"Memory Usage - "
            f"RSS: {mem_info.rss / 1024 / 1024:.1f}MB, "
            f"VMS: {mem_info.vms / 1024 / 1024:.1f}MB"
        )
    except Exception as e:
        logger.error(f"Error getting memory usage: {e}") 