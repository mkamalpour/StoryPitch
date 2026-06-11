"""
API Server Management Utilities
Handles starting, stopping, and health checking of the FastAPI server
"""

import asyncio
import httpx
import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
from config import API_HOST, API_PORT

logger = logging.getLogger(__name__)

# Global API process reference
_api_process: Optional[subprocess.Popen] = None


async def check_api_health(timeout: float = 2.0) -> bool:
    """
    Check if the API server is running and healthy.
    
    Args:
        timeout: Maximum time to wait for response (seconds)
    
    Returns:
        True if API is healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"http://{API_HOST}:{API_PORT}/api/health")
            return response.status_code == 200
    except Exception as e:
        logger.debug(f"API health check failed: {e}")
        return False


async def wait_for_api_ready(max_wait: float = 30.0, check_interval: float = 0.5) -> bool:
    """
    Wait for the API server to become ready.
    
    Args:
        max_wait: Maximum time to wait (seconds)
        check_interval: Time between health checks (seconds)
    
    Returns:
        True if API became ready, False if timeout
    """
    logger.info("⏳ Waiting for API server to become ready...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        if await check_api_health():
            elapsed = time.time() - start_time
            logger.info(f"✅ API server ready after {elapsed:.1f}s")
            return True
        await asyncio.sleep(check_interval)
    
    logger.error(f"❌ API server did not become ready within {max_wait}s")
    return False


def start_api_server() -> subprocess.Popen:
    """
    Start the API server in a background process.
    
    Returns:
        The subprocess.Popen object for the API server
    """
    global _api_process
    
    logger.info("🚀 Starting API server in background...")
    logger.info(f"   Host: {API_HOST}")
    logger.info(f"   Port: {API_PORT}")
    
    _api_process = subprocess.Popen(
        [sys.executable, "-m", "api.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent
    )
    
    logger.info(f"✅ API server process started (PID: {_api_process.pid})")
    return _api_process


def stop_api_server():
    """Stop the API server if it's running."""
    global _api_process
    
    if _api_process and _api_process.poll() is None:
        logger.info("🛑 Stopping API server...")
        try:
            _api_process.terminate()
            _api_process.wait(timeout=5)
            logger.info("✅ API server stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping API server: {e}")
            try:
                _api_process.kill()
                logger.warning("⚠️  API server forcefully killed")
            except Exception:
                pass
        finally:
            _api_process = None


async def ensure_api_running() -> Tuple[bool, bool]:
    """
    Ensure the API server is running, starting it if necessary.
    
    Returns:
        Tuple of (is_running, was_started)
        - is_running: True if API is now running
        - was_started: True if we started it (False if it was already running)
    """
    logger.info("🔍 Checking API server status...")
    
    # Check if already running
    if await check_api_health():
        logger.info("✅ API server already running")
        return True, False
    
    # Not running, try to start it
    logger.info("⚠️  API server not running, starting it...")
    start_api_server()
    
    # Wait for it to become ready
    if await wait_for_api_ready():
        logger.info("✅ API server started successfully")
        return True, True
    else:
        logger.error("❌ Failed to start API server")
        stop_api_server()
        return False, False