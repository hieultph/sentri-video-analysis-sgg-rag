"""
Database setup for Sentri camera monitoring system
Creates and initializes tmp/sentri.db with all required tables
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("tmp/sentri.db")

def init_database():
    """Initialize Sentri database with all required tables and indexes"""
    
    # Ensure tmp directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Auth users table (stores password hashes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_users (
                user_id INTEGER PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Cameras table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                location TEXT,
                stream_url TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Media table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('frame', 'video')),
                file_path TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE
            )
        """)
        
        # Scene graphs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scene_graphs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                graph_json TEXT NOT NULL,
                model_version TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 5),
                description TEXT
            )
        """)
        
        # Event logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                camera_id INTEGER NOT NULL,
                scene_graph_id INTEGER NOT NULL,
                confidence REAL,
                occurred_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE,
                FOREIGN KEY (scene_graph_id) REFERENCES scene_graphs(id) ON DELETE CASCADE
            )
        """)
        
        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_log_id INTEGER NOT NULL,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (event_log_id) REFERENCES event_logs(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cameras_user_id ON cameras(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_camera_timestamp ON media(camera_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_logs_camera_occurred ON event_logs(camera_id, occurred_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)")
        
        # Insert default events if not exist
        default_events = [
            ('collision_detected', 5, 'Collision detected between objects'),
            ('falling_off_detected', 4, 'Object falling off detected'),
            ('lying_on_detected', 3, 'Object lying on another object detected'),
            ('fire_detected', 5, 'Fire or smoke detected'),
            ('weapon_detected', 5, 'Weapon detected in scene'),
            ('intrusion', 4, 'Unauthorized intrusion detected'),
            ('loitering', 2, 'Suspicious loitering detected')
        ]
        
        for event_name, severity, description in default_events:
            cursor.execute("""
                INSERT OR IGNORE INTO events (name, severity, description)
                VALUES (?, ?, ?)
            """, (event_name, severity, description))
        
        conn.commit()
        logger.info("Database initialized successfully at tmp/sentri.db")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_database()
    print("Database setup complete!")
