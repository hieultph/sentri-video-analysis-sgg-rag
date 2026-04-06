"""
Test search for specific scene graph with dog
"""
import sys
sys.path.insert(0, '.')

def test_dog_scene_graph():
    """Test if the scene graph with dog is properly indexed and searchable"""
    print("🐕 Testing dog scene graph search...")
    
    try:
        from vector_search import get_vector_search
        import sqlite3
        import json
        
        vector_search = get_vector_search()
        
        # First, check if scene graph 3907 exists in database
        print("\n📋 Checking scene graph 3907 in database:")
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT graph_json FROM scene_graphs WHERE id = ?", (3907,))
        result = cursor.fetchone()
        
        if result:
            graph_json_str = result[0]
            graph_json = json.loads(graph_json_str)
            parsed_text = vector_search.scene_graph_to_text(graph_json)
            print(f"   Found in DB: {parsed_text}")
        else:
            print("   ❌ Scene graph 3907 not found in database")
            
            # Find any scene graph with dog
            cursor.execute("SELECT id, graph_json FROM scene_graphs WHERE graph_json LIKE '%dog%' LIMIT 5")
            dog_results = cursor.fetchall()
            print(f"\n🔍 Found {len(dog_results)} scene graphs containing 'dog':")
            for sg_id, graph_json_str in dog_results:
                try:
                    graph_json = json.loads(graph_json_str)
                    parsed_text = vector_search.scene_graph_to_text(graph_json)
                    print(f"   Scene {sg_id}: {parsed_text}")
                except:
                    print(f"   Scene {sg_id}: Parse error")
        
        conn.close()
        
        # Force reload vector search to get fresh collection
        from vector_search import get_vector_search
        import importlib
        import vector_search
        importlib.reload(vector_search)
        vector_search_fresh = vector_search.get_vector_search()
        
        print(f"\n🔍 Testing various dog searches with fresh instance:")
        
        search_terms = ["dog", "chó", "con chó", "dog running", "animal", "pet"]
        
        for term in search_terms:
            print(f"\n   Query: '{term}'")
            results = vector_search_fresh.search_scene_graphs(term, limit=3)
            print(f"   Results: {len(results)}")
            
            for i, result in enumerate(results):
                if "dog" in result['content'].lower() or "chó" in result['content'].lower():
                    print(f"     ✓ Scene {result['scene_graph_id']}: {result['content']}")
                    print(f"       Score: {result['similarity_score']:.3f}")
                    break
                elif i == 0:  # Show first result anyway
                    print(f"     → Scene {result['scene_graph_id']}: {result['content'][:60]}...")
                    print(f"       Score: {result['similarity_score']:.3f}")
        
        # Check collection stats with fresh instance  
        print(f"\n📊 Collection stats (fresh instance):")
        try:
            count = vector_search_fresh.collection.count()
            print(f"   Total indexed: {count}")
            
            # Sample a few documents to see what's indexed
            sample = vector_search_fresh.collection.get(limit=5)
            print(f"   Sample documents:")
            for i, doc in enumerate(sample['documents']):
                print(f"     {i+1}. {doc[:80]}...")
                
        except Exception as e:
            print(f"   ❌ Could not get stats: {e}")
        
        print("\n🎯 Testing direct agent tool:")
        from tools.tool import SentriTools
        
        class MockAgent:
            def __init__(self):
                self.session_data = {"user_id": 1}
                self.session_state = {"user_id": 1}
        
        tools = SentriTools()
        mock_agent = MockAgent()
        
        results = tools.search_scene_graphs_semantic(mock_agent, "dog", limit=5)
        print(f"   Agent tool found {len(results)} results")
        
        for i, result in enumerate(results):
            print(f"     {i+1}. Scene {result['scene_graph_id']}: {result['content'][:80]}...")
            print(f"        Score: {result['similarity_score']:.3f}")
            if "dog" in result['content'].lower():
                print(f"        ✓ FOUND DOG IN AGENT RESULTS!")
                break
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dog_scene_graph()