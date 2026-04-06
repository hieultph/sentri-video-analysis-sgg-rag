#!/usr/bin/env python3
"""
Migration script to index existing scene graphs into vector database
Run this once to migrate existing SQLite data to Chroma DB
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vector_search import get_vector_search

def migrate_scene_graphs_to_vector_db():
    """Migrate all existing scene graphs from SQLite to vector database"""
    
    print("=== MIGRATING SCENE GRAPHS TO VECTOR DATABASE ===")
    
    # Initialize vector search
    vector_search = get_vector_search()
    
    # Connect to SQLite database
    conn = sqlite3.connect('tmp/sentri.db')
    cursor = conn.cursor()
    
    try:
        # Get all scene graphs with camera info
        query = """
            SELECT 
                sg.id, sg.graph_json, sg.created_at,
                c.name as camera_name, c.location as camera_location,
                c.user_id, m.timestamp
            FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id  
            JOIN cameras c ON m.camera_id = c.id
            ORDER BY sg.created_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} scene graphs to migrate")
        
        success_count = 0
        error_count = 0
        
        for i, row in enumerate(rows):
            scene_graph_id, graph_json_str, created_at, camera_name, camera_location, user_id, timestamp = row
            
            try:
                # Parse graph JSON
                graph_json = json.loads(graph_json_str)
                
                # Prepare metadata
                metadata = {
                    "camera_name": camera_name or "",
                    "camera_location": camera_location or "",
                    "created_at": created_at,
                    "timestamp": timestamp,
                    "user_id": user_id
                }
                
                # Index in vector database
                success = vector_search.index_scene_graph(
                    scene_graph_id=scene_graph_id,
                    graph_json=graph_json,
                    metadata=metadata
                )
                
                if success:
                    success_count += 1
                    if (i + 1) % 50 == 0:
                        print(f"  Processed {i + 1}/{len(rows)} scene graphs...")
                else:
                    error_count += 1
                    print(f"  Failed to index scene graph {scene_graph_id}")
                    
            except json.JSONDecodeError:
                error_count += 1
                print(f"  Invalid JSON for scene graph {scene_graph_id}")
            except Exception as e:
                error_count += 1
                print(f"  Error processing scene graph {scene_graph_id}: {e}")
        
        print(f"\n=== MIGRATION COMPLETE ===")
        print(f"✅ Successfully indexed: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"📊 Total processed: {len(rows)}")
        
        # Get vector DB stats
        stats = vector_search.get_stats()
        print(f"📈 Vector DB now contains: {stats.get('total_indexed', 0)} scene graphs")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def test_vector_search():
    """Test vector search functionality"""
    print("\n=== TESTING VECTOR SEARCH ===")
    
    vector_search = get_vector_search()
    
    # Test queries
    test_queries = [
        "person walking",
        "car on road",
        "people standing",
        "objects on table",
        "person beside car"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Search: '{query}'")
        results = vector_search.search_scene_graphs(query, user_id=1, limit=3)
        
        if results:
            for i, result in enumerate(results):
                print(f"  {i+1}. Scene {result['scene_graph_id']} (Score: {result['similarity_score']})")
                print(f"     📹 {result['camera_name']} - {result['created_at']}")
                print(f"     📝 {result['content'][:100]}...")
        else:
            print("  No results found")

if __name__ == "__main__":
    # Run migration
    migrate_scene_graphs_to_vector_db()
    
    # Test search
    test_vector_search()