#!/usr/bin/env python3
"""
Utils Test - Focused testing of utility functions

Tests:
- HTTP client creation (http_client.py)
- API utilities (api_utils.py)
- Formatting utilities (formatting.py)
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from utils.http_client import get_headers, create_async_client, create_sync_client
from utils.formatting import (
    print_section_header, print_success, print_error,
    print_info, print_warning, print_step, format_duration
)

configure_logging()


def test_http_client():
    """Test HTTP client utilities"""
    print_info("Testing HTTP client utilities...")

    try:
        # Test header generation without API key
        headers = get_headers()
        assert isinstance(headers, dict), "Headers should be a dictionary"
        print_success("Headers generated without API key")

        # Test header generation with API key
        headers_with_key = get_headers(api_key="test_key_123")
        assert "x-api-key" in headers_with_key, "API key not in headers"
        assert headers_with_key["x-api-key"] == "test_key_123", "API key mismatch"
        print_success("Headers generated with API key")

        # Test async client creation
        async_client = create_async_client()
        assert async_client is not None, "Async client creation failed"
        async_client.close()
        print_success("Async HTTP client created")

        # Test sync client creation
        sync_client = create_sync_client()
        assert sync_client is not None, "Sync client creation failed"
        sync_client.close()
        print_success("Sync HTTP client created")

        # Test client with API key
        async_client_with_key = create_async_client(api_key="test_key")
        assert async_client_with_key is not None, "Async client with key failed"
        async_client_with_key.close()
        print_success("HTTP client with API key created")

        return True

    except Exception as e:
        print_error(f"HTTP client test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_formatting_utilities():
    """Test formatting utilities"""
    print_info("Testing formatting utilities...")

    try:
        # Test duration formatting
        duration_str = format_duration(125.5)
        assert "2m 5.50s" in duration_str or "125.50s" in duration_str, f"Duration format unexpected: {duration_str}"
        print_success(f"Duration formatting works: {duration_str}")

        # Test short duration
        short_duration = format_duration(5.123)
        assert "5.12s" in short_duration, f"Short duration format unexpected: {short_duration}"
        print_success(f"Short duration formatting works: {short_duration}")

        # Test print functions (just verify they don't crash)
        print_success("Test success message")
        print_error("Test error message")
        print_warning("Test warning message")
        print_info("Test info message")
        print_step(1, 5, "Test step")
        print_section_header("Test Section")

        print_success("All formatting utilities work correctly")
        return True

    except Exception as e:
        print_error(f"Formatting utilities test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_constants_import():
    """Test that constants can be imported and used"""
    print_info("Testing constants import...")

    try:
        from constants import (
            THEME_LIST, TRAIT_LIST, FALLBACK_CHOICES,
            FALLBACK_NARRATION, LOG_SEPARATOR
        )

        # Verify constants exist and have expected types
        assert isinstance(THEME_LIST, list), "THEME_LIST should be a list"
        assert len(THEME_LIST) > 0, "THEME_LIST should not be empty"
        print_success(f"THEME_LIST loaded - {len(THEME_LIST)} themes")

        assert isinstance(TRAIT_LIST, list), "TRAIT_LIST should be a list"
        assert len(TRAIT_LIST) > 0, "TRAIT_LIST should not be empty"
        print_success(f"TRAIT_LIST loaded - {len(TRAIT_LIST)} traits")

        assert isinstance(FALLBACK_CHOICES, list), "FALLBACK_CHOICES should be a list"
        assert len(FALLBACK_CHOICES) >= 2, "FALLBACK_CHOICES should have at least 2 choices"
        print_success(f"FALLBACK_CHOICES loaded - {len(FALLBACK_CHOICES)} choices")

        assert isinstance(FALLBACK_NARRATION, str), "FALLBACK_NARRATION should be a string"
        assert len(FALLBACK_NARRATION) > 0, "FALLBACK_NARRATION should not be empty"
        print_success("FALLBACK_NARRATION loaded")

        assert isinstance(LOG_SEPARATOR, str), "LOG_SEPARATOR should be a string"
        print_success("LOG_SEPARATOR loaded")

        return True

    except Exception as e:
        print_error(f"Constants import test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_config_import():
    """Test that config can be imported and used"""
    print_info("Testing config import...")

    try:
        from config import (
            API_HOST, API_PORT, DATABASE_URL, LM_STUDIO_URL,
            DEFAULT_MODEL, STORY_CHOICES_COUNT
        )

        # Verify config values exist and have expected types
        assert isinstance(API_HOST, str), "API_HOST should be a string"
        assert len(API_HOST) > 0, "API_HOST should not be empty"
        print_success(f"API_HOST: {API_HOST}")

        assert isinstance(API_PORT, int), "API_PORT should be an integer"
        assert API_PORT > 0, "API_PORT should be positive"
        print_success(f"API_PORT: {API_PORT}")

        assert isinstance(DATABASE_URL, str), "DATABASE_URL should be a string"
        assert len(DATABASE_URL) > 0, "DATABASE_URL should not be empty"
        print_success(f"DATABASE_URL: {DATABASE_URL[:50]}...")

        assert isinstance(LM_STUDIO_URL, str), "LM_STUDIO_URL should be a string"
        print_success(f"LM_STUDIO_URL: {LM_STUDIO_URL}")

        assert isinstance(DEFAULT_MODEL, str), "DEFAULT_MODEL should be a string"
        print_success(f"DEFAULT_MODEL: {DEFAULT_MODEL}")

        assert isinstance(STORY_CHOICES_COUNT, int), "STORY_CHOICES_COUNT should be an integer"
        assert STORY_CHOICES_COUNT >= 2, "STORY_CHOICES_COUNT should be at least 2"
        print_success(f"STORY_CHOICES_COUNT: {STORY_CHOICES_COUNT}")

        return True

    except Exception as e:
        print_error(f"Config import test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def main():
    """Run utility tests"""
    start_time = time.time()

    print_section_header("🔧 UTILS TEST")
    print("Testing utility functions and configuration\n")

    tests_passed = 0
    total_tests = 4

    # Test 1: HTTP Client
    print("\n[1/4] HTTP Client Utilities")
    if test_http_client():
        tests_passed += 1

    # Test 2: Formatting Utilities
    print("\n[2/4] Formatting Utilities")
    if test_formatting_utilities():
        tests_passed += 1

    # Test 3: Constants Import
    print("\n[3/4] Constants Import")
    if test_constants_import():
        tests_passed += 1

    # Test 4: Config Import
    print("\n[4/4] Config Import")
    if test_config_import():
        tests_passed += 1

    # Summary
    duration = time.time() - start_time
    print(f"\n{LOG_SEPARATOR}")
    print("📊 TEST RESULTS")
    print(LOG_SEPARATOR)
    print(f"Passed: {tests_passed}/{total_tests}")
    print(f"Duration: {format_duration(duration)}")
    print(LOG_SEPARATOR)

    if tests_passed == total_tests:
        print("🎉 ALL UTILS TESTS PASSED!")
        print("All utility functions are working correctly.")
    else:
        print(f"❌ {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
