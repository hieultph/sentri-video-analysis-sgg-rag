import os
import json
import sys
import base64
import math
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
import logging
from urllib.parse import urlparse
import sqlite3

import cv2
import requests
from agno.tools.toolkit import Toolkit
from agno.agent import Agent
from tools.utils import APIHandler, DroneController, DEFAULT_MISSION_DIR

# Import vector search if available, fallback to simple search
try:
    from vector_search import get_vector_search
    VECTOR_SEARCH_AVAILABLE = True
    SIMPLE_SEARCH_AVAILABLE = False
    print("Vector search available")
except ImportError as e:
    print(f"Vector search not available: {e}")
    VECTOR_SEARCH_AVAILABLE = False
    try:
        from simple_search import get_simple_search
        SIMPLE_SEARCH_AVAILABLE = True
        print("Using simple search fallback")
    except ImportError as e2:
        print(f"Simple search also not available: {e2}")
        SIMPLE_SEARCH_AVAILABLE = False

# For numerical operations
import numpy as np
import time

# API Configuration
# AI_MODEL_API_URL = "http://10.5.9.16/act"
# AIRSIM_VIDEO_URL = "http://127.0.0.1:5000/video_feed"
MAVLINK_CONNECTION = 'udpin:0.0.0.0:14555'

# Flight Configuration
TAKEOFF_ALTITUDE = 20.0  # meters
HOVER_TOLERANCE = 0.3   # meters
MAX_TAKEOFF_TIME = 30   # seconds

DETECTION_DEFAULT_SIZE = 640
DETECTION_DEFAULT_ZOOM = 19


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for UAV connection and state
takeoff_position = None
drone_ready = False

import subprocess, time, socket, http.client


# Helper utilities for decoding and rendering detection imagery
def _decode_image_payload(image_block: Dict[str, Any]) -> np.ndarray:
    if not image_block:
        raise ValueError("Empty image payload")
    if image_block.get("encoding") != "base64":
        raise ValueError("Unsupported image encoding")
    data = image_block.get("data")
    if not data:
        raise ValueError("Missing base64 data")
    binary = base64.b64decode(data)
    array = np.frombuffer(binary, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image data")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _render_detected_image(api_response: Dict[str, Any]) -> np.ndarray:
    base_payload = api_response.get("base_map") or api_response.get("annotated_map")
    annotated = _decode_image_payload(base_payload or {})
    for building in api_response.get("buildings", []):
        bbox = building.get("bbox", {})
        x1, y1 = bbox.get("x1"), bbox.get("y1")
        x2, y2 = bbox.get("x2"), bbox.get("y2")
        if None in (x1, y1, x2, y2):
            continue
        try:
            coords = [int(round(float(value))) for value in (x1, y1, x2, y2)]
        except (TypeError, ValueError):
            continue
        x1_i, y1_i, x2_i, y2_i = coords
        cv2.rectangle(annotated, (x1_i, y1_i), (x2_i, y2_i), (0, 255, 0), 2)
        label = f"ID {building.get('id', '?')}"
        cv2.putText(
            annotated,
            label,
            (x1_i, max(15, y1_i - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )
    return annotated


# wait for a TCP port to be open
def wait_for_port(host: str, port: int, timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Poll until a TCP port is reachable or the timeout elapses.

    Args:
        host: Hostname or IP address exposing the port.
        port: TCP port number to probe.
        timeout: Total seconds to wait before giving up.
        interval: Delay in seconds between retries.

    Returns:
        ``True`` when the socket opens successfully, otherwise ``False``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return True
        except OSError:
            time.sleep(interval)
    return False

# wait for an HTTP server to return 200 OK
def wait_for_http_ok(host: str, port: int, path: str = "/health", timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Ping an HTTP endpoint until it responds with a healthy status code.

    Args:
        host: Hostname or IP of the HTTP service.
        port: Port where the server listens.
        path: Relative path that should return an OK status.
        timeout: Maximum seconds to keep retrying.
        interval: Seconds to sleep between attempts.

    Returns:
        ``True`` if a 2xx/3xx response is observed; ``False`` on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", path)
            resp = conn.getresponse()
            # 200-399 coi như OK (tùy server của bạn, có thể chỉ cần 200)
            if 200 <= resp.status < 400:
                return True
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        time.sleep(interval)
    return False

class SentriTools(Toolkit):
    
    def __init__(self):
        super().__init__(name = "Sentri Tools")
        self.api_handler = APIHandler()
        
        self.register(self.get_scene_graphs_simple)
        self.register(self.search_scene_graphs_semantic)
        self.register(self.show_scene_graph_image)

    def _get_db_connection(self):
        """Get database connection - same as in app.py"""
        return sqlite3.connect('tmp/sentri.db', check_same_thread=False)

    def _get_user_id_from_session(self, agent) -> int:
        """Extract user_id from agent session state"""
        user_id = agent.session_state.get("user_id")
        if not user_id or user_id == "":
            return 1  # Default to user 1
            
        # If it's already a number, return it
        if isinstance(user_id, int):
            return user_id
            
        # If it's a string that looks like a number, convert it
        if isinstance(user_id, str):
            try:
                return int(user_id)
            except ValueError:
                # It's a username, lookup user_id from database
                return self._lookup_user_id_by_username(user_id)
                
        return 1  # Default fallback

    def _lookup_user_id_by_username(self, username: str) -> int:
        """Lookup user_id from username"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                # User not found, return default
                return 1
        except Exception as e:
            print(f"Error looking up user {username}: {e}")
            return 1
        finally:
            conn.close()

    def get_scene_graphs_simple(self, agent, limit: int = 50, start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """
        Get scene graphs in ultra simple format: just ID and relationships text.
        
        Args:
            limit: Maximum number of scene graphs to return (default: 50)
            start_time: Start datetime filter in format "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD" (optional)
            end_time: End datetime filter in format "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD" (optional)
            
        Returns:
            List of simple dicts: {"scene_graph_id": X, "relationships": "A over B; C beside D", "created_at": "timestamp"}
        """

        print("[Agent Tool] get_scene_graphs_simple called")
        user_id = self._get_user_id_from_session(agent)
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            base_query = """
                SELECT 
                    sg.id, sg.graph_json, sg.created_at,
                    c.name as camera_name, c.location
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                WHERE c.user_id = ?
            """
            
            params = [user_id]
            
            if start_time:
                try:
                    if len(start_time) == 10:
                        start_time = start_time + " 00:00:00"
                    datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    base_query += " AND sg.created_at >= ?"
                    params.append(start_time)
                except ValueError:
                    pass
            
            if end_time:
                try:
                    if len(end_time) == 10:
                        end_time = end_time + " 23:59:59"
                    datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    base_query += " AND sg.created_at <= ?"
                    params.append(end_time)
                except ValueError:
                    pass
            
            query = base_query + " ORDER BY sg.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            
            for i, row in enumerate(rows):
                scene_graph_id = row[0]
                graph_json = row[1]
                created_at = row[2]
                camera_name = row[3]
                camera_location = row[4]
                
                try:
                    graph_data = json.loads(graph_json)
                    
                    relationships = []
                    if 'relationships' in graph_data:
                        for j, rel in enumerate(graph_data['relationships']):
                            subject = rel.get('subject', '')
                            predicate = rel.get('predicate', '')
                            obj = rel.get('object', '')
                            if subject and predicate and obj:
                                relationships.append(f"{subject} {predicate} {obj}")
                    
                    if relationships:
                        relationship_text = "; ".join(relationships)
                    else:
                        relationship_text = "No relationships detected"
                    
                    results.append({
                        "scene_graph_id": scene_graph_id,
                        "relationships": relationship_text,
                        "created_at": created_at,
                        "camera_name": camera_name
                    })
                    
                except json.JSONDecodeError as e:
                    continue
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to get scene graphs: {e}")
        finally:
            conn.close()

    def show_scene_graph_image(self, agent, scene_graph_id: int) -> Dict[str, Any]:
        """
        Show image for a specific scene graph by ID.
        
        Args:
            scene_graph_id: ID of the scene graph to show image for
            
        Returns:
            Image file path and details for display in chat
        """

        user_id = self._get_user_id_from_session(agent)
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT 
                    m.file_path, m.timestamp, m.type,
                    c.name as camera_name, c.location,
                    sg.created_at
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                WHERE sg.id = ? AND c.user_id = ?
            """
            
            cursor.execute(query, (scene_graph_id, user_id))
            row = cursor.fetchone()
            
            if not row:
                return {
                    'success': False,
                    'error': f'Không tìm thấy scene graph {scene_graph_id} hoặc bạn không có quyền truy cập'
                }
            
            file_path, timestamp, media_type, camera_name, camera_location, created_at = row
            
            import os
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'File ảnh không tồn tại: {file_path}'
                }
            
            return {
                'success': True,
                'file_path': file_path,
                'timestamp': timestamp,
                'media_type': media_type,
                'camera_name': camera_name,
                'camera_location': camera_location,
                'created_at': created_at,
                'display_info': f"📷 {camera_name} ({camera_location}) - {created_at}",
                'image_url': f"/static/recordings/{os.path.basename(file_path)}"
            }
            
        except Exception as e:
            raise Exception(f"Failed to get scene graph image: {e}")
        finally:
            conn.close()

    def search_scene_graphs_semantic(self, agent, query: str, limit: int = 10, start_time: str = None, end_time: str = None, camera_name: str = None) -> List[Dict[str, Any]]:
        """
        🔥 PRIMARY TOOL: Semantic search for scene graphs using AI vector database.
        
        IMPORTANT: This tool returns ACTUAL SCENE GRAPH DATA. If len(results) > 0, then objects EXIST in the camera data.
        
        Args:
            query: Natural language query describing what to look for
                  Examples: "dog", "person walking", "car on road", "chó", "xe ô tô" 
            limit: Maximum number of results (default: 10)
            start_time: Optional time filter "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD" 
            end_time: Optional time filter "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
            camera_name: Optional camera filter
            
        Returns:
            List[Dict] with keys:
            - scene_graph_id: Unique ID for this detection
            - content: Human readable description "Objects: A, B | Relationships: A verb B"  
            - camera_name: Which camera detected this
            - created_at: When this was detected "YYYY-MM-DD HH:MM:SS"
            - similarity_score: Relevance score (higher = more relevant)
            
        Example Response:
        [
          {
            "scene_graph_id": 3988,
            "content": "Objects: grass, dog | Relationships: dog standing on grass",
            "camera_name": "screen", 
            "created_at": "2025-12-15 01:36:23",
            "similarity_score": 0.449
          }
        ]
        
        AGENT INSTRUCTIONS:
        - If len(results) > 0: Objects were detected → Answer positively about findings
        - If len(results) == 0: No objects found → Use "chưa ghi nhận" response
        - Check result["content"] field to see what objects and relationships were detected
        - Example: If user asks "Có chó không?" and result contains "dog" → Answer "Có! Phát hiện chó..."
        """
        
        user_id = self._get_user_id_from_session(agent)
        
        try:
            # Try vector search first
            if VECTOR_SEARCH_AVAILABLE:
                vector_search = get_vector_search()
                search_service = vector_search
                search_type = "vector"
            elif SIMPLE_SEARCH_AVAILABLE:
                simple_search = get_simple_search()
                search_service = simple_search
                search_type = "simple"
            else:
                raise Exception("No search service available")
            
            # Format time filters if provided
            formatted_start_time = None
            formatted_end_time = None
            
            if start_time:
                try:
                    if len(start_time) == 10:
                        formatted_start_time = start_time + " 00:00:00"
                    else:
                        formatted_start_time = start_time
                    datetime.strptime(formatted_start_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            
            if end_time:
                try:
                    if len(end_time) == 10:
                        formatted_end_time = end_time + " 23:59:59"
                    else:
                        formatted_end_time = end_time
                    datetime.strptime(formatted_end_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            
            # Perform semantic search
            results = search_service.search_scene_graphs(
                query=query,
                user_id=user_id,
                limit=limit,
                start_time=formatted_start_time,
                end_time=formatted_end_time,
                camera_name=camera_name
            )
            
            # Format results for agent consumption
            formatted_results = []
            for result in results:
                formatted_result = {
                    "scene_graph_id": result["scene_graph_id"],
                    "content": result["content"],
                    "camera_name": result["camera_name"],
                    "camera_location": result["camera_location"],
                    "created_at": result["created_at"],
                    "similarity_score": result["similarity_score"]
                }
                # Add search type indicator
                if search_type == "simple":
                    formatted_result["search_type"] = "text_matching"
                else:
                    formatted_result["search_type"] = "vector_similarity"
                    
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            raise Exception(f"Semantic search failed: {e}")

# class IrrigationTools(Toolkit):
    
#     def __init__(self):
#         super().__init__(name = "Irrigation Tools")
#         self.api_handler = APIHandler()
        
#         self.register(self.create_irrigation_schedule)
#         self.register(self.show_irrigation_schedule)
#         self.register(self.controllers_by_mission_id)
#         self.register(self.list_area_by_mission_id)
#         self.register(self.weather_forecast)

#     def create_irrigation_schedule(
#         self,
#         area_id: str,
#         controller_id: str,
#         dtstart: str,
#         number_of_events: int = 1,
#         quantity: List[int] = [180, 0, 0],
#         ph_setpoint: float = 5.1,
#         ec_setpoint: float = 1.9,
#         program_id: Optional[str] = None,
#         irrigation_interval: int = 60
#     ) -> List[Dict[str, Any]]:
#         """
#         Create a new irrigation schedule for a given mission and area.
        
#         Args:
#             area_id (str): The ID of the irrigation area.
#             controller_id (str): The ID of the controller to create the program for.
#             dtstart (str): Start datetime in timestamp format "%Y-%m-%d %H:%M:%S" (default: current time).
#             number_of_events (int): Number of irrigation events to create (default: 1). 
#             quantity (List[int]): A list containing exactly 3 elements. The first element represents the irrigation duration in seconds. The second and third elements must always be set to 0.Default: [180, 0, 0] (180 seconds).
#             ph_setpoint (float): pH setpoint value (default: 5.1).
#             ec_setpoint (float): EC setpoint value. (default: 1.9).
#             program_id (Optional[str]): The ID of the irrigation program. If the irrigation events still belong to the same program, you must pass the same program_id in the next tool call. 
#                         However, if the user wants to create an entirely new irrigation schedule, do not pass the program_id. (default: None).
#             irrigation_interval (int): The interval between irrigation events in minutes (default: 60).
            
#         Returns:
#             List[Dict[str, Any]]: List of created irrigation events with their details.
#         """
#         try:
#             # Create controller_id for the irrigation area
#             if program_id is None:
#                 program_id = self.api_handler.create_program(
#                     controller_id=controller_id
#                 ).get("program_id")
            
#             logger.info(f"Created irrigation program with ID: {program_id}")

#             response = self.api_handler.create_irrigation_events(
#                 program_id=program_id,
#                 area_id=area_id,
#                 dtstart=dtstart,
#                 number_of_events=number_of_events,
#                 quantity=quantity,
#                 ph_setpoint=ph_setpoint,
#                 ec_setpoint=ec_setpoint,
#                 irrigation_interval=irrigation_interval
#             )
            
#             return response
#         except Exception as e:
#             raise Exception(f"Failed to create irrigation schedule: {e}")
    
#     def show_irrigation_schedule(
#         self,
#         program_id: str
#     ) -> List[Dict[str, Any]]:
#         """
#         List all irrigation events for a given program ID.
        
#         Args:
#             program_id (str): The ID of the irrigation program.
        
#         Returns:
#             List[Dict[str, Any]]: List of irrigation events with their details.
#         """
#         try:
#             response = self.api_handler.list_programs_irrigation_events(program_id=program_id)
#             return response
#         except Exception as e:
#             raise Exception(f"Failed to list irrigation events: {e}")

#     def controllers_by_mission_id(self, mission_id: str = "5c182350-1866-4c9f-ac68-2eb7e5336d1d") -> List[Dict[str, Any]]:
#         """
#         Get a list of controllers by mission ID.

#         Args:
#             mission_id (str): The ID of the mission. Default is "5c182350-1866-4c9f-ac68-2eb7e5336d1d".

#         Returns:
#             List[Dict[str, Any]]: A list of controllers with their names and IDs.
#         """
#         try:
#             response = self.api_handler.get_controllers_by_mission_id(mission_id=mission_id)
#             return response
#         except Exception as e:
#             raise Exception(f"Failed to get controllers by mission ID: {e}")
    
#     def list_area_by_mission_id(self, mission_id: str = "5c182350-1866-4c9f-ac68-2eb7e5336d1d") -> List[Dict[str, Any]]:
#         """
#         Get a list of areas by mission ID.

#         Args:
#             mission_id (str): The ID of the mission. Default is "5c182350-1866-4c9f-ac68-2eb7e5336d1d".

#         Returns:
#             List[Dict[str, Any]]: A list of areas with their names and IDs.
#         """
#         try:
#             response = self.api_handler.get_list_area_by_mission_api(mission_id=mission_id)
#             return response
#         except Exception as e:
#             raise Exception(f"Failed to get areas by mission ID: {e}")

#     def weather_forecast(
    #     self,
    # ) -> Dict[str, Any]:
    #     """
    #     Get the weather forecast.

    #     Returns:
    #         Dict[str, Any]: weather forecast data.
    #     """
    #     return self.api_handler.get_weather_forecast()