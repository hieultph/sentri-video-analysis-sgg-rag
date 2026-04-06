"""
Check Database Schema
"""
import sqlite3

def check_database_schema():
    """Check the schema of the database"""
    print("🔍 Checking database schema...")
    
    try:
        conn = sqlite3.connect('tmp/sentri.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Tables found: {[t[0] for t in tables]}")
        print("")
        
        for table in tables:
            table_name = table[0]
            print(f"📋 Table: {table_name}")
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("  Columns:")
            for col in columns:
                col_id, name, data_type, not_null, default_val, pk = col
                print(f"    - {name} ({data_type})")
            
            # Sample data count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  Records: {count}")
            print("")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_database_schema()