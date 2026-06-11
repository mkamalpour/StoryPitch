"""
Formatting and Display Utilities
Provides consistent formatting for console output and logging
"""


def print_section_header(title: str, width: int = 100):
    """Print a formatted section header."""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"⚠️  {message}")


def print_info(message: str):
    """Print an info message."""
    print(f"ℹ️  {message}")


def print_step(step_num: int, total: int, description: str):
    """Print a step in a multi-step process."""
    print(f"\n[{step_num}/{total}] {description}")


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"