"""
Vector Database Service for Sentri Scene Graph Search
Uses Chroma DB for semantic search capabilities
"""
import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

import chromadb
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class SentriVectorSearch:
    """Vector search service for scene graphs using Chroma DB"""
    
    def __init__(self, db_path: str = "tmp/sentri_vectordb"):
        """Initialize vector search with Chroma DB"""
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="scene_graphs",
            metadata={"description": "Scene graph embeddings for semantic search"}
        )
        
        # Initialize sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        logger.info(f"Vector search initialized with {self.collection.count()} indexed scene graphs")
    
    def scene_graph_to_text(self, graph_json: dict) -> str:
        """Convert scene graph JSON to searchable text"""
        text_parts = []
        
        # Create object ID to label mapping for relationships
        object_map = {}
        
        # Extract objects (actual format: {label, object_id, x1, y1, x2, y2, confidence})
        if 'objects' in graph_json:
            objects = []
            for obj in graph_json['objects']:
                # Handle both old format (name/class) and new format (label/object_id)
                obj_label = obj.get('label', obj.get('name', obj.get('class', '')))
                obj_id = obj.get('object_id')
                
                if obj_label:
                    objects.append(obj_label)
                    
                    # Map object_id to label for relationships
                    if obj_id is not None:
                        object_map[obj_id] = obj_label
                        
            if objects:
                text_parts.append(f"Objects: {', '.join(objects)}")
        
        # Extract relationships (actual format: {subject_id, object_id, predicate, confidence})
        if 'relationships' in graph_json:
            relationships = []
            for rel in graph_json['relationships']:
                # Handle both old format (subject/object names) and new format (subject_id/object_id)
                if 'subject_id' in rel and 'object_id' in rel:
                    # New format with IDs
                    subject_id = rel.get('subject_id')
                    object_id = rel.get('object_id') 
                    predicate = rel.get('predicate', '')
                    
                    subject_name = object_map.get(subject_id, f"object_{subject_id}")
                    object_name = object_map.get(object_id, f"object_{object_id}")
                    
                    if predicate:
                        relationships.append(f"{subject_name} {predicate} {object_name}")
                else:
                    # Old format with names
                    subject = rel.get('subject', '')
                    predicate = rel.get('predicate', '')
                    obj = rel.get('object', '')
                    if subject and predicate and obj:
                        relationships.append(f"{subject} {predicate} {obj}")
                        
            if relationships:
                text_parts.append(f"Relationships: {'; '.join(relationships)}")
        
        # Extract attributes if available (legacy format)
        if 'attributes' in graph_json:
            attributes = []
            for attr in graph_json['attributes']:
                attr_name = attr.get('attribute', '')
                obj_name = attr.get('object', '')
                if attr_name and obj_name:
                    attributes.append(f"{obj_name} is {attr_name}")
            if attributes:
                text_parts.append(f"Attributes: {'; '.join(attributes)}")
        
        return " | ".join(text_parts) if text_parts else "Empty scene graph"
    
    def index_scene_graph(self, scene_graph_id: int, graph_json: dict, metadata: dict) -> bool:
        """Add or update scene graph in vector index"""
        try:
            # Convert to searchable text
            text = self.scene_graph_to_text(graph_json)
            
            # Generate embedding
            embedding = self.model.encode([text])
            
            # Prepare metadata
            vector_metadata = {
                "scene_graph_id": scene_graph_id,
                "camera_name": metadata.get("camera_name", ""),
                "camera_location": metadata.get("camera_location", ""),
                "created_at": metadata.get("created_at", ""),
                "timestamp": metadata.get("timestamp", ""),
                "user_id": metadata.get("user_id", 1)
            }
            
            # Check if already exists
            existing = self.collection.get(ids=[str(scene_graph_id)])
            
            if existing['ids']:
                # Update existing
                self.collection.update(
                    ids=[str(scene_graph_id)],
                    embeddings=embedding.tolist(),
                    documents=[text],
                    metadatas=[vector_metadata]
                )
                logger.debug(f"Updated scene graph {scene_graph_id} in vector index")
            else:
                # Add new
                self.collection.add(
                    ids=[str(scene_graph_id)],
                    embeddings=embedding.tolist(),
                    documents=[text],
                    metadatas=[vector_metadata]
                )
                logger.debug(f"Added scene graph {scene_graph_id} to vector index")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to index scene graph {scene_graph_id}: {e}")
            return False
    
    def index_all_scene_graphs(self) -> int:
        """Index all scene graphs from database, prioritizing non-empty ones"""
        import sqlite3
        import json
        
        try:
            conn = sqlite3.connect('tmp/sentri.db', check_same_thread=False)
            cursor = conn.cursor()
            
            # Get non-empty scene graphs first (prioritize content)
            cursor.execute("""
                SELECT 
                    sg.id, sg.graph_json, sg.created_at,
                    c.name as camera_name, c.location as camera_location,
                    c.user_id, m.timestamp
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                WHERE sg.graph_json NOT LIKE '%"objects": []%'
                ORDER BY sg.created_at DESC
            """)
            
            priority_rows = cursor.fetchall()
            
            # Then get remaining scene graphs
            cursor.execute("""
                SELECT 
                    sg.id, sg.graph_json, sg.created_at,
                    c.name as camera_name, c.location as camera_location,
                    c.user_id, m.timestamp
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                WHERE sg.graph_json LIKE '%"objects": []%'
                ORDER BY sg.created_at DESC
            """)
            
            empty_rows = cursor.fetchall()
            
            all_rows = priority_rows + empty_rows
            indexed_count = 0
            
            logger.info(f"Starting to index {len(priority_rows)} non-empty + {len(empty_rows)} empty scene graphs...")
            
            for row in all_rows:
                sg_id, graph_json_str, created_at, cam_name, cam_location, user_id, timestamp = row
                
                try:
                    # Parse scene graph JSON
                    graph_json = json.loads(graph_json_str)
                    
                    # Skip truly empty scene graphs for now to save space
                    objects = graph_json.get('objects', [])
                    if not objects and indexed_count > 100:  # Only index first 100 empty ones
                        continue
                    
                    # Prepare metadata
                    metadata = {
                        "camera_name": cam_name or "",
                        "camera_location": cam_location or "", 
                        "created_at": created_at,
                        "timestamp": timestamp,
                        "user_id": user_id
                    }
                    
                    # Index this scene graph
                    if self.index_scene_graph(sg_id, graph_json, metadata):
                        indexed_count += 1
                        
                        # Log non-empty ones
                        if objects:
                            parsed_text = self.scene_graph_to_text(graph_json)
                            logger.info(f"Indexed scene {sg_id}: {parsed_text}")
                        
                    if indexed_count % 10 == 0:
                        logger.info(f"Indexed {indexed_count}/{len(all_rows)} scene graphs...")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON for scene graph {sg_id}")
                    continue
                except Exception as e:
                    logger.error(f"Error indexing scene graph {sg_id}: {e}")
                    continue
            
            conn.close()
            logger.info(f"Successfully indexed {indexed_count} scene graphs ({len(priority_rows)} with content)")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Failed to index all scene graphs: {e}")
            return 0
    
    def search_scene_graphs(
        self, 
        query: str, 
        user_id: int = 1,
        limit: int = 10,
        start_time: str = None,
        end_time: str = None,
        camera_name: str = None
    ) -> List[Dict[str, Any]]:
        """Semantic search for scene graphs"""
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query])
            
            # Build metadata filters (only for non-time filters to avoid type issues)
            filter_conditions = []
            filter_conditions.append({"user_id": {"$eq": user_id}})
            
            if camera_name:
                filter_conditions.append({"camera_name": {"$eq": camera_name}})
            
            # Build final where clause
            if len(filter_conditions) == 1:
                where_clause = filter_conditions[0]
            else:
                where_clause = {"$and": filter_conditions}
            
            # Perform semantic search (without time filters)
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=limit * 2,  # Get more results to filter by time later
                where=where_clause
            )
            
            # Format results
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i, scene_graph_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    document = results['documents'][0][i]
                    distance = results['distances'][0][i] if results['distances'] else 0
                    
                    created_at = metadata.get("created_at", "")
                    
                    # Apply time filters manually
                    if start_time and created_at < start_time:
                        continue
                    if end_time and created_at > end_time:
                        continue
                    
                    formatted_results.append({
                        "scene_graph_id": int(scene_graph_id),
                        "content": document,
                        "camera_name": metadata.get("camera_name", ""),
                        "camera_location": metadata.get("camera_location", ""),
                        "created_at": created_at,
                        "similarity_score": round(1 - distance, 3),  # Convert distance to similarity
                        "metadata": metadata
                    })
                    
                    # Stop when we have enough results
                    if len(formatted_results) >= limit:
                        break
            
            logger.info(f"Vector search for '{query}' returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector database statistics"""
        try:
            count = self.collection.count()
            return {
                "total_indexed": count,
                "collection_name": self.collection.name,
                "model_name": self.model.get_sentence_embedding_dimension(),
                "db_path": self.db_path
            }
        except Exception as e:
            logger.error(f"Failed to get vector DB stats: {e}")
            return {}

# Global instance
_vector_search_instance = None

def get_vector_search() -> SentriVectorSearch:
    """Get singleton vector search instance"""
    global _vector_search_instance
    if _vector_search_instance is None:
        _vector_search_instance = SentriVectorSearch()
    return _vector_search_instance