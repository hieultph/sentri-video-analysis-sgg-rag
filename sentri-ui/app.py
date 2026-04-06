import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import pytz

import cv2
import httpx
from agno.os import AgentOS
from agents.assistant import get_assistant_agent
from fastapi import File, FastAPI, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import Stream Chat integration
# from stream_integration import stream_chat_manager
from websocket_handler import handle_websocket_connection

# Import mobile API functions (WEBHOOK VERSION)
from mobile_api_webhook import (
    MobileChannelRequest,
    MobileChatMessage,
    MobileStreamMessage,
    create_mobile_channel_webhook_api,
    send_mobile_message_webhook_api,
    send_mobile_stream_message_webhook_api,
    get_user_channels_webhook_api,
    close_mobile_channel_webhook_api,
    get_channel_info_webhook_api
)

# Import Sentri system components
from db_setup import init_database, get_db_connection
from auth_helpers import (
    hash_password, verify_password, create_session, 
    get_user_from_token, delete_session, require_auth, get_user_info
)
from camera_capture import (
    start_camera_capture, stop_camera_capture, 
    start_all_active_cameras, stop_all_cameras, ingest_scene_graph,
    get_camera_config, update_camera_config, 
    get_global_config, update_global_config
)

# Setup logging - chỉ hiển thị WARNING và ERROR
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Giảm log từ các thư viện khác
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

class Body(BaseModel):
    message: str

class StreamChatRequest(BaseModel):
    channel_id: str
    channel_type: str = "messaging"

class StreamWebhook(BaseModel):
    type: str
    channel_id: Optional[str] = None
    message: Optional[Dict] = None
    user: Optional[Dict] = None

# Sentri system models
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class AddCameraRequest(BaseModel):
    name: str
    location: Optional[str] = None
    stream_url: str

class IngestSceneGraphRequest(BaseModel):
    camera_id: int
    media_type: str = "frame"
    file_path: Optional[str] = None
    timestamp: str  # ISO format
    graph_json: dict
    model_version: Optional[str] = None
    confidence: Optional[float] = None

class AgentChatRequest(BaseModel):
    message: str
    camera_id: Optional[int] = None
    search_objects: Optional[List[str]] = None  # Specific objects to search for
    search_relationships: Optional[List[str]] = None  # Specific relationships to search for
    include_summary: Optional[bool] = False  # Whether to include scene graph summary
    days_back: Optional[int] = 7  # How many days back to search
    filters: Optional[dict] = None

class CameraConfigRequest(BaseModel):
    capture_interval: Optional[float] = None
    auto_detection: Optional[bool] = None
    save_frames: Optional[bool] = None

class GlobalConfigRequest(BaseModel):
    default_capture_interval: Optional[float] = None
    auto_detection: Optional[bool] = None
    save_frames: Optional[bool] = None

# Store active agents per session
active_agents: Dict[str, any] = {}

# Global variables for shared webcam access
webcam_lock = threading.Lock()
latest_webcam_frame = None
webcam_active = False
webcam_capture_thread = None

def get_or_create_agent(user_id: str) -> any:
    """Get existing agent or create new one for user"""
    if user_id not in active_agents:
        # Create agent with proper user_id (convert string back to int for session)
        try:
            numeric_user_id = int(user_id)
        except ValueError:
            numeric_user_id = 1  # fallback
            
        active_agents[user_id] = get_assistant_agent(numeric_user_id)
    return active_agents[user_id]

def capture_webcam_frames():
    """Continuously capture frames from webcam in a separate thread"""
    global latest_webcam_frame, webcam_active
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("ERROR: Cannot open webcam")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    webcam_active = True
    
    try:
        while webcam_active:
            ret, frame = cap.read()
            if not ret:
                logger.error("ERROR: Cannot read frame from webcam")
                time.sleep(0.1)
                continue
            
            # Encode frame to JPEG
            _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            # Update the latest frame (thread-safe)
            with webcam_lock:
                latest_webcam_frame = jpg.tobytes()
            
            time.sleep(0.033)  # ~30 FPS
    except Exception as e:
        logger.error(f"Webcam capture error: {e}")
    finally:
        cap.release()

def start_webcam_stream():
    """Start the webcam capture thread"""
    global webcam_capture_thread, webcam_active
    
    if webcam_capture_thread is not None and webcam_capture_thread.is_alive():
        return
    
    webcam_active = True
    webcam_capture_thread = threading.Thread(target=capture_webcam_frames, daemon=True)
    webcam_capture_thread.start()

def stop_webcam_stream():
    """Stop the webcam capture thread"""
    global webcam_active
    webcam_active = False

# Create default agent for AgentOS
a = get_assistant_agent()

# Create custom FastAPI app first
app = FastAPI(
    title="Mimosatek Agent API",
    description="A basic agent that can answer questions and help with tasks.",
    version="1.0.0",
    openapi_url="/api/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
if cors_origins_env:
    allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = ["*"]

allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower() == "true"
if "*" in allowed_origins and allow_credentials_env:
    allow_credentials = False
else:
    allow_credentials = allow_credentials_env

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/tools", StaticFiles(directory="tools"), name="tools")
app.mount("/static", StaticFiles(directory="static"), name="static")

RECORDINGS_DIR = Path("static/recordings")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# STT_ENDPOINT = os.getenv(
#     "STT_ENDPOINT",
#     "https://privacy-mat-escape-doug.trycloudflare.com/transcribe",
# )

STT_ENDPOINT = os.getenv(
    "STT_ENDPOINT",
    "http://10.5.10.165:8001/transcribe",
)

# Custom OpenAPI schema function
# def custom_openapi():
#     if app.openapi_schema:
#         return app.openapi_schema
#     openapi_schema = get_openapi(
#         title="Mimosatek Agent API",
#         version="1.0.0",
#         description="A basic agent that can answer questions and help with tasks.",
#         routes=app.routes,
#     )
#     app.openapi_schema = openapi_schema
#     return app.openapi_schema

# # Override OpenAPI schema
# app.openapi = custom_openapi

# app.title = "Mimosatek Agent API"
# app.description = "A basic agent that can answer questions and help with tasks."
# app.version = "1.0.0"
# app.openapi_url = "/api/openapi.json"
# app.docs_url = "/docs"
# app.redoc_url = "/redoc"

# Thêm health check endpoint cho Docker
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Initialize Sentri database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and start camera captures on startup"""
    try:
        init_database()
        start_all_active_cameras()
        # start_webcam_stream()
        print("\n✓ Server started successfully")
        # print("✓ Webcam stream: http://localhost:7777/webcam/stream\n")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop all camera captures on shutdown"""
    try:
        stop_all_cameras()
        # stop_webcam_stream()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# ============================================
# SENTRI AUTH ENDPOINTS
# ============================================

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """Register a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Get Vietnam time for created_at
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        vietnam_now = datetime.now(vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert user
        cursor.execute("""
            INSERT INTO users (username, email, created_at)
            VALUES (?, ?, ?)
        """, (request.username, request.email, vietnam_now))
        
        user_id = cursor.lastrowid
        
        # Hash and store password
        password_hash = hash_password(request.password)
        cursor.execute("""
            INSERT INTO auth_users (user_id, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (user_id, password_hash, vietnam_now))
        
        conn.commit()
        
        # Get user info
        user_info = get_user_info(user_id)
        
        return {
            "success": True,
            "user": user_info,
            "message": "Registration successful"
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        conn.close()

@app.post("/auth/login")
async def login(request: LoginRequest):
    """Login user and return session token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user and password hash
        cursor.execute("""
            SELECT u.id, u.username, u.email, a.password_hash
            FROM users u
            JOIN auth_users a ON u.id = a.user_id
            WHERE u.username = ?
        """, (request.username,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Verify password
        if not verify_password(request.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Create session
        user_id = row["id"]
        token = create_session(user_id)
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"]
            }
        }
        
    finally:
        conn.close()

@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """Logout user"""
    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        delete_session(token)
    
    return {"success": True, "message": "Logged out successfully"}

@app.get("/auth/me")
async def get_current_user(user_id: int = Depends(require_auth)):
    """Get current user info"""
    user_info = get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user_info

# ============================================
# SENTRI CAMERA ENDPOINTS
# ============================================

@app.post("/camera/add")
async def add_camera(request: AddCameraRequest, user_id: int = Depends(require_auth)):
    """Add a new camera for the current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get Vietnam time for created_at
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        vietnam_now = datetime.now(vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            INSERT INTO cameras (user_id, name, location, stream_url, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, request.name, request.location, request.stream_url, vietnam_now))
        
        camera_id = cursor.lastrowid
        conn.commit()
        
        # Start capture for this camera
        start_camera_capture(camera_id, request.stream_url)
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Camera added successfully"
        }
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to add camera")
    finally:
        conn.close()

@app.get("/camera/list")
async def list_cameras(user_id: int = Depends(require_auth)):
    """List all cameras for the current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, location, stream_url, is_active, created_at
        FROM cameras
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    cameras = []
    for row in cursor.fetchall():
        cameras.append({
            "id": row["id"],
            "name": row["name"],
            "location": row["location"],
            "stream_url": row["stream_url"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"]
        })
    
    conn.close()
    return {"cameras": cameras}

@app.delete("/camera/{camera_id}")
async def delete_camera(camera_id: int, user_id: int = Depends(require_auth)):
    """Delete a camera for the current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if camera belongs to user
        cursor.execute("""
            SELECT id, name FROM cameras 
            WHERE id = ? AND user_id = ?
        """, (camera_id, user_id))
        
        camera = cursor.fetchone()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        # Stop camera capture if active
        try:
            stop_camera_capture(camera_id)
        except:
            pass  # Continue even if stop fails
        
        # Delete camera from database
        cursor.execute("""
            DELETE FROM cameras 
            WHERE id = ? AND user_id = ?
        """, (camera_id, user_id))
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Camera '{camera['name']}' deleted successfully"
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete camera")
    finally:
        conn.close()

@app.get("/camera/{camera_id}/config")
async def get_camera_config_endpoint(camera_id: int, user_id: int = Depends(require_auth)):
    """Get camera configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify camera belongs to user
        cursor.execute("""
            SELECT id FROM cameras 
            WHERE id = ? AND user_id = ?
        """, (camera_id, user_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Camera not found")
        
        config = get_camera_config(camera_id)
        return {"config": config}
        
    finally:
        conn.close()

@app.post("/camera/{camera_id}/config")
async def update_camera_config_endpoint(camera_id: int, request: CameraConfigRequest, user_id: int = Depends(require_auth)):
    """Update camera configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify camera belongs to user
        cursor.execute("""
            SELECT id, stream_url FROM cameras 
            WHERE id = ? AND user_id = ?
        """, (camera_id, user_id))
        
        camera_row = cursor.fetchone()
        if not camera_row:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        # Update configuration
        config_dict = {}
        if request.capture_interval is not None:
            config_dict["capture_interval"] = request.capture_interval
        if request.auto_detection is not None:
            config_dict["auto_detection"] = request.auto_detection
        if request.save_frames is not None:
            config_dict["save_frames"] = request.save_frames
        
        needs_restart = update_camera_config(camera_id, config_dict)
        
        # Restart camera if interval changed
        if needs_restart:
            try:
                stop_camera_capture(camera_id)
                start_camera_capture(camera_id, camera_row["stream_url"])
            except Exception as e:
                logger.warning(f"Failed to restart camera {camera_id}: {e}")
        
        updated_config = get_camera_config(camera_id)
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": updated_config,
            "restarted": needs_restart
        }
        
    finally:
        conn.close()

@app.delete("/camera/{camera_id}/history")
async def clear_camera_history(camera_id: int, user_id: int = Depends(require_auth)):
    """Clear all history data for a camera (media, scene_graphs, event_logs, notifications)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify camera belongs to user
        cursor.execute("""
            SELECT id, name FROM cameras 
            WHERE id = ? AND user_id = ?
        """, (camera_id, user_id))
        
        camera = cursor.fetchone()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Get counts before deletion for response
        cursor.execute("SELECT COUNT(*) FROM media WHERE camera_id = ?", (camera_id,))
        media_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM event_logs el
            JOIN cameras c ON el.camera_id = c.id
            WHERE c.id = ? AND c.user_id = ?
        """, (camera_id, user_id))
        events_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM notifications n
            JOIN event_logs el ON n.event_log_id = el.id
            JOIN cameras c ON el.camera_id = c.id
            WHERE c.id = ? AND c.user_id = ?
        """, (camera_id, user_id))
        notifications_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM scene_graphs sg
            JOIN media m ON sg.media_id = m.id
            WHERE m.camera_id = ?
        """, (camera_id,))
        scene_graphs_count = cursor.fetchone()[0]
        
        # Delete in correct order due to foreign key constraints
        
        # 1. Delete notifications (references event_logs)
        cursor.execute("""
            DELETE FROM notifications
            WHERE event_log_id IN (
                SELECT el.id FROM event_logs el
                JOIN cameras c ON el.camera_id = c.id
                WHERE c.id = ? AND c.user_id = ?
            )
        """, (camera_id, user_id))
        
        # 2. Delete event_logs (references cameras, scene_graphs)
        cursor.execute("""
            DELETE FROM event_logs
            WHERE camera_id = ? AND camera_id IN (
                SELECT id FROM cameras WHERE user_id = ?
            )
        """, (camera_id, user_id))
        
        # 3. Delete scene_graphs (references media)
        cursor.execute("""
            DELETE FROM scene_graphs
            WHERE media_id IN (
                SELECT id FROM media WHERE camera_id = ?
            )
        """, (camera_id,))
        
        # 4. Delete media (references cameras)
        cursor.execute("DELETE FROM media WHERE camera_id = ?", (camera_id,))
        
        # Commit transaction
        cursor.execute("COMMIT")
        
        return {
            "success": True,
            "message": f"All history cleared for camera '{camera['name']}'",
            "deleted": {
                "media_files": media_count,
                "scene_graphs": scene_graphs_count, 
                "event_logs": events_count,
                "notifications": notifications_count
            }
        }
        
    except HTTPException:
        cursor.execute("ROLLBACK")
        raise
    except Exception as e:
        cursor.execute("ROLLBACK")
        logger.error(f"Failed to clear camera history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear camera history")
    finally:
        conn.close()

@app.get("/config/global")
async def get_global_config_endpoint(user_id: int = Depends(require_auth)):
    """Get global configuration"""
    config = get_global_config()
    return {"config": config}

@app.post("/config/global")
async def update_global_config_endpoint(request: GlobalConfigRequest, user_id: int = Depends(require_auth)):
    """Update global configuration"""
    config_dict = {}
    if request.default_capture_interval is not None:
        config_dict["default_capture_interval"] = request.default_capture_interval
    if request.auto_detection is not None:
        config_dict["auto_detection"] = request.auto_detection
    if request.save_frames is not None:
        config_dict["save_frames"] = request.save_frames
    
    update_global_config(config_dict)
    
    updated_config = get_global_config()
    return {
        "success": True,
        "message": "Global configuration updated successfully",
        "config": updated_config
    }

@app.get("/webcam/stream")
async def webcam_stream():
    """Stream webcam video - multiple viewers supported"""
    if not webcam_active:
        return Response(content=b"ERROR: Webcam not available", status_code=503)
    
    async def generate():
        """Generate MJPEG stream"""
        try:
            while webcam_active:
                # Get the latest frame (thread-safe)
                with webcam_lock:
                    if latest_webcam_frame is None:
                        await asyncio.sleep(0.033)
                        continue
                    frame_data = latest_webcam_frame
                
                # Send frame to client
                yield (b"--jpgboundary\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame_data)).encode() + b"\r\n\r\n" +
                       frame_data + b"\r\n")
                
                await asyncio.sleep(0.033)  # ~30 FPS
        except Exception:
            pass
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=--jpgboundary",
        headers={"Access-Control-Allow-Origin": "*"}
    )

# ============================================
# SENTRI INGESTION ENDPOINT
# ============================================

@app.post("/ingest/scene-graph")
async def ingest_scene_graph_endpoint(request: IngestSceneGraphRequest, user_id: int = Depends(require_auth)):
    """Ingest scene graph data (internal or external use)"""
    
    # Verify camera belongs to user
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM cameras WHERE id = ?", (request.camera_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Camera not found or access denied")
    
    # Parse timestamp and ensure Vietnam timezone
    try:
        timestamp = datetime.fromisoformat(request.timestamp)
        # Ensure timezone consistency 
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        if timestamp.tzinfo is None:
            # If naive datetime, assume it's already in Vietnam time
            timestamp = vietnam_tz.localize(timestamp)
        else:
            # Convert to Vietnam timezone for consistency
            timestamp = timestamp.astimezone(vietnam_tz)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {e}")
    
    # Ingest
    success = ingest_scene_graph(
        camera_id=request.camera_id,
        media_type=request.media_type,
        file_path=request.file_path or "",
        timestamp=timestamp,
        graph_json=request.graph_json,
        model_version=request.model_version,
        confidence=request.confidence
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to ingest scene graph")
    
    return {"success": True, "message": "Scene graph ingested successfully"}

# ============================================
# SENTRI EVENTS & NOTIFICATIONS ENDPOINTS
# ============================================

@app.get("/events")
async def get_events(
    camera_id: Optional[int] = None,
    event_name: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user_id: int = Depends(require_auth)
):
    """Get event logs with filters"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query
    query = """
        SELECT 
            el.id, el.occurred_at, el.confidence,
            e.name as event_name, e.severity, e.description,
            c.id as camera_id, c.name as camera_name,
            sg.graph_json, m.file_path
        FROM event_logs el
        JOIN events e ON el.event_id = e.id
        JOIN cameras c ON el.camera_id = c.id
        JOIN scene_graphs sg ON el.scene_graph_id = sg.id
        LEFT JOIN media m ON sg.media_id = m.id
        WHERE c.user_id = ?
    """
    params = [user_id]
    
    if camera_id:
        query += " AND c.id = ?"
        params.append(camera_id)
    
    if event_name:
        query += " AND e.name = ?"
        params.append(event_name)
    
    if from_date:
        query += " AND el.occurred_at >= ?"
        params.append(from_date)
    
    if to_date:
        query += " AND el.occurred_at <= ?"
        params.append(to_date)
    
    query += " ORDER BY el.occurred_at DESC LIMIT 100"
    
    cursor.execute(query, params)
    
    events = []
    for row in cursor.fetchall():
        events.append({
            "id": row["id"],
            "occurred_at": row["occurred_at"],
            "confidence": row["confidence"],
            "event_name": row["event_name"],
            "severity": row["severity"],
            "description": row["description"],
            "camera_id": row["camera_id"],
            "camera_name": row["camera_name"],
            "graph_json": json.loads(row["graph_json"]),
            "file_path": row["file_path"]
        })
    
    conn.close()
    return {"events": events}

@app.get("/notifications")
async def get_notifications(user_id: int = Depends(require_auth)):
    """Get notifications for current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            n.id, n.title, n.message, n.is_read, n.created_at,
            el.occurred_at, el.confidence,
            e.name as event_name,
            c.name as camera_name
        FROM notifications n
        JOIN event_logs el ON n.event_log_id = el.id
        JOIN events e ON el.event_id = e.id
        JOIN cameras c ON el.camera_id = c.id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
        LIMIT 50
    """, (user_id,))
    
    notifications = []
    for row in cursor.fetchall():
        notifications.append({
            "id": row["id"],
            "title": row["title"],
            "message": row["message"],
            "is_read": bool(row["is_read"]),
            "created_at": row["created_at"],
            "event_name": row["event_name"],
            "camera_name": row["camera_name"],
            "occurred_at": row["occurred_at"],
            "confidence": row["confidence"]
        })
    
    conn.close()
    return {"notifications": notifications}

@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, user_id: int = Depends(require_auth)):
    """Mark a notification as read"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify notification belongs to user
        cursor.execute("SELECT user_id FROM notifications WHERE id = ?", (notification_id,))
        row = cursor.fetchone()
        
        if not row or row["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Mark as read
        cursor.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE id = ?
        """, (notification_id,))
        
        conn.commit()
        return {"success": True, "message": "Notification marked as read"}
        
    finally:
        conn.close()

# ============================================
# SENTRI SCENE GRAPH ANALYSIS HELPERS
# ============================================

def search_scene_graphs_by_objects(user_id: int, object_names: list, camera_id: Optional[int] = None, limit: int = 20):
    """Search scene graphs containing specific objects"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query to search for objects in graph_json
    query = """
        SELECT 
            sg.id, sg.graph_json, sg.created_at, sg.model_version,
            m.file_path, m.timestamp as media_timestamp,
            c.name as camera_name, c.location
        FROM scene_graphs sg
        JOIN media m ON sg.media_id = m.id  
        JOIN cameras c ON m.camera_id = c.id
        WHERE c.user_id = ?
    """
    params = [user_id]
    
    if camera_id:
        query += " AND c.id = ?"
        params.append(camera_id)
    
    # Add object search conditions
    for obj_name in object_names:
        query += " AND LOWER(sg.graph_json) LIKE LOWER(?)"
        params.append(f'%"{obj_name}"%')
    
    query += " ORDER BY sg.created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    results = []
    
    for row in cursor.fetchall():
        try:
            graph_data = json.loads(row["graph_json"])
            # Extract object information
            objects_found = []
            if "objects" in graph_data:
                for obj in graph_data["objects"]:
                    obj_label = obj.get("label", "").lower()
                    if any(name.lower() in obj_label for name in object_names):
                        objects_found.append({
                            "label": obj.get("label"),
                            "confidence": obj.get("confidence"),
                            "coordinates": obj.get("coordinates", {})
                        })
            
            results.append({
                "scene_graph_id": row["id"],
                "timestamp": row["media_timestamp"],
                "camera_name": row["camera_name"],
                "location": row["location"],
                "file_path": row["file_path"],
                "objects_found": objects_found,
                "total_objects": len(graph_data.get("objects", [])),
                "total_relationships": len(graph_data.get("relationships", []))
            })
        except json.JSONDecodeError:
            continue
    
    conn.close()
    return results

def search_scene_graphs_by_relationships(user_id: int, relationship_types: list, camera_id: Optional[int] = None, limit: int = 20):
    """Search scene graphs containing specific relationships"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            sg.id, sg.graph_json, sg.created_at,
            m.file_path, m.timestamp as media_timestamp,
            c.name as camera_name, c.location
        FROM scene_graphs sg
        JOIN media m ON sg.media_id = m.id  
        JOIN cameras c ON m.camera_id = c.id
        WHERE c.user_id = ?
    """
    params = [user_id]
    
    if camera_id:
        query += " AND c.id = ?"
        params.append(camera_id)
    
    # Add relationship search conditions
    for rel_type in relationship_types:
        query += " AND LOWER(sg.graph_json) LIKE LOWER(?)"
        params.append(f'%"{rel_type}"%')
    
    query += " ORDER BY sg.created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    results = []
    
    for row in cursor.fetchall():
        try:
            graph_data = json.loads(row["graph_json"])
            relationships_found = []
            if "relationships" in graph_data:
                for rel in graph_data["relationships"]:
                    rel_predicate = rel.get("predicate", "").lower()
                    if any(rel_type.lower() in rel_predicate for rel_type in relationship_types):
                        relationships_found.append({
                            "predicate": rel.get("predicate"),
                            "subject": rel.get("subject"),
                            "object": rel.get("object"),
                            "confidence": rel.get("confidence")
                        })
            
            results.append({
                "scene_graph_id": row["id"],
                "timestamp": row["media_timestamp"],
                "camera_name": row["camera_name"],
                "location": row["location"],
                "file_path": row["file_path"],
                "relationships_found": relationships_found
            })
        except json.JSONDecodeError:
            continue
    
    conn.close()
    return results

def get_scene_graph_summary(user_id: int, camera_id: Optional[int] = None, days: int = 7):
    """Get summary of objects and relationships in recent scene graphs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT sg.graph_json, c.name as camera_name
        FROM scene_graphs sg
        JOIN media m ON sg.media_id = m.id  
        JOIN cameras c ON m.camera_id = c.id
        WHERE c.user_id = ? AND sg.created_at >= datetime('now', '-{} days')
    """.format(days)
    
    params = [user_id]
    if camera_id:
        query += " AND c.id = ?"
        params.append(camera_id)
    
    query += " ORDER BY sg.created_at DESC LIMIT 100"
    
    cursor.execute(query, params)
    
    object_counts = {}
    relationship_counts = {}
    
    for row in cursor.fetchall():
        try:
            graph_data = json.loads(row["graph_json"])
            
            # Count objects
            for obj in graph_data.get("objects", []):
                label = obj.get("label", "unknown")
                object_counts[label] = object_counts.get(label, 0) + 1
            
            # Count relationships  
            for rel in graph_data.get("relationships", []):
                predicate = rel.get("predicate", "unknown")
                relationship_counts[predicate] = relationship_counts.get(predicate, 0) + 1
                
        except json.JSONDecodeError:
            continue
    
    conn.close()
    
    # Sort by frequency
    top_objects = sorted(object_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_relationships = sorted(relationship_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "summary_period_days": days,
        "top_objects": top_objects,
        "top_relationships": top_relationships,
        "total_unique_objects": len(object_counts),
        "total_unique_relationships": len(relationship_counts)
    }

# ============================================
# SENTRI AGENT CHAT ENDPOINT
# ============================================

@app.post("/agent/chat")
async def agent_chat(request: AgentChatRequest, user_id: int = Depends(require_auth)):
    """Chat with Sentri AI agent with enhanced scene graph analysis"""
    
    # Get agent for user - use user_id directly as string
    agent = get_or_create_agent(str(user_id))
    
    # Set proper session state with numeric user_id
    agent.session_state["user_id"] = user_id
    if request.camera_id:
        agent.session_state["camera_id"] = request.camera_id
    
    # Build enhanced context
    context_parts = [f"User message: {request.message}"]
    
    # Analyze user message for potential object or relationship queries
    message_lower = request.message.lower()
    
    # Check for object search terms
    common_objects = ["person", "car", "dog", "cat", "motorcycle", "bicycle", "truck", "bird", "animal", "vehicle"]
    mentioned_objects = [obj for obj in common_objects if obj in message_lower]
    
    # Check for relationship search terms  
    common_relationships = ["collides", "falls", "lying", "sitting", "standing", "running", "walking", "carrying"]
    mentioned_relationships = [rel for rel in common_relationships if rel in message_lower]
    
    # Add camera context if provided
    if request.camera_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get camera info
        cursor.execute("""
            SELECT name, location
            FROM cameras
            WHERE id = ? AND user_id = ?
        """, (request.camera_id, user_id))
        
        camera_row = cursor.fetchone()
        if camera_row:
            context_parts.append(f"Selected camera: {camera_row['name']}")
            if camera_row['location']:
                context_parts.append(f"Location: {camera_row['location']}")
        
        # Get recent events for this camera
        cursor.execute("""
            SELECT el.occurred_at, e.name, e.description, el.confidence
            FROM event_logs el
            JOIN events e ON el.event_id = e.id
            WHERE el.camera_id = ?
            ORDER BY el.occurred_at DESC
            LIMIT 5
        """, (request.camera_id,))
        
        events = cursor.fetchall()
        if events:
            context_parts.append("\nRecent events:")
            for evt in events:
                context_parts.append(f"- {evt['occurred_at']}: {evt['name']} ({evt['description']}) [confidence: {evt['confidence']}]")
        
        conn.close()
        camera_context_id = request.camera_id
    else:
        camera_context_id = None
    
    # Search for objects if mentioned
    if mentioned_objects:
        try:
            object_results = search_scene_graphs_by_objects(user_id, mentioned_objects, camera_context_id, limit=10)
            if object_results:
                context_parts.append(f"\nFound {len(object_results)} frames with mentioned objects ({', '.join(mentioned_objects)}):")
                for result in object_results[:5]:  # Limit to 5 most recent
                    context_parts.append(f"- {result['timestamp']}: {result['camera_name']} - {len(result['objects_found'])} matching objects")
                    for obj in result['objects_found'][:3]:  # Show top 3 objects
                        context_parts.append(f"  * {obj['label']} (confidence: {obj.get('confidence', 'unknown')})")
        except Exception as e:
            logger.error(f"Object search error: {e}")
    
    # Search for relationships if mentioned
    if mentioned_relationships:
        try:
            relationship_results = search_scene_graphs_by_relationships(user_id, mentioned_relationships, camera_context_id, limit=10)
            if relationship_results:
                context_parts.append(f"\nFound {len(relationship_results)} frames with mentioned relationships ({', '.join(mentioned_relationships)}):")
                for result in relationship_results[:5]:
                    context_parts.append(f"- {result['timestamp']}: {result['camera_name']} - {len(result['relationships_found'])} matching relationships")
                    for rel in result['relationships_found'][:3]:
                        context_parts.append(f"  * {rel['predicate']} between {rel['subject']} and {rel['object']}")
        except Exception as e:
            logger.error(f"Relationship search error: {e}")
    
    # Add scene graph summary if user asks about general statistics
    summary_keywords = ["summary", "statistics", "overview", "what", "how many", "most common", "frequent"]
    if any(keyword in message_lower for keyword in summary_keywords):
        try:
            summary = get_scene_graph_summary(user_id, camera_context_id, days=7)
            context_parts.append(f"\nRecent activity summary (last {summary['summary_period_days']} days):")
            context_parts.append(f"- Total unique objects detected: {summary['total_unique_objects']}")
            context_parts.append(f"- Total unique relationships: {summary['total_unique_relationships']}")
            
            if summary['top_objects']:
                context_parts.append("Top objects detected:")
                for obj, count in summary['top_objects'][:5]:
                    context_parts.append(f"  * {obj}: {count} times")
            
            if summary['top_relationships']:
                context_parts.append("Top relationships detected:")
                for rel, count in summary['top_relationships'][:5]:
                    context_parts.append(f"  * {rel}: {count} times")
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
    
    # Add helpful instructions for the agent
    context_parts.append("\nYou are Sentri AI, a smart security assistant. You have access to:")
    context_parts.append("- Event logs and notifications from security cameras")
    context_parts.append("- Scene graph data showing detected objects and their relationships") 
    context_parts.append("- Frame images and timestamps from camera captures")
    context_parts.append("- Camera information and locations")
    context_parts.append("\nYou can help users find specific objects, analyze relationships, and provide security insights.")
    context_parts.append("If users ask about finding objects or relationships not shown above, suggest they be more specific with object names or time ranges.")
    
    # Combine context
    full_message = "\n".join(context_parts)
    
    # Get agent response
    try:
        response = agent.run(full_message)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        return {"reply": reply}
        
    except Exception as e:
        logger.error(f"Agent chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent response")

# ============================================
# SENTRI SCENE GRAPH SEARCH ENDPOINTS  
# ============================================

@app.get("/scene-graphs/search/objects")
async def search_objects_endpoint(
    objects: str,  # Comma-separated object names
    camera_id: Optional[int] = None,
    limit: int = 20,
    user_id: int = Depends(require_auth)
):
    """Search for scene graphs containing specific objects"""
    object_list = [obj.strip() for obj in objects.split(",") if obj.strip()]
    if not object_list:
        raise HTTPException(status_code=400, detail="At least one object name required")
    
    results = search_scene_graphs_by_objects(user_id, object_list, camera_id, limit)
    return {"objects_searched": object_list, "results": results, "count": len(results)}

@app.get("/scene-graphs/search/relationships") 
async def search_relationships_endpoint(
    relationships: str,  # Comma-separated relationship types
    camera_id: Optional[int] = None,
    limit: int = 20,
    user_id: int = Depends(require_auth)
):
    """Search for scene graphs containing specific relationships"""
    relationship_list = [rel.strip() for rel in relationships.split(",") if rel.strip()]
    if not relationship_list:
        raise HTTPException(status_code=400, detail="At least one relationship type required")
    
    results = search_scene_graphs_by_relationships(user_id, relationship_list, camera_id, limit)
    return {"relationships_searched": relationship_list, "results": results, "count": len(results)}

@app.get("/scene-graphs/summary")
async def get_scene_graph_summary_endpoint(
    camera_id: Optional[int] = None,
    days: int = 7,
    user_id: int = Depends(require_auth)
):
    """Get summary statistics of objects and relationships in scene graphs"""
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days parameter must be between 1 and 90")
    
    summary = get_scene_graph_summary(user_id, camera_id, days)
    return summary

# ============================================
# EXISTING ENDPOINTS (UNCHANGED)
# ============================================

# WebSocket endpoint for real-time communication
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
    await handle_websocket_connection(websocket, client_id)

# Mobile App API Endpoints (WEBHOOK-BASED)
@app.post("/mobile/create-channel")
async def create_mobile_channel(request: MobileChannelRequest):
    """Create a mobile channel for user and mission (with webhook support)"""
    try:
        result = await create_mobile_channel_webhook_api(request)
        return result
    except Exception as e:
        logger.error(f"Failed to create mobile channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mobile/send-message")
async def send_mobile_message(request: MobileChatMessage):
    """Send message to AI agent via mobile app (webhook-based)"""
    try:
        result = await send_mobile_message_webhook_api(request)
        return result
    except Exception as e:
        logger.error(f"Failed to send mobile message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mobile/stream-message")
async def send_mobile_stream_message(request: MobileStreamMessage):
    """Send message to AI agent via mobile app with webhook-based streaming response"""
    try:
        result = await send_mobile_stream_message_webhook_api(request)
        return result
    except Exception as e:
        logger.error(f"Failed to send mobile stream message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mobile/channels/{user_id}")
async def get_user_channels(user_id: str):
    """Get all channels for a user"""
    try:
        result = await get_user_channels_webhook_api(user_id)
        return result
    except Exception as e:
        logger.error(f"Failed to get user channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mobile/close-channel")
async def close_mobile_channel(request: MobileChannelRequest):
    """Close mobile channel"""
    try:
        result = await close_mobile_channel_webhook_api(request)
        return result
    except Exception as e:
        logger.error(f"Failed to close mobile channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mobile/channel-info/{user_id}/{mission_id}")
async def get_channel_info(user_id: str, mission_id: str):
    """Get information about a specific channel"""
    try:
        result = await get_channel_info_webhook_api(user_id, mission_id)
        return result
    except Exception as e:
        logger.error(f"Failed to get channel info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def mobile_demo_interface():
    """Serve the Enhanced Mobile Streaming API demo interface"""
    try:
        with open("static/mobile_streaming_demo.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("Mobile streaming demo interface not found. Please ensure static/mobile_streaming_demo.html exists.", status_code=404)

@app.get("/webcam", response_class=HTMLResponse)
def webcam_viewer():
    """Serve the webcam viewer page"""
    try:
        with open("static/webcam.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("Webcam viewer not found.", status_code=404)

@app.get("/test-stream", response_class=HTMLResponse)
def stream_test():
    """Serve the stream test page"""
    try:
        with open("static/stream-test.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("Stream test page not found.", status_code=404)

@app.get("/agent-status", response_class=HTMLResponse)
def agent_status_redirect():
    """Redirect to AgentOS status/control interface"""
    return HTMLResponse("""
    <html>
        <head>
            <title>Agent Status - Redirecting</title>
            <meta http-equiv="refresh" content="0; url=/sessions">
        </head>
        <body>
            <h1>Redirecting to Agent Status...</h1>
            <p>If you are not redirected automatically, <a href="/sessions">click here</a>.</p>
            <p>Available AgentOS endpoints:</p>
            <ul>
                <li><a href="/sessions">Sessions</a></li>
                <li><a href="/agents">Agents</a></li>
                <li><a href="/docs">API Documentation</a></li>
            </ul>
        </body>
    </html>
    """, status_code=200)


@app.post("/mobile/save-audio")
async def save_audio_debug(file: UploadFile = File(...)):
    """Persist uploaded audio into static/recordings for debugging."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        suffix = Path(file.filename).suffix.lower() or ".wav"
        if suffix not in {".wav", ".webm", ".mp3", ".m4a"}:
            raise HTTPException(status_code=400, detail="Unsupported audio format")

        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        safe_suffix = suffix if suffix else ".wav"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"ctrx_{timestamp}{safe_suffix}"
        destination = RECORDINGS_DIR / filename

        with destination.open("wb") as out_file:
            out_file.write(contents)

        return {
            "status": "saved",
            "filename": filename,
            "path": f"/static/recordings/{filename}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save audio" )
        raise HTTPException(status_code=500, detail="Failed to save audio") from exc


@app.post("/mobile/transcribe")
async def proxy_transcribe_audio(file: UploadFile = File(...)):
    """Forward audio to the configured transcription service to avoid browser CORS issues."""
    if not STT_ENDPOINT:
        raise HTTPException(status_code=500, detail="Transcription endpoint not configured")

    try:
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        filename = file.filename or "recording.wav"
        content_type = file.content_type or "audio/wav"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                STT_ENDPOINT,
                files={"file": (filename, payload, content_type)},
            )
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.exception("Transcription service request failed")
        raise HTTPException(status_code=502, detail="Transcription service unavailable") from exc

    media_type = response.headers.get("content-type", "application/json")
    return Response(content=response.content, status_code=response.status_code, media_type=media_type)

@app.post("/run")
async def run(body: Body):
    agent = get_or_create_agent("default_user")
    response = agent.run(body.message)
    return {"response": response.content}

# Create AgentOS with custom app as base
agent_os = AgentOS(
    agents=[a],
    name="Basic Agent",
    description="A basic agent that can answer questions and help with tasks.",
    base_app=app,
    on_route_conflict="preserve_base_app",  # Preserve our custom routes over AgentOS defaults
)

# Get the final app with both custom and AgentOS routes
app = agent_os.get_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777)