"""
Worker class responsible for managing individual scraper processes.
"""

import asyncio
import subprocess
import logging
import sys
from typing import Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class Worker:
    """
    Manages an individual scraper process.
    
    Attributes:
        worker_id (str): Unique identifier for the worker
        api_session (str): API session identifier
        institution_id (Optional[str]): Optional institution ID for filtering
        process (Optional[subprocess.Popen]): Subprocess handle for the worker
        start_time (datetime): Time when the worker was started
        restart_interval (int): Time in seconds before worker should be restarted
    """

    def __init__(
        self, 
        worker_id: str, 
        api_session: str,
        institution_id: Optional[str] = None,
        restart_interval: int = 1800  # 30 minutes
    ):
        """
        Initialize a Worker instance.

        Args:
            worker_id: Unique identifier for this worker
            api_session: API session identifier
            institution_id: Optional institution ID for filtering URLs
            restart_interval: Time in seconds before worker should be restarted
        """
        self.worker_id = worker_id
        self.api_session = api_session
        self.institution_id = institution_id
        self.process: Optional[subprocess.Popen] = None
        self.start_time = datetime.now()
        self.restart_interval = restart_interval

    async def start(self) -> None:
        """
        Start the worker process.
        
        Raises:
            RuntimeError: If worker is already running
        """
        if self.process:
            raise RuntimeError(f"Worker {self.worker_id} is already running")

        try:
            # Build command with all necessary arguments
            command = [
                sys.executable,
                '-m',
                'src.scraper.main',
                '--session', self.api_session,
                '--worker-id', self.worker_id
            ]

            if self.institution_id:
                command.extend(['--institution-id', self.institution_id])

            # Start process with pipe for output
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                env=os.environ.copy()  # Pass current environment
            )
            
            self.start_time = datetime.now()
            logger.info(f"Started worker {self.worker_id}")

            # Start output monitoring
            asyncio.create_task(self._monitor_output())

        except Exception as e:
            logger.error(f"Failed to start worker {self.worker_id}: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the worker process gracefully.
        """
        if not self.process:
            return

        try:
            # Try graceful shutdown first
            self.process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_exit()),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # Force kill if graceful shutdown fails
                logger.warning(f"Worker {self.worker_id} did not stop gracefully, forcing kill")
                self.process.kill()
                await self._wait_for_exit()

        except Exception as e:
            logger.error(f"Error stopping worker {self.worker_id}: {e}")
        finally:
            # Clean up process resources
            if self.process:
                try:
                    self.process.stdout.close()
                    self.process.stderr.close()
                except:
                    pass
                self.process = None

    async def is_alive(self) -> bool:
        """
        Check if the worker process is alive and should continue running.
        
        Returns:
            bool: True if worker is alive and within restart interval
        """
        if not self.process:
            return False

        # Check if process is still running
        if self.process.poll() is not None:
            return False

        # Check if worker should be restarted due to age
        age = (datetime.now() - self.start_time).total_seconds()
        if age >= self.restart_interval:
            logger.info(f"Worker {self.worker_id} reached restart interval")
            return False

        return True

    async def _wait_for_exit(self) -> None:
        """Wait for process to exit."""
        if self.process:
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self.process.wait
            )

    async def _monitor_output(self) -> None:
        """
        Monitor and log worker process output.
        """
        if not self.process:
            return

        async def read_stream(stream, level):
            while True:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    stream.readline
                )
                if not line:
                    break
                line = line.strip()
                if line:
                    logger.log(level, f"Worker {self.worker_id}: {line}")

        try:
            # Monitor both stdout and stderr
            await asyncio.gather(
                read_stream(self.process.stdout, logging.INFO),
                read_stream(self.process.stderr, logging.ERROR)
            )
        except Exception as e:
            logger.error(f"Error monitoring worker {self.worker_id} output: {e}")

    def __del__(self):
        """Ensure process is cleaned up on deletion."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1)
            except:
                try:
                    self.process.kill()
                except:
                    pass 