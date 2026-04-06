"""
Authentication helpers for Sentri system
"""
import bcrypt
import secrets
from typing import Optional, Dict
from functools import wraps
from fastapi import HTTPException, Header
from db_setup import get_db_connection

# Simple in-memory session store (use Redis in production)
sessions: Dict[str, int] = {}  # token -> user_id

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def create_session(user_id: int) -> str:
    """Create a new session token"""
    token = secrets.token_urlsafe(32)
    sessions[token] = user_id
    return token

def get_user_from_token(token: Optional[str]) -> Optional[int]:
    """Get user_id from session token"""
    if not token:
        return None
    return sessions.get(token)

def delete_session(token: str):
    """Delete a session"""
    if token in sessions:
        del sessions[token]

def require_auth(authorization: Optional[str] = Header(None)) -> int:
    """Dependency to require authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    # Support both "Bearer TOKEN" and just "TOKEN"
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    user_id = get_user_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user_id

def get_user_info(user_id: int) -> Optional[Dict]:
    """Get user information by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, created_at
        FROM users
        WHERE id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "created_at": row["created_at"]
        }
    return None
