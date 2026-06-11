"""
Utility functions for the Story Maker Bot
Provides common functionality like API server management, health checks, etc.
"""

from .api_utils import (
    check_api_health,
    wait_for_api_ready,
    start_api_server,
    stop_api_server,
    ensure_api_running
)

from .formatting import (
    print_section_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_step,
    format_duration
)

__all__ = [
    'check_api_health',
    'wait_for_api_ready',
    'start_api_server',
    'stop_api_server',
    'ensure_api_running',
    'print_section_header',
    'print_success',
    'print_error',
    'print_warning',
    'print_info',
    'print_step',
    'format_duration'
]