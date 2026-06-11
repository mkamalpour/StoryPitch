#!/usr/bin/env python3
"""
StoryPitch Launcher – Simple menu with API endpoints list
"""

import subprocess
import sys
import time
import atexit
import webbrowser
import socket
from pathlib import Path

# ============================================================================
# Config
# ============================================================================

API_MODULE = "api.main"
GRADIO_MODULE = "ui.gradio_ui"
TELEGRAM_MODULE = "ui.telegram_bot"
SEED_MODULE = "db.seed_data"
HTML_DIR = Path("ui")

API_STARTUP_WAIT = 4

_api_proc = None
_frontend_proc = None
_api_port = None
_html_port = None


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except socket.error:
            return False


def find_free_port(start_port: int, max_tries: int = 10) -> int:
    for offset in range(max_tries):
        port = start_port + offset
        if is_port_free(port):
            return port
    raise RuntimeError(f"No free port found starting from {start_port}")


def start_api():
    global _api_proc, _api_port
    default_api_port = 8000
    if is_port_free(default_api_port):
        _api_port = default_api_port
        print(f"✅ API port {_api_port} is free.")
    else:
        print(f"⚠️ Port {default_api_port} is busy. Searching...")
        _api_port = find_free_port(default_api_port)
        print(f"✅ Using API port {_api_port} instead.")

    env = dict(subprocess.os.environ)
    env["API_PORT"] = str(_api_port)

    print(f"🚀 Starting API server on port {_api_port}...")
    _api_proc = subprocess.Popen([sys.executable, "-m", API_MODULE], env=env)
    time.sleep(API_STARTUP_WAIT)
    print(f"✅ API running on http://127.0.0.1:{_api_port}")


def start_html_server():
    global _html_port
    default_html_port = 8080
    if is_port_free(default_html_port):
        _html_port = default_html_port
        print(f"✅ HTML port {_html_port} is free.")
    else:
        print(f"⚠️ Port {default_html_port} is busy. Searching...")
        _html_port = find_free_port(default_html_port)
        print(f"✅ Using HTML port {_html_port} instead.")

    if not HTML_DIR.exists():
        print(f"❌ HTML directory not found: {HTML_DIR}")
        return None

    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(_html_port)],
        cwd=str(HTML_DIR)
    )
    return proc


def stop_all():
    global _api_proc, _frontend_proc
    if _frontend_proc and _frontend_proc.poll() is None:
        print("\n🛑 Stopping frontend...")
        _frontend_proc.terminate()
        _frontend_proc.wait(timeout=5)
    if _api_proc and _api_proc.poll() is None:
        print("🛑 Stopping API...")
        _api_proc.terminate()
        _api_proc.wait(timeout=5)
    print("✅ All stopped.")


def run_html():
    global _frontend_proc
    start_api()
    print("🌐 Starting HTML frontend...")
    _frontend_proc = start_html_server()
    if not _frontend_proc:
        return
    url = f"http://127.0.0.1:{_html_port}/index.html"
    webbrowser.open(url)
    print(f"✅ HTML frontend at {url}")
    print("\nPress Ctrl+C to stop.\n")
    try:
        _frontend_proc.wait()
    except KeyboardInterrupt:
        pass


def run_gradio():
    global _frontend_proc
    start_api()
    print("🌐 Starting Gradio UI...")
    _frontend_proc = subprocess.Popen([sys.executable, "-m", GRADIO_MODULE])
    webbrowser.open("http://127.0.0.1:7860")
    print("✅ Gradio at http://127.0.0.1:7860 (or next free port)")
    print("\nPress Ctrl+C to stop.\n")
    try:
        _frontend_proc.wait()
    except KeyboardInterrupt:
        pass


def run_telegram():
    global _frontend_proc
    start_api()
    print("🤖 Starting Telegram bot...")
    _frontend_proc = subprocess.Popen([sys.executable, "-m", TELEGRAM_MODULE])
    print("✅ Telegram bot started.")
    print("\nPress Ctrl+C to stop.\n")
    try:
        _frontend_proc.wait()
    except KeyboardInterrupt:
        pass


def run_seed():
    print("🌱 Seeding test data...")
    subprocess.run([sys.executable, "-m", SEED_MODULE])
    print("✅ Done.")
    sys.exit(0)


def show_api_endpoints():
    """Display all available API endpoints (from api/main.py)"""
    endpoints = """
======================================================================
📡 STORYPITCH API ENDPOINTS
======================================================================

USER & SESSION:
  POST   /api/user                          - Create a new user
  POST   /api/session/start                 - Start a new story session
  GET    /api/session/{id}/state            - Get current session state
  GET    /api/session/{id}/processing       - Check if session is busy

STORY PROGRESSION:
  POST   /api/session/{id}/step             - Continue the story (choice or custom action)
  POST   /api/session/{id}/reset            - Reset session

SAVE / LOAD (Snapshots):
  POST   /api/session/{id}/save             - Save current game state
  GET    /api/session/{id}/snapshots        - List all saves for a session
  POST   /api/session/{id}/load/{snapshot_id} - Load a specific save
  GET    /api/snapshot/{snapshot_id}        - Get save details
  PUT    /api/snapshot/{snapshot_id}/rename - Rename a save
  PUT    /api/snapshot/{snapshot_id}/description - Update save description
  DELETE /api/snapshot/{snapshot_id}        - Delete a save

MEMORY SYSTEM:
  GET    /api/session/{id}/memory           - Get all tracked memory (NPCs, locations, inventory, etc.)
  POST   /api/session/{id}/refresh-memory   - Force AI to analyze and update memory

STORY HISTORY & EXPORT:
  GET    /api/session/{id}/history          - Get all story steps
  GET    /api/session/{id}/story-full       - Get full story with narration + user actions
  GET    /api/session/{id}/export           - Export story as JSON or text
  POST   /api/session/{id}/summarize        - Generate a summary of a scene

ADMIN (Database Management):
  GET    /api/admin/users                   - List all users
  GET    /api/admin/sessions                - List all sessions
  GET    /api/admin/snapshots               - List all saves
  DELETE /api/admin/user/{user_id}          - Delete a user
  DELETE /api/admin/session/{session_id}    - Delete a session
  DELETE /api/admin/snapshot/{snapshot_id}  - Delete a save
  POST   /api/admin/clear-all               - Delete EVERYTHING (nuclear option)

UTILITIES:
  GET    /api/health                        - Health check
  GET    /api/performance                   - Get cache and performance stats
  GET    /api/admin/ping-lmstudio           - Test LM Studio connection

======================================================================
💡 TIP: Visit http://127.0.0.1:8000/docs for interactive API documentation
======================================================================
"""
    print(endpoints)
    input("\nPress Enter to return to menu...")


def show_menu():
    print("\n" + "=" * 55)
    print("  🎭 StoryPitch Launcher")
    print("=" * 55)
    print("\n📋 What do you want to run?")
    print("")
    print("  1. 🌐  HTML Frontend     → Beautiful web interface (recommended)")
    print("  2. 🎮  Gradio UI         → Alternative web interface")
    print("  3. 🤖  Telegram Bot      → Play via Telegram messenger")
    print("  4. 🌱  Seed Test Data    → Add sample users/sessions to database")
    print("  5. 📡  Show API Endpoints → See all available backend commands")
    print("  0. 🚪  Exit")
    print("=" * 55)


def main():
    atexit.register(stop_all)

    while True:
        show_menu()
        choice = input("\n👉 Enter your choice (0-5): ").strip()
        
        if choice == "1":
            run_html()
            break
        elif choice == "2":
            run_gradio()
            break
        elif choice == "3":
            run_telegram()
            break
        elif choice == "4":
            run_seed()
            break
        elif choice == "5":
            show_api_endpoints()
        elif choice == "0":
            print("\n👋 Goodbye!")
            sys.exit(0)
        else:
            print("\n❌ Invalid choice. Please type 0, 1, 2, 3, 4, or 5.")

    stop_all()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted")
        sys.exit(0)