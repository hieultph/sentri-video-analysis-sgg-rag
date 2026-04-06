"""
Simple Vector Search Service for Sentri Scene Graph Search
Fallback version without heavy ML dependencies
"""
import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

class SentriSimpleSearch:
    """Simple search service for scene graphs using text matching"""
    
    def __init__(self):
        """Initialize simple search"""
        # Translation mapping for Vietnamese to English
        self.translation_map = {
            "người": "person people human",
            "xe": "car vehicle automobile",
            "ô tô": "car automobile vehicle",
            "xe máy": "motorcycle motorbike bike", 
            "đi bộ": "walking walk pedestrian",
            "chạy": "running run",
            "đứng": "standing stand",
            "ngồi": "sitting sit",
            "bàn": "table desk",
            "ghế": "chair seat",
            "cửa": "door entrance",
            "cửa sổ": "window",
            "đường": "road street path",
            "nhà": "house building home",
            "cây": "tree plant",
            "trời": "sky cloud weather",
            "sáng": "morning bright light",
            "tối": "evening dark night",
            "hoạt động": "activity action movement"
        }
        
        logger.info("Simple search initialized")
    
    def _normalize_query(self, query: str) -> List[str]:
        """Normalize and expand search query"""
        query = query.lower().strip()
        
        # Translate Vietnamese terms to English
        expanded_terms = [query]
        
        for vn_term, en_terms in self.translation_map.items():
            if vn_term in query:
                expanded_terms.extend(en_terms.split())
                expanded_terms.append(query.replace(vn_term, en_terms))
        
        # Add common variations
        if any(term in query for term in ['person', 'people', 'người']):
            expanded_terms.extend(['human', 'man', 'woman', 'pedestrian'])
        
        if any(term in query for term in ['car', 'vehicle', 'xe', 'ô tô']):
            expanded_terms.extend(['automobile', 'truck', 'bus'])
            
        return list(set(expanded_terms))
    
    def _calculate_similarity(self, text: str, query_terms: List[str]) -> float:
        """Calculate text similarity score"""
        text_lower = text.lower()
        
        # Count term matches
        matches = 0
        total_score = 0
        
        for term in query_terms:
            term_lower = term.lower()
            
            # Exact match (highest score)
            if term_lower in text_lower:
                matches += 1
                total_score += 1.0
                
            # Partial match (medium score)  
            elif any(word in text_lower for word in term_lower.split()):
                matches += 1
                total_score += 0.7
                
            # Fuzzy match (low score)
            elif any(term_word in text_word for term_word in term_lower.split() 
                    for text_word in text_lower.split() if len(term_word) > 3):
                matches += 1
                total_score += 0.4
        
        # Calculate final score
        if not query_terms:
            return 0.0
            
        similarity = total_score / len(query_terms)
        
        # Bonus for multiple matches
        if matches > 1:
            similarity *= (1 + matches * 0.1)
            
        return min(similarity, 1.0)
    
    def search_scene_graphs(
        self, 
        query: str, 
        user_id: int = 1,
        limit: int = 10,
        start_time: str = None,
        end_time: str = None,
        camera_name: str = None
    ) -> List[Dict[str, Any]]:
        """Simple semantic search for scene graphs"""
        try:
            # Connect to database
            conn = sqlite3.connect('tmp/sentri.db', check_same_thread=False)
            cursor = conn.cursor()
            
            # Normalize query
            query_terms = self._normalize_query(query)
            logger.info(f"Search query '{query}' expanded to: {query_terms}")
            
            # Build SQL query with filters
            sql_query = """
                SELECT 
                    sg.id, sg.graph_json, sg.created_at,
                    c.name as camera_name, c.location as camera_location
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                WHERE c.user_id = ?
            """
            
            params = [user_id]
            
            # Add time filters
            if start_time:
                sql_query += " AND sg.created_at >= ?"
                params.append(start_time)
            if end_time:
                sql_query += " AND sg.created_at <= ?"
                params.append(end_time)
            if camera_name:
                sql_query += " AND c.name = ?"
                params.append(camera_name)
            
            sql_query += " ORDER BY sg.created_at DESC"
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            # Score and rank results
            scored_results = []
            
            for row in rows:
                scene_graph_id, graph_json_str, created_at, cam_name, cam_location = row
                
                try:
                    # Parse scene graph
                    graph_json = json.loads(graph_json_str)
                    
                    # Create searchable text
                    searchable_text = self._create_searchable_text(graph_json)
                    
                    # Calculate similarity
                    similarity = self._calculate_similarity(searchable_text, query_terms)
                    
                    if similarity > 0.1:  # Minimum threshold
                        scored_results.append({
                            "scene_graph_id": scene_graph_id,
                            "content": searchable_text,
                            "camera_name": cam_name or "",
                            "camera_location": cam_location or "",
                            "created_at": created_at,
                            "similarity_score": round(similarity, 3),
                            "metadata": {
                                "scene_graph_id": scene_graph_id,
                                "camera_name": cam_name,
                                "camera_location": cam_location,
                                "created_at": created_at,
                                "user_id": user_id
                            }
                        })
                        
                except json.JSONDecodeError:
                    continue
            
            # Sort by similarity score
            scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            # Return top results
            final_results = scored_results[:limit]
            
            logger.info(f"Simple search for '{query}' returned {len(final_results)} results")
            
            conn.close()
            return final_results
            
        except Exception as e:
            logger.error(f"Simple search failed: {e}")
            return []
    
    def _create_searchable_text(self, graph_json: dict) -> str:
        """Create searchable text from scene graph JSON"""
        text_parts = []
        
        # Extract objects
        if 'objects' in graph_json:
            objects = []
            for obj in graph_json['objects']:
                obj_name = obj.get('name', obj.get('class', ''))
                if obj_name:
                    objects.append(obj_name)
            if objects:
                text_parts.append(f"Objects: {', '.join(objects)}")
        
        # Extract relationships
        if 'relationships' in graph_json:
            relationships = []
            for rel in graph_json['relationships']:
                subject = rel.get('subject', '')
                predicate = rel.get('predicate', '')
                obj = rel.get('object', '')
                if subject and predicate and obj:
                    relationships.append(f"{subject} {predicate} {obj}")
            if relationships:
                text_parts.append(f"Relationships: {'; '.join(relationships)}")
        
        # Extract attributes
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        try:
            conn = sqlite3.connect('tmp/sentri.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scene_graphs")
            count = cursor.fetchone()[0]
            conn.close()
            
            return {
                "total_indexed": count,
                "search_type": "simple_text_matching",
                "translation_terms": len(self.translation_map)
            }
        except Exception:
            return {"error": "Could not get stats"}

# Global instance
_simple_search_instance = None

def get_simple_search() -> SentriSimpleSearch:
    """Get singleton simple search instance"""
    global _simple_search_instance
    if _simple_search_instance is None:
        _simple_search_instance = SentriSimpleSearch()
    return _simple_search_instance