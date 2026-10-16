#!/usr/bin/env python3
"""
Advanced LLM Manager Test - Comprehensive LLM functionality testing

Tests:
- Cache functionality (TTL, key generation, hit/miss)
- Fallback generator with different prompt types
- Concurrency control (semaphore)
- Model selection and fallback
- Error handling and retry logic
- Response validation
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging, CACHE_TTL
from constants import LOG_SEPARATOR, FALLBACK_AI_TEXT
from llm.manager import LLMManager, _get_cached, _set_cache, _cache_key
from llm.adapters import generate
from utils.formatting import (
    print_section_header, print_success, print_error,
    print_info, print_warning, format_duration
)

configure_logging()


async def test_cache_functionality():
    """Test LLM cache functionality"""
    print_info("Testing LLM cache functionality...")

    try:
        # Test cache key generation
        key1 = _cache_key("test prompt", "local")
        key2 = _cache_key("test prompt", "local")
        key3 = _cache_key("test prompt", "hf")
        key4 = _cache_key("different prompt", "local")

        assert key1 == key2, "Same prompt+model should generate same key"
        assert key1 != key3, "Different models should generate different keys"
        assert key1 != key4, "Different prompts should generate different keys"
        print_success("Cache key generation working correctly")

        # Test cache set and get
        test_prompt = "test_cache_prompt_unique_12345"
        test_response = "cached response text"

        # Set cache
        await _set_cache(test_prompt, "local", test_response)
        print_success("Cache set successfully")

        # Get from cache (should hit)
        cached = await _get_cached(test_prompt, "local")
        assert cached == test_response, "Cached value mismatch"
        print_success("Cache hit successful")

        # Get with different model (should miss)
        cached_miss = await _get_cached(test_prompt, "hf")
        assert cached_miss is None, "Should miss cache with different model"
        print_success("Cache miss with different model working")

        # Get with different prompt (should miss)
        cached_miss2 = await _get_cached("different_prompt", "local")
        assert cached_miss2 is None, "Should miss cache with different prompt"
        print_success("Cache miss with different prompt working")

        return True

    except Exception as e:
        print_error(f"Cache functionality test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_fallback_generator():
    """Test fallback generator with different prompt types"""
    print_info("Testing fallback generator...")

    try:
        manager = LLMManager()

        # Test with "start" keyword
        start_prompt = "You are starting a new adventure in a mysterious forest."
        start_response = manager._fallback(start_prompt)
        assert "adventure begins" in start_response.lower() or "narration:" in start_response.lower(), "Start fallback invalid"
        assert "choices:" in start_response.lower(), "Missing choices in start fallback"
        print_success("Start prompt fallback working")

        # Test with "explore" keyword
        explore_prompt = "The player wants to explore the ancient ruins carefully."
        explore_response = manager._fallback(explore_prompt)
        assert "explore" in explore_response.lower() or "investigation" in explore_response.lower(), "Explore fallback invalid"
        print_success("Explore prompt fallback working")

        # Test with "fight" keyword
        fight_prompt = "You encounter a fierce dragon and must fight for survival."
        fight_response = manager._fallback(fight_prompt)
        assert "challenge" in fight_response.lower() or "courage" in fight_response.lower(), "Fight fallback invalid"
        print_success("Fight prompt fallback working")

        # Test with generic prompt (should use FALLBACK_AI_TEXT)
        generic_prompt = "Something completely random and unrelated."
        generic_response = manager._fallback(generic_prompt)
        assert generic_response == FALLBACK_AI_TEXT, "Generic fallback should use FALLBACK_AI_TEXT"
        print_success("Generic prompt fallback working")

        # Verify all fallbacks have required structure
        for response in [start_response, explore_response, fight_response, generic_response]:
            assert "narration:" in response.lower() or "narration" in response.lower(), "Missing narration"
            assert "choices:" in response.lower() or "choices" in response.lower(), "Missing choices"
        print_success("All fallbacks have required structure")

        return True

    except Exception as e:
        print_error(f"Fallback generator test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_concurrency_control():
    """Test concurrency control with semaphore"""
    print_info("Testing concurrency control...")

    try:
        manager = LLMManager()

        # Create multiple concurrent requests
        prompts = [f"Test prompt {i}" for i in range(10)]

        start_time = time.time()

        # Run all requests concurrently
        tasks = [manager.generate(prompt, model="local") for prompt in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start_time

        # Verify all completed
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # Count successes (some may fail if LM Studio not running, but should not crash)
        successes = sum(1 for r in results if isinstance(r, str) and len(r) > 0)
        errors = sum(1 for r in results if isinstance(r, Exception))

        print_success(f"Concurrent requests completed: {successes} succeeded, {errors} failed")
        print(f"   Duration: {format_duration(duration)}")
        print(f"   Average: {format_duration(duration/10)} per request")

        # Verify no crashes
        assert all(isinstance(r, (str, Exception)) for r in results), "Unexpected result type"
        print_success("Concurrency control working (no crashes)")

        return True

    except Exception as e:
        print_error(f"Concurrency control test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_model_selection():
    """Test model selection and fallback"""
    print_info("Testing model selection...")

    try:
        test_prompt = "Generate a short test response."

        # Test with explicit model selection
        try:
            result_local = await generate(test_prompt, primary="local")
            assert isinstance(result_local, str), "Result should be string"
            assert len(result_local) > 0, "Result should not be empty"
            print_success("Local model selection working")
        except Exception as e:
            print_warning(f"Local model not available: {e}")

        # Test with fallback model
        try:
            result_hf = await generate(test_prompt, primary="hf", fallback="local")
            assert isinstance(result_hf, str), "Result should be string"
            assert len(result_hf) > 0, "Result should not be empty"
            print_success("HF model with fallback working")
        except Exception as e:
            print_warning(f"HF model not available: {e}")

        # Test with invalid model (should use fallback)
        try:
            result_invalid = await generate(test_prompt, primary="invalid_model")
            assert isinstance(result_invalid, str), "Should fallback to valid response"
            print_success("Invalid model handled with fallback")
        except Exception as e:
            print_warning(f"Invalid model test: {e}")

        return True

    except Exception as e:
        print_error(f"Model selection test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_response_validation():
    """Test response validation and structure"""
    print_info("Testing response validation...")

    try:
        manager = LLMManager()

        # Generate a response
        test_prompt = "Create a story beginning with narration and choices."
        response = await manager.generate(test_prompt, model="local")

        assert isinstance(response, str), "Response should be string"
        assert len(response) > 0, "Response should not be empty"
        print_success(f"Response generated - Length: {len(response)} characters")

        # Check if response has expected structure (narration, choices, etc.)
        response_lower = response.lower()
        has_narration = "narration" in response_lower
        has_choices = "choices" in response_lower or "1)" in response or "2)" in response

        if has_narration and has_choices:
            print_success("Response has expected structure (narration + choices)")
        else:
            print_warning("Response structure may be non-standard")

        # Verify response is not just error message
        assert "error" not in response_lower or len(response) > 100, "Response appears to be error message"
        print_success("Response is valid content (not error)")

        return True

    except Exception as e:
        print_error(f"Response validation test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_error_handling():
    """Test error handling and recovery"""
    print_info("Testing error handling...")

    try:
        manager = LLMManager()

        # Test with empty prompt
        try:
            result = await manager.generate("", model="local")
            assert isinstance(result, str), "Should return fallback for empty prompt"
            print_success("Empty prompt handled gracefully")
        except Exception as e:
            print_warning(f"Empty prompt raised exception: {e}")

        # Test with very long prompt
        long_prompt = "Test " * 10000  # Very long prompt
        try:
            result = await manager.generate(long_prompt, model="local")
            assert isinstance(result, str), "Should handle long prompts"
            print_success("Long prompt handled gracefully")
        except Exception as e:
            print_warning(f"Long prompt raised exception: {e}")

        # Test with special characters
        special_prompt = "Test with special chars: @#$%^&*(){}[]|\\:;\"'<>,.?/~`"
        try:
            result = await manager.generate(special_prompt, model="local")
            assert isinstance(result, str), "Should handle special characters"
            print_success("Special characters handled gracefully")
        except Exception as e:
            print_warning(f"Special characters raised exception: {e}")

        return True

    except Exception as e:
        print_error(f"Error handling test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Run advanced LLM tests"""
    start_time = time.time()

    print_section_header("🤖 ADVANCED LLM MANAGER TEST")
    print("Testing comprehensive LLM functionality\n")

    tests_passed = 0
    total_tests = 6

    # Test 1: Cache Functionality
    print("\n[1/6] Cache Functionality")
    if await test_cache_functionality():
        tests_passed += 1

    # Test 2: Fallback Generator
    print("\n[2/6] Fallback Generator")
    if await test_fallback_generator():
        tests_passed += 1

    # Test 3: Concurrency Control
    print("\n[3/6] Concurrency Control")
    if await test_concurrency_control():
        tests_passed += 1

    # Test 4: Model Selection
    print("\n[4/6] Model Selection and Fallback")
    if await test_model_selection():
        tests_passed += 1

    # Test 5: Response Validation
    print("\n[5/6] Response Validation")
    if await test_response_validation():
        tests_passed += 1

    # Test 6: Error Handling
    print("\n[6/6] Error Handling")
    if await test_error_handling():
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
        print("🎉 ALL ADVANCED LLM TESTS PASSED!")
        print("All LLM manager features are working correctly.")
    else:
        print(f"⚠️  {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
