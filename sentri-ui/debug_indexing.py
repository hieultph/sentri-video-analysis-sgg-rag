"""
Debug indexing process - check what gets indexed
"""
import sys
sys.path.insert(0, '.')

def debug_indexing():
    """Debug what scene graphs are actually being indexed"""
    print("🔍 Debugging indexing process...")
    
    try:
        from vector_search import get_vector_search
        import sqlite3
        import json
        
        # Check database content first
        print("\n📋 Database content analysis:")
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Get stats on scene graph content
        cursor.execute("SELECT COUNT(*) FROM scene_graphs")
        total_count = cursor.fetchone()[0]
        print(f"   Total scene graphs: {total_count}")
        
        # Check for non-empty vs empty
        cursor.execute("""
            SELECT 
                id, graph_json, created_at,
                LENGTH(graph_json) as json_length
            FROM scene_graphs 
            WHERE graph_json NOT LIKE '%"objects": []%'
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        non_empty = cursor.fetchall()
        print(f"   Non-empty scene graphs: {len(non_empty)}")
        
        for sg_id, graph_json_str, created_at, json_len in non_empty:
            try:
                graph_json = json.loads(graph_json_str)
                objects = graph_json.get('objects', [])
                relationships = graph_json.get('relationships', [])
                print(f"     Scene {sg_id}: {len(objects)} objects, {len(relationships)} rels")
                
                # Show object labels
                if objects:
                    labels = [obj.get('label', obj.get('name', '?')) for obj in objects]
                    print(f"       Objects: {', '.join(labels)}")
                    
            except Exception as e:
                print(f"     Scene {sg_id}: Parse error - {e}")
        
        # Test manual indexing of scene 3907
        print(f"\n🔧 Manual indexing test for scene 3907:")
        
        cursor.execute("""
            SELECT 
                sg.id, sg.graph_json, sg.created_at,
                c.name as camera_name, c.location as camera_location,
                c.user_id, m.timestamp
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id  
            JOIN cameras c ON m.camera_id = c.id
            WHERE sg.id = 3907
        """)
        
        result = cursor.fetchone()
        if result:
            sg_id, graph_json_str, created_at, cam_name, cam_location, user_id, timestamp = result
            
            print(f"   Found scene {sg_id}: camera={cam_name}, user={user_id}")
            
            # Test indexing
            vector_search = get_vector_search()
            graph_json = json.loads(graph_json_str)
            
            metadata = {
                "camera_name": cam_name or "",
                "camera_location": cam_location or "", 
                "created_at": created_at,
                "timestamp": timestamp,
                "user_id": user_id
            }
            
            # Parse text
            parsed_text = vector_search.scene_graph_to_text(graph_json)
            print(f"   Parsed text: {parsed_text}")
            
            # Try to index it
            success = vector_search.index_scene_graph(sg_id, graph_json, metadata)
            print(f"   Index success: {success}")
            
            # Try to find it in collection
            try:
                existing = vector_search.collection.get(ids=[str(sg_id)])
                if existing['ids']:
                    print(f"   ✓ Found in collection: {existing['documents'][0]}")
                else:
                    print(f"   ❌ Not found in collection")
            except Exception as e:
                print(f"   ❌ Collection error: {e}")
            
        else:
            print(f"   ❌ Scene 3907 not found in database")
            
        conn.close()
        
        # Test search after manual index
        print(f"\n🔍 Search test after manual index:")
        vector_search = get_vector_search()
        
        results = vector_search.search_scene_graphs("dog", user_id=1, limit=5)
        print(f"   Found {len(results)} results for 'dog'")
        
        for result in results:
            print(f"     Scene {result['scene_graph_id']}: {result['content']}")
            print(f"       Score: {result['similarity_score']:.3f}")
            if "dog" in result['content'].lower():
                print(f"       ✓ FOUND DOG!")
                break
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_indexing()