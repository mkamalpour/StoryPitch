#!/usr/bin/env python3
"""
UI Dependencies Test - Focused testing of UI library imports

Tests:
- Gradio import and basic functionality
- Telegram bot library imports
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import configure_logging
from constants import LOG_SEPARATOR
from utils.formatting import (
    print_section_header, print_success, print_error, 
    print_warning, print_info, format_duration
)

configure_logging()


def test_gradio_import():
    """Test that Gradio can be imported and basic setup works"""
    print_info("Testing Gradio UI dependencies...")
    
    try:
        import gradio as gr
        print_success("Gradio imported successfully")
        
        # Test basic Gradio components
        with gr.Blocks() as demo:
            gr.Markdown("# Test Interface")
            gr.Textbox(label="Test Input")
            gr.Button("Test Button")
        
        print_success("Gradio components working")
        print(f"   Gradio version: {gr.__version__}")
        return True
        
    except ImportError as e:
        print_error(f"Gradio import failed: {e}")
        print_warning("Install with: pip install gradio")
        return False
    except Exception as e:
        print_error(f"Gradio test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_telegram_import():
    """Test that Telegram bot dependencies can be imported"""
    print_info("Testing Telegram bot dependencies...")
    
    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
        
        print_success("Telegram bot libraries imported successfully")
        
        # Test basic handler creation
        async def test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            pass
        
        handler = CommandHandler("test", test_handler)
        print_success("Telegram handlers can be created")
        
        return True
        
    except ImportError as e:
        print_error(f"Telegram import failed: {e}")
        print_warning("Install with: pip install python-telegram-bot")
        return False
    except Exception as e:
        print_error(f"Telegram test failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def main():
    """Run UI dependency tests"""
    start_time = time.time()
    
    print_section_header("🎨 UI DEPENDENCIES TEST")
    print("Testing Gradio and Telegram bot library imports\n")
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Gradio
    print("\n[1/2] Gradio UI")
    if test_gradio_import():
        tests_passed += 1
    
    # Test 2: Telegram
    print("\n[2/2] Telegram Bot")
    if test_telegram_import():
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
        print("🎉 ALL UI TESTS PASSED!")
        print("All UI dependencies are installed and working.")
    elif tests_passed > 0:
        print(f"⚠️  PARTIAL SUCCESS: {tests_passed}/{total_tests} UI libraries working")
        print("Some UI features may not be available.")
    else:
        print("❌ ALL UI TESTS FAILED!")
        print("Install missing dependencies to use UI features.")
    print(LOG_SEPARATOR)
    
    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())