import cv2
import asyncio
import threading
import time
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Webcam Streaming Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
webcam_lock = threading.Lock()
current_frame = None
webcam_running = False
capture_thread = None

def webcam_capture():
    """Capture frames from webcam in background thread"""
    global current_frame, webcam_running
    
    # Try to open camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return
    
    print("📷 Camera opened successfully!")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    webcam_running = True
    
    try:
        while webcam_running:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to read frame")
                continue
            
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            # Update current frame
            with webcam_lock:
                current_frame = buffer.tobytes()
            
            time.sleep(0.03)  # ~33 FPS
            
    except Exception as e:
        print(f"💥 Camera error: {e}")
    finally:
        cap.release()
        webcam_running = False
        print("📷 Camera released")

async def generate_frames():
    """Generate video frames for streaming"""
    global current_frame
    
    while True:
        # Get current frame
        with webcam_lock:
            if current_frame is None:
                await asyncio.sleep(0.01)
                continue
            frame_data = current_frame
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        
        await asyncio.sleep(0.03)  # Control frame rate

@app.on_event("startup")
async def startup_event():
    """Start webcam capture when app starts"""
    global capture_thread
    print("🚀 Starting FastAPI Webcam Server...")
    
    capture_thread = threading.Thread(target=webcam_capture, daemon=True)
    capture_thread.start()
    
    # Wait a bit for camera to initialize
    await asyncio.sleep(1)
    
    if webcam_running:
        print("✅ Webcam ready!")
    else:
        print("❌ Webcam failed to start")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop webcam capture when app shuts down"""
    global webcam_running
    webcam_running = False
    print("🛑 Shutting down webcam...")

@app.get("/")
async def home():
    return {
        "message": "FastAPI Webcam Streaming Server",
        "stream_url": "/stream",
        "status": "running" if webcam_running else "stopped"
    }

@app.get("/stream")
async def video_stream():
    """Stream video endpoint"""
    if not webcam_running:
        return Response(content="Camera not available", status_code=503)
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/test")
async def test_page():
    """Simple test page with video"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Webcam Test</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            img { max-width: 100%; border: 2px solid #333; border-radius: 10px; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <h1>📹 FastAPI Webcam Stream</h1>
        <img src="/stream" alt="Live Webcam" />
        <p>Stream URL: <code>/stream</code></p>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")

if __name__ == "__main__":
    print("🎯 Starting FastAPI Webcam Server on port 8080...")
    print("🌐 Access URLs:")
    print("   - Test page: http://localhost:8080/test")
    print("   - Stream: http://localhost:8080/stream")
    print("   - API info: http://localhost:8080/")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080,
        log_level="warning"  # Reduce logs
    )