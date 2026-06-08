# Pydantic schemas for Auth Forum API

from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import Optional, List
import re
import html
from models import UserRole

# User schemas
class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Valid email address")
    username: str = Field(..., min_length=3, max_length=30, description="Username between 3-30 characters")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name up to 100 characters")
    bio: Optional[str] = Field(None, max_length=500, description="Bio up to 500 characters")
    
    @validator('username')
    def validate_username(cls, v):
        # Allow alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()
    
    @validator('full_name')
    def validate_full_name(cls, v):
        # Basic sanitization
        return html.escape(v.strip())
    
    @validator('bio')
    def validate_bio(cls, v):
        if v is None:
            return v
        # Sanitize HTML and limit length
        return html.escape(v.strip())

class UserCreate(UserBase):
    password: str = Field(..., min_length=12, max_length=128, description="Password between 12-128 characters with uppercase, lowercase, number, and special character")
    
    @validator('password')
    def validate_password(cls, v):
        # Enhanced password strength requirements
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        
        # Check against common weak passwords
        weak_passwords = {
            'password123', '123456789', 'qwerty123', 'admin123', 'letmein123',
            'welcome123', 'password1234', 'administrator', 'root123456',
            'Password123!', 'Welcome123!', 'Admin123!'
        }
        if v.lower() in [pwd.lower() for pwd in weak_passwords]:
            raise ValueError('Password is too common. Please choose a stronger password')
        
        # Check for repeated characters (more than 3 consecutive)
        if re.search(r'(.)\1{3,}', v):
            raise ValueError('Password cannot contain more than 3 consecutive identical characters')
        
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None

class UserRoleUpdate(BaseModel):
    role: UserRole

class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Public user schema for forum responses (excludes sensitive data like email)
class PublicUser(BaseModel):
    id: int
    username: str
    full_name: str
    bio: Optional[str] = None
    role: UserRole

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int  # Access token expiration in seconds

class TokenRefresh(BaseModel):
    refresh_token: str

class TokenRevoke(BaseModel):
    token: str

class TokenData(BaseModel):
    email: Optional[str] = None
    token_type: Optional[str] = None
    jti: Optional[str] = None

# Post schemas
class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Post title up to 200 characters")
    content: str = Field(..., min_length=1, max_length=10000, description="Post content up to 10,000 characters")
    
    @validator('title')
    def validate_title(cls, v):
        # Sanitize HTML tags
        return html.escape(v.strip())
    
    @validator('content')
    def validate_content(cls, v):
        # Sanitize HTML tags but preserve newlines
        return html.escape(v.strip())

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class PostResponse(PostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    author: PublicUser

    class Config:
        from_attributes = True

# Comment schemas
class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="Comment content up to 2,000 characters")
    
    @validator('content')
    def validate_content(cls, v):
        # Sanitize HTML tags
        return html.escape(v.strip())

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = None

class CommentResponse(CommentBase):
    id: int
    post_id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    author: PublicUser

    class Config:
        from_attributes = True