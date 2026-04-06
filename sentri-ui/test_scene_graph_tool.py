#!/usr/bin/env python3

import sys
import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any

# Add current directory to Python path to import our tools
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.tool import SentriTools

class MockAgent:
    """Mock agent class for testing"""
    def __init__(self, user_id=1):
        self.session_state = {"user_id": user_id}

def test_scene_graph_tool():
    """Test the get_scene_graphs_simple tool directly"""
    
    print("=== TESTING SCENE GRAPH TOOL ===")
    
    # Initialize tool
    sentri_tools = SentriTools()
    mock_agent = MockAgent(user_id=1)
    
    print(f"Mock agent user_id: {mock_agent.session_state['user_id']}")
    
    try:
        # Test 1: Basic call without filters
        print("\n--- Test 1: Basic call (no time filters) ---")
        results = sentri_tools.get_scene_graphs_simple(mock_agent, limit=5)
        
        print(f"Results type: {type(results)}")
        print(f"Number of results: {len(results)}")
        
        if results:
            print("Sample results:")
            for i, result in enumerate(results[:3]):
                print(f"  {i+1}. {result}")
        else:
            print("No results returned!")
        
        # Test 2: With time filter (today)
        print("\n--- Test 2: With today's date filter ---")
        today = datetime.now().strftime('%Y-%m-%d')
        results_today = sentri_tools.get_scene_graphs_simple(
            mock_agent, 
            limit=5, 
            start_time=today, 
            end_time=today
        )
        
        print(f"Results for today ({today}): {len(results_today)}")
        if results_today:
            print("Sample today's results:")
            for i, result in enumerate(results_today[:2]):
                print(f"  {i+1}. {result}")
        
        # Test 3: With specific time range
        print("\n--- Test 3: With specific time range ---")
        start_time = f"{today} 00:00:00"
        end_time = f"{today} 23:59:59"
        results_range = sentri_tools.get_scene_graphs_simple(
            mock_agent,
            limit=10,
            start_time=start_time,
            end_time=end_time
        )
        
        print(f"Results for time range {start_time} to {end_time}: {len(results_range)}")
        
        # Test 4: Direct database query to compare
        print("\n--- Test 4: Direct database comparison ---")
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Check total scene graphs in DB
        cursor.execute("SELECT COUNT(*) FROM scene_graphs")
        total_sg = cursor.fetchone()[0]
        print(f"Total scene graphs in DB: {total_sg}")
        
        # Check scene graphs for user 1
        cursor.execute("""
            SELECT COUNT(*)
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id
            JOIN cameras c ON m.camera_id = c.id
            WHERE c.user_id = 1
        """)
        user_sg = cursor.fetchone()[0]
        print(f"Scene graphs for user 1: {user_sg}")
        
        # Check recent scene graphs
        cursor.execute("""
            SELECT sg.id, sg.created_at, c.name as camera_name
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id
            JOIN cameras c ON m.camera_id = c.id
            WHERE c.user_id = 1
            ORDER BY sg.created_at DESC LIMIT 5
        """)
        recent_sg = cursor.fetchall()
        print(f"Recent scene graphs:")
        for sg in recent_sg:
            print(f"  ID {sg[0]}: {sg[1]} - Camera: {sg[2]}")
        
        # Check scene graphs with valid relationships
        cursor.execute("""
            SELECT sg.id, sg.graph_json, c.name as camera_name
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id
            JOIN cameras c ON m.camera_id = c.id
            WHERE c.user_id = 1
            ORDER BY sg.created_at DESC LIMIT 5
        """)
        valid_sg = cursor.fetchall()
        
        print(f"\nChecking scene graphs with valid relationships:")
        valid_count = 0
        for sg in valid_sg:
            sg_id, graph_json, camera_name = sg
            try:
                graph_data = json.loads(graph_json)
                relationships = []
                if 'relationships' in graph_data:
                    for rel in graph_data['relationships']:
                        subject = rel.get('subject', '')
                        predicate = rel.get('predicate', '')
                        obj = rel.get('object', '')
                        if subject and predicate and obj:
                            relationships.append(f"{subject} {predicate} {obj}")
                
                if relationships:
                    valid_count += 1
                    relationship_text = "; ".join(relationships)
                    print(f"  ID {sg_id} ({camera_name}): {relationship_text}")
                else:
                    print(f"  ID {sg_id} ({camera_name}): No valid relationships")
                    
            except json.JSONDecodeError:
                print(f"  ID {sg_id} ({camera_name}): JSON decode error")
        
        print(f"Total scene graphs with valid relationships: {valid_count}")
        
        conn.close()
        
        # Test 5: Performance test
        print("\n--- Test 5: Performance test ---")
        import time
        start = time.time()
        
        # Call tool multiple times to see if it's slow
        for i in range(3):
            results_perf = sentri_tools.get_scene_graphs_simple(mock_agent, limit=10)
            print(f"  Call {i+1}: {len(results_perf)} results")
        
        end = time.time()
        print(f"3 calls took {end - start:.2f} seconds")
        
        print("\n=== SUMMARY ===")
        print(f"Tool working: {'YES' if results is not None else 'NO'}")
        print(f"Returns data: {'YES' if results else 'NO'}")
        print(f"Time filters working: {'YES' if results_today is not None else 'NO'}")
        print(f"Data consistency: {'OK' if valid_count > 0 else 'CHECK RELATIONSHIPS'}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scene_graph_tool()