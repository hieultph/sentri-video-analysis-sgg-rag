#!/usr/bin/env python3
"""
Test script for Sentri Agent with Scene Graph Tools
==================================================

This script tests the new scene graph tools integration with the agent.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.assistant import get_assistant_agent, add_agent_state

def test_agent_tools():
    """Test agent with various scene graph queries"""
    
    print("🤖 Testing Sentri Agent with Scene Graph Tools")
    print("=" * 50)
    
    # Create agent instance
    agent = get_assistant_agent("test_user")
    
    # Set up agent state
    add_agent_state(agent, user_id="1", camera_id="1")
    
    # Test queries
    test_queries = [
        "Camera gần đây phát hiện gì?",
        "Có ai đi qua camera không?",
        "Camera có thấy xe nào không?", 
        "Thống kê những gì camera thường phát hiện trong tuần qua?",
        "Hôm nay từ 8h sáng đến 6h chiều camera thấy gì?",
        "Có ai đang cầm gì đó không?",
        "Danh sách camera hiện tại?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test {i}: {query}")
        print("-" * 40)
        
        try:
            # Run agent with query
            response = agent.run(query)
            print(f"🤖 Agent: {response.content}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Agent tool testing completed!")

def test_individual_tools():
    """Test individual tools directly"""
    
    print("\n🔧 Testing Individual Tools")
    print("=" * 50)
    
    from tools.tool import SentriTools
    
    # Create tools instance
    tools = SentriTools()
    
    # Mock agent with session state
    class MockAgent:
        def __init__(self):
            self.session_state = {"user_id": 1}
    
    mock_agent = MockAgent()
    
    # Test each tool
    print("\n🎯 Testing get_camera_list...")
    try:
        cameras = tools.get_camera_list(mock_agent)
        print(f"   Cameras found: {len(cameras) if cameras else 0}")
        if cameras:
            for cam in cameras[:2]:  # Show first 2
                print(f"   - {cam.get('name', 'Unknown')} ({cam.get('location', 'No location')})")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎯 Testing get_recent_scene_graphs...")
    try:
        recent = tools.get_recent_scene_graphs(mock_agent, limit=5)
        print(f"   Recent scene graphs found: {len(recent) if recent else 0}")
        if recent:
            for sg in recent[:2]:  # Show first 2
                print(f"   - {sg.get('created_at')} | Objects: {sg.get('object_count', 0)} | {sg.get('camera_name', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎯 Testing search_scene_graphs_by_objects...")
    try:
        objects_result = tools.search_scene_graphs_by_objects(mock_agent, ['person', 'car'], limit=3)
        print(f"   Object search results: {len(objects_result) if objects_result else 0}")
        if objects_result:
            for result in objects_result[:1]:  # Show first result
                print(f"   - Found: {result.get('camera_name')} | Objects: {len(result.get('detected_objects', []))}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎯 Testing get_scene_graph_summary...")
    try:
        summary = tools.get_scene_graph_summary(mock_agent, days=7)
        print(f"   Summary generated for {summary.get('summary_period_days', 0)} days")
        print(f"   - Unique objects: {summary.get('total_unique_objects', 0)}")
        print(f"   - Unique relationships: {summary.get('total_unique_relationships', 0)}")
        if summary.get('top_objects'):
            print(f"   - Top objects: {summary['top_objects'][:3]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n✅ Individual tools testing completed!")

if __name__ == "__main__":
    print("🚀 Sentri Agent Tools Test Suite")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists("sentri.db"):
        print("⚠️  Warning: sentri.db not found. Some tests may fail.")
        print("   Make sure the Sentri system is set up and has data.")
    
    # Run tests
    test_individual_tools()
    
    # Ask if user wants to run agent tests
    print("\n" + "=" * 60)
    response = input("Run agent conversation tests? (y/n): ").strip().lower()
    
    if response == 'y':
        test_agent_tools()
    else:
        print("✅ Test completed!")