"""
Main entry point for the web scraping worker manager.
Handles initialization and startup of the worker manager system.
"""

import asyncio
import argparse
import logging
from worker_manager.manager import WorkerManager
from utils.logging import setup_logging
import os

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments for worker manager configuration."""
    parser = argparse.ArgumentParser(description='Manage multiple webscraper workers')
    parser.add_argument(
        '--workers', 
        type=int, 
        default=int(os.getenv('MAX_WORKERS', 5)),
        help='Number of worker processes to run (default: from MAX_WORKERS env var or 5)'
    )
    parser.add_argument(
        '--max-memory', 
        type=float, 
        default=float(os.getenv('MAX_MEMORY_PERCENT', 80)),
        help='Maximum memory usage percentage (default: from MAX_MEMORY_PERCENT env var or 80)'
    )
    parser.add_argument(
        '--max-temp', 
        type=float, 
        default=float(os.getenv('MAX_CPU_TEMP', 75)),
        help='Maximum CPU temperature in Celsius (default: from MAX_CPU_TEMP env var or 75)'
    )
    parser.add_argument(
        '--session', 
        type=str,
        help='API session ID for all workers'
    )
    parser.add_argument(
        '--institution-id',
        type=str,
        default=None,
        help='Institution ID for filtering URLs (optional)'
    )
    return parser.parse_args()

async def main():
    """
    Main function to initialize and run the worker manager.
    
    Handles:
    - Argument parsing
    - Logging setup
    - Worker manager initialization and execution
    - Graceful shutdown
    """
    args = parse_arguments()
    setup_logging()
    
    # If session not provided via CLI, prompt for it
    session = args.session
    if not session:
        session = input("Please enter the API session ID: ").strip()
        if not session:
            logger.error("API session ID is required")
            return
    
    logger.info(f"Starting manager with {args.workers} workers")
    logger.info(f"API Session: {session}")
    logger.info(f"Memory limit: {args.max_memory}%, Temperature limit: {args.max_temp}°C")
    
    manager = WorkerManager(
        num_workers=args.workers,
        max_memory_percent=args.max_memory,
        max_temp=args.max_temp,
        api_session=session,
        institution_id=args.institution_id
    )
    
    try:
        await manager.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())