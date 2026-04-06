"""
Simple test - recreate collection and test immediately
"""
import sys
sys.path.insert(0, '.')

def simple_test():
    """Simple test without any reloading"""
    print("🔧 Simple vector search test...")
    
    try:
        from vector_search import get_vector_search
        
        # Get fresh instance
        vector_search = get_vector_search()
        
        # Delete and recreate collection
        try:
            vector_search.client.delete_collection("sentri_scene_graphs")
            print("✓ Deleted existing collection")
        except Exception:
            print("✓ No existing collection to delete")
        
        # Recreate collection
        from chromadb.utils import embedding_functions
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        vector_search.collection = vector_search.client.get_or_create_collection(
            name="sentri_scene_graphs", 
            embedding_function=sentence_transformer_ef
        )
        print("✓ Created new collection")
        
        # Index only dog scene graphs
        import sqlite3
        import json
        
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                sg.id, sg.graph_json, sg.created_at,
                c.name as camera_name, c.location as camera_location,
                c.user_id, m.timestamp
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id  
            JOIN cameras c ON m.camera_id = c.id
            WHERE sg.graph_json LIKE '%dog%'
            ORDER BY sg.created_at DESC
            LIMIT 10
        """)
        
        dog_rows = cursor.fetchall()
        print(f"✓ Found {len(dog_rows)} dog scene graphs")
        
        indexed_count = 0
        for row in dog_rows:
            sg_id, graph_json_str, created_at, cam_name, cam_location, user_id, timestamp = row
            
            try:
                graph_json = json.loads(graph_json_str)
                
                metadata = {
                    "camera_name": cam_name or "",
                    "camera_location": cam_location or "", 
                    "created_at": created_at,
                    "timestamp": timestamp,
                    "user_id": user_id
                }
                
                success = vector_search.index_scene_graph(sg_id, graph_json, metadata)
                if success:
                    indexed_count += 1
                    parsed_text = vector_search.scene_graph_to_text(graph_json)
                    print(f"   ✓ Indexed Scene {sg_id}: {parsed_text}")
                    
            except Exception as e:
                print(f"   ❌ Failed to index Scene {sg_id}: {e}")
        
        conn.close()
        print(f"✓ Indexed {indexed_count} dog scenes")
        
        # Test search immediately
        print(f"\n🔍 Testing search for 'dog':")
        results = vector_search.search_scene_graphs("dog", user_id=1, limit=5)
        print(f"   Found {len(results)} results")
        
        for result in results:
            print(f"     Scene {result['scene_graph_id']}: {result['content']}")
            print(f"       Score: {result['similarity_score']:.3f}")
            if "dog" in result['content'].lower():
                print(f"       ✅ SUCCESS! Found dog!")
        
        # Test agent tool
        print(f"\n🤖 Testing agent tool:")
        from tools.tool import SentriTools
        
        class MockAgent:
            def __init__(self):
                self.session_data = {"user_id": 1}
                self.session_state = {"user_id": 1}
        
        tools = SentriTools()
        mock_agent = MockAgent()
        
        agent_results = tools.search_scene_graphs_semantic(mock_agent, "dog", limit=3)
        print(f"   Agent found {len(agent_results)} results")
        
        for result in agent_results:
            print(f"     Scene {result['scene_graph_id']}: {result['content']}")
            print(f"       Score: {result['similarity_score']:.3f}")
            if "dog" in result['content'].lower():
                print(f"       ✅ AGENT SUCCESS! Can find dogs!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_test()