"""
Debug Scene Graph Content
"""
import sqlite3
import json
import sys

def debug_scene_graphs():
    """Debug what's actually in the scene graphs"""
    print("🔍 Debugging Scene Graph Content")
    print("=" * 50)
    
    try:
        # Connect to database
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Get sample scene graphs
        cursor.execute("""
            SELECT sg.id, sg.graph_json, sg.created_at, c.name as camera_name
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id
            JOIN cameras c ON m.camera_id = c.id
            ORDER BY sg.created_at DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        print(f"Found {len(rows)} scene graphs in database\n")
        
        for i, (sg_id, graph_json_str, created_at, camera_name) in enumerate(rows):
            print(f"Scene Graph {i+1}: ID {sg_id}")
            print(f"  Camera: {camera_name}")
            print(f"  Time: {created_at}")
            print(f"  JSON Length: {len(graph_json_str)} characters")
            
            # Try to parse JSON
            try:
                graph_data = json.loads(graph_json_str)
                print(f"  JSON Structure:")
                
                # Check what keys exist
                if isinstance(graph_data, dict):
                    print(f"    Keys: {list(graph_data.keys())}")
                    
                    # Check objects
                    if 'objects' in graph_data:
                        objects = graph_data['objects']
                        print(f"    Objects: {len(objects)} items")
                        if objects:
                            print(f"      Sample: {objects[0] if objects else 'None'}")
                    
                    # Check relationships  
                    if 'relationships' in graph_data:
                        relationships = graph_data['relationships']
                        print(f"    Relationships: {len(relationships)} items")
                        if relationships:
                            print(f"      Sample: {relationships[0] if relationships else 'None'}")
                    
                    # Check attributes
                    if 'attributes' in graph_data:
                        attributes = graph_data['attributes']
                        print(f"    Attributes: {len(attributes)} items")
                        if attributes:
                            print(f"      Sample: {attributes[0] if attributes else 'None'}")
                            
                    # Show raw content if small
                    if len(graph_json_str) < 200:
                        print(f"    Raw JSON: {graph_json_str}")
                        
                else:
                    print(f"    JSON is not a dict: {type(graph_data)}")
                    print(f"    Content: {graph_data}")
                    
            except json.JSONDecodeError as e:
                print(f"    ❌ JSON Parse Error: {e}")
                print(f"    Raw content (first 100 chars): {graph_json_str[:100]}")
            
            print("")
            
            if i >= 4:  # Show only first 5 for brevity
                break
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_scene_graphs()