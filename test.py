#!/usr/bin/env python3
"""
Comprehensive test runner that executes ALL test files in the tests/ folder.
Simply run: python test.py

This script:
- Discovers all test_*.py files in tests/ folder
- Runs each test file independently
- Reports results for each test file
- Provides a summary of all test results
"""

import subprocess
import sys
from pathlib import Path
import time
from constants import LOG_SEPARATOR

def run_test_file(test_file: Path) -> tuple[bool, float]:
    """Run a single test file and return (success, duration)"""
    print("\n" + LOG_SEPARATOR)
    print(f"🧪 Running: {test_file.name}")
    print(LOG_SEPARATOR)
    
    start = time.time()
    result = subprocess.call([sys.executable, str(test_file)])
    duration = time.time() - start
    
    success = result == 0
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"\n{status} - {test_file.name} (took {duration:.2f}s)")
    
    return success, duration

if __name__ == "__main__":
    tests_dir = Path(__file__).parent / "tests"
    
    # Discover all test files
    test_files = sorted(tests_dir.glob("test_*.py"))
    
    if not test_files:
        print("❌ No test files found in tests/ folder")
        sys.exit(1)
    
    print("\n" + LOG_SEPARATOR)
    print("🚀 COMPREHENSIVE TEST SUITE")
    print(LOG_SEPARATOR)
    print(f"📁 Test Directory: {tests_dir}")
    print(f"📝 Found {len(test_files)} test file(s):")
    for tf in test_files:
        print(f"   - {tf.name}")
    print(LOG_SEPARATOR)
    
    # Run all tests
    results = []
    total_duration = 0
    
    for test_file in test_files:
        success, duration = run_test_file(test_file)
        results.append((test_file.name, success, duration))
        total_duration += duration
    
    # Summary
    print("\n" + LOG_SEPARATOR)
    print("📊 TEST SUMMARY")
    print(LOG_SEPARATOR)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    
    for name, success, duration in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {name} ({duration:.2f}s)")
    
    print(LOG_SEPARATOR)
    print(f"Total: {len(results)} test files")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Total Duration: {total_duration:.2f}s")
    print(LOG_SEPARATOR)
    
    # Exit with error if any test failed
    sys.exit(0 if failed == 0 else 1)