"""
Test Simple Search functionality
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

def test_simple_search():
    """Test simple search functionality"""
    print("Testing simple search...")
    
    try:
        from simple_search import get_simple_search
        search = get_simple_search()
        print("✓ Simple search initialized successfully")
        
        # Test basic queries
        queries = [
            "person",
            "người",
            "car",
            "xe ô tô", 
            "walking",
            "activity"
        ]
        
        print("\n=== Testing Simple Search ===")
        
        for query in queries:
            print(f"\nQuery: '{query}'")
            results = search.search_scene_graphs(query, limit=3)
            print(f"Found {len(results)} results")
            
            for i, result in enumerate(results[:2]):
                print(f"  {i+1}. Score: {result['similarity_score']:.3f}")
                print(f"     Content: {result['content'][:100]}...")
                print(f"     Camera: {result['camera_name']}")
                print(f"     Time: {result['created_at']}")
        
        # Test stats
        print("\n=== Search Statistics ===")
        stats = search.get_stats()
        print(f"Stats: {stats}")
        
        print("\n✓ Simple search test completed successfully!")
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = test_simple_search()
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Tests failed!")