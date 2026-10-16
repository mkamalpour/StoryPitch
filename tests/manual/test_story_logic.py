#!/usr/bin/env python3
"""
Story Logic Test - Focused testing of story generation logic

Tests:
- Session creation (start_session)
- Session advancement (advance_session)
- World state management
- Story progression
- Integration with LLM and database
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from db.db import init_db, create_user, delete_user, delete_session
from story.logic import start_session, advance_session
from utils.formatting import (
    print_section_header, print_success, print_error,
    print_info, print_warning, format_duration
)

configure_logging()


async def test_start_session():
    """Test starting a new story session"""
    print_info("Testing session start...")

    try:
        # Initialize database
        init_db()

        # Create test user
        user = create_user("test_story_user")
        user_id = user.id
        print_success(f"Test user created - ID: {user_id}")

        # Start a session
        result = await start_session(
            user_id=user_id,
            title="Test Story Session",
            theme="A mysterious adventure in an ancient temple",
            traits=["brave", "curious", "clever"],
            character_name="TestHero"
        )

        # Verify result structure
        assert result, "start_session returned None"
        assert "session_id" in result, "Missing session_id in result"
        assert "narration" in result, "Missing narration in result"
        assert "choices" in result, "Missing choices in result"

        session_id = result["session_id"]
        narration = result["narration"]
        choices = result["choices"]

        # Verify content
        assert session_id > 0, "Invalid session_id"
        assert len(narration) > 0, "Empty narration"
        assert len(choices) >= 2, f"Not enough choices: {len(choices)}"

        print_success(f"Session started successfully - ID: {session_id}")
        print(f"   Narration length: {len(narration)} characters")
        print(f"   Choices count: {len(choices)}")
        print(f"   First choice: {choices[0][:50]}...")

        return user_id, session_id

    except Exception as e:
        print_error(f"Session start test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return None, None


async def test_advance_session(session_id):
    """Test advancing a story session"""
    print_info("Testing session advancement...")

    try:
        # Advance the session with user input
        result = await advance_session(
            session_id=session_id,
            user_input="I decide to explore the ancient temple carefully"
        )

        # Verify result structure
        assert result, "advance_session returned None"
        assert "narration" in result, "Missing narration in result"
        assert "choices" in result, "Missing choices in result"
        assert "step_index" in result, "Missing step_index in result"

        narration = result["narration"]
        choices = result["choices"]
        step_index = result["step_index"]

        # Verify content
        assert len(narration) > 0, "Empty narration"
        assert len(choices) >= 2, f"Not enough choices: {len(choices)}"
        assert step_index > 0, "Invalid step_index"

        print_success(f"Session advanced successfully - Step: {step_index}")
        print(f"   Narration length: {len(narration)} characters")
        print(f"   Choices count: {len(choices)}")

        return True

    except Exception as e:
        print_error(f"Session advancement test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_multiple_advances(session_id):
    """Test multiple story advancements"""
    print_info("Testing multiple session advancements...")

    try:
        user_inputs = [
            "I look around for clues",
            "I examine the ancient writings on the wall",
            "I proceed deeper into the temple"
        ]

        for i, user_input in enumerate(user_inputs, start=1):
            print(f"   → Advance {i}/{len(user_inputs)}: {user_input[:40]}...")

            result = await advance_session(
                session_id=session_id,
                user_input=user_input
            )

            assert result, f"Advance {i} returned None"
            assert "narration" in result, f"Advance {i} missing narration"
            assert "step_index" in result, f"Advance {i} missing step_index"

            step_index = result["step_index"]
            print(f"      ✓ Step {step_index} completed")

        print_success(f"Multiple advancements successful - {len(user_inputs)} steps")
        return True

    except Exception as e:
        print_error(f"Multiple advancements test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_world_state_persistence(session_id):
    """Test that world state persists across steps"""
    print_info("Testing world state persistence...")

    try:
        from db.db import get_session

        # Get session and check world state
        session = get_session(session_id)
        assert session, "Session not found"

        world_state = session.get_world_state()
        assert world_state, "World state is empty"

        # Verify key world state elements
        assert "theme" in world_state, "Theme not in world state"
        assert "traits" in world_state, "Traits not in world state"
        assert "character_name" in world_state, "Character name not in world state"

        print_success("World state persists correctly")
        print(f"   Theme: {world_state.get('theme', 'N/A')[:50]}...")
        print(f"   Character: {world_state.get('character_name', 'N/A')}")
        print(f"   Traits: {world_state.get('traits', [])}")

        return True

    except Exception as e:
        print_error(f"World state persistence test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_cleanup(user_id, session_id):
    """Clean up test data"""
    print_info("Cleaning up test data...")

    try:
        if session_id:
            delete_session(session_id)
            print_success(f"Session {session_id} deleted")

        if user_id:
            delete_user(user_id)
            print_success(f"User {user_id} deleted")

        return True

    except Exception as e:
        print_warning(f"Cleanup failed: {e}")
        return False


async def main():
    """Run story logic tests"""
    start_time = time.time()

    print_section_header("📖 STORY LOGIC TEST")
    print("Testing story generation and progression logic\n")

    tests_passed = 0
    total_tests = 5
    user_id = None
    session_id = None

    # Test 1: Start Session
    print("\n[1/5] Session Start")
    user_id, session_id = await test_start_session()
    if user_id and session_id:
        tests_passed += 1
    else:
        print_error("Cannot continue without session")
        duration = time.time() - start_time
        print(f"\n{LOG_SEPARATOR}")
        print(f"❌ TEST FAILED: {tests_passed}/{total_tests} tests passed")
        print(f"Duration: {format_duration(duration)}")
        print(LOG_SEPARATOR)
        return 1

    # Test 2: Advance Session
    print("\n[2/5] Session Advancement")
    if await test_advance_session(session_id):
        tests_passed += 1

    # Test 3: Multiple Advances
    print("\n[3/5] Multiple Advancements")
    if await test_multiple_advances(session_id):
        tests_passed += 1

    # Test 4: World State Persistence
    print("\n[4/5] World State Persistence")
    if await test_world_state_persistence(session_id):
        tests_passed += 1

    # Test 5: Cleanup
    print("\n[5/5] Cleanup")
    if await test_cleanup(user_id, session_id):
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
        print("🎉 ALL STORY LOGIC TESTS PASSED!")
        print("Story generation and progression are working correctly.")
    else:
        print(f"❌ {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
