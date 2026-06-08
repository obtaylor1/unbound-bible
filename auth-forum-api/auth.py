# Authentication utilities for Auth Forum API

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from database import get_db
from models import User, UserRole
from schemas import TokenData

# Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required for security. "
        "Please set a strong secret key (minimum 32 characters) in your environment variables."
    )

# Validate secret key strength
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be at least 32 characters long for security. "
        f"Current length: {len(SECRET_KEY)}"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour for better security
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days for refresh token

# Token blacklist for revoked tokens (use Redis in production)
_token_blacklist = set()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token with enhanced security"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add additional security claims
    issued_at = datetime.utcnow()
    to_encode.update({
        "exp": expire,
        "iat": issued_at,
        "type": "access",
        "jti": f"{data.get('sub', 'unknown')}_{int(issued_at.timestamp())}"
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create a refresh token for long-term authentication"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    issued_at = datetime.utcnow()
    
    to_encode.update({
        "exp": expire,
        "iat": issued_at,
        "type": "refresh",
        "jti": f"refresh_{data.get('sub', 'unknown')}_{int(issued_at.timestamp())}"
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def revoke_token(token: str) -> bool:
    """Add token to blacklist for revocation"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti:
            _token_blacklist.add(jti)
            return True
    except JWTError:
        pass
    return False

def is_token_revoked(token: str) -> bool:
    """Check if token is in blacklist"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        return jti in _token_blacklist
    except JWTError:
        return True  # Invalid tokens are considered revoked

def verify_token(token: str, token_type: str = "access") -> TokenData:
    """Verify and decode a JWT token with enhanced security checks"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Check if token is blacklisted
        if is_token_revoked(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        token_type_claim: Optional[str] = payload.get("type")
        
        if email is None:
            raise credentials_exception
        
        # Verify token type matches expected type
        if token_type_claim != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    return token_data

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not getattr(user, 'is_active', True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

def get_current_active_moderator(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify they are a moderator"""
    if getattr(current_user, 'role', None) != UserRole.moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user