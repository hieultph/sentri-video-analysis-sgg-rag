import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time

# Global variables for shared camera access
camera_lock = threading.Lock()
latest_frame = None
camera_active = False

def capture_frames():
    """Continuously capture frames from the camera in a separate thread"""
    global latest_frame, camera_active
    
    # Try multiple camera indices
    camera_indices = [0, 1, 2, -1]  # Try different camera sources
    cap = None
    
    for camera_index in camera_indices:
        print(f"🔍 Trying camera index {camera_index}...")
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                # Test if camera actually works
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    print(f"✅ Camera {camera_index} working!")
                    break
                else:
                    print(f"❌ Camera {camera_index} opened but no frames")
                    cap.release()
            else:
                print(f"❌ Cannot open camera {camera_index}")
        except Exception as e:
            print(f"❌ Error with camera {camera_index}: {e}")
        
        if cap:
            cap.release()
        cap = None
    
    if not cap or not cap.isOpened():
        print("❌ No working camera found!")
        print("💡 Possible solutions:")
        print("   - Close other apps using camera (Teams, Skype, etc.)")
        print("   - Check if camera is connected")
        print("   - Try running as administrator")
        return
    
    # Configure camera
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # Get camera info
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    print(f"📷 Camera settings: {width}x{height} @ {fps}fps")
    
    camera_active = True
    
    try:
        while camera_active:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Cannot read frame, retrying...")
                time.sleep(0.1)
                continue
            
            # Encode frame to JPEG
            _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            
            # Update the latest frame (thread-safe)
            with camera_lock:
                latest_frame = jpg.tobytes()
            
            time.sleep(0.033)  # ~30 FPS
    except Exception as e:
        print(f"💥 Camera capture error: {e}")
    finally:
        cap.release()
        camera_active = False
        print("📷 Camera released")

class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            
            if not camera_active:
                try:
                    self.wfile.write(b"ERROR: Camera not available")
                except:
                    pass
                return
            
            client_id = f"{self.client_address[0]}:{self.client_address[1]}"
            print(f"📹 New viewer connected: {client_id}")
            
            try:
                frame_count = 0
                while camera_active:
                    # Get the latest frame (thread-safe)
                    with camera_lock:
                        if latest_frame is None:
                            time.sleep(0.01)  # Short wait to avoid busy loop
                            continue
                        frame_data = latest_frame
                    
                    # Send frame to client
                    boundary = b"--jpgboundary\r\n"
                    content_type = b"Content-Type: image/jpeg\r\n"
                    content_length = f"Content-Length: {len(frame_data)}\r\n\r\n".encode()
                    
                    try:
                        self.wfile.write(boundary)
                        self.wfile.write(content_type) 
                        self.wfile.write(content_length)
                        self.wfile.write(frame_data)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                        
                        frame_count += 1
                        if frame_count % 150 == 0:  # Log every 5 seconds at 30fps
                            print(f"📊 {client_id}: {frame_count} frames sent")
                            
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        # Client disconnected
                        break
                    except Exception as e:
                        print(f"⚠️ Stream error for {client_id}: {e}")
                        break
                    
                    time.sleep(0.033)  # ~30 FPS
                    
            except Exception as e:
                print(f"❌ Client {client_id} error: {e}")
            finally:
                print(f"🔌 Viewer disconnected: {client_id}")
                
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>404 - Not Found</h1><p>Use /stream for video feed</p>")
    
    def log_message(self, format, *args):
        # Suppress log messages for cleaner output
        pass

if __name__ == '__main__':
    print("🚀 Starting Multi-Viewer Webcam Server...")
    print("🔧 Checking system...")
    
    # Check OpenCV version
    print(f"📚 OpenCV version: {cv2.__version__}")
    
    # Start the camera capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    
    # Wait for camera to initialize
    print("⏳ Initializing camera...")
    for i in range(10):  # Wait up to 10 seconds
        time.sleep(1)
        if camera_active:
            break
        print(f"⏳ Still waiting... ({i+1}/10)")
    
    if not camera_active:
        print("\n❌ Failed to initialize camera!")
        print("\n🛠️ Troubleshooting steps:")
        print("1. Close Teams, Skype, Zoom, etc.")
        print("2. Check Device Manager for camera")
        print("3. Try running as Administrator")
        print("4. Restart your computer")
        input("\n📱 Press Enter to exit...")
        exit(1)
    
    # Start the HTTP server
    try:
        server = HTTPServer(('0.0.0.0', 8600), StreamHandler)
        print("\n✅ Server started successfully!")
        print(f"📡 Stream URL: http://0.0.0.0:8600/stream")
        print(f"🌐 Local access: http://localhost:8600/stream")  
        print("👥 Multiple clients supported - share the URL!")
        print("\n📝 Press Ctrl+C to stop\n")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        camera_active = False
        server.shutdown()
        print("✅ Server stopped successfully!")
    except Exception as e:
        print(f"\n💥 Server error: {e}")
        camera_active = False