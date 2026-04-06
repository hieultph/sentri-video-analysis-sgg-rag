# Sentri - Personal Camera Monitoring System

Complete implementation of a personal camera monitoring web system with AI agent integration.

## System Overview

**Sentri** is a personal camera monitoring system that provides:

- User authentication (register/login)
- Camera management via HTTP stream URLs
- Live video stream viewing
- Scene Graph Generation (SGG) via external API
- Event detection and logging
- Real-time notifications
- AI Agent chat for explanation and support

## Architecture

### Backend

- **Python FastAPI** server
- **SQLite database** (`tmp/sentri.db`)
- **Agno AI Agent** framework (Gemini 2.5 Flash)
- **OpenCV** for video stream capture
- **bcrypt** for password hashing
- Background threads for camera stream processing

### Frontend

- **Plain HTML/CSS/JavaScript** (no frameworks)
- Responsive dashboard design
- Real-time updates
- Modal-based chat interface

### External Integration

- **SGG API**: `https://hieultph.site/sgg` for Scene Graph Generation

## Database Schema

The system uses `tmp/sentri.db` with the following tables:

- **users**: User accounts
- **auth_users**: Password hashes
- **cameras**: Camera configurations
- **media**: Captured frames and videos
- **scene_graphs**: SGG analysis results
- **events**: Event type definitions
- **event_logs**: Detected event instances
- **notifications**: User notifications

## Installation & Setup

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Windows OS (or adapt commands for Linux/Mac)

### Step 1: Install Dependencies

```powershell
# Navigate to project directory
cd "H:\gdrive\Takeout\Drive\School\4 Fourth year\BCTN\code\ctrix3"

# Install required packages (bcrypt is now in requirements.txt)
pip install -r requirements.txt
```

### Step 2: Initialize Database

```powershell
# Run database initialization
python db_setup.py
```

This creates `tmp/sentri.db` with all required tables and default events.

### Step 3: Start the Server

```powershell
# Start the FastAPI server
python app.py
```

The server will start on `http://0.0.0.0:7777`

## Usage Guide

### 1. Register a New Account

1. Open your browser and navigate to: `http://localhost:7777/static/register.html`
2. Fill in:
   - Username (required)
   - Email (optional)
   - Password (minimum 6 characters)
   - Confirm Password
3. Click "Register"
4. You'll be redirected to the login page

### 2. Login

1. Navigate to: `http://localhost:7777/static/login.html`
2. Enter your username and password
3. Click "Login"
4. You'll be redirected to the dashboard

### 3. Add a Camera

1. On the dashboard, click "➕ Add Camera"
2. Fill in:
   - **Camera Name**: e.g., "Front Door"
   - **Location**: e.g., "Main Entrance" (optional)
   - **Stream URL**: HTTP stream URL (e.g., `http://camera-ip:port/stream`)
3. Click "Add Camera"

**Supported Stream Formats:**

- MJPEG streams (most common for IP cameras)
- HLS streams
- Direct video URLs

**Example Stream URLs:**

- MJPEG: `http://192.168.1.100:8080/video_feed`
- Test stream: `http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4`

### 4. View Live Stream

1. Select a camera from the dropdown
2. The live stream will appear in the video section
3. If the stream cannot be displayed in-browser, click "Open in New Tab"

### 5. Monitor Events

- Events are automatically detected from SGG analysis
- View events in the "Event Logs" table
- Filter by camera or event type using the dropdowns
- Click "Details" to view more information

### 6. Check Notifications

- Notifications appear when events are detected
- Unread notifications are highlighted
- Click a notification to mark it as read

### 7. Chat with Sentri AI

1. Click the "💬 Chat" button
2. Ask questions about events, cameras, or security
3. Examples:
   - "What happened at the front door?"
   - "Explain the latest event"
   - "Is there any unusual activity?"

## Event Detection

The system currently detects:

**Primary Rule:**

- **Motorcycle Collision**: Detects when a motorcycle collides with a person
  - Scene graph pattern: `(motorcycle) -[collides_with]-> (person)`
  - Severity: Level 5 (Critical)
  - Creates notification automatically

**Additional Events (in database):**

- Person Falls (Severity 4)
- Intrusion (Severity 4)
- Fire (Severity 5)
- Loitering (Severity 2)

## How Stream Capture Works

1. When you add a camera, a background thread starts automatically
2. Every 2 seconds, the system:
   - Captures a frame from the stream
   - Saves it to `static/recordings/frames/`
   - Sends it to the SGG API
   - Analyzes the scene graph for events
   - Creates event logs and notifications if events are detected

## API Endpoints

### Authentication

- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get token
- `POST /auth/logout` - Logout
- `GET /auth/me` - Get current user info

### Cameras

- `POST /camera/add` - Add new camera
- `GET /camera/list` - List user's cameras

### Events & Notifications

- `GET /events` - Get event logs (with filters)
- `GET /notifications` - Get notifications
- `POST /notifications/{id}/read` - Mark notification as read

### Agent Chat

- `POST /agent/chat` - Chat with Sentri AI agent

### Ingestion

- `POST /ingest/scene-graph` - Manually ingest scene graph data

## Troubleshooting

### Cannot connect to camera stream

- Verify the stream URL is accessible
- Check if camera requires authentication
- Try opening the URL directly in browser
- Some cameras require specific formats (RTSP → MJPEG conversion)

### Database errors

- Delete `tmp/sentri.db` and run `python db_setup.py` again
- Check file permissions on tmp/ directory

### Events not detected

- Verify SGG API is accessible: `https://hieultph.site/sgg`
- Check camera capture logs in terminal
- Ensure camera stream is active

### Login issues

- Clear browser localStorage: `F12` → Console → `localStorage.clear()`
- Try registering a new account
- Check terminal for authentication errors

## File Structure

```
ctrix3/
├── app.py                          # Main FastAPI application
├── db_setup.py                     # Database initialization
├── auth_helpers.py                 # Authentication utilities
├── camera_capture.py               # Stream capture & SGG integration
├── agents/
│   └── assistant.py                # Sentri AI agent configuration
├── static/
│   ├── register.html               # Registration page
│   ├── login.html                  # Login page
│   ├── index.html                  # Main dashboard
│   ├── style.css                   # Styling
│   ├── script.js                   # Frontend logic
│   └── recordings/
│       └── frames/                 # Captured camera frames
├── tmp/
│   ├── sentri.db                   # Sentri database
│   └── agent.db                    # Agno agent storage (separate)
└── requirements.txt                # Python dependencies
```

## Technical Details

### Authentication

- Uses bcrypt for password hashing
- Session-based authentication with bearer tokens
- Tokens stored in localStorage (client-side)
- All protected endpoints require `Authorization` header

### Camera Capture

- Background threads per camera (non-blocking)
- Automatic retry on connection failures
- Graceful error handling
- Configurable capture interval (default: 2 seconds)

### AI Agent Integration

- Uses existing Agno agent framework
- Gemini 2.5 Flash model
- Context-aware responses
- Vietnamese language support (from original config)
- Conversation history stored in `tmp/agent.db`

## Development Notes

- The system is designed for **personal/demo use**, not production
- Suitable for **university thesis demonstrations**
- Simple architecture, easy to explain and modify
- No external database server required
- Minimal dependencies

## Future Enhancements (Not Implemented)

- Multi-user video streaming (WebRTC)
- Email/SMS notifications
- Video recording and playback
- Advanced scene graph visualizations
- Mobile app integration
- Custom event rule builder

## License

This is a university thesis project. Use for educational purposes.

## Support

For issues or questions during thesis defense preparation, review:

1. Database schema in `db_setup.py`
2. API endpoints in `app.py`
3. Event detection logic in `camera_capture.py`
4. Frontend code in `static/script.js`
