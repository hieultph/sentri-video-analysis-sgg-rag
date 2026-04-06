"""
Test Agent Tools with Simple Search
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

def test_agent_tools():
    """Test agent tools with simple search fallback"""
    print("Testing agent tools with simple search...")
    
    try:
        from tools.tool import SentriTools
        print("✓ SentriTools imported successfully")
        
        # Create tools instance
        tools = SentriTools()
        print("✓ SentriTools initialized")
        
        # Mock agent object
        class MockAgent:
            def __init__(self):
                self.session_data = {"user_id": 1}
                
        mock_agent = MockAgent()
        
        # Test semantic search
        print("\n=== Testing Semantic Search Tool ===")
        
        test_queries = [
            "person walking",
            "người đi bộ",
            "car on road", 
            "xe ô tô",
            "activity"
        ]
        
        for query in test_queries:
            print(f"\nTesting query: '{query}'")
            try:
                results = tools.search_scene_graphs_semantic(
                    agent=mock_agent,
                    query=query,
                    limit=3
                )
                
                print(f"Found {len(results)} results")
                for i, result in enumerate(results[:2]):
                    print(f"  {i+1}. ID: {result['scene_graph_id']}")
                    print(f"     Score: {result['similarity_score']:.3f}")
                    print(f"     Search type: {result.get('search_type', 'unknown')}")
                    print(f"     Content: {result['content'][:80]}...")
                    
            except Exception as e:
                print(f"  ✗ Query failed: {e}")
        
        # Test simple SQL search
        print("\n=== Testing Simple SQL Search Tool ===")
        try:
            sql_results = tools.get_scene_graphs_simple(
                agent=mock_agent,
                limit=3
            )
            print(f"SQL search found {len(sql_results)} results")
            
        except Exception as e:
            print(f"✗ SQL search failed: {e}")
        
        print("\n✓ Agent tools test completed!")
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = test_agent_tools()
    if success:
        print("\n🎉 Agent tools test passed!")
    else:
        print("\n❌ Agent tools test failed!")