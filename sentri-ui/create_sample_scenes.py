"""
Create Sample Scene Graphs for Testing
"""
import sqlite3
import json
from datetime import datetime

def create_sample_scene_graphs():
    """Create sample scene graphs with actual content for testing"""
    print("🎬 Creating sample scene graphs...")
    
    # Sample scene graphs with realistic content
    sample_scenes = [
        {
            "description": "Person walking on street",
            "objects": [
                {"id": 1, "name": "person", "class": "person", "bbox": [100, 200, 150, 300]},
                {"id": 2, "name": "street", "class": "road", "bbox": [0, 300, 640, 480]},
                {"id": 3, "name": "sidewalk", "class": "path", "bbox": [0, 250, 640, 300]}
            ],
            "relationships": [
                {"subject": "person", "predicate": "walking_on", "object": "street"},
                {"subject": "person", "predicate": "near", "object": "sidewalk"}
            ],
            "attributes": [
                {"object": "person", "attribute": "moving"},
                {"object": "street", "attribute": "paved"}
            ]
        },
        {
            "description": "Car driving on road",
            "objects": [
                {"id": 1, "name": "car", "class": "car", "bbox": [200, 150, 350, 250]},
                {"id": 2, "name": "road", "class": "road", "bbox": [0, 200, 640, 480]},
                {"id": 3, "name": "building", "class": "building", "bbox": [450, 50, 640, 200]}
            ],
            "relationships": [
                {"subject": "car", "predicate": "driving_on", "object": "road"},
                {"subject": "building", "predicate": "next_to", "object": "road"}
            ],
            "attributes": [
                {"object": "car", "attribute": "red"},
                {"object": "car", "attribute": "moving"},
                {"object": "road", "attribute": "asphalt"}
            ]
        },
        {
            "description": "People sitting at table",
            "objects": [
                {"id": 1, "name": "person1", "class": "person", "bbox": [100, 100, 150, 200]},
                {"id": 2, "name": "person2", "class": "person", "bbox": [200, 100, 250, 200]},
                {"id": 3, "name": "table", "class": "table", "bbox": [120, 180, 230, 220]},
                {"id": 4, "name": "chair1", "class": "chair", "bbox": [90, 160, 130, 200]},
                {"id": 5, "name": "chair2", "class": "chair", "bbox": [210, 160, 250, 200]}
            ],
            "relationships": [
                {"subject": "person1", "predicate": "sitting_on", "object": "chair1"},
                {"subject": "person2", "predicate": "sitting_on", "object": "chair2"},
                {"subject": "chair1", "predicate": "at", "object": "table"},
                {"subject": "chair2", "predicate": "at", "object": "table"}
            ],
            "attributes": [
                {"object": "person1", "attribute": "sitting"},
                {"object": "person2", "attribute": "sitting"},
                {"object": "table", "attribute": "wooden"}
            ]
        },
        {
            "description": "Motorcycle on street",
            "objects": [
                {"id": 1, "name": "motorcycle", "class": "motorcycle", "bbox": [150, 200, 200, 280]},
                {"id": 2, "name": "person", "class": "person", "bbox": [155, 180, 180, 230]},
                {"id": 3, "name": "street", "class": "road", "bbox": [0, 250, 640, 480]}
            ],
            "relationships": [
                {"subject": "person", "predicate": "riding", "object": "motorcycle"},
                {"subject": "motorcycle", "predicate": "on", "object": "street"}
            ],
            "attributes": [
                {"object": "motorcycle", "attribute": "blue"},
                {"object": "person", "attribute": "wearing_helmet"},
                {"object": "street", "attribute": "concrete"}
            ]
        },
        {
            "description": "Dog running in park",
            "objects": [
                {"id": 1, "name": "dog", "class": "dog", "bbox": [250, 200, 300, 250]},
                {"id": 2, "name": "grass", "class": "grass", "bbox": [0, 250, 640, 480]},
                {"id": 3, "name": "tree", "class": "tree", "bbox": [500, 50, 580, 250]}
            ],
            "relationships": [
                {"subject": "dog", "predicate": "running_on", "object": "grass"},
                {"subject": "tree", "predicate": "in", "object": "grass"}
            ],
            "attributes": [
                {"object": "dog", "attribute": "brown"},
                {"object": "dog", "attribute": "running"},
                {"object": "grass", "attribute": "green"}
            ]
        }
    ]
    
    try:
        # Connect to database
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Get the first camera and create media entries
        cursor.execute("SELECT id FROM cameras LIMIT 1")
        camera_result = cursor.fetchone()
        if not camera_result:
            print("❌ No cameras found in database")
            return
            
        camera_id = camera_result[0]
        
        created_count = 0
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for i, scene in enumerate(sample_scenes):
            # Create media entry (matching actual schema)
            media_filename = f"sample_scene_{i+1}.jpg"
            file_path = f"static/recordings/frames/{media_filename}"
            
            cursor.execute("""
                INSERT INTO media (camera_id, type, file_path, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (camera_id, 'image', file_path, current_time, current_time))
            
            media_id = cursor.lastrowid
            
            # Create scene graph JSON
            scene_graph = {
                "objects": scene["objects"],
                "relationships": scene["relationships"],
                "attributes": scene.get("attributes", []),
                "num_objects": len(scene["objects"]),
                "num_relationships": len(scene["relationships"])
            }
            
            # Insert scene graph
            cursor.execute("""
                INSERT INTO scene_graphs (media_id, graph_json, created_at)
                VALUES (?, ?, ?)
            """, (media_id, json.dumps(scene_graph), current_time))
            
            created_count += 1
            print(f"✓ Created: {scene['description']}")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Created {created_count} sample scene graphs!")
        print("Now vector search will have real content to index and search")
        
    except Exception as e:
        print(f"❌ Error creating samples: {e}")

if __name__ == "__main__":
    create_sample_scene_graphs()