# Authentication utilities for Backend API
# Shared JWT authentication with Auth Forum API

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

from database import get_db

# Configuration - shared secret with auth service
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required for security. "
        "Please set a strong secret key (minimum 32 characters) in your environment variables."
    )

ALGORITHM = "HS256"
AUTH_SERVICE_URL = "http://localhost:8008"  # Auth Forum API URL

# HTTP Bearer token
security = HTTPBearer()

class TokenData:
    def __init__(self, email: str):
        self.email = email

def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token using shared secret"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    return token_data

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get the current authenticated user by validating JWT token"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    # Validate token with auth service to ensure user still exists and is active
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{AUTH_SERVICE_URL}/auth/me", headers=headers, timeout=5)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_data = response.json()
        return user_data
        
    except requests.RequestException:
        # Fallback to basic token validation if auth service is unavailable
        return {"email": token_data.email, "id": None, "username": "unknown"}

# Rate limiting storage (in-memory for demo - use Redis in production)
_rate_limit_storage = {}

def check_rate_limit(key: str, max_requests: int = 5, window_minutes: int = 15) -> bool:
    """Simple in-memory rate limiting - replace with Redis in production"""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    
    if key not in _rate_limit_storage:
        _rate_limit_storage[key] = []
    
    # Remove old requests outside the window
    _rate_limit_storage[key] = [
        req_time for req_time in _rate_limit_storage[key] 
        if req_time > window_start
    ]
    
    # Check if rate limit exceeded
    if len(_rate_limit_storage[key]) >= max_requests:
        return False
    
    # Add current request
    _rate_limit_storage[key].append(now)
    return True

def rate_limit_check(max_requests: int = 5, window_minutes: int = 15):
    """Rate limiting decorator"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get user from request (assumes get_current_user dependency is used)
            current_user = kwargs.get('current_user')
            if current_user:
                key = f"user_{current_user.get('id', current_user.get('email'))}"
            else:
                # Fallback to IP-based limiting if no user
                key = "anonymous"
            
            if not check_rate_limit(key, max_requests, window_minutes):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {max_requests} requests per {window_minutes} minutes."
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator