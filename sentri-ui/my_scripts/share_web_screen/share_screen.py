import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from mss import mss
import time

# Define capture region (left, top, width, height)
MONITOR = {"top": 0, "left": 0, "width": 800, "height": 600}

class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            
            with mss() as sct:
                try:
                    while True:
                        # Capture screen region
                        img = np.array(sct.grab(MONITOR))
                        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                        
                        _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        
                        self.wfile.write(b"--jpgboundary\r\n")
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', str(len(jpg)))
                        self.end_headers()
                        self.wfile.write(jpg.tobytes())
                        self.wfile.write(b"\r\n")
                        
                        time.sleep(0.033)  # ~30 FPS
                except:
                    pass
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8601), StreamHandler)
    print(f"Streaming screen region at http://0.0.0.0:6001/stream")
    print(f"Region: {MONITOR}")
    server.serve_forever()