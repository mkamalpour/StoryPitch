#!/usr/bin/env python3
"""
Advanced Database Operations Test - Comprehensive database testing

Tests:
- Session reset with step deletion
- World state JSON serialization edge cases
- Admin query functions (get_all_*)
- Snapshot operations (create, load, delete)
- Step retrieval and ordering
- Database cleanup operations
- Edge cases and error handling
"""

import asyncio
import sys
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from db.db import (
    init_db, create_user, create_session, get_session, update_session,
    save_step, get_steps, create_snapshot, load_snapshot, delete_user,
    delete_session, delete_snapshot, reset_session, get_all_users,
    get_all_sessions, get_all_snapshots, get_user
)
from utils.formatting import (
    print_section_header, print_success, print_error, 
    print_info, print_warning, format_duration
)

configure_logging()


async def test_world_state_serialization():
    """Test world state JSON serialization with complex data"""
    print_info("Testing world state serialization...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_worldstate_user")
        
        # Test complex world state
        complex_state = {
            "theme": "Test Theme",
            "traits": ["brave", "clever", "curious"],
            "character_name": "TestHero",
            "clues": ["clue1", "clue2", "clue3"],
            "consequences": ["action1", "action2"],
            "discoveries": ["discovery1"],
            "relationships": {"npc1": "friendly", "npc2": "hostile"},
            "inventory": ["sword", "shield", "potion"],
            "story_arc": "rising",
            "nested_data": {
                "level1": {
                    "level2": {
                        "value": "deep_nested"
                    }
                }
            },
            "unicode_test": "Hello 世界 🎮",
            "special_chars": "Test with \"quotes\" and 'apostrophes' and \n newlines"
        }
        
        sess = create_session(user.id, title="WorldState Test", world_state=complex_state)
        print_success(f"Session created with complex world state - ID: {sess.id}")
        
        # Retrieve and verify
        retrieved_sess = get_session(sess.id)
        retrieved_state = retrieved_sess.get_world_state()
        
        # Verify all fields
        assert retrieved_state["theme"] == complex_state["theme"], "Theme mismatch"
        assert retrieved_state["traits"] == complex_state["traits"], "Traits mismatch"
        assert retrieved_state["clues"] == complex_state["clues"], "Clues mismatch"
        assert retrieved_state["nested_data"]["level1"]["level2"]["value"] == "deep_nested", "Nested data mismatch"
        assert retrieved_state["unicode_test"] == complex_state["unicode_test"], "Unicode mismatch"
        print_success("Complex world state serialization working correctly")
        
        # Test update with modified state
        complex_state["new_field"] = "added_after_creation"
        complex_state["clues"].append("clue4")
        update_session(sess.id, world_state=complex_state)
        
        updated_sess = get_session(sess.id)
        updated_state = updated_sess.get_world_state()
        assert "new_field" in updated_state, "New field not added"
        assert len(updated_state["clues"]) == 4, "Clue not appended"
        print_success("World state updates working correctly")
        
        # Cleanup
        delete_session(sess.id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"World state serialization test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_session_reset_with_steps():
    """Test session reset functionality with step deletion"""
    print_info("Testing session reset with step deletion...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_reset_user")
        sess = create_session(user.id, title="Reset Test")
        
        # Add multiple steps
        for i in range(1, 6):
            save_step(sess.id, i, f"prompt_{i}", f"output_{i}", f"input_{i}")
        
        # Update session state
        update_session(sess.id, current_step=5)
        
        # Verify steps exist
        steps_before = get_steps(sess.id)
        assert len(steps_before) == 5, f"Expected 5 steps, got {len(steps_before)}"
        print_success(f"Created {len(steps_before)} steps")
        
        # Reset session
        reset_sess = reset_session(sess.id)
        assert reset_sess is not None, "Reset returned None"
        assert reset_sess.current_step == 0, "Step not reset to 0"
        
        # Verify steps deleted
        steps_after = get_steps(sess.id)
        assert len(steps_after) == 0, f"Steps not deleted, found {len(steps_after)}"
        print_success("Session reset successfully - all steps deleted")
        
        # Verify world state cleared
        world_state = reset_sess.get_world_state()
        assert world_state == {}, "World state not cleared"
        print_success("World state cleared on reset")
        
        # Cleanup
        delete_session(sess.id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Session reset test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_admin_query_functions():
    """Test admin query functions (get_all_*)"""
    print_info("Testing admin query functions...")
    
    try:
        init_db()
        
        # Create multiple users
        users = []
        for i in range(3):
            user = create_user(f"admin_test_user_{i}")
            users.append(user)
        
        # Create multiple sessions
        sessions = []
        for user in users:
            sess = create_session(user.id, title=f"Session for {user.username}")
            sessions.append(sess)
        
        # Create snapshots
        snapshots = []
        for sess in sessions:
            snap = create_snapshot(sess.id, title=f"Snapshot for session {sess.id}")
            snapshots.append(snap)
        
        # Test get_all_users
        all_users = get_all_users()
        assert len(all_users) >= 3, f"Expected at least 3 users, got {len(all_users)}"
        print_success(f"get_all_users() returned {len(all_users)} user(s)")
        
        # Test get_all_sessions
        all_sessions = get_all_sessions()
        assert len(all_sessions) >= 3, f"Expected at least 3 sessions, got {len(all_sessions)}"
        print_success(f"get_all_sessions() returned {len(all_sessions)} session(s)")
        
        # Test get_all_snapshots
        all_snapshots = get_all_snapshots()
        assert len(all_snapshots) >= 3, f"Expected at least 3 snapshots, got {len(all_snapshots)}"
        print_success(f"get_all_snapshots() returned {len(all_snapshots)} snapshot(s)")
        
        # Test get_user
        test_user = get_user(users[0].id)
        assert test_user is not None, "get_user returned None"
        assert test_user.username == users[0].username, "Username mismatch"
        print_success("get_user() working correctly")
        
        # Cleanup
        for snap in snapshots:
            delete_snapshot(snap.id)
        for sess in sessions:
            delete_session(sess.id)
        for user in users:
            delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Admin query functions test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_step_ordering():
    """Test step retrieval and ordering"""
    print_info("Testing step ordering...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_ordering_user")
        sess = create_session(user.id, title="Ordering Test")
        
        # Add steps in non-sequential order
        step_indices = [3, 1, 5, 2, 4]
        for idx in step_indices:
            save_step(sess.id, idx, f"prompt_{idx}", f"output_{idx}", f"input_{idx}")
        
        # Retrieve steps
        steps = get_steps(sess.id)
        assert len(steps) == 5, f"Expected 5 steps, got {len(steps)}"
        
        # Verify ordering (should be sorted by step_index)
        for i, step in enumerate(steps):
            expected_idx = i + 1
            assert step.step_index == expected_idx, f"Step {i} has index {step.step_index}, expected {expected_idx}"
        
        print_success("Steps retrieved in correct order (1, 2, 3, 4, 5)")
        
        # Verify step content
        assert steps[0].prompt == "prompt_1", "Step 1 prompt mismatch"
        assert steps[2].ai_output == "output_3", "Step 3 output mismatch"
        assert steps[4].user_input == "input_5", "Step 5 input mismatch"
        print_success("Step content verified")
        
        # Cleanup
        delete_session(sess.id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Step ordering test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_snapshot_operations():
    """Test comprehensive snapshot operations"""
    print_info("Testing snapshot operations...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_snapshot_user")
        sess = create_session(user.id, title="Snapshot Test")
        
        # Set initial state
        initial_state = {"step": 1, "data": "initial"}
        update_session(sess.id, world_state=initial_state, current_step=1)
        
        # Create first snapshot
        snap1 = create_snapshot(sess.id, title="snapshot_1")
        assert snap1 is not None, "Failed to create snapshot 1"
        print_success(f"Snapshot 1 created - ID: {snap1.id}")
        
        # Modify session
        modified_state = {"step": 2, "data": "modified"}
        update_session(sess.id, world_state=modified_state, current_step=2)
        
        # Create second snapshot
        snap2 = create_snapshot(sess.id, title="snapshot_2")
        assert snap2 is not None, "Failed to create snapshot 2"
        print_success(f"Snapshot 2 created - ID: {snap2.id}")
        
        # Load first snapshot
        loaded_sess = load_snapshot(sess.id, snap1.id)
        assert loaded_sess is not None, "Failed to load snapshot 1"
        assert loaded_sess.current_step == 1, "Step not restored to 1"
        loaded_state = loaded_sess.get_world_state()
        assert loaded_state["data"] == "initial", "State not restored correctly"
        print_success("Snapshot 1 loaded successfully - state restored")
        
        # Load second snapshot
        loaded_sess2 = load_snapshot(sess.id, snap2.id)
        assert loaded_sess2.current_step == 2, "Step not restored to 2"
        loaded_state2 = loaded_sess2.get_world_state()
        assert loaded_state2["data"] == "modified", "State not restored to modified"
        print_success("Snapshot 2 loaded successfully - state restored")
        
        # Load latest snapshot (without specifying ID)
        loaded_latest = load_snapshot(sess.id, snapshot_id=None)
        assert loaded_latest is not None, "Failed to load latest snapshot"
        assert loaded_latest.current_step == 2, "Latest snapshot not loaded"
        print_success("Latest snapshot loaded successfully")
        
        # Delete snapshots
        assert delete_snapshot(snap1.id), "Failed to delete snapshot 1"
        assert delete_snapshot(snap2.id), "Failed to delete snapshot 2"
        print_success("Snapshots deleted successfully")
        
        # Cleanup
        delete_session(sess.id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Snapshot operations test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_edge_cases():
    """Test edge cases and error handling"""
    print_info("Testing edge cases...")
    
    try:
        init_db()
        
        # Test get_session with invalid ID
        invalid_sess = get_session(999999)
        assert invalid_sess is None, "Should return None for invalid session ID"
        print_success("Invalid session ID handled correctly")
        
        # Test get_user with invalid ID
        invalid_user = get_user(999999)
        assert invalid_user is None, "Should return None for invalid user ID"
        print_success("Invalid user ID handled correctly")
        
        # Test delete_session with invalid ID
        result = delete_session(999999)
        assert result is False, "Should return False for invalid session ID"
        print_success("Invalid session deletion handled correctly")
        
        # Test delete_user with invalid ID
        result = delete_user(999999)
        assert result is False, "Should return False for invalid user ID"
        print_success("Invalid user deletion handled correctly")
        
        # Test delete_snapshot with invalid ID
        result = delete_snapshot(999999)
        assert result is False, "Should return False for invalid snapshot ID"
        print_success("Invalid snapshot deletion handled correctly")
        
        # Test empty world state
        user = create_user("test_edge_user")
        sess = create_session(user.id, title="Edge Test", world_state={})
        retrieved_state = sess.get_world_state()
        assert retrieved_state == {}, "Empty world state not handled"
        print_success("Empty world state handled correctly")
        
        # Test None world state
        sess2 = create_session(user.id, title="Edge Test 2", world_state=None)
        retrieved_state2 = sess2.get_world_state()
        assert retrieved_state2 == {}, "None world state not handled"
        print_success("None world state handled correctly")
        
        # Cleanup
        delete_session(sess.id)
        delete_session(sess2.id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Edge cases test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Run advanced database tests"""
    start_time = time.time()
    
    print_section_header("🗄️  ADVANCED DATABASE OPERATIONS TEST")
    print("Testing comprehensive database functionality\n")
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: World State Serialization
    print("\n[1/6] World State Serialization")
    if await test_world_state_serialization():
        tests_passed += 1
    
    # Test 2: Session Reset with Steps
    print("\n[2/6] Session Reset with Step Deletion")
    if await test_session_reset_with_steps():
        tests_passed += 1
    
    # Test 3: Admin Query Functions
    print("\n[3/6] Admin Query Functions")
    if await test_admin_query_functions():
        tests_passed += 1
    
    # Test 4: Step Ordering
    print("\n[4/6] Step Ordering")
    if await test_step_ordering():
        tests_passed += 1
    
    # Test 5: Snapshot Operations
    print("\n[5/6] Snapshot Operations")
    if await test_snapshot_operations():
        tests_passed += 1
    
    # Test 6: Edge Cases
    print("\n[6/6] Edge Cases and Error Handling")
    if await test_edge_cases():
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
        print("🎉 ALL ADVANCED DATABASE TESTS PASSED!")
        print("All database operations are working correctly.")
    else:
        print(f"⚠️  {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)
    
    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))