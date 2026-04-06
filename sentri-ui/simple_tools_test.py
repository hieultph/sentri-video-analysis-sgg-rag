#!/usr/bin/env python3
"""
Simple test for SentriTools
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.tool import SentriTools
import sqlite3

# Mock agent with session state
class MockAgent:
    def __init__(self, user_id=1):
        self.session_state = {"user_id": str(user_id)}

def test_basic_connection():
    """Test basic database connection"""
    print("🔧 Testing Database Connection")
    print("-" * 40)
    
    try:
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Check if database exists and has tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"✅ Connected to database")
        print(f"   Tables found: {', '.join(tables)}")
        
        # Check if required tables exist
        required_tables = ['users', 'cameras', 'media', 'scene_graphs']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"❌ Missing tables: {', '.join(missing_tables)}")
            return False
        else:
            print("✅ All required tables found")
        
        # Check user data
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"   Users: {user_count}")
        
        cursor.execute("SELECT COUNT(*) FROM cameras")
        camera_count = cursor.fetchone()[0]
        print(f"   Cameras: {camera_count}")
        
        cursor.execute("SELECT COUNT(*) FROM scene_graphs")
        sg_count = cursor.fetchone()[0]
        print(f"   Scene graphs: {sg_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_tools_basic():
    """Test SentriTools basic functionality"""
    print("\n🔧 Testing SentriTools")
    print("-" * 40)
    
    tools = SentriTools()
    mock_agent = MockAgent(user_id=1)
    
    # Test 1: get_camera_list
    try:
        print("📝 Testing get_camera_list...")
        cameras = tools.get_camera_list(mock_agent)
        print(f"   ✅ Camera list: {len(cameras) if cameras else 0} cameras")
        if cameras and len(cameras) > 0:
            print(f"      Sample: {cameras[0].get('name', 'No name')}")
    except Exception as e:
        print(f"   ❌ get_camera_list failed: {e}")
    
    # Test 2: get_recent_scene_graphs
    try:
        print("📝 Testing get_recent_scene_graphs...")
        recent = tools.get_recent_scene_graphs(mock_agent, limit=3)
        print(f"   ✅ Recent scene graphs: {len(recent) if recent else 0} found")
        if recent and len(recent) > 0:
            print(f"      Sample: {recent[0].get('camera_name', 'No name')} - {recent[0].get('object_count', 0)} objects")
    except Exception as e:
        print(f"   ❌ get_recent_scene_graphs failed: {e}")
    
    # Test 3: search_scene_graphs_by_objects
    try:
        print("📝 Testing search_scene_graphs_by_objects...")
        results = tools.search_scene_graphs_by_objects(mock_agent, ['person'], limit=3)
        print(f"   ✅ Object search results: {len(results) if results else 0} found")
    except Exception as e:
        print(f"   ❌ search_scene_graphs_by_objects failed: {e}")

if __name__ == "__main__":
    print("🚀 Simple SentriTools Test")
    print("=" * 50)
    
    # Test database connection first
    if test_basic_connection():
        # Test tools if connection works
        test_tools_basic()
    
    print("\n✅ Testing completed!")