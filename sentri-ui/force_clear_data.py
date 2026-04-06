#!/usr/bin/env python3
"""
Force Clear Data Script for Sentri System
=========================================

This script uses multiple approaches to ensure data is actually deleted.
Use this if the regular clear_data.py didn't work.
"""

import sqlite3
import os
import sys
from pathlib import Path

def force_clear_data():
    """Force clear all data with multiple approaches"""
    
    print("🔥 FORCE CLEARING SENTRI DATA")
    print("=" * 50)
    
    # Check database path
    db_path = "tmp/sentri.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    cursor = conn.cursor()
    
    try:
        print("🔧 Checking foreign key constraints...")
        cursor.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]
        print(f"   Foreign keys: {'ON' if fk_status else 'OFF'}")
        
        # Show current counts
        tables_to_clear = ['notifications', 'event_logs', 'scene_graphs', 'media', 'events']
        print("\n📊 Current data:")
        total_before = 0
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table:15}: {count:6} records")
                total_before += count
            except Exception as e:
                print(f"   {table:15}: ERROR - {e}")
        
        if total_before == 0:
            print("✅ Database is already clean!")
            return True
        
        print(f"\n🎯 Total records to delete: {total_before}")
        print("\n🚀 Starting force cleanup...")
        
        # Method 1: Try with foreign keys OFF first
        print("\n📝 Method 1: Disable foreign keys and clear")
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        deleted_counts = {}
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM {table}")
                count = cursor.rowcount
                deleted_counts[table] = count
                print(f"   🗑️  {table}: {count} records deleted")
            except Exception as e:
                print(f"   ❌ {table}: Failed - {e}")
                deleted_counts[table] = 0
        
        # Commit the deletions
        conn.commit()
        print("   ✅ Changes committed")
        
        # Method 2: Re-enable foreign keys and clean up sequences
        print("\n📝 Method 2: Reset auto-increment sequences")
        cursor.execute("PRAGMA foreign_keys = ON")
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                print(f"   🔄 {table}: sequence reset")
            except Exception as e:
                print(f"   ⚠️  {table}: sequence reset failed - {e}")
        
        conn.commit()
        
        # Method 3: Verify cleanup
        print("\n📝 Method 3: Verification")
        total_after = 0
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   📊 {table:15}: {count:6} records remaining")
                total_after += count
            except Exception as e:
                print(f"   ❌ {table:15}: ERROR - {e}")
        
        # Method 4: Clear physical files
        print("\n📝 Method 4: Clear physical files")
        recordings_dir = Path("static/recordings")
        file_count = 0
        
        if recordings_dir.exists():
            # Clear frames
            frames_dir = recordings_dir / "frames"
            if frames_dir.exists():
                for file_path in frames_dir.glob("*"):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                            file_count += 1
                        except Exception as e:
                            print(f"   ⚠️  Failed to delete {file_path.name}: {e}")
            
            # Clear other media files
            for file_path in recordings_dir.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mov', '.webm']:
                    try:
                        file_path.unlink()
                        file_count += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed to delete {file_path.name}: {e}")
        
        print(f"   🗑️  Physical files deleted: {file_count}")
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 CLEANUP SUMMARY")
        print("=" * 50)
        
        print(f"Database records before: {total_before:6}")
        print(f"Database records after:  {total_after:6}")
        print(f"Database records cleared: {total_before - total_after:6}")
        print(f"Physical files cleared:   {file_count:6}")
        
        if total_after == 0:
            print("\n🎉 SUCCESS: All data cleared successfully!")
            return True
        else:
            print(f"\n⚠️  WARNING: {total_after} records still remain")
            print("   Some data may not have been deleted due to constraints")
            return False
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        return False
        
    finally:
        conn.close()

def main():
    print("⚠️  FORCE DATA CLEANUP")
    print("This will aggressively clear all data except users and cameras")
    print()
    
    response = input("Type 'FORCE' to proceed with force cleanup: ")
    
    if response != "FORCE":
        print("❌ Operation cancelled")
        sys.exit(0)
    
    success = force_clear_data()
    
    if success:
        print("\n✅ Force cleanup completed successfully!")
    else:
        print("\n❌ Force cleanup encountered issues")
        print("💡 You may need to manually check the database")

if __name__ == "__main__":
    main()