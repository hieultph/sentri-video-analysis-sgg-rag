"""
Quick test script to verify Sentri system setup
Run this after installing dependencies to check if everything is working
"""
import sys
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    try:
        import bcrypt
        print("✓ bcrypt")
    except ImportError:
        print("✗ bcrypt - Run: pip install bcrypt")
        return False
    
    try:
        import cv2
        print("✓ opencv-python")
    except ImportError:
        print("✗ opencv-python - Already in requirements.txt")
        return False
    
    try:
        import fastapi
        print("✓ fastapi")
    except ImportError:
        print("✗ fastapi - Already in requirements.txt")
        return False
    
    try:
        import httpx
        print("✓ httpx")
    except ImportError:
        print("✗ httpx - Already in requirements.txt")
        return False
    
    try:
        import sqlite3
        print("✓ sqlite3 (built-in)")
    except ImportError:
        print("✗ sqlite3 - Should be built-in with Python")
        return False
    
    return True

def test_database():
    """Test database creation"""
    print("\nTesting database setup...")
    try:
        from db_setup import init_database, get_db_connection
        
        # Initialize database
        init_database()
        print("✓ Database initialized")
        
        # Test connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['users', 'auth_users', 'cameras', 'media', 
                          'scene_graphs', 'events', 'event_logs', 'notifications']
        
        for table in required_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' missing")
                conn.close()
                return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

def test_auth():
    """Test authentication helpers"""
    print("\nTesting authentication...")
    try:
        # Import bcrypt first to check
        import bcrypt
        
        # Test password hashing directly
        password = "test123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        print("✓ Password hashing works")
        
        # Test password verification
        if bcrypt.checkpw(password.encode('utf-8'), hashed):
            print("✓ Password verification works")
        else:
            print("✗ Password verification failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Auth test failed: {e}")
        return False

def test_file_structure():
    """Test if required files exist"""
    print("\nTesting file structure...")
    
    required_files = [
        'app.py',
        'db_setup.py',
        'auth_helpers.py',
        'camera_capture.py',
        'agents/assistant.py',
        'static/register.html',
        'static/login.html',
        'static/index.html',
        'static/style.css',
        'static/script.js'
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} missing")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 50)
    print("SENTRI SYSTEM TEST")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Database Test", test_database),
        ("Authentication Test", test_auth),
        ("File Structure Test", test_file_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✓ All tests passed! You can run: python app.py")
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
