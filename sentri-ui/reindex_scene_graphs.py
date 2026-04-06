"""
Re-index all scene graphs with correct parsing
"""
import sys
sys.path.insert(0, '.')

from vector_search import get_vector_search
import json

def reindex_all_scene_graphs():
    """Re-index all scene graphs with correct format parsing"""
    print("🔄 Re-indexing all scene graphs...")
    
    try:
        vector_search = get_vector_search()
        
        # Clear existing collection by deleting and recreating it
        try:
            vector_search.client.delete_collection("sentri_scene_graphs")
            print("✓ Deleted existing collection")
        except Exception:
            print("✓ Collection didn't exist, creating new")
        
        # Re-initialize collection
        from chromadb.utils import embedding_functions
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        vector_search.collection = vector_search.client.get_or_create_collection(
            name="sentri_scene_graphs",
            embedding_function=sentence_transformer_ef
        )
        print("✓ Recreated collection")
        
        # Re-index all scene graphs
        indexed_count = vector_search.index_all_scene_graphs()
        print(f"✓ Re-indexed {indexed_count} scene graphs")
        
        # Test parsing with your example
        example_scene = {
            "objects": [
                {
                    "x1": 50, "y1": 71, "x2": 799, "y2": 576,
                    "confidence": 0.9232370853424072,
                    "label": "grass",
                    "object_id": 0
                },
                {
                    "x1": 156, "y1": 78, "x2": 798, "y2": 514,
                    "confidence": 0.7602601051330566,
                    "label": "dog", 
                    "object_id": 1
                }
            ],
            "relationships": [
                {
                    "subject_id": 1,
                    "object_id": 0,
                    "predicate": "running on",
                    "confidence": 0.1293618232011795
                }
            ],
            "num_objects": 2,
            "num_relationships": 1
        }
        
        parsed_text = vector_search.scene_graph_to_text(example_scene)
        print(f"\n📝 Example parsing:")
        print(f"   Input: {json.dumps(example_scene, indent=2)[:200]}...")
        print(f"   Parsed: {parsed_text}")
        
        # Test search for dog
        print("\n🔍 Testing search for 'dog':")
        results = vector_search.search_scene_graphs("dog", limit=5)
        print(f"   Found {len(results)} results")
        for result in results[:3]:
            print(f"   - Scene {result['scene_graph_id']}: {result['content']}")
            print(f"     Score: {result['similarity_score']:.3f}")
        
        print("\n🎉 Re-indexing completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during re-indexing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reindex_all_scene_graphs()