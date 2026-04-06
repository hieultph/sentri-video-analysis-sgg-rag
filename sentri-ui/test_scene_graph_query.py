#!/usr/bin/env python3

import sqlite3
import json

def test_scene_graph_query():
    """Test the scene graph query to check data structure"""
    
    conn = sqlite3.connect('tmp/sentri.db')
    cursor = conn.cursor()
    
    try:
        print("=== Testing Scene Graphs Query ===")
        
        # First, check what's in scene_graphs table
        print("\n1. Scene Graphs Table Structure:")
        cursor.execute("PRAGMA table_info(scene_graphs)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col}")
        
        # Check total count
        print("\n2. Total Scene Graphs:")
        cursor.execute("SELECT COUNT(*) FROM scene_graphs")
        total = cursor.fetchone()[0]
        print(f"  Total: {total}")
        
        # Check some sample data
        print("\n3. Sample Scene Graph Records:")
        cursor.execute("SELECT id, media_id, created_at FROM scene_graphs ORDER BY created_at DESC LIMIT 5")
        samples = cursor.fetchall()
        for sample in samples:
            print(f"  ID: {sample[0]}, Media ID: {sample[1]}, Created: {sample[2]}")
        
        # Test the actual query used in the function
        print("\n4. Testing Actual Query (user_id=1):")
        query = """
            SELECT 
                sg.id, sg.graph_json, sg.created_at,
                c.name as camera_name, c.location
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id  
            JOIN cameras c ON m.camera_id = c.id
            WHERE c.user_id = ?
            ORDER BY sg.created_at DESC LIMIT 5
        """
        
        cursor.execute(query, (1,))
        results = cursor.fetchall()
        
        print(f"  Found {len(results)} results for user_id=1")
        
        for i, row in enumerate(results):
            scene_graph_id = row[0]
            graph_json = row[1]
            created_at = row[2]
            camera_name = row[3]
            camera_location = row[4]
            
            print(f"\n  Result {i+1}:")
            print(f"    Scene Graph ID: {scene_graph_id}")
            print(f"    Camera: {camera_name} ({camera_location})")
            print(f"    Created: {created_at}")
            
            # Parse graph_json to check relationships
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
                    print(f"    Relationships: {'; '.join(relationships)}")
                else:
                    print(f"    Relationships: None found")
                    print(f"    Raw graph_data keys: {list(graph_data.keys())}")
                    if 'relationships' in graph_data:
                        print(f"    Raw relationships: {graph_data['relationships']}")
                        
            except json.JSONDecodeError as e:
                print(f"    JSON Error: {e}")
                print(f"    Raw JSON: {graph_json[:200]}...")
        
        # Check if there are any scene graphs without proper JOIN
        print("\n5. Checking Scene Graphs without Media/Camera:")
        cursor.execute("""
            SELECT sg.id 
            FROM scene_graphs sg
            LEFT JOIN media m ON sg.media_id = m.id
            WHERE m.id IS NULL
        """)
        orphaned = cursor.fetchall()
        if orphaned:
            print(f"  Found {len(orphaned)} scene graphs without media records:")
            for orphan in orphaned:
                print(f"    Scene Graph ID: {orphan[0]}")
        else:
            print("  All scene graphs have corresponding media records")
            
        # Check media->camera join
        print("\n6. Checking Media without Camera:")
        cursor.execute("""
            SELECT m.id 
            FROM media m
            LEFT JOIN cameras c ON m.camera_id = c.id
            WHERE c.id IS NULL
        """)
        orphaned_media = cursor.fetchall()
        if orphaned_media:
            print(f"  Found {len(orphaned_media)} media records without camera records:")
            for orphan in orphaned_media:
                print(f"    Media ID: {orphan[0]}")
        else:
            print("  All media records have corresponding camera records")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    test_scene_graph_query()