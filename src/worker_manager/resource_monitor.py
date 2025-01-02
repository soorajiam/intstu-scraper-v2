"""
System resource monitoring functionality for the worker manager.
"""

from dataclasses import dataclass
import psutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class SystemResources:
    """
    Data class representing system resource measurements.
    
    Attributes:
        memory_percent (float): Current memory usage percentage
        cpu_temp (float): Current CPU temperature in Celsius
        within_limits (bool): Whether resources are within acceptable limits
    """
    memory_percent: float
    cpu_temp: float
    within_limits: bool

class ResourceMonitor:
    """
    Monitors system resources including memory usage and CPU temperature.
    
    Attributes:
        max_memory_percent (float): Maximum allowed memory usage percentage
        max_temp (float): Maximum allowed CPU temperature
        temp_monitoring_available (bool): Whether temperature monitoring is available
    """

    def __init__(self, max_memory_percent: float, max_temp: float):
        """
        Initialize the ResourceMonitor.

        Args:
            max_memory_percent: Maximum allowed memory usage percentage
            max_temp: Maximum allowed CPU temperature in Celsius
        """
        self.max_memory_percent = max_memory_percent
        self.max_temp = max_temp
        self.temp_monitoring_available = self._check_temp_monitoring()

    def _check_temp_monitoring(self) -> bool:
        """Check if temperature monitoring is available on the system."""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                float(f.read()) / 1000.0
                return True
        except:
            logger.warning("Temperature monitoring not available")
            return False

    def get_cpu_temperature(self) -> float:
        """
        Get current CPU temperature.
        
        Returns:
            float: CPU temperature in Celsius or 0.0 if unavailable
        """
        if not self.temp_monitoring_available:
            return 0.0
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read()) / 1000.0
        except Exception as e:
            logger.error(f"Error reading CPU temperature: {e}")
            return 0.0

    def get_memory_usage(self) -> float:
        """
        Get current system memory usage percentage.
        
        Returns:
            float: Memory usage percentage
        """
        return psutil.virtual_memory().percent

    async def check_resources(self) -> SystemResources:
        """
        Check if system resources are within acceptable limits.
        
        Returns:
            SystemResources: Current system resource measurements
        """
        temp = self.get_cpu_temperature()
        mem_usage = self.get_memory_usage()
        
        within_limits = (
            temp <= self.max_temp and 
            mem_usage <= self.max_memory_percent
        )
        
        if not within_limits:
            logger.warning(
                f"Resource limits exceeded - "
                f"Temperature: {temp:.1f}°C, "
                f"Memory: {mem_usage:.1f}%"
            )
            
        return SystemResources(
            memory_percent=mem_usage,
            cpu_temp=temp,
            within_limits=within_limits
        ) 