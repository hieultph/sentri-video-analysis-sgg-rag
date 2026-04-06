#!/usr/bin/env python3
"""
Quick test of vector search functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.tool import SentriTools

class MockAgent:
    """Mock agent for testing"""
    def __init__(self, user_id=1):
        self.session_state = {"user_id": user_id}

def test_semantic_search_tool():
    """Test semantic search tool directly"""
    
    print("=== TESTING SEMANTIC SEARCH TOOL ===")
    
    # Initialize tools
    sentri_tools = SentriTools()
    mock_agent = MockAgent(user_id=1)
    
    # Test queries
    test_queries = [
        "person walking",
        "người đi bộ", 
        "car vehicle",
        "xe ô tô",
        "activity"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing query: '{query}'")
        print("-" * 40)
        
        try:
            results = sentri_tools.search_scene_graphs_semantic(
                agent=mock_agent,
                query=query,
                limit=3
            )
            
            print(f"Found {len(results)} results:")
            
            for i, result in enumerate(results):
                print(f"  {i+1}. Scene {result['scene_graph_id']} (Score: {result['similarity_score']})")
                print(f"     📹 {result['camera_name']} - {result['created_at']}")
                print(f"     📝 {result['content'][:80]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Test traditional tool for comparison
    print(f"\n=== COMPARISON WITH TRADITIONAL SEARCH ===")
    try:
        traditional_results = sentri_tools.get_scene_graphs_simple(
            agent=mock_agent,
            limit=5
        )
        print(f"Traditional search returned {len(traditional_results)} results")
        
        if traditional_results:
            print("Sample traditional results:")
            for i, result in enumerate(traditional_results[:2]):
                print(f"  {i+1}. Scene {result['scene_graph_id']} - {result['camera_name']}")
                print(f"     📝 {result['relationships'][:60]}...")
        
    except Exception as e:
        print(f"❌ Traditional search error: {e}")

if __name__ == "__main__":
    test_semantic_search_tool()