"""
Camera stream capture and SGG integration for Sentri
"""
import asyncio
import base64
import json
import logging
import threading
import time
from datetime import datetime
import pytz
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import cv2
import httpx
from db_setup import get_db_connection
from vector_search import get_vector_search

logger = logging.getLogger(__name__)

# SGG API endpoint
SGG_API_URL = "https://j3wk9tcla3zhgt-8889.proxy.runpod.net/predict"

# Configuration settings
DEFAULT_CAPTURE_INTERVAL = 1  # seconds
MIN_CAPTURE_INTERVAL = 0.5     # minimum 0.5 seconds
MAX_CAPTURE_INTERVAL = 60      # maximum 60 seconds

# Global configuration
camera_configs = {}  # {camera_id: {"capture_interval": seconds}}
global_config = {
    "default_capture_interval": DEFAULT_CAPTURE_INTERVAL,
    "auto_detection": True,
    "save_frames": True,
    "use_realtime_mode": True  # Enable real-time frame capture
}

# Storage for captured frames
FRAMES_DIR = Path("static/recordings/frames")
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

# Active stream capture threads
active_captures: Dict[int, threading.Thread] = {}
stop_flags: Dict[int, threading.Event] = {}

# Real-time frame storage for each camera
latest_frames: Dict[int, tuple] = {}  # {camera_id: (frame, timestamp)}
frame_locks: Dict[int, threading.Lock] = {}  # Thread locks for frame access


def detect_event_from_scene_graph(graph_json: dict) -> Optional[str]:
    """
    Detect events from scene graph JSON
    Returns event name if detected, None otherwise
    
    Expected format:
    {
        "objects": [{"label": "person", "object_id": 0}, {"label": "motorcycle", "object_id": 1}],
        "relationships": [{"subject_id": 1, "object_id": 0, "predicate": "collides_with"}]
    }
    """
    try:
        objects = graph_json.get("objects", [])
        relationships = graph_json.get("relationships", [])
        
        # Create mapping from object_id to label for context
        id_to_label = {obj["object_id"]: obj["label"].lower() for obj in objects}
        
        # Check relationships for specific predicates
        for relationship in relationships:
            subject_id = relationship.get("subject_id")
            object_id = relationship.get("object_id")
            predicate = relationship.get("predicate", "").lower().strip()
            
            # Get object labels for better event description
            subject_label = id_to_label.get(subject_id, f"object_{subject_id}")
            object_label = id_to_label.get(object_id, f"object_{object_id}")
            
            # Rule 1: Collision detection
            if "collides" in predicate and "with" in predicate:
                logger.info(f"Collision detected: {subject_label} collides with {object_label}")
                return "collision_detected"
            
            # Rule 2: Falling off detection  
            if "falling" in predicate and "off" in predicate:
                logger.info(f"Falling detected: {subject_label} falling off {object_label}")
                return "falling_off_detected"
            
            # Rule 3: Lying on detection
            if "lying" in predicate and "on" in predicate:
                logger.info(f"Lying detected: {subject_label} lying on {object_label}")
                return "lying_on_detected"
        
        # Also check for single objects that might indicate dangerous situations
        for obj in objects:
            label = obj["label"].lower()
            confidence = obj.get("confidence", 0)
            
            # High confidence fire detection
            if "fire" in label and confidence > 0.8:
                logger.info(f"Fire detected with confidence {confidence}")
                return "fire_detected"
            
            # High confidence weapon detection
            if any(weapon in label for weapon in ["gun", "knife", "weapon"]) and confidence > 0.8:
                logger.info(f"Weapon detected: {label} with confidence {confidence}")
                return "weapon_detected"
        
        return None
        
    except Exception as e:
        logger.error(f"Error detecting event from scene graph: {e}")
        return None


def ingest_scene_graph(
    camera_id: int,
    media_type: str,
    file_path: str,
    timestamp: datetime,
    graph_json: dict,
    model_version: Optional[str] = None,
    confidence: Optional[float] = None
) -> bool:
    """
    Ingest scene graph data and detect events
    
    Returns True if successful
    """
    # Ensure timezone consistency - convert to Vietnam timezone
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    if timestamp.tzinfo is None:
        # If naive datetime, assume it's already in Vietnam time
        timestamp = vietnam_tz.localize(timestamp)
    else:
        # Convert to Vietnam timezone
        timestamp = timestamp.astimezone(vietnam_tz)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get Vietnam time for created_at
        vietnam_now = datetime.now(vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert media record with timezone-aware timestamp
        cursor.execute("""
            INSERT INTO media (camera_id, type, file_path, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (camera_id, media_type, file_path, timestamp.strftime('%Y-%m-%d %H:%M:%S'), vietnam_now))
        
        media_id = cursor.lastrowid
        
        # Insert scene graph with Vietnam timezone
        cursor.execute("""
            INSERT INTO scene_graphs (media_id, graph_json, model_version, created_at)
            VALUES (?, ?, ?, ?)
        """, (media_id, json.dumps(graph_json), model_version, vietnam_now))
        
        scene_graph_id = cursor.lastrowid
        
        # Index in vector database for semantic search
        try:
            # Get camera info for metadata
            cursor.execute("SELECT name, location, user_id FROM cameras WHERE id = ?", (camera_id,))
            camera_row = cursor.fetchone()
            
            if camera_row:
                camera_name, camera_location, user_id = camera_row
                vector_search = get_vector_search()
                vector_metadata = {
                    "camera_name": camera_name or "",
                    "camera_location": camera_location or "",
                    "created_at": vietnam_now,
                    "timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    "user_id": user_id
                }
                
                vector_search.index_scene_graph(
                    scene_graph_id=scene_graph_id,
                    graph_json=graph_json,
                    metadata=vector_metadata
                )
                logger.debug(f"Indexed scene graph {scene_graph_id} in vector database")
        except Exception as e:
            logger.warning(f"Failed to index scene graph {scene_graph_id} in vector DB: {e}")
        
        # Detect events
        event_name = detect_event_from_scene_graph(graph_json)
        
        if event_name:
            # Get event info
            cursor.execute("SELECT id, description FROM events WHERE name = ?", (event_name,))
            event_row = cursor.fetchone()
            
            if event_row:
                event_id = event_row["id"]
                event_description = event_row["description"]
                
                # Insert event log with Vietnam timezone
                cursor.execute("""
                    INSERT INTO event_logs (event_id, camera_id, scene_graph_id, confidence, occurred_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (event_id, camera_id, scene_graph_id, confidence, timestamp.strftime('%Y-%m-%d %H:%M:%S'), vietnam_now))
                
                event_log_id = cursor.lastrowid
                
                # Get camera owner to create notification
                cursor.execute("SELECT user_id, name FROM cameras WHERE id = ?", (camera_id,))
                camera_row = cursor.fetchone()
                
                if camera_row:
                    user_id = camera_row["user_id"]
                    camera_name = camera_row["name"]
                    
                    # Create notification
                    notification_title = f"⚠️ {event_name.replace('_', ' ').title()}"
                    notification_message = f"{event_description} at {camera_name} on {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    cursor.execute("""
                        INSERT INTO notifications (user_id, event_log_id, title, message, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, event_log_id, notification_title, notification_message, vietnam_now))
                    
                    logger.info(f"Event detected: {event_name} on camera {camera_id}")
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to ingest scene graph: {e}")
        return False
    finally:
        conn.close()


async def send_frame_to_sgg(frame_bytes: bytes) -> Optional[dict]:
    """
    Send frame to SGG API and get scene graph response
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("frame.jpg", frame_bytes, "image/jpeg")}
            response = await client.post(SGG_API_URL, files=files)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"SGG API returned status {response.status_code}: {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to send frame to SGG API: {e}")
        return None


def capture_stream_worker(camera_id: int, stream_url: str, capture_interval: int = 2):
    """
    Background worker to capture frames from camera stream
    
    Args:
        camera_id: Camera database ID
        stream_url: Camera stream URL
        capture_interval: Seconds between captures (default 2)
    """
    logger.info(f"Starting stream capture for camera {camera_id}: {stream_url}")
    
    stop_flag = stop_flags[camera_id]
    retry_count = 0
    max_retries = 5
    
    while not stop_flag.is_set():
        try:
            # Open video stream
            cap = cv2.VideoCapture(stream_url)
            
            if not cap.isOpened():
                logger.error(f"Failed to open stream for camera {camera_id}: {stream_url}")
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for camera {camera_id}, stopping")
                    break
                time.sleep(5)
                continue
            
            # Configure VideoCapture for real-time streaming
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer to get latest frame
            cap.set(cv2.CAP_PROP_FPS, 30)  # Try to set reasonable FPS
            
            # For IP cameras, try to reduce latency
            if "http" in stream_url.lower():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            retry_count = 0  # Reset on successful connection
            
            logger.info(f"Camera {camera_id} capture started with {capture_interval}s interval")
            
            while not stop_flag.is_set():
                start_time = time.time()
                
                # Flush buffer by reading multiple frames to get the latest one
                frame = None
                for _ in range(5):  # Read up to 5 frames to get the latest
                    ret, temp_frame = cap.read()
                    if ret:
                        frame = temp_frame
                    else:
                        break
                
                if frame is None:
                    logger.warning(f"Failed to read frame from camera {camera_id}")
                    break
                
                try:
                    # Only process if auto_detection is enabled
                    if global_config.get("auto_detection", True):
                        timestamp = datetime.now()
                        
                        # Save frame to disk if enabled
                        if global_config.get("save_frames", True):
                            filename = f"cam{camera_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                            file_path = FRAMES_DIR / filename
                            cv2.imwrite(str(file_path), frame)
                        else:
                            filename = f"cam{camera_id}_temp.jpg"  # Temporary filename
                        
                        # Encode frame as JPEG for API
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        frame_bytes = buffer.tobytes()
                        
                        # Send to SGG API (using asyncio in sync context)
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        scene_graph = loop.run_until_complete(send_frame_to_sgg(frame_bytes))
                        loop.close()
                        
                        if scene_graph:
                            # Ingest scene graph
                            file_path_str = f"static/recordings/frames/{filename}" if global_config.get("save_frames", True) else ""
                            ingest_scene_graph(
                                camera_id=camera_id,
                                media_type="frame",
                                file_path=file_path_str,
                                timestamp=timestamp,
                                graph_json=scene_graph,
                                model_version=scene_graph.get("model_version"),
                                confidence=scene_graph.get("confidence")
                            )
                            logger.debug(f"Processed frame for camera {camera_id} at {timestamp}")
                    
                except Exception as e:
                    logger.error(f"Error processing frame from camera {camera_id}: {e}")
                
                # Calculate remaining time to wait
                processing_time = time.time() - start_time
                remaining_time = max(0, capture_interval - processing_time)
                
                if remaining_time > 0:
                    stop_flag.wait(timeout=remaining_time)
                else:
                    logger.debug(f"Camera {camera_id}: Processing took {processing_time:.2f}s, no wait needed")
            
            cap.release()
            
        except Exception as e:
            logger.error(f"Stream capture error for camera {camera_id}: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"Max retries reached for camera {camera_id}, stopping")
                break
            time.sleep(5)
    
    logger.info(f"Stopped stream capture for camera {camera_id}")


def continuous_frame_reader(camera_id: int, stream_url: str):
    """
    Continuously read frames from camera and store latest frame in memory
    This runs in a separate thread to ensure we always have the latest frame
    """
    logger.info(f"Starting continuous frame reader for camera {camera_id}")
    
    stop_flag = stop_flags[camera_id]
    retry_count = 0
    max_retries = 3
    
    while not stop_flag.is_set():
        try:
            cap = cv2.VideoCapture(stream_url)
            
            if not cap.isOpened():
                logger.error(f"Failed to open stream for camera {camera_id}: {stream_url}")
                retry_count += 1
                if retry_count >= max_retries:
                    break
                time.sleep(5)
                continue
            
            # Configure for real-time streaming
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            retry_count = 0
            
            while not stop_flag.is_set():
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning(f"Frame read failed for camera {camera_id}")
                    break
                
                # Store latest frame with timestamp
                timestamp = datetime.now()
                
                with frame_locks[camera_id]:
                    latest_frames[camera_id] = (frame.copy(), timestamp)
                
                time.sleep(0.033)  # ~30fps capture rate
            
            cap.release()
            
        except Exception as e:
            logger.error(f"Continuous reader error for camera {camera_id}: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                break
            time.sleep(5)
    
    logger.info(f"Stopped continuous frame reader for camera {camera_id}")


def realtime_capture_worker(camera_id: int, capture_interval: float):
    """
    Process latest available frames at specified intervals
    """
    logger.info(f"Starting real-time capture worker for camera {camera_id}")
    
    stop_flag = stop_flags[camera_id]
    
    while not stop_flag.is_set():
        try:
            # Get latest frame
            frame = None
            timestamp = None
            
            with frame_locks[camera_id]:
                if camera_id in latest_frames:
                    frame, timestamp = latest_frames[camera_id]
            
            if frame is not None and global_config.get("auto_detection", True):
                try:
                    # Save frame to disk if enabled
                    if global_config.get("save_frames", True):
                        filename = f"cam{camera_id}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]}.jpg"
                        file_path = FRAMES_DIR / filename
                        cv2.imwrite(str(file_path), frame)
                    else:
                        filename = f"cam{camera_id}_temp.jpg"
                    
                    # Encode frame as JPEG for API
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    frame_bytes = buffer.tobytes()
                    
                    # Send to SGG API
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    scene_graph = loop.run_until_complete(send_frame_to_sgg(frame_bytes))
                    loop.close()
                    
                    if scene_graph:
                        file_path_str = f"static/recordings/frames/{filename}" if global_config.get("save_frames", True) else ""
                        ingest_scene_graph(
                            camera_id=camera_id,
                            media_type="frame",
                            file_path=file_path_str,
                            timestamp=timestamp,
                            graph_json=scene_graph,
                            model_version=scene_graph.get("model_version"),
                            confidence=scene_graph.get("confidence")
                        )
                        logger.debug(f"Processed latest frame for camera {camera_id}")
                
                except Exception as e:
                    logger.error(f"Error processing latest frame from camera {camera_id}: {e}")
        
        except Exception as e:
            logger.error(f"Real-time worker error for camera {camera_id}: {e}")
        
        # Wait for next processing cycle
        stop_flag.wait(timeout=capture_interval)
    
    logger.info(f"Stopped real-time capture worker for camera {camera_id}")


def start_camera_capture(camera_id: int, stream_url: str, capture_interval: int = None, use_realtime: bool = True):
    """
    Start capturing frames from a camera stream
    
    Args:
        camera_id: Camera ID
        stream_url: Camera stream URL  
        capture_interval: Capture interval in seconds
        use_realtime: If True, use continuous frame reading + periodic processing
                     If False, use traditional sequential processing
    """
    if camera_id in active_captures and active_captures[camera_id].is_alive():
        logger.warning(f"Capture already running for camera {camera_id}")
        return False
    
    # Use custom interval if provided, otherwise use camera config or global default
    if capture_interval is None:
        capture_interval = camera_configs.get(camera_id, {}).get(
            "capture_interval", global_config["default_capture_interval"]
        )
    
    # Validate interval
    capture_interval = max(MIN_CAPTURE_INTERVAL, min(MAX_CAPTURE_INTERVAL, capture_interval))
    
    # Store config for this camera
    if camera_id not in camera_configs:
        camera_configs[camera_id] = {}
    camera_configs[camera_id]["capture_interval"] = capture_interval
    
    # Create stop flag and frame lock
    stop_flags[camera_id] = threading.Event()
    frame_locks[camera_id] = threading.Lock()
    
    if use_realtime:
        # Start continuous frame reader thread
        reader_thread = threading.Thread(
            target=continuous_frame_reader,
            args=(camera_id, stream_url),
            daemon=True,
            name=f"FrameReader-{camera_id}"
        )
        reader_thread.start()
        
        # Start processing worker thread
        worker_thread = threading.Thread(
            target=realtime_capture_worker,
            args=(camera_id, capture_interval),
            daemon=True,
            name=f"CaptureWorker-{camera_id}"
        )
        worker_thread.start()
        
        # Store both threads (we'll use worker_thread as main reference)
        active_captures[camera_id] = worker_thread
        active_captures[f"{camera_id}_reader"] = reader_thread
        
        logger.info(f"Started real-time capture for camera {camera_id} with {capture_interval}s interval")
    else:
        # Use traditional sequential processing
        thread = threading.Thread(
            target=capture_stream_worker,
            args=(camera_id, stream_url, capture_interval),
            daemon=True,
            name=f"StreamCapture-{camera_id}"
        )
        thread.start()
        
        active_captures[camera_id] = thread
        logger.info(f"Started sequential capture for camera {camera_id} with {capture_interval}s interval")
    
    return True


def stop_camera_capture(camera_id: int):
    """
    Stop capturing frames from a camera stream
    """
    if camera_id not in stop_flags:
        return False
    
    # Set stop flag
    stop_flags[camera_id].set()
    
    # Wait for main thread to finish
    if camera_id in active_captures:
        thread = active_captures[camera_id]
        thread.join(timeout=5)
        del active_captures[camera_id]
    
    # Stop frame reader thread if exists (real-time mode)
    reader_key = f"{camera_id}_reader"
    if reader_key in active_captures:
        reader_thread = active_captures[reader_key]
        reader_thread.join(timeout=5)
        del active_captures[reader_key]
    
    # Clean up
    if camera_id in latest_frames:
        del latest_frames[camera_id]
    if camera_id in frame_locks:
        del frame_locks[camera_id]
    del stop_flags[camera_id]
    
    logger.info(f"Stopped capture for camera {camera_id}")
    return True


def start_all_active_cameras():
    """
    Start capture for all active cameras in database
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, stream_url
        FROM cameras
        WHERE is_active = 1
    """)
    
    cameras = cursor.fetchall()
    conn.close()
    
    use_realtime = global_config.get("use_realtime_mode", True)
    
    for camera in cameras:
        try:
            start_camera_capture(camera["id"], camera["stream_url"], use_realtime=use_realtime)
        except Exception as e:
            logger.error(f"Failed to start capture for camera {camera['id']}: {e}")
    
    mode = "real-time" if use_realtime else "sequential"
    logger.info(f"Started {mode} capture for {len(cameras)} active cameras")


def get_camera_config(camera_id: int) -> dict:
    """
    Get camera configuration
    """
    return camera_configs.get(camera_id, {
        "capture_interval": global_config["default_capture_interval"]
    })


def update_camera_config(camera_id: int, config: dict) -> bool:
    """
    Update camera configuration
    Returns True if camera needs to be restarted
    """
    if camera_id not in camera_configs:
        camera_configs[camera_id] = {}
    
    old_interval = camera_configs[camera_id].get("capture_interval")
    
    # Update config
    if "capture_interval" in config:
        interval = max(MIN_CAPTURE_INTERVAL, min(MAX_CAPTURE_INTERVAL, config["capture_interval"]))
        camera_configs[camera_id]["capture_interval"] = interval
    
    # Check if restart needed (interval changed)
    new_interval = camera_configs[camera_id].get("capture_interval")
    return old_interval != new_interval and camera_id in active_captures


def get_global_config() -> dict:
    """
    Get global configuration
    """
    return global_config.copy()


def update_global_config(config: dict):
    """
    Update global configuration
    """
    if "default_capture_interval" in config:
        interval = max(MIN_CAPTURE_INTERVAL, min(MAX_CAPTURE_INTERVAL, config["default_capture_interval"]))
        global_config["default_capture_interval"] = interval
    
    if "auto_detection" in config:
        global_config["auto_detection"] = bool(config["auto_detection"])
    
    if "save_frames" in config:
        global_config["save_frames"] = bool(config["save_frames"])


def stop_all_cameras():
    """
    Stop all active camera captures
    """
    camera_ids = list(active_captures.keys())
    for camera_id in camera_ids:
        stop_camera_capture(camera_id)
    
    logger.info("Stopped all camera captures")
