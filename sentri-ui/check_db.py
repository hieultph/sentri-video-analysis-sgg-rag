#!/usr/bin/env python3
"""
Debug script to check current database state
"""

import sqlite3
import os

def check_database():
    """Check current database state"""
    
    if not os.path.exists("sentri.db"):
        print("❌ Database not found!")
        return
    
    conn = sqlite3.connect("sentri.db")
    cursor = conn.cursor()
    
    # Check foreign key setting
    cursor.execute("PRAGMA foreign_keys")
    fk_status = cursor.fetchone()[0]
    print(f"🔧 Foreign keys enabled: {bool(fk_status)}")
    
    # Get table counts
    tables = ['users', 'auth_users', 'cameras', 'media', 'scene_graphs', 
              'events', 'event_logs', 'notifications']
    
    print("\n📊 Current table counts:")
    print("-" * 40)
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            emoji = "✅" if table in ['users', 'auth_users', 'cameras'] else "🗑️"
            print(f"{table:15} : {count:6} records {emoji}")
        except sqlite3.Error as e:
            print(f"{table:15} : ERROR - {e}")
    
    # Check table structure
    print("\n🏗️  Table structures:")
    print("-" * 40)
    
    for table in tables:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print(f"\n{table.upper()}:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
        except sqlite3.Error as e:
            print(f"{table}: ERROR - {e}")
    
    conn.close()

if __name__ == "__main__":
    check_database()