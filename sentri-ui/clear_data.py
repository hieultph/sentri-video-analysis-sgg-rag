#!/usr/bin/env python3
"""
Clear Data Script for Sentri System
===================================

This script clears all data from the Sentri database except for:
- users table
- auth_users table  
- cameras table

It will delete:
- media files and records
- scene_graphs
- events
- event_logs
- notifications

USE WITH CAUTION! This action cannot be undone.
"""

import sqlite3
import os
import sys
from pathlib import Path

def get_db_connection():
    """Get database connection"""
    db_path = "sentri.db"  # Fixed: was tmp/sentri.db
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        print("Make sure you're running this script from the correct directory.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_table_counts(conn):
    """Get current record counts for all tables"""
    cursor = conn.cursor()
    
    tables = {
        'notifications': 'SELECT COUNT(*) FROM notifications',
        'event_logs': 'SELECT COUNT(*) FROM event_logs', 
        'events': 'SELECT COUNT(*) FROM events',
        'scene_graphs': 'SELECT COUNT(*) FROM scene_graphs',
        'media': 'SELECT COUNT(*) FROM media',
        'cameras': 'SELECT COUNT(*) FROM cameras',
        'users': 'SELECT COUNT(*) FROM users'
    }
    
    counts = {}
    for table, query in tables.items():
        try:
            cursor.execute(query)
            counts[table] = cursor.fetchone()[0]
        except sqlite3.Error as e:
            counts[table] = f"Error: {e}"
    
    return counts

def clear_media_files():
    """Clear physical media files from recordings directory"""
    recordings_dir = Path("static/recordings")
    if not recordings_dir.exists():
        print("📁 No recordings directory found")
        return 0
    
    deleted_count = 0
    
    # Clear frames directory
    frames_dir = recordings_dir / "frames"
    if frames_dir.exists():
        for file_path in frames_dir.glob("*"):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to delete {file_path}: {e}")
    
    # Clear any other media files
    for file_path in recordings_dir.glob("*"):
        if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.png', '.mp4', '.avi', '.mov']:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"⚠️  Failed to delete {file_path}: {e}")
    
    return deleted_count

def clear_database_tables(conn):
    """Clear all data tables except users, auth_users, and cameras"""
    cursor = conn.cursor()
    deleted_counts = {}
    
    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Delete in correct order due to foreign key constraints
        
        # 1. Delete notifications (references event_logs)
        cursor.execute("DELETE FROM notifications")
        deleted_counts['notifications'] = cursor.rowcount
        print(f"🗑️  Deleted {cursor.rowcount} notifications")
        
        # 2. Delete event_logs (references events, cameras, scene_graphs)
        cursor.execute("DELETE FROM event_logs")
        deleted_counts['event_logs'] = cursor.rowcount
        print(f"🗑️  Deleted {cursor.rowcount} event logs")
        
        # 3. Delete scene_graphs (references media)
        cursor.execute("DELETE FROM scene_graphs")
        deleted_counts['scene_graphs'] = cursor.rowcount
        print(f"🗑️  Deleted {cursor.rowcount} scene graphs")
        
        # 4. Delete media (references cameras)
        cursor.execute("DELETE FROM media")
        deleted_counts['media'] = cursor.rowcount
        print(f"🗑️  Deleted {cursor.rowcount} media records")
        
        # 5. Delete events (standalone table, but referenced by event_logs)
        cursor.execute("DELETE FROM events")
        deleted_counts['events'] = cursor.rowcount
        print(f"🗑️  Deleted {cursor.rowcount} event definitions")
        
        # Commit transaction
        cursor.execute("COMMIT")
        print("✅ Database cleanup completed successfully!")
        
        return deleted_counts
        
    except sqlite3.Error as e:
        # Rollback on error
        cursor.execute("ROLLBACK")
        print(f"❌ Database error: {e}")
        print("🔄 Transaction rolled back")
        raise

def reset_auto_increment(conn):
    """Reset auto-increment counters for cleared tables"""
    cursor = conn.cursor()
    
    tables_to_reset = ['notifications', 'event_logs', 'scene_graphs', 'media', 'events']
    
    try:
        for table in tables_to_reset:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        
        conn.commit()
        print("🔄 Auto-increment counters reset")
        
    except sqlite3.Error as e:
        print(f"⚠️  Warning: Failed to reset auto-increment: {e}")

def main():
    print("=" * 60)
    print("🧹 SENTRI DATA CLEANUP SCRIPT")
    print("=" * 60)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("app.py"):
        print("❌ This doesn't appear to be the Sentri project directory.")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    # Get database connection
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Show current data counts
    print("📊 Current database status:")
    print("-" * 30)
    counts = get_table_counts(conn)
    
    tables_to_clear = ['notifications', 'event_logs', 'scene_graphs', 'media', 'events']
    tables_to_keep = ['users', 'cameras']
    
    for table in tables_to_clear:
        status = "🗑️  TO DELETE" if isinstance(counts[table], int) and counts[table] > 0 else "✅ EMPTY"
        print(f"{table:15} : {counts[table]:6} records {status}")
    
    print()
    for table in tables_to_keep:
        print(f"{table:15} : {counts[table]:6} records ✅ WILL KEEP")
    
    print("\n" + "=" * 60)
    print("⚠️  WARNING: This will permanently delete:")
    print("   • All media files and frame images")
    print("   • All scene graph data")
    print("   • All event logs and notifications")
    print("   • All event type definitions")
    print()
    print("💾 The following will be preserved:")
    print("   • User accounts and authentication")
    print("   • Camera configurations")
    print("=" * 60)
    
    # Confirmation
    response = input("\n🤔 Do you want to proceed? Type 'DELETE' to confirm: ")
    
    if response != "DELETE":
        print("❌ Operation cancelled")
        conn.close()
        sys.exit(0)
    
    print("\n🚀 Starting cleanup process...")
    print("-" * 30)
    
    # Clear physical media files first
    print("📁 Clearing physical media files...")
    deleted_files = clear_media_files()
    print(f"🗑️  Deleted {deleted_files} media files")
    
    # Clear database tables
    print("\n💾 Clearing database tables...")
    try:
        deleted_counts = clear_database_tables(conn)
        
        # Reset auto-increment counters
        reset_auto_increment(conn)
        
        # Show final summary
        print("\n" + "=" * 60)
        print("✅ CLEANUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("📊 Summary of deleted data:")
        print(f"   • Physical files    : {deleted_files:6}")
        
        total_records = 0
        for table, count in deleted_counts.items():
            print(f"   • {table:15} : {count:6}")
            total_records += count
        
        print(f"   • Total DB records  : {total_records:6}")
        
        print("\n💾 Preserved data:")
        final_counts = get_table_counts(conn)
        print(f"   • Users             : {final_counts['users']:6}")
        print(f"   • Cameras           : {final_counts['cameras']:6}")
        
        print("\n🎉 Your Sentri system is now clean and ready for fresh data!")
        
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()