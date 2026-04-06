#!/usr/bin/env python3
"""
Debug Database Schema for Sentri System
======================================

This script checks the actual database schema and data.
"""

import sqlite3
import json

def check_database_schema():
    """Check current database schema and sample data"""
    
    print("🔍 CHECKING SENTRI DATABASE SCHEMA")
    print("=" * 50)
    
    conn = sqlite3.connect('tmp/sentri.db')
    cursor = conn.cursor()
    
    try:
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Tables found: {', '.join(tables)}")
        print()
        
        # Check each table schema and data count
        for table in tables:
            print(f"🏗️  Table: {table}")
            print("-" * 30)
            
            # Get schema
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            print("Columns:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                pk_indicator = " (PK)" if pk else ""
                null_indicator = " NOT NULL" if not_null else ""
                default_indicator = f" DEFAULT {default_val}" if default_val else ""
                print(f"  - {col_name}: {col_type}{pk_indicator}{null_indicator}{default_indicator}")
            
            # Get count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Records: {count}")
            
            # Show sample data for non-empty tables
            if count > 0 and count < 10:
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                rows = cursor.fetchall()
                if rows:
                    print("Sample data:")
                    for i, row in enumerate(rows[:2]):  # Show first 2 rows
                        print(f"  Row {i+1}: {row}")
            
            print()
        
        # Check specific scene_graphs data if exists
        if 'scene_graphs' in tables:
            print("🎯 SCENE GRAPHS DETAILED CHECK")
            print("-" * 40)
            
            cursor.execute("""
                SELECT 
                    sg.id, sg.model_version, sg.created_at,
                    m.file_path, m.type,
                    c.name as camera_name
                FROM scene_graphs sg
                JOIN media m ON sg.media_id = m.id  
                JOIN cameras c ON m.camera_id = c.id
                LIMIT 3
            """)
            
            rows = cursor.fetchall()
            if rows:
                print("Scene graphs with media info:")
                for row in rows:
                    print(f"  ID: {row[0]}, Model: {row[1]}, Time: {row[2]}")
                    print(f"      File: {row[3]}, Type: {row[4]}, Camera: {row[5]}")
                
                # Check sample graph_json structure
                cursor.execute("SELECT graph_json FROM scene_graphs LIMIT 1")
                json_row = cursor.fetchone()
                if json_row:
                    try:
                        graph_data = json.loads(json_row[0])
                        print("\nSample graph_json structure:")
                        if 'objects' in graph_data:
                            print(f"  Objects: {len(graph_data['objects'])}")
                            if graph_data['objects']:
                                obj_sample = graph_data['objects'][0]
                                print(f"    Sample object: {obj_sample}")
                        
                        if 'relationships' in graph_data:
                            print(f"  Relationships: {len(graph_data['relationships'])}")
                            if graph_data['relationships']:
                                rel_sample = graph_data['relationships'][0]
                                print(f"    Sample relationship: {rel_sample}")
                    except json.JSONDecodeError:
                        print("  Error: Invalid JSON in graph_json")
            else:
                print("  No scene graphs found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        conn.close()

def test_user_access():
    """Test user access and data visibility"""
    
    print("\n🔐 TESTING USER ACCESS")
    print("=" * 50)
    
    conn = sqlite3.connect('tmp/sentri.db')
    cursor = conn.cursor()
    
    try:
        # Check users
        cursor.execute("SELECT id, username FROM users LIMIT 5")
        users = cursor.fetchall()
        
        if users:
            print("Available users:")
            for user_id, username in users:
                print(f"  User {user_id}: {username}")
                
                # Check cameras for this user
                cursor.execute("SELECT COUNT(*) FROM cameras WHERE user_id = ?", (user_id,))
                camera_count = cursor.fetchone()[0]
                
                # Check scene graphs accessible to this user
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM scene_graphs sg
                    JOIN media m ON sg.media_id = m.id  
                    JOIN cameras c ON m.camera_id = c.id
                    WHERE c.user_id = ?
                """, (user_id,))
                sg_count = cursor.fetchone()[0]
                
                print(f"    Cameras: {camera_count}, Scene graphs: {sg_count}")
        else:
            print("❌ No users found!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    check_database_schema()
    test_user_access()
    
    print("\n✅ Database schema check completed!")