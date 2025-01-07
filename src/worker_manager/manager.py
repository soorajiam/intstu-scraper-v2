"""
Worker manager for coordinating multiple scraper processes.
"""

import asyncio
import logging
import psutil
from typing import Optional
import uuid

from src.scraper.main import ScraperOrchestrator
from src.utils.logging import get_logger

logger = get_logger(__name__)

class WorkerManager:
    """Manages multiple scraper worker processes."""
    
    def __init__(
        self,
        num_workers: int,
        max_memory_percent: float,
        max_temp: float,
        api_session: str,
        institution_id: Optional[str] = None
    ):
        """Initialize the worker manager."""
        self.num_workers = num_workers
        self.max_memory_percent = max_memory_percent
        self.max_temp = max_temp
        self.api_session = api_session
        self.institution_id = institution_id
        self.workers = []
        self.stopped = False

    async def _check_resources(self) -> bool:
        """Check if system resources are within limits."""
        try:
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > self.max_memory_percent:
                logger.warning(f"Memory usage too high: {memory.percent}%")
                return False

            # Check CPU temperature if available
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current > self.max_temp:
                                logger.warning(f"CPU temperature too high: {entry.current}°C")
                                return False

            return True
            
        except Exception as e:
            logger.error(f"Error checking resources: {e}")
            return True  # Continue on error

    async def _start_worker(self) -> None:
        """Start a single worker process."""
        worker_id = str(uuid.uuid4())[:8]
        try:
            orchestrator = ScraperOrchestrator(
                session=self.api_session,
                worker_id=worker_id,
                institution_id=self.institution_id
            )
            await orchestrator.run()
        except Exception as e:
            logger.error(f"Worker {worker_id} failed: {e}")

    async def run(self) -> None:
        """Run the worker manager."""
        logger.info(f"Starting {self.num_workers} workers")
        
        try:
            while not self.stopped:
                # Check system resources
                if not await self._check_resources():
                    logger.warning("Resource limits exceeded, pausing new workers")
                    await asyncio.sleep(60)
                    continue

                # Start workers up to num_workers
                while len(self.workers) < self.num_workers:
                    worker = asyncio.create_task(self._start_worker())
                    self.workers.append(worker)

                # Clean up finished workers
                self.workers = [w for w in self.workers if not w.done()]
                
                await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Worker manager error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown all workers."""
        self.stopped = True
        for worker in self.workers:
            try:
                worker.cancel()
                await worker
            except:
                pass
        self.workers = [] 