#!/usr/bin/env python3
"""
Advanced Integration Test - Comprehensive end-to-end testing

Tests:
- Multi-step story progression (10+ steps)
- Save/load/restore workflow
- Multiple concurrent sessions
- Error recovery scenarios
- World state persistence across steps
- Story arc progression
- Consequence and discovery tracking
- Complete user journey
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from db.db import init_db, create_user, delete_user, delete_session, get_session
from story.logic import start_session, advance_session
from utils.formatting import (
    print_section_header, print_success, print_error, 
    print_info, print_warning, format_duration
)

configure_logging()


async def test_multi_step_progression():
    """Test multi-step story progression (10 steps)"""
    print_info("Testing multi-step story progression...")
    
    try:
        init_db()
        
        # Create user
        user = create_user("test_multistep_user")
        user_id = user.id
        print_success(f"User created - ID: {user_id}")
        
        # Start session
        result = await start_session(
            user_id=user_id,
            title="Multi-Step Test",
            theme="A journey through an enchanted forest",
            traits=["brave", "curious"],
            character_name="Adventurer"
        )
        
        session_id = result["session_id"]
        print_success(f"Session started - ID: {session_id}")
        
        # Advance through 10 steps
        for step in range(1, 11):
            print_info(f"Advancing to step {step}...")
            
            result = await advance_session(
                session_id=session_id,
                user_input=f"I continue my journey through the forest (step {step})"
            )
            
            assert "narration" in result, f"Step {step}: Missing narration"
            assert "choices" in result, f"Step {step}: Missing choices"
            assert result["step_index"] == step + 1, f"Step {step}: Index mismatch"
            
            # Verify world state is being updated
            sess = get_session(session_id)
            world_state = sess.get_world_state()
            assert "last_narration" in world_state, f"Step {step}: Missing last_narration"
            assert "last_action" in world_state, f"Step {step}: Missing last_action"
            
            print_success(f"Step {step} completed - Narration: {len(result['narration'])} chars")
        
        # Verify final state
        final_sess = get_session(session_id)
        assert final_sess.current_step == 11, "Final step count incorrect"
        
        final_state = final_sess.get_world_state()
        assert "consequences" in final_state, "Missing consequences tracking"
        assert len(final_state["consequences"]) >= 10, "Not all consequences tracked"
        
        print_success(f"Multi-step progression complete - {final_sess.current_step} steps total")
        print(f"   Consequences tracked: {len(final_state['consequences'])}")
        
        # Cleanup
        delete_session(session_id)
        delete_user(user_id)
        
        return True
        
    except Exception as e:
        print_error(f"Multi-step progression test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_save_load_restore_workflow():
    """Test complete save/load/restore workflow"""
    print_info("Testing save/load/restore workflow...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_saveload_user")
        result = await start_session(
            user_id=user.id,
            title="Save/Load Test",
            theme="A test adventure",
            traits=["clever"],
            character_name="Tester"
        )
        
        session_id = result["session_id"]
        print_success(f"Session started - ID: {session_id}")
        
        # Advance a few steps
        for i in range(3):
            await advance_session(session_id, user_input=f"Action {i+1}")
        
        # Get state before save
        sess_before = get_session(session_id)
        step_before = sess_before.current_step
        state_before = sess_before.get_world_state()
        
        print_success(f"Advanced to step {step_before}")
        
        # Create snapshot
        from db.db import create_snapshot
        snap = create_snapshot(session_id, title="test_snapshot")
        assert snap is not None, "Failed to create snapshot"
        print_success(f"Snapshot created - ID: {snap.id}")
        
        # Continue advancing
        for i in range(3):
            await advance_session(session_id, user_input=f"Action after save {i+1}")
        
        sess_after = get_session(session_id)
        step_after = sess_after.current_step
        assert step_after > step_before, "Session didn't advance"
        print_success(f"Advanced further to step {step_after}")
        
        # Load snapshot
        from db.db import load_snapshot
        loaded_sess = load_snapshot(session_id, snap.id)
        assert loaded_sess is not None, "Failed to load snapshot"
        assert loaded_sess.current_step == step_before, "Step not restored"
        
        loaded_state = loaded_sess.get_world_state()
        assert loaded_state["last_narration"] == state_before["last_narration"], "State not restored"
        
        print_success(f"Snapshot loaded - Restored to step {loaded_sess.current_step}")
        
        # Continue from restored point
        result = await advance_session(session_id, user_input="Action after restore")
        assert result["step_index"] == step_before + 1, "Continuation failed"
        print_success("Continued successfully from restored point")
        
        # Cleanup
        from db.db import delete_snapshot
        delete_snapshot(snap.id)
        delete_session(session_id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Save/load/restore workflow test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_concurrent_sessions():
    """Test multiple concurrent user sessions"""
    print_info("Testing concurrent sessions...")
    
    try:
        init_db()
        
        # Create multiple users
        users = []
        for i in range(3):
            user = create_user(f"concurrent_user_{i}")
            users.append(user)
        
        print_success(f"Created {len(users)} users")
        
        # Start sessions concurrently
        start_tasks = [
            start_session(
                user_id=user.id,
                title=f"Concurrent Session {i}",
                theme=f"Adventure {i}",
                traits=["brave"],
                character_name=f"Hero{i}"
            )
            for i, user in enumerate(users)
        ]
        
        session_results = await asyncio.gather(*start_tasks)
        session_ids = [r["session_id"] for r in session_results]
        
        print_success(f"Started {len(session_ids)} concurrent sessions")
        
        # Advance all sessions concurrently
        for step in range(3):
            advance_tasks = [
                advance_session(sid, user_input=f"Concurrent action {step}")
                for sid in session_ids
            ]
            
            advance_results = await asyncio.gather(*advance_tasks)
            assert len(advance_results) == len(session_ids), "Not all sessions advanced"
            print_success(f"All sessions advanced to step {step + 2}")
        
        # Verify all sessions are independent
        for i, sid in enumerate(session_ids):
            sess = get_session(sid)
            assert sess.user_id == users[i].id, f"Session {i} user mismatch"
            assert sess.current_step == 4, f"Session {i} step mismatch"
            print_success(f"Session {i} verified - Independent state maintained")
        
        # Cleanup
        for sid in session_ids:
            delete_session(sid)
        for user in users:
            delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Concurrent sessions test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_story_arc_progression():
    """Test story arc progression through stages"""
    print_info("Testing story arc progression...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_arc_user")
        result = await start_session(
            user_id=user.id,
            title="Arc Test",
            theme="An epic journey",
            traits=["brave"],
            character_name="Hero"
        )
        
        session_id = result["session_id"]
        
        # Check initial arc
        sess = get_session(session_id)
        state = sess.get_world_state()
        assert state.get("story_arc") == "beginning", "Initial arc should be 'beginning'"
        print_success("Story arc starts at 'beginning'")
        
        # Advance to "rising" (steps 4-8)
        for i in range(4):
            await advance_session(session_id, user_input=f"Action {i+1}")
        
        sess = get_session(session_id)
        state = sess.get_world_state()
        assert state.get("story_arc") == "rising", "Arc should be 'rising'"
        print_success("Story arc progressed to 'rising'")
        
        # Advance to "climax" (steps 9-12)
        for i in range(5):
            await advance_session(session_id, user_input=f"Action {i+5}")
        
        sess = get_session(session_id)
        state = sess.get_world_state()
        assert state.get("story_arc") == "climax", "Arc should be 'climax'"
        print_success("Story arc progressed to 'climax'")
        
        # Advance to "resolution" (steps 13+)
        for i in range(2):
            await advance_session(session_id, user_input=f"Action {i+10}")
        
        sess = get_session(session_id)
        state = sess.get_world_state()
        assert state.get("story_arc") == "resolution", "Arc should be 'resolution'"
        print_success("Story arc progressed to 'resolution'")
        
        # Cleanup
        delete_session(session_id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"Story arc progression test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_world_state_persistence():
    """Test world state persistence across steps"""
    print_info("Testing world state persistence...")
    
    try:
        init_db()
        
        # Create user and session
        user = create_user("test_persistence_user")
        result = await start_session(
            user_id=user.id,
            title="Persistence Test",
            theme="A persistent world",
            traits=["curious", "clever"],
            character_name="Observer"
        )
        
        session_id = result["session_id"]
        
        # Verify initial state
        sess = get_session(session_id)
        state = sess.get_world_state()
        
        assert state["theme"] == "A persistent world", "Theme not persisted"
        assert "curious" in state["traits"], "Traits not persisted"
        assert state["character_name"] == "Observer", "Character name not persisted"
        print_success("Initial world state persisted correctly")
        
        # Advance and check persistence
        for i in range(5):
            await advance_session(session_id, user_input=f"Persistent action {i+1}")
            
            sess = get_session(session_id)
            state = sess.get_world_state()
            
            # Verify core state persists
            assert state["theme"] == "A persistent world", f"Step {i+1}: Theme lost"
            assert "curious" in state["traits"], f"Step {i+1}: Traits lost"
            assert state["character_name"] == "Observer", f"Step {i+1}: Character name lost"
            
            # Verify accumulating data
            assert "consequences" in state, f"Step {i+1}: Consequences missing"
            assert len(state["consequences"]) == i + 1, f"Step {i+1}: Consequence count wrong"
            
            print_success(f"Step {i+1}: World state persisted correctly")
        
        # Verify final state completeness
        final_sess = get_session(session_id)
        final_state = final_sess.get_world_state()
        
        assert "last_narration" in final_state, "Missing last_narration"
        assert "last_action" in final_state, "Missing last_action"
        assert "last_choices" in final_state, "Missing last_choices"
        assert len(final_state["consequences"]) == 5, "Consequences not accumulated"
        
        print_success("Complete world state persistence verified")
        
        # Cleanup
        delete_session(session_id)
        delete_user(user.id)
        
        return True
        
    except Exception as e:
        print_error(f"World state persistence test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_complete_user_journey():
    """Test complete user journey from start to finish"""
    print_info("Testing complete user journey...")
    
    try:
        init_db()
        
        # 1. User registration
        user = create_user("journey_user")
        print_success(f"✓ User registered - ID: {user.id}")
        
        # 2. Start first session
        session1 = await start_session(
            user_id=user.id,
            title="First Adventure",
            theme="A mysterious castle",
            traits=["brave", "clever"],
            character_name="Knight"
        )
        sid1 = session1["session_id"]
        print_success(f"✓ First session started - ID: {sid1}")
        
        # 3. Play through session
        for i in range(3):
            await advance_session(sid1, user_input=f"Explore the castle {i+1}")
        print_success("✓ Played through first session")
        
        # 4. Save progress
        from db.db import create_snapshot
        snap1 = create_snapshot(sid1, title="castle_save")
        print_success(f"✓ Progress saved - Snapshot ID: {snap1.id}")
        
        # 5. Start second session
        session2 = await start_session(
            user_id=user.id,
            title="Second Adventure",
            theme="A dark forest",
            traits=["cautious"],
            character_name="Ranger"
        )
        sid2 = session2["session_id"]
        print_success(f"✓ Second session started - ID: {sid2}")
        
        # 6. Play second session
        for i in range(2):
            await advance_session(sid2, user_input=f"Navigate the forest {i+1}")
        print_success("✓ Played through second session")
        
        # 7. Return to first session
        from db.db import load_snapshot
        loaded = load_snapshot(sid1, snap1.id)
        assert loaded is not None, "Failed to load first session"
        print_success("✓ Returned to first session")
        
        # 8. Continue first session
        await advance_session(sid1, user_input="Continue castle exploration")
        print_success("✓ Continued first session")
        
        # 9. Verify both sessions exist independently
        from db.db import get_all_sessions
        all_sessions = get_all_sessions()
        user_sessions = [s for s in all_sessions if s.user_id == user.id]
        assert len(user_sessions) >= 2, "Both sessions should exist"
        print_success(f"✓ Both sessions exist independently ({len(user_sessions)} sessions)")
        
        # 10. Cleanup
        from db.db import delete_snapshot
        delete_snapshot(snap1.id)
        delete_session(sid1)
        delete_session(sid2)
        delete_user(user.id)
        print_success("✓ Cleanup completed")
        
        print_success("\n🎉 Complete user journey successful!")
        
        return True
        
    except Exception as e:
        print_error(f"Complete user journey test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Run advanced integration tests"""
    start_time = time.time()
    
    print_section_header("🔗 ADVANCED INTEGRATION TEST")
    print("Testing comprehensive end-to-end scenarios\n")
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: Multi-Step Progression
    print("\n[1/6] Multi-Step Story Progression (10 steps)")
    if await test_multi_step_progression():
        tests_passed += 1
    
    # Test 2: Save/Load/Restore Workflow
    print("\n[2/6] Save/Load/Restore Workflow")
    if await test_save_load_restore_workflow():
        tests_passed += 1
    
    # Test 3: Concurrent Sessions
    print("\n[3/6] Concurrent User Sessions")
    if await test_concurrent_sessions():
        tests_passed += 1
    
    # Test 4: Story Arc Progression
    print("\n[4/6] Story Arc Progression")
    if await test_story_arc_progression():
        tests_passed += 1
    
    # Test 5: World State Persistence
    print("\n[5/6] World State Persistence")
    if await test_world_state_persistence():
        tests_passed += 1
    
    # Test 6: Complete User Journey
    print("\n[6/6] Complete User Journey")
    if await test_complete_user_journey():
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
        print("🎉 ALL ADVANCED INTEGRATION TESTS PASSED!")
        print("All end-to-end scenarios are working correctly.")
    else:
        print(f"⚠️  {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)
    
    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))