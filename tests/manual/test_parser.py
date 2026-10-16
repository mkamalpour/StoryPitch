#!/usr/bin/env python3
"""
Parser Components Test - Focused testing of parsing and text processing

Tests:
- JSON parser (parse_ai_output)
- Prompt builder (build_prompt)
- Postprocessor (normalize_ai_text_to_story)
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from story.parser import parse_ai_output
from story.prompts import build_prompt
from story.postprocess import normalize_ai_text_to_story
from utils.formatting import (
    print_section_header, print_success, print_error,
    print_info, format_duration
)

configure_logging()


def test_json_parser():
    """Test JSON parser"""
    print_info("Testing JSON parser...")

    try:
        # Test valid JSON
        ai_output = '{"narration":"You enter a dark cave.","choices":["Go deeper","Turn back","Light a torch"],"clues":"strange markings"}'
        result = parse_ai_output(ai_output)

        assert result.get("narration"), "Narration not parsed"
        assert len(result.get("choices", [])) >= 2, "Choices not parsed correctly"
        print_success(f"JSON parser working - Parsed {len(result.get('choices', []))} choices")

        # Test with extra whitespace
        ai_output2 = '''
        {
            "narration": "The forest is quiet.",
            "choices": ["Listen carefully", "Move forward"],
            "clues": "footprints"
        }
        '''
        result2 = parse_ai_output(ai_output2)
        assert result2.get("narration"), "Parser failed with whitespace"
        print_success("JSON parser handles whitespace correctly")

        # Test with memory extraction
        ai_output3 = '''
        {
            "narration": "You meet a mysterious stranger named Marcus in the old library.",
            "choices": ["Talk to Marcus", "Explore the library", "Leave quietly"],
            "clues": "ancient book on the table",
            "memory": {
                "npcs": ["Marcus"],
                "locations": ["Old Library"],
                "items": ["Ancient Book"],
                "events": ["Met Marcus"],
                "discoveries": ["Library contains forbidden knowledge"]
            }
        }
        '''
        result3 = parse_ai_output(ai_output3)
        assert result3.get("memory"), "Memory not parsed"
        assert "Marcus" in result3["memory"].get("npcs", []), "NPC not extracted"
        assert "Old Library" in result3["memory"].get("locations", []), "Location not extracted"
        print_success(f"JSON parser extracts memory - {len(result3['memory'].get('npcs', []))} NPCs, {len(result3['memory'].get('locations', []))} locations")

        return True

    except Exception as e:
        print_error(f"JSON parser test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_prompt_builder():
    """Test prompt builder"""
    print_info("Testing prompt builder...")

    try:
        from db.db import SessionModel

        # Create a mock session
        session = SessionModel(id=1, user_id=1, title="Test Adventure")
        session.set_world_state({
            "theme": "Mystery School",
            "traits": ["brave", "curious"],
            "character_name": "Alex",
            "clues": ["old key", "whisper in the hallway"],
            "last_narration": "You stand in a dimly lit hallway."
        })

        # Build prompt
        prompt = build_prompt(session, user_input="Open the door with the key")

        # Verify prompt contains key elements
        assert "Theme:" in prompt, "Theme not in prompt"
        assert "Player Action:" in prompt, "Player action not in prompt"
        assert "Mystery School" in prompt, "Theme content not in prompt"
        assert "Open the door" in prompt, "User input not in prompt"

        print_success("Prompt builder working correctly")
        print(f"   Generated prompt length: {len(prompt)} characters")

        return True

    except Exception as e:
        print_error(f"Prompt builder test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_postprocessor():
    """Test postprocessor"""
    print_info("Testing postprocessor...")

    try:
        # Test with markdown-wrapped JSON
        raw_output = """
        ```json
        {"narration":"Hello brave adventurer!","choices":["Go north","Go south","Go south"],"clues":"ancient map"}
        ```
        """

        result = normalize_ai_text_to_story(raw_output, max_choices=3)

        assert result.get("narration"), "Narration not extracted"
        assert result["narration"].startswith("Hello"), "Narration not cleaned"
        assert len(result.get("choices", [])) >= 2, "Choices not extracted"

        # Check duplicate removal
        choices = result.get("choices", [])
        unique_choices = set(choices)
        print_success(f"Postprocessor working - {len(choices)} choices, {len(unique_choices)} unique")

        # Test with plain JSON
        raw_output2 = '{"narration":"Test narration","choices":["A","B","C"],"clues":"hint"}'
        result2 = normalize_ai_text_to_story(raw_output2, max_choices=3)
        assert result2.get("narration") == "Test narration", "Plain JSON not handled"
        print_success("Postprocessor handles plain JSON correctly")

        # Test with memory extraction (THE CRITICAL FIX!)
        raw_output3 = '''
        ```json
        {
            "narration": "You encounter Sarah the merchant in the bustling marketplace.",
            "choices": ["Buy supplies", "Ask about rumors", "Continue walking"],
            "clues": "She seems nervous",
            "memory": {
                "npcs": ["Sarah"],
                "locations": ["Marketplace"],
                "items": ["Healing Potion"],
                "events": ["Met Sarah the merchant"],
                "discoveries": ["Marketplace is unusually busy"]
            }
        }
        ```
        '''
        result3 = normalize_ai_text_to_story(raw_output3, max_choices=3)
        assert result3.get("memory"), "Memory not preserved by postprocessor"
        assert "Sarah" in result3["memory"].get("npcs", []), "NPC not preserved"
        assert "Marketplace" in result3["memory"].get("locations", []), "Location not preserved"
        assert "Healing Potion" in result3["memory"].get("items", []), "Item not preserved"
        print_success(f"Postprocessor preserves memory - {len(result3['memory'].get('npcs', []))} NPCs, {len(result3['memory'].get('locations', []))} locations, {len(result3['memory'].get('items', []))} items")

        return True

    except Exception as e:
        print_error(f"Postprocessor test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def main():
    """Run parser component tests"""
    start_time = time.time()

    print_section_header("🔧 PARSER COMPONENTS TEST")
    print("Testing parser, prompt builder, and postprocessor\n")

    tests_passed = 0
    total_tests = 3

    # Test 1: JSON Parser
    print("\n[1/3] JSON Parser")
    if test_json_parser():
        tests_passed += 1

    # Test 2: Prompt Builder
    print("\n[2/3] Prompt Builder")
    if test_prompt_builder():
        tests_passed += 1

    # Test 3: Postprocessor
    print("\n[3/3] Postprocessor")
    if test_postprocessor():
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
        print("🎉 ALL PARSER TESTS PASSED!")
        print("All text processing components are working correctly.")
    else:
        print(f"❌ {total_tests - tests_passed} TEST(S) FAILED!")
        print("Check the errors above for details.")
    print(LOG_SEPARATOR)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
