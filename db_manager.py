#!/usr/bin/env python3
"""
Full Database Management Tool - Complete Access
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from config import API_HOST, API_PORT, API_KEY, configure_logging
from utils.http_client import create_async_client
from constants import THREAD_SHUTDOWN_TIMEOUT_SECONDS

configure_logging()

class DatabaseManager:
    def __init__(self):
        self.base_url = f"http://{API_HOST}:{API_PORT}"
    
    async def _make_request(self, method: str, endpoint: str, error_msg: str, default_return=None, json_key=None):
        """
        Centralized request handler to eliminate duplicate error handling.
        
        Args:
            method: HTTP method ('GET', 'POST', 'DELETE')
            endpoint: API endpoint path
            error_msg: Error message prefix
            default_return: Value to return on error (None or [])
            json_key: Optional key to extract from JSON response
        """
        try:
            async with create_async_client(API_KEY) as client:
                if method == 'GET':
                    response = await client.get(f"{self.base_url}{endpoint}")
                elif method == 'POST':
                    response = await client.post(f"{self.base_url}{endpoint}")
                elif method == 'DELETE':
                    response = await client.delete(f"{self.base_url}{endpoint}")
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code == 200:
                    data = response.json()
                    return data[json_key] if json_key else data
                else:
                    print(f"{error_msg}: {response.status_code} - {response.text}")
                    return default_return
        except Exception as e:
            print(f"Connection error contacting API at {self.base_url}: {e}")
            if default_return == []:
                print("Start the API server: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000")
            return default_return
    
    async def get_all_users(self):
        """Get all users"""
        return await self._make_request('GET', '/api/admin/users', 'Error getting users', [], 'users')
    
    async def get_all_sessions(self):
        """Get all sessions"""
        return await self._make_request('GET', '/api/admin/sessions', 'Error getting sessions', [], 'sessions')
    
    async def get_all_snapshots(self):
        """Get all snapshots"""
        return await self._make_request('GET', '/api/admin/snapshots', 'Error getting snapshots', [], 'snapshots')
    
    async def delete_user(self, user_id):
        """Delete a user"""
        return await self._make_request('DELETE', f'/api/admin/user/{user_id}', 'Error deleting user', None)
    
    async def delete_session(self, session_id):
        """Delete a session"""
        return await self._make_request('DELETE', f'/api/admin/session/{session_id}', 'Error deleting session', None)
    
    async def delete_snapshot(self, snapshot_id):
        """Delete a snapshot"""
        return await self._make_request('DELETE', f'/api/admin/snapshot/{snapshot_id}', 'Error deleting snapshot', None)
    
    async def clear_all_data(self):
        """Clear all data"""
        return await self._make_request('POST', '/api/admin/clear-all', 'Error clearing data', None)

async def list_users(manager):
    """List all users"""
    print("\n=== USERS ===")
    users = await manager.get_all_users()
    if users:
        for user in users:
            print(f"ID: {user['id']}, Username: {user['username']}, Created: {user['created_at']}")
    else:
        print("No users found")

async def list_sessions(manager):
    """List all sessions"""
    print("\n=== SESSIONS ===")
    sessions = await manager.get_all_sessions()
    if sessions:
        for session in sessions:
            print(f"ID: {session['id']}, User: {session['user_id']}, Title: {session['title']}, Step: {session['current_step']}")
    else:
        print("No sessions found")

async def list_snapshots(manager):
    """List all snapshots"""
    print("\n=== SNAPSHOTS ===")
    snapshots = await manager.get_all_snapshots()
    if snapshots:
        for snapshot in snapshots:
            print(f"ID: {snapshot['id']}, Session: {snapshot['session_id']}, Title: {snapshot['title']}, Created: {snapshot['created_at']}")
    else:
        print("No snapshots found")

async def delete_user_interactive(manager):
    """Delete a user interactively"""
    users = await manager.get_all_users()
    if not users:
        print("No users to delete")
        return
    
    print("\nUsers:")
    for user in users:
        print(f"ID: {user['id']}, Username: {user['username']}")
    
    try:
        user_id = int(input("\nEnter user ID to delete: "))
        result = await manager.delete_user(user_id)
        if result:
            print(f"SUCCESS: {result['message']}")
        else:
            print("FAILED: Could not delete user")
    except ValueError:
        print("Invalid user ID")

async def delete_session_interactive(manager):
    """Delete a session interactively"""
    sessions = await manager.get_all_sessions()
    if not sessions:
        print("No sessions to delete")
        return
    
    print("\nSessions:")
    for session in sessions:
        print(f"ID: {session['id']}, User: {session['user_id']}, Title: {session['title']}")
    
    try:
        session_id = int(input("\nEnter session ID to delete: "))
        result = await manager.delete_session(session_id)
        if result:
            print(f"SUCCESS: {result['message']}")
        else:
            print("FAILED: Could not delete session")
    except ValueError:
        print("Invalid session ID")

async def delete_snapshot_interactive(manager):
    """Delete a snapshot interactively"""
    snapshots = await manager.get_all_snapshots()
    if not snapshots:
        print("No snapshots to delete")
        return
    
    print("\nSnapshots:")
    for snapshot in snapshots:
        print(f"ID: {snapshot['id']}, Session: {snapshot['session_id']}, Title: {snapshot['title']}")
    
    try:
        snapshot_id = int(input("\nEnter snapshot ID to delete: "))
        result = await manager.delete_snapshot(snapshot_id)
        if result:
            print(f"SUCCESS: {result['message']}")
        else:
            print("FAILED: Could not delete snapshot")
    except ValueError:
        print("Invalid snapshot ID")

async def clear_all_interactive(manager):
    """Clear all data interactively"""
    print("\nWARNING: This will delete ALL data!")
    print("Users, sessions, snapshots, and steps will be permanently deleted.")
    
    confirm = input("Type 'DELETE ALL' to confirm: ")
    if confirm == "DELETE ALL":
        result = await manager.clear_all_data()
        if result:
            print(f"SUCCESS: {result['message']}")
        else:
            print("FAILED: Could not clear data")
    else:
        print("Operation cancelled")

async def main():
    """Main menu"""
    print("=" * 60)
    print("Database Manager")
    print("=" * 60)
    
    manager = DatabaseManager()
    
    while True:
        print("\nChoose an option:")
        print("1. List all users")
        print("2. List all sessions")
        print("3. List all snapshots")
        print("4. Delete user")
        print("5. Delete session")
        print("6. Delete snapshot")
        print("7. Clear all data")
        print("8. Exit")
        
        choice = input("\nEnter your choice (1-8): ").strip()
        
        if choice == "1":
            await list_users(manager)
        elif choice == "2":
            await list_sessions(manager)
        elif choice == "3":
            await list_snapshots(manager)
        elif choice == "4":
            await delete_user_interactive(manager)
        elif choice == "5":
            await delete_session_interactive(manager)
        elif choice == "6":
            await delete_snapshot_interactive(manager)
        elif choice == "7":
            await clear_all_interactive(manager)
        elif choice == "8":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-8.")

if __name__ == "__main__":
    asyncio.run(main())
