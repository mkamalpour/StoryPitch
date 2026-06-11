# utils/performance.py
"""
Performance optimization utilities
Provides caching and optimization for Story Maker Bot
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class LRUCache:
    """
    Simple LRU (Least Recently Used) Cache implementation.
    Thread-safe for single-threaded applications.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache, return None if not found"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any):
        """Set item in cache, evict oldest if full"""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
        else:
            # Add new
            if len(self.cache) >= self.max_size:
                # Remove oldest (first item)
                self.cache.popitem(last=False)
        self.cache[key] = value
    
    def clear(self):
        """Clear all cached items"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }


# Global caches
_context_cache = LRUCache(max_size=50)  # Cache for context summaries
_memory_cache = LRUCache(max_size=50)   # Cache for memory queries


def timed_function(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    Logs warning if function takes > 1 second.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        if elapsed > 1.0:
            logger.warning(f"{func.__name__} took {elapsed:.2f}s (slow!)")
        elif elapsed > 0.1:
            logger.info(f"{func.__name__} took {elapsed:.3f}s")
        
        return result
    return wrapper


def cached_context(session_id: int, step_count: int) -> Optional[str]:
    """
    Get cached context summary for a session.
    Cache key includes step count to invalidate on new steps.
    
    Args:
        session_id: Session ID
        step_count: Current number of steps
        
    Returns:
        Cached context or None
    """
    cache_key = f"context_{session_id}_{step_count}"
    return _context_cache.get(cache_key)


def cache_context(session_id: int, step_count: int, context: str):
    """
    Cache context summary for a session.
    
    Args:
        session_id: Session ID
        step_count: Current number of steps
        context: Context summary to cache
    """
    cache_key = f"context_{session_id}_{step_count}"
    _context_cache.set(cache_key, context)


def cached_memory_summary(session_id: int, step_count: int) -> Optional[str]:
    """
    Get cached memory summary for a session.
    
    Args:
        session_id: Session ID
        step_count: Current number of steps
        
    Returns:
        Cached memory summary or None
    """
    cache_key = f"memory_{session_id}_{step_count}"
    return _memory_cache.get(cache_key)


def cache_memory_summary(session_id: int, step_count: int, summary: str):
    """
    Cache memory summary for a session.
    
    Args:
        session_id: Session ID
        step_count: Current number of steps
        summary: Memory summary to cache
    """
    cache_key = f"memory_{session_id}_{step_count}"
    _memory_cache.set(cache_key, summary)


def clear_session_cache(session_id: int):
    """
    Clear all cached data for a specific session.
    Call this when session is deleted or reset.
    
    Args:
        session_id: Session ID to clear
    """
    # Remove all keys containing this session_id
    for cache in [_context_cache, _memory_cache]:
        keys_to_remove = [k for k in cache.cache.keys() if f"_{session_id}_" in k]
        for key in keys_to_remove:
            cache.cache.pop(key, None)
    
    logger.info(f"Cleared cache for session {session_id}")


def clear_all_caches():
    """Clear all caches"""
    _context_cache.clear()
    _memory_cache.clear()
    logger.info("Cleared all caches")


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches"""
    return {
        "context_cache": _context_cache.get_stats(),
        "memory_cache": _memory_cache.get_stats()
    }


def optimize_world_state(world_state: Dict[str, Any], max_events: int = 50) -> Dict[str, Any]:
    """
    Optimize world_state by removing old/unnecessary data.
    Keeps most recent and important items.
    
    Args:
        world_state: World state dictionary
        max_events: Maximum number of events to keep
        
    Returns:
        Optimized world state
    """
    if "memory" not in world_state:
        return world_state
    
    memory = world_state["memory"]
    
    # Limit events to most recent + high importance
    if "events" in memory and len(memory["events"]) > max_events:
        events = memory["events"]
        
        # Keep all critical/high importance events
        important = [e for e in events if e.get("importance") in ["critical", "high"]]
        
        # Keep most recent normal/low events
        others = [e for e in events if e.get("importance") not in ["critical", "high"]]
        recent_others = others[-(max_events - len(important)):]
        
        memory["events"] = important + recent_others
        logger.info(f"Optimized events: {len(events)} -> {len(memory['events'])}")
    
    # Limit discoveries to most recent
    if "discoveries" in memory and len(memory["discoveries"]) > 30:
        discoveries = memory["discoveries"]
        memory["discoveries"] = discoveries[-30:]
        logger.info(f"Optimized discoveries: {len(discoveries)} -> 30")
    
    return world_state


class PerformanceMonitor:
    """
    Monitor performance metrics for the application.
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
    
    def record(self, metric_name: str, value: float):
        """Record a metric value"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)
        
        # Keep only last 100 values
        if len(self.metrics[metric_name]) > 100:
            self.metrics[metric_name] = self.metrics[metric_name][-100:]
    
    def get_average(self, metric_name: str) -> Optional[float]:
        """Get average value for a metric"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return None
        return sum(self.metrics[metric_name]) / len(self.metrics[metric_name])
    
    def get_stats(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a metric"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return None
        
        values = self.metrics[metric_name]
        return {
            "count": len(values),
            "average": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "recent": values[-1] if values else 0
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics"""
        return {
            name: self.get_stats(name)
            for name in self.metrics.keys()
        }


# Global performance monitor
_performance_monitor = PerformanceMonitor()


def record_metric(metric_name: str, value: float):
    """Record a performance metric"""
    _performance_monitor.record(metric_name, value)


def get_performance_stats() -> Dict[str, Any]:
    """Get all performance statistics"""
    return {
        "caches": get_cache_stats(),
        "metrics": _performance_monitor.get_all_stats()
    }