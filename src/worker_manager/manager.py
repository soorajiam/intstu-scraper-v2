"""
WorkerManager class responsible for managing and coordinating scraper worker processes.
Handles worker lifecycle, resource monitoring, and system constraints.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional
import gc

from .worker import Worker
from .resource_monitor import ResourceMonitor
from utils.logging import get_logger

logger = get_logger(__name__)

class WorkerManager:
    """
    Manages multiple scraper worker processes while monitoring system resources.
    
    Attributes:
        num_workers (int): Maximum number of concurrent workers
        max_memory_percent (float): Maximum allowed memory usage percentage
        max_temp (float): Maximum allowed CPU temperature
        api_session (str): API session identifier
        institution_id (Optional[str]): Optional institution ID for filtering
        workers (Dict[str, Worker]): Dictionary of active workers
        resource_monitor (ResourceMonitor): System resource monitor
        stopped (bool): Flag indicating if manager is stopped
    """

    def __init__(
        self, 
        num_workers: int = 5, 
        max_memory_percent: float = 80, 
        max_temp: float = 75,
        api_session: str = None,
        institution_id: Optional[str] = None
    ):
        """
        Initialize the WorkerManager.

        Args:
            num_workers: Maximum number of concurrent workers
            max_memory_percent: Maximum allowed memory usage percentage
            max_temp: Maximum allowed CPU temperature in Celsius
            api_session: API session identifier
            institution_id: Optional institution ID for filtering URLs
        """
        if not api_session:
            raise ValueError("API session is required")
            
        self.num_workers = num_workers
        self.max_memory_percent = max_memory_percent
        self.max_temp = max_temp
        self.api_session = api_session
        self.institution_id = institution_id
        
        # Initialize components
        self.workers: Dict[str, Worker] = {}
        self.resource_monitor = ResourceMonitor(
            max_memory_percent=max_memory_percent,
            max_temp=max_temp
        )
        self.stopped = False

    async def start_worker(self) -> str:
        """
        Start a new worker process.
        
        Returns:
            str: Unique worker ID
        """
        worker_id = str(uuid.uuid4())
        try:
            worker = Worker(
                worker_id=worker_id,
                api_session=self.api_session,
                institution_id=self.institution_id
            )
            await worker.start()
            self.workers[worker_id] = worker
            logger.info(f"Started worker {worker_id}")
            return worker_id
        except Exception as e:
            logger.error(f"Error starting worker: {e}")
            return ""

    async def kill_worker(self, worker_id: str) -> None:
        """
        Kill a specific worker process.
        
        Args:
            worker_id: ID of the worker to kill
        """
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            try:
                await worker.stop()
            except Exception as e:
                logger.error(f"Error stopping worker {worker_id}: {e}")
            finally:
                self.workers.pop(worker_id)
                gc.collect()
                logger.info(f"Killed worker {worker_id}")

    async def kill_all_workers(self) -> None:
        """Kill all active worker processes."""
        for worker_id in list(self.workers.keys()):
            await self.kill_worker(worker_id)
        gc.collect()

    async def manage_workers(self) -> None:
        """Main worker management loop."""
        while not self.stopped:
            try:
                # Check system resources
                resources = await self.resource_monitor.check_resources()
                
                if not resources.within_limits:
                    logger.warning(f"Resource limits exceeded: {resources}")
                    await self.kill_all_workers()
                    await asyncio.sleep(30)
                    continue

                # Manage worker count
                current_workers = len(self.workers)
                if current_workers < self.num_workers:
                    workers_to_add = min(
                        self.num_workers - current_workers,
                        max(1, (self.num_workers - current_workers) // 2)
                    )
                    
                    for _ in range(workers_to_add):
                        await self.start_worker()
                        await asyncio.sleep(5)

                # Check worker health
                for worker_id in list(self.workers.keys()):
                    worker = self.workers[worker_id]
                    if not await worker.is_alive():
                        await self.kill_worker(worker_id)

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in manage_workers: {e}")
                await asyncio.sleep(10)
                gc.collect()

    async def run(self) -> None:
        """Run the worker manager."""
        logger.info(f"Starting worker manager with {self.num_workers} workers")
        await self.manage_workers()

    async def shutdown(self) -> None:
        """Gracefully shutdown the worker manager."""
        self.stopped = True
        logger.info("Shutting down worker manager...")
        await self.kill_all_workers()
        logger.info("Worker manager stopped") 