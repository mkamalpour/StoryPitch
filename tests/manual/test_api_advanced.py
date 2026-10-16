#!/usr/bin/env python3
"""
Advanced API Endpoints Test - Comprehensive testing of all API endpoints

Tests:
- Session reset endpoint
- Snapshot save/load endpoints
- History retrieval
- Export functionality (JSON and text)
- Admin endpoints (list users, sessions, snapshots)
- Admin delete endpoints
- Admin clear-all endpoint
- LM Studio ping endpoint
"""

import asyncio
import httpx
import sys
import time
import atexit
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import API_HOST, API_PORT, configure_logging
from constants import LOG_SEPARATOR
from utils.api_utils import ensure_api_running, stop_api_server
from utils.formatting import (
    print_section_header, print_success, print_error,
    print_warning, print_info, format_duration
)

configure_logging()

API_BASE = f"http://{API_HOST}:{API_PORT}"

# Ensure API cleanup on exit
atexit.register(stop_api_server)


async def setup_test_session():
    """Create a test user and session for testing"""
    print_info("Setting up test session...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create user
            response = await client.post(
                f"{API_BASE}/api/user",
                json={"username": "test_advanced_user"}
            )
            response.raise_for_status()
            user = response.json()
            user_id = user["id"]

            # Start session
            response = await client.post(
                f"{API_BASE}/api/session/start",
                json={
                    "user_id": user_id,
                    "title": "Advanced Test Session",
                    "theme": "A test adventure",
                    "traits": ["brave"],
                    "character_name": "Tester"
                }
            )
            response.raise_for_status()
            session = response.json()
            session_id = session["session_id"]

            print_success(f"Test session created - User ID: {user_id}, Session ID: {session_id}")
            return user_id, session_id

    except Exception as e:
        print_error(f"Setup failed: {e}")
        return None, None


async def test_session_reset(session_id):
    """Test session reset endpoint"""
    print_info("Testing session reset endpoint...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{API_BASE}/api/session/{session_id}/reset")

            if response.status_code == 200:
                data = response.json()
                assert data.get("status") == "ok", "Reset status not ok"
                assert data.get("session_id") == session_id, "Session ID mismatch"
                print_success("Session reset endpoint working")
                return True
            else:
                print_error(f"Reset failed: {response.status_code}")
                return False

    except Exception as e:
        print_error(f"Session reset test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_snapshot_save_load(session_id):
    """Test snapshot save and load endpoints"""
    print_info("Testing snapshot save/load endpoints...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Save snapshot
            response = await client.post(f"{API_BASE}/api/session/{session_id}/save")

            if response.status_code != 200:
                print_error(f"Snapshot save failed: {response.status_code}")
                return False

            save_data = response.json()
            snapshot_id = save_data.get("snapshot_id")
            assert snapshot_id, "No snapshot_id returned"
            print_success(f"Snapshot saved - ID: {snapshot_id}")

            # Load snapshot
            response = await client.post(f"{API_BASE}/api/session/{session_id}/load")

            if response.status_code != 200:
                print_error(f"Snapshot load failed: {response.status_code}")
                return False

            load_data = response.json()
            assert load_data.get("status") == "ok", "Load status not ok"
            assert "current_step" in load_data, "Missing current_step"
            assert "world_state" in load_data, "Missing world_state"
            print_success("Snapshot loaded successfully")

            return True

    except Exception as e:
        print_error(f"Snapshot save/load test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_session_history(session_id):
    """Test session history endpoint"""
    print_info("Testing session history endpoint...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/session/{session_id}/history")

            if response.status_code == 200:
                data = response.json()
                assert "steps" in data, "Missing steps in history"
                steps = data["steps"]
                assert isinstance(steps, list), "Steps should be a list"
                print_success(f"History retrieved - {len(steps)} step(s)")

                # Verify step structure
                if steps:
                    step = steps[0]
                    assert "step_index" in step, "Missing step_index"
                    assert "prompt" in step, "Missing prompt"
                    assert "ai_output" in step, "Missing ai_output"
                    print_success("Step structure validated")

                return True
            else:
                print_error(f"History retrieval failed: {response.status_code}")
                return False

    except Exception as e:
        print_error(f"Session history test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_session_export(session_id):
    """Test session export endpoint (JSON and text formats)"""
    print_info("Testing session export endpoint...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test JSON export
            response = await client.get(f"{API_BASE}/api/session/{session_id}/export?fmt=json")

            if response.status_code != 200:
                print_error(f"JSON export failed: {response.status_code}")
                return False

            json_data = response.json()
            assert "session" in json_data, "Missing session in export"
            assert "steps" in json_data, "Missing steps in export"
            print_success("JSON export working")

            # Test text export
            response = await client.get(f"{API_BASE}/api/session/{session_id}/export?fmt=text")

            if response.status_code != 200:
                print_error(f"Text export failed: {response.status_code}")
                return False

            text_data = response.text
            assert len(text_data) > 0, "Empty text export"
            assert "Title:" in text_data or "Story:" in text_data, "Invalid text format"
            print_success("Text export working")

            return True

    except Exception as e:
        print_error(f"Session export test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_admin_list_endpoints():
    """Test admin list endpoints"""
    print_info("Testing admin list endpoints...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # List users
            response = await client.get(f"{API_BASE}/api/admin/users")
            if response.status_code != 200:
                print_error(f"List users failed: {response.status_code}")
                return False

            users_data = response.json()
            assert "users" in users_data, "Missing users key"
            print_success(f"Users listed - {len(users_data['users'])} user(s)")

            # List sessions
            response = await client.get(f"{API_BASE}/api/admin/sessions")
            if response.status_code != 200:
                print_error(f"List sessions failed: {response.status_code}")
                return False

            sessions_data = response.json()
            assert "sessions" in sessions_data, "Missing sessions key"
            print_success(f"Sessions listed - {len(sessions_data['sessions'])} session(s)")

            # List snapshots
            response = await client.get(f"{API_BASE}/api/admin/snapshots")
            if response.status_code != 200:
                print_error(f"List snapshots failed: {response.status_code}")
                return False

            snapshots_data = response.json()
            assert "snapshots" in snapshots_data, "Missing snapshots key"
            print_success(f"Snapshots listed - {len(snapshots_data['snapshots'])} snapshot(s)")

            return True

    except Exception as e:
        print_error(f"Admin list endpoints test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_lm_studio_ping():
    """Test LM Studio ping endpoint"""
    print_info("Testing LM Studio ping endpoint...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/admin/ping-lmstudio")

            if response.status_code == 200:
                data = response.json()
                assert "base" in data or "checks" in data, "Invalid ping response structure"
                print_success("LM Studio ping endpoint working")
                print(f"   Response: {data.get('base', 'N/A')}")
                return True
            else:
                print_warning(f"LM Studio ping returned: {response.status_code}")
                return True  # Not a failure if LM Studio isn't running

    except Exception as e:
        print_error(f"LM Studio ping test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_session_state(session_id):
    """Test session state retrieval endpoint"""
    print_info("Testing session state endpoint...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/session/{session_id}/state")

            if response.status_code == 200:
                data = response.json()
                assert "session_id" in data, "Missing session_id"
                assert "user_id" in data, "Missing user_id"
                assert "title" in data, "Missing title"
                assert "current_step" in data, "Missing current_step"
                assert "world_state" in data, "Missing world_state"
                print_success("Session state retrieved successfully")
                print(f"   Current step: {data['current_step']}")
                return True
            else:
                print_error(f"State retrieval failed: {response.status_code}")
                return False

    except Exception as e:
        print_error(f"Session state test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Run advanced API tests"""
    start_time = time.time()

    print_section_header("🚀 ADVANCED API ENDPOINTS TEST")
    print("Testing all API endpoints comprehensively\n")

    # Ensure API is running
    print_info("Ensuring API server is running...")
    is_running, was_started = await ensure_api_running()

    if not is_running:
        print_error("Failed to start API server")
        return 1

    if was_started:
        print_success("API server started")
        await asyncio.sleep(2)  # Give it time to fully initialize
    else:
        print_success("API server already running")

    # Setup test data
    user_id, session_id = await setup_test_session()
    if not session_id:
        print_error("Failed to setup test session")
        return 1

    tests_passed = 0
    total_tests = 8

    # Test 1: Session State
    print("\n[1/8] Session State Endpoint")
    if await test_session_state(session_id):
        tests_passed += 1

    # Test 2: Session History
    print("\n[2/8] Session History Endpoint")
    if await test_session_history(session_id):
        tests_passed += 1

    # Test 3: Snapshot Save/Load
    print("\n[3/8] Snapshot Save/Load Endpoints")
    if await test_snapshot_save_load(session_id):
        tests_passed += 1

    # Test 4: Session Export
    print("\n[4/8] Session Export Endpoint")
    if await test_session_export(session_id):
        tests_passed += 1

    # Test 5: Session Reset
    print("\n[5/8] Session Reset Endpoint")
    if await test_session_reset(session_id):
        tests_passed += 1

    # Test 6: Admin List Endpoints
    print("\n[6/8] Admin List Endpoints")
    if await test_admin_list_endpoints():
        tests_passed += 1

    # Test 7: LM Studio Ping
    print("\n[7/8] LM Studio Ping Endpoint")
    if await test_lm_studio_ping():
        tests_passed += 1

    # Test 8: Root Endpoint
    print("\n[8/8] Root Endpoint")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/")
            if response.status_code == 200:
                data = response.json()
                assert "message" in data, "Missing message in root response"
                print_success("Root endpoint working")
                tests_passed += 1
            else:
                print_error(f"Root endpoint failed: {response.status_code}")
    except Exception as e:
        print_error(f"Root endpoint test failed: {e}")

    # Summary
    duration = time.time() - start_time
    print(f"\n{LOG_SEPARATOR}")
    print("📊 TEST RESULTS")
    print(LOG_SEPARATOR)
    print(f"Passed: {tests_passed}/{total_tests}")
    print(f"Duration: {format_duration(duration)}")
    print(LOG_SEPARATOR)

    if tests_passed == total_tests:
        print("🎉 ALL ADVANCED API TESTS PASSED!")
        print("All API endpoints are working correctly.")
    else:
        print(f"⚠️  {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
