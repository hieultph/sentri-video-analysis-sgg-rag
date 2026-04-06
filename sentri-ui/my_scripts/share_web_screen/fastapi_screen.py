import cv2
import numpy as np
import asyncio
import threading
import time
from mss import mss
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Screen Sharing Streaming Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
screen_lock = threading.Lock()
current_screen_frame = None
screen_streaming = False
capture_thread = None

# Screen capture settings - you can modify these
# MONITOR = {"top": 0, "left": 0, "width": 1920, "height": 1080}  # Full screen
MONITOR = {"top": 0, "left": 0, "width": 800, "height": 600}  # Smaller region

def screen_capture():
    """Capture screen frames in background thread"""
    global current_screen_frame, screen_streaming
    
    print("🖥️ Starting screen capture...")
    print(f"📺 Using region: {MONITOR['width']}x{MONITOR['height']} at ({MONITOR['left']}, {MONITOR['top']})")
    screen_streaming = True
    
    try:
        with mss() as sct:            
            while screen_streaming:
                # Capture screen using the defined MONITOR region
                img = np.array(sct.grab(MONITOR))
                
                # Convert BGRA to BGR (remove alpha channel)
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Resize if too big (for better streaming)
                height, width = frame.shape[:2]
                if width > 1280:  # Resize if wider than 1280px
                    scale = 1280 / width
                    new_width = 1280
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                
                # Update current frame
                with screen_lock:
                    current_screen_frame = buffer.tobytes()
                
                time.sleep(0.033)  # ~30 FPS
                
    except Exception as e:
        print(f"💥 Screen capture error: {e}")
    finally:
        screen_streaming = False
        print("🖥️ Screen capture stopped")

async def generate_screen_frames():
    """Generate screen frames for streaming"""
    global current_screen_frame
    
    while True:
        # Get current frame
        with screen_lock:
            if current_screen_frame is None:
                await asyncio.sleep(0.01)
                continue
            frame_data = current_screen_frame
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        
        await asyncio.sleep(0.033)  # Control frame rate

@app.on_event("startup")
async def startup_event():
    """Start screen capture when app starts"""
    global capture_thread
    print("🚀 Starting FastAPI Screen Sharing Server...")
    
    capture_thread = threading.Thread(target=screen_capture, daemon=True)
    capture_thread.start()
    
    # Wait a bit for capture to initialize
    await asyncio.sleep(1)
    
    if screen_streaming:
        print("✅ Screen sharing ready!")
    else:
        print("❌ Screen capture failed to start")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop screen capture when app shuts down"""
    global screen_streaming
    screen_streaming = False
    print("🛑 Shutting down screen capture...")

@app.get("/")
async def home():
    return {
        "message": "FastAPI Screen Sharing Server",
        "stream_url": "/stream",
        "monitor_region": MONITOR,
        "status": "running" if screen_streaming else "stopped"
    }

@app.get("/stream")
async def screen_stream():
    """Stream screen endpoint"""
    if not screen_streaming:
        return Response(content="Screen capture not available", status_code=503)
    
    return StreamingResponse(
        generate_screen_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/test")
async def test_page():
    """Simple test page with screen stream"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screen Share Test</title>
        <style>
            body {{ 
                font-family: Arial; 
                text-align: center; 
                padding: 20px; 
                background: #f0f0f0;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            img {{ 
                max-width: 100%; 
                border: 2px solid #333; 
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            h1 {{ color: #333; }}
            .info {{
                background: #e8f4fd;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🖥️ FastAPI Screen Share Stream</h1>
            <div class="info">
                <strong>Monitor:</strong> {MONITOR['width']}x{MONITOR['height']}<br>
                <strong>Stream URL:</strong> <code>/stream</code><br>
                <strong>Port:</strong> 8081
            </div>
            <img src="/stream" alt="Live Screen Share" />
            <p><strong>Multiple viewers supported!</strong> Share this URL with others.</p>
        </div>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")

if __name__ == "__main__":
    print("🎯 Starting FastAPI Screen Share Server on port 8081...")
    print("🖥️ Access URLs:")
    print("   - Test page: http://localhost:8081/test")
    print("   - Stream: http://localhost:8081/stream")
    print("   - API info: http://localhost:8081/")
    print(f"📺 Monitor region: {MONITOR}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8081,
        log_level="warning"  # Reduce logs
    )