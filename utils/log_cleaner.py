"""
log_cleaner.py - Automatic Log File Cleaner
============================================

This module provides a background task that automatically clears log files
at regular intervals to prevent them from growing too large.

USAGE:
    from utils.log_cleaner import start_log_cleaner, stop_log_cleaner
    
    # Start the cleaner (clears logs every 60 seconds by default)
    start_log_cleaner(interval=60)
    
    # Stop the cleaner when shutting down
    stop_log_cleaner()
"""

import threading
import time
import logging
from pathlib import Path
from config import LOG_FILE, LOG_DIR
from constants import THREAD_SHUTDOWN_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Global thread control
_cleaner_thread = None
_stop_event = threading.Event()


def clear_log_file(log_path: Path) -> bool:
    """
    Clear a log file by truncating it to zero bytes.
    
    Args:
        log_path: Path to the log file to clear
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use truncate() for faster file clearing (no encoding overhead)
        with open(log_path, 'r+', encoding='utf-8') as f:
            f.truncate(0)
        return True
    except FileNotFoundError:
        return True  # File doesn't exist, nothing to clear
    except Exception:
        return False


def clear_all_logs():
    """Clear all log files in the logs directory."""
    try:
        log_dir = Path(LOG_DIR)
        if not log_dir.exists():
            return
        
        # Collect all log files first (faster than checking one by one)
        log_files = [f for f in log_dir.glob("*.log*") if f.is_file()]
        
        if not log_files:
            return
        
        # Clear all files in batch
        cleared_count = sum(1 for log_file in log_files if clear_log_file(log_file))
        
        if cleared_count > 0:
            print(f"🧹 Cleared {cleared_count} log file(s)")
                
    except Exception:
        pass  # Silent fail for performance


def _log_cleaner_worker(interval: int):
    """
    Background worker that clears logs at regular intervals.
    
    Args:
        interval: Time in seconds between log clears
    """
    print(f"🧹 Log cleaner started - clearing logs every {interval} seconds")
    
    while not _stop_event.is_set():
        # Clear the logs immediately on first run
        clear_all_logs()
        
        # Wait for the interval or until stop is signaled
        if _stop_event.wait(timeout=interval):
            break  # Stop event was set
    
    print("🛑 Log cleaner stopped")


def start_log_cleaner(interval: int = 60):
    """
    Start the automatic log cleaner in a background thread.
    
    Args:
        interval: Time in seconds between log clears (default: 60)
    """
    global _cleaner_thread
    
    # Don't start if already running
    if _cleaner_thread is not None and _cleaner_thread.is_alive():
        return
    
    # Reset stop event
    _stop_event.clear()
    
    # Start the cleaner thread with higher priority
    _cleaner_thread = threading.Thread(
        target=_log_cleaner_worker,
        args=(interval,),
        daemon=True,  # Daemon thread will exit when main program exits
        name="LogCleaner"
    )
    _cleaner_thread.start()


def stop_log_cleaner():
    """Stop the automatic log cleaner."""
    global _cleaner_thread
    
    if _cleaner_thread is None or not _cleaner_thread.is_alive():
        return
    
    # Signal the thread to stop
    _stop_event.set()
    
    # Wait for thread to finish (with shorter timeout for faster shutdown)
    _cleaner_thread.join(timeout=THREAD_SHUTDOWN_TIMEOUT_SECONDS)
    
    _cleaner_thread = None


def is_cleaner_running() -> bool:
    """Check if the log cleaner is currently running."""
    return _cleaner_thread is not None and _cleaner_thread.is_alive()