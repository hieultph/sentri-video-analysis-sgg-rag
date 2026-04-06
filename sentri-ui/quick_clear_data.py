#!/usr/bin/env python3
"""
Quick Clear Data Script for Sentri System
=========================================

This is a non-interactive version that clears all data immediately.
Use this for automated cleanup or when you're sure you want to clear everything.

Usage: python quick_clear_data.py
"""

import sqlite3
import os
import sys
from pathlib import Path

def clear_all_data():
    """Clear all data from Sentri system"""
    
    # Database connection
    if not os.path.exists("sentri.db"):
        print("❌ Database not found!")
        return False
    
    conn = sqlite3.connect("sentri.db")
    cursor = conn.cursor()
    
    try:
        print("🧹 Clearing Sentri data...")
        
        # Clear physical files
        recordings_dir = Path("static/recordings/frames")
        if recordings_dir.exists():
            file_count = 0
            for file_path in recordings_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    file_count += 1
            print(f"📁 Deleted {file_count} media files")
        
        # Clear database in correct order
        cursor.execute("BEGIN TRANSACTION")
        
        tables = ['notifications', 'event_logs', 'scene_graphs', 'media', 'events']
        total_deleted = 0
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            count = cursor.rowcount
            total_deleted += count
            print(f"🗑️  {table}: {count} records")
        
        # Reset auto-increment
        for table in tables:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        
        cursor.execute("COMMIT")
        
        print(f"✅ Cleanup complete! Deleted {total_deleted} database records")
        return True
        
    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"❌ Error: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        print("🚀 Force clearing all data...")
        clear_all_data()
    else:
        print("⚠️  This will delete ALL Sentri data (except users and cameras)")
        print("💡 Use --force flag to run without confirmation")
        print("💡 Or use 'python clear_data.py' for interactive version")