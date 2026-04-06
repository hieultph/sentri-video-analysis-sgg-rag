#!/usr/bin/env python3

import sqlite3
import json
from datetime import datetime, timezone
import pytz

def check_and_fix_timezone():
    """Check timezone issues in Sentri database and provide fixes"""
    
    conn = sqlite3.connect('tmp/sentri.db')
    cursor = conn.cursor()
    
    try:
        print("=== TIMEZONE ANALYSIS ===")
        
        # Check current timezone info
        vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        utc_tz = pytz.UTC
        current_vietnam = datetime.now(vietnam_tz)
        current_utc = datetime.now(utc_tz)
        
        print(f"Current Vietnam time: {current_vietnam}")
        print(f"Current UTC time: {current_utc}")
        print(f"Vietnam offset: {current_vietnam.strftime('%z')}")
        
        # Check media table timestamps
        print("\n=== MEDIA TABLE TIMESTAMPS ===")
        cursor.execute("SELECT id, timestamp, created_at FROM media ORDER BY created_at DESC LIMIT 5")
        media_records = cursor.fetchall()
        
        for record in media_records:
            media_id, timestamp, created_at = record
            print(f"Media ID {media_id}:")
            print(f"  timestamp: {timestamp}")
            print(f"  created_at: {created_at}")
            
            # Try to parse timestamp
            try:
                if 'T' in timestamp:  # ISO format
                    parsed_ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    print(f"  parsed timestamp: {parsed_ts}")
                    print(f"  timezone aware: {parsed_ts.tzinfo is not None}")
            except Exception as e:
                print(f"  Error parsing timestamp: {e}")
            print()
        
        # Check scene_graphs table timestamps
        print("\n=== SCENE GRAPHS TABLE TIMESTAMPS ===")
        cursor.execute("SELECT id, created_at FROM scene_graphs ORDER BY created_at DESC LIMIT 5")
        sg_records = cursor.fetchall()
        
        for record in sg_records:
            sg_id, created_at = record
            print(f"Scene Graph ID {sg_id}:")
            print(f"  created_at: {created_at}")
            
            # Try to parse created_at
            try:
                parsed_ca = datetime.fromisoformat(created_at)
                print(f"  parsed created_at: {parsed_ca}")
                print(f"  timezone aware: {parsed_ca.tzinfo is not None}")
            except Exception as e:
                print(f"  Error parsing created_at: {e}")
            print()
        
        # Check event_logs table
        print("\n=== EVENT LOGS TABLE TIMESTAMPS ===")
        cursor.execute("SELECT id, occurred_at, created_at FROM event_logs ORDER BY created_at DESC LIMIT 5")
        event_records = cursor.fetchall()
        
        for record in event_records:
            event_id, occurred_at, created_at = record
            print(f"Event ID {event_id}:")
            print(f"  occurred_at: {occurred_at}")
            print(f"  created_at: {created_at}")
            print()
        
        # Check notifications table
        print("\n=== NOTIFICATIONS TABLE TIMESTAMPS ===")
        cursor.execute("SELECT id, created_at FROM notifications ORDER BY created_at DESC LIMIT 5")
        notif_records = cursor.fetchall()
        
        for record in notif_records:
            notif_id, created_at = record
            print(f"Notification ID {notif_id}:")
            print(f"  created_at: {created_at}")
            print()
        
        print("\n=== RECOMMENDATIONS ===")
        print("1. Ensure all datetime inputs are in Vietnam timezone (UTC+7)")
        print("2. Convert all stored timestamps to consistent format")
        print("3. Use timezone-aware datetime objects in application code")
        print("4. Consider storing all times in UTC and converting for display")
        
        print("\n=== PROPOSED FIX ===")
        print("Update camera_capture.py to use Vietnam timezone:")
        print("""
# At top of file:
import pytz
vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

# When saving timestamp:
timestamp_vietnam = timestamp.astimezone(vietnam_tz)
cursor.execute(\"\"\"
    INSERT INTO media (camera_id, type, file_path, timestamp)
    VALUES (?, ?, ?, ?)
\"\"\", (camera_id, media_type, file_path, timestamp_vietnam.isoformat()))
        """)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def test_timezone_conversion():
    """Test timezone conversion logic"""
    print("\n=== TIMEZONE CONVERSION TEST ===")
    
    # Test different timestamp formats
    test_timestamps = [
        "2024-12-15T10:30:00Z",  # UTC
        "2024-12-15T17:30:00+07:00",  # Vietnam time
        "2024-12-15 17:30:00",  # Local time string
        "2024-12-15T10:30:00.123456Z"  # UTC with microseconds
    ]
    
    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    for ts_str in test_timestamps:
        print(f"Input: {ts_str}")
        try:
            # Parse timestamp
            if ts_str.endswith('Z'):
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            elif '+' in ts_str[-6:] or ts_str.count(':') == 3:
                dt = datetime.fromisoformat(ts_str)
            else:
                # Assume local time, add Vietnam timezone
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                dt = vietnam_tz.localize(dt)
            
            # Convert to Vietnam time
            vietnam_time = dt.astimezone(vietnam_tz)
            print(f"  Vietnam time: {vietnam_time}")
            print(f"  ISO format: {vietnam_time.isoformat()}")
            print(f"  For DB storage: {vietnam_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            print(f"  Error: {e}")
        print()

if __name__ == "__main__":
    check_and_fix_timezone()
    test_timezone_conversion()