# utils/http_client.py
"""
Centralized HTTP Client Factory

Provides consistent HTTP client configuration across the application.
"""

import httpx
from typing import Optional, Dict
from config import HTTP_TIMEOUT


def get_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get HTTP headers with optional API key.
    
    Args:
        api_key: Optional API key for authentication
        
    Returns:
        Dictionary of HTTP headers
    """
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def create_async_client(api_key: Optional[str] = None, timeout: Optional[float] = HTTP_TIMEOUT) -> httpx.AsyncClient:
    """
    Create a configured async HTTP client.
    
    Args:
        api_key: Optional API key for authentication
        timeout: Request timeout (None for unlimited)
        
    Returns:
        Configured httpx.AsyncClient
    """
    headers = get_headers(api_key)
    return httpx.AsyncClient(timeout=timeout, headers=headers)


def create_sync_client(api_key: Optional[str] = None, timeout: Optional[float] = HTTP_TIMEOUT) -> httpx.Client:
    """
    Create a configured sync HTTP client.
    
    Args:
        api_key: Optional API key for authentication
        timeout: Request timeout (None for unlimited)
        
    Returns:
        Configured httpx.Client
    """
    headers = get_headers(api_key)
    return httpx.Client(timeout=timeout, headers=headers)