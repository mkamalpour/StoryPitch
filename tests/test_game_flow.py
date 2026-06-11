#!/usr/bin/env python3
"""
Game Flow Debug Test - Comprehensive testing with detailed step tracking

This script tests every component of the story game flow with detailed
logging and automatic API server management. Perfect for debugging and
verifying that all systems work together correctly.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import httpx
import time
import subprocess
import atexit
from config import API_HOST, API_PORT, configure_logging, LM_STUDIO_URL, DEFAULT_MODEL, LM_STUDIO_USE_CHAT
from utils.api_utils import ensure_api_running, stop_api_server
from utils.formatting import (
    print_section_header, print_success, print_error, 
    print_warning, print_info, format_duration
)

configure_logging()

# Ensure cleanup on exit
atexit.register(stop_api_server)

async def _ensure_api_running_tracked(tracker: 'GameFlowTracker'):
    """Ensure API is running with tracking"""
    is_running, was_started = await ensure_api_running()
    if is_running:
        if was_started:
            tracker.log_step("API server started", True, f"http://{API_HOST}:{API_PORT}")
        else:
            tracker.log_step("API already running", True, f"http://{API_HOST}:{API_PORT}")
    else:
        tracker.log_step("Failed to start API", False, "Could not start or connect to API server")

class GameFlowTracker:
    def __init__(self):
        self.steps = []
        self.start_time = time.time()
    
    def log_step(self, step, success, details=""):
        elapsed = time.time() - self.start_time
        status = "PASS" if success else "FAIL"
        self.steps.append({
            "step": step,
            "success": success,
            "details": details,
            "elapsed": f"{elapsed:.2f}s"
        })
        print(f"[{elapsed:.2f}s] {status}: {step}")
        if details:
            print(f"    Details: {details}")

async def test_lm_studio_direct():
    """Test LM Studio directly by auto-detecting a loaded model and trying chat/completions"""
    tracker = GameFlowTracker()
    tracker.log_step("Starting LM Studio direct test", True)
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:  # Unlimited timeout
            base = LM_STUDIO_URL.rstrip('/')
            # Discover models
            models_url = f"{base}/v1/models"
            tracker.log_step("Fetching LM Studio models", True, f"URL: {models_url}")
            models_resp = await client.get(models_url)
            if models_resp.status_code != 200:
                tracker.log_step("LM Studio models fetch failed", False, f"Status: {models_resp.status_code} Body: {models_resp.text[:200]}")
                return False
            models = models_resp.json().get("data") or models_resp.json()
            model_id = None
            if isinstance(models, list) and models:
                # Try first model id field patterns
                first = models[0]
                model_id = first.get("id") or first.get("model") or first.get("name")
            if not model_id:
                tracker.log_step("No models reported by LM Studio", False, "Load a model in LM Studio and retry")
                return False

            # Try chat then completions
            endpoints = ["/v1/chat/completions", "/v1/completions"] if LM_STUDIO_USE_CHAT else ["/v1/completions", "/v1/chat/completions"]
            for ep in endpoints:
                url = f"{base}{ep}"
                if ep.endswith("chat/completions"):
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": "Hello, test message"}],
                        "max_tokens": 50,
                        "temperature": 0.7,
                        "stream": False
                    }
                else:
                    payload = {
                        "model": model_id,
                        "prompt": "Hello, test message",
                        "max_tokens": 50,
                        "temperature": 0.7,
                        "stream": False
                    }

                tracker.log_step("Sending request to LM Studio", True, f"URL: {url} model={model_id}")
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    # Extract text robustly
                    text = None
                    if "choices" in data and data["choices"]:
                        ch0 = data["choices"][0]
                        if isinstance(ch0, dict):
                            if "message" in ch0 and isinstance(ch0["message"], dict):
                                text = ch0["message"].get("content")
                            text = text or ch0.get("text")
                    text = text or data.get("text") or data.get("generated_text") or data.get("output")
                    if text:
                        tracker.log_step("LM Studio responded", True, f"Response: {str(text)[:100]}...")
                        return True
                else:
                    tracker.log_step("LM Studio endpoint failed", False, f"EP: {ep} Status: {response.status_code} Body: {response.text[:200]}")
            return False
                
    except Exception as e:
        tracker.log_step("LM Studio error", False, str(e))
        return False

async def test_llm_manager():
    """Test LLM manager directly"""
    tracker = GameFlowTracker()
    tracker.log_step("Testing LLM Manager", True)
    
    try:
        from llm.manager import LLMManager
        manager = LLMManager()
        
        tracker.log_step("LLM Manager created", True, f"Default model: {manager.default_model}")
        
        result = await manager.generate("Test prompt for game", max_tokens=50)
        
        if result:
            tracker.log_step("LLM Manager generated text", True, f"Length: {len(result)} chars")
            return True
        else:
            tracker.log_step("LLM Manager returned empty", False)
            return False
            
    except Exception as e:
        tracker.log_step("LLM Manager error", False, str(e))
        return False

async def test_story_logic():
    """Test story logic directly"""
    tracker = GameFlowTracker()
    tracker.log_step("Testing Story Logic", True)
    
    try:
        # Ensure DB initialized via import side-effects of story.logic (it calls init_db now)
        from story.logic import start_session
        
        tracker.log_step("Story logic imported", True)
        
        result = await start_session(
            user_id=999,  # Use test user ID
            title="Debug Test Story",
            theme="A test adventure",
            traits=["brave"],
            character_name="TestHero"
        )
        
        if result and result.get("session_id"):
            tracker.log_step("Story session created", True, f"Session ID: {result['session_id']}")
            tracker.log_step("Narration generated", True, f"Length: {len(result.get('narration', ''))}")
            tracker.log_step("Choices generated", True, f"Count: {len(result.get('choices', []))}")
            return True
        else:
            tracker.log_step("Story session failed", False, f"Result: {result}")
            return False
            
    except Exception as e:
        tracker.log_step("Story logic error", False, str(e))
        import traceback
        print(f"    Traceback: {traceback.format_exc()}")
        return False

async def test_api_endpoints():
    """Test API endpoints"""
    tracker = GameFlowTracker()
    tracker.log_step("Testing API Endpoints", True)
    
    try:
        await _ensure_api_running_tracked(tracker)
        async with httpx.AsyncClient(timeout=None) as client:  # Unlimited timeout
            # Test root endpoint
            tracker.log_step("Testing API root", True)
            response = await client.get(f"http://{API_HOST}:{API_PORT}/")
            if response.status_code != 200:
                tracker.log_step("API root failed", False, f"Status: {response.status_code}")
                return False
            
            # Test user creation
            tracker.log_step("Testing user creation", True)
            response = await client.post(f"http://{API_HOST}:{API_PORT}/api/user", json={"username": "debug_test"})
            if response.status_code != 200:
                tracker.log_step("User creation failed", False, f"Status: {response.status_code}")
                return False
            
            user_data = response.json()
            user_id = user_data["id"]
            tracker.log_step("User created", True, f"User ID: {user_id}")
            
            # Test session start
            tracker.log_step("Testing session start", True)
            response = await client.post(
                f"http://{API_HOST}:{API_PORT}/api/session/start",
                json={
                    "user_id": user_id,
                    "title": "Debug Test",
                    "theme": "Test Adventure",
                    "traits": ["brave"],
                    "character_name": "TestHero"
                }
            )
            
            if response.status_code == 200:
                session_data = response.json()
                tracker.log_step("Session started", True, f"Session ID: {session_data['session_id']}")
                tracker.log_step("API test complete", True)
                return True
            else:
                tracker.log_step("Session start failed", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
    except Exception as e:
        tracker.log_step("API test error", False, str(e))
        return False

async def main():
    """Run complete game flow debug"""
    print("=" * 80)
    print("🔍 GAME FLOW DEBUG TEST - Tracking Every Step")
    print("=" * 80)
    
    print(f"\nConfiguration:")
    print(f"   API: http://{API_HOST}:{API_PORT}")
    print(f"   LM Studio: {LM_STUDIO_URL}")
    print(f"   Default Model: {DEFAULT_MODEL}")
    
    print(f"\n🧪 Running Tests...")
    
    # Test 1: LM Studio Direct
    print(f"\n1. Testing LM Studio Direct...")
    lm_direct_ok = await test_lm_studio_direct()
    
    # Test 2: LLM Manager
    print(f"\n2. Testing LLM Manager...")
    llm_manager_ok = await test_llm_manager()
    
    # Test 3: Story Logic
    print(f"\n3️⃣ Testing Story Logic...")
    story_logic_ok = await test_story_logic()
    
    # Test 4: API Endpoints
    print(f"\n4️⃣ Testing API Endpoints...")
    api_ok = await test_api_endpoints()
    
    # Summary
    print(f"\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 80)
    
    tests = [
        ("LM Studio Direct", lm_direct_ok),
        ("LLM Manager", llm_manager_ok),
        ("Story Logic", story_logic_ok),
        ("API Endpoints", api_ok)
    ]
    
    all_passed = True
    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n🎯 DIAGNOSIS:")
    if all_passed:
        print("✅ All components work individually!")
        print("💡 The issue is likely in the UI-API communication or timing")
        print("🔧 Try: python run.py both")
    else:
        print("❌ Some components are failing")
        if not lm_direct_ok:
            print("   - LM Studio is not responding")
        if not llm_manager_ok:
            print("   - LLM Manager has issues")
        if not story_logic_ok:
            print("   - Story logic is broken")
        if not api_ok:
            print("   - API server is not running or has issues")

if __name__ == "__main__":
    asyncio.run(main())
