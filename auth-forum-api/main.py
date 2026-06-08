# Auth Forum API - Separate FastAPI Service
# User authentication and forum management system

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db
from models import Base, User, Post, Comment, UserRole
from schemas import (
    UserCreate, UserLogin, UserResponse, UserUpdate, UserRoleUpdate, Token, TokenRefresh, TokenRevoke, PublicUser,
    PostCreate, PostUpdate, PostResponse,
    CommentCreate, CommentUpdate, CommentResponse
)
from auth import (
    create_access_token, create_refresh_token, verify_token, get_current_user, get_current_active_moderator,
    verify_password, get_password_hash, revoke_token, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Auth Forum API",
    description="Authentication and Forum Management Service",
    version="1.0.0"
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Health check
@app.get("/")
def read_root():
    return {"message": "Auth Forum API is running!", "status": "healthy"}

# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse)
@limiter.limit("5/hour")  # Rate limit: 5 registrations per hour per IP
def register_user(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="Email already registered"
        )
    
    # Check if username is taken
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        role=UserRole.member
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@app.post("/auth/login", response_model=Token)
@limiter.limit("10/15minutes")  # Rate limit: 10 login attempts per 15 minutes per IP
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token"""
    user = db.query(User).filter(User.email == user_credentials.email).first()
    
    if not user or not verify_password(user_credentials.password, getattr(user, 'hashed_password', '')):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    if not getattr(user, 'is_active', True):
        raise HTTPException(
            status_code=401,
            detail="Account is disabled"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }

@app.get("/auth/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user

@app.put("/auth/profile", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    # Check if new email is already taken by another user
    if user_update.email and user_update.email != current_user.email:
        existing_email = db.query(User).filter(
            User.email == user_update.email,
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already in use"
            )
    
    # Check if new username is already taken by another user
    if user_update.username and user_update.username != current_user.username:
        existing_username = db.query(User).filter(
            User.username == user_update.username,
            User.id != current_user.id
        ).first()
        if existing_username:
            raise HTTPException(
                status_code=400,
                detail="Username already taken"
            )
    
    # Update user fields
    if user_update.email:
        setattr(current_user, 'email', user_update.email)
    if user_update.username:
        setattr(current_user, 'username', user_update.username)
    if user_update.full_name:
        setattr(current_user, 'full_name', user_update.full_name)
    if user_update.bio:
        setattr(current_user, 'bio', user_update.bio)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

# Token Management endpoints
@app.post("/auth/refresh", response_model=Token)
def refresh_token_endpoint(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        token_payload = verify_token(token_data.refresh_token, token_type="refresh")
        
        # Get user to ensure they still exist and are active
        user = db.query(User).filter(User.email == token_payload.email).first()
        if not user or not getattr(user, 'is_active', True):
            raise HTTPException(
                status_code=401,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        new_access_token = create_access_token(data={"sub": user.email})
        new_refresh_token = create_refresh_token(data={"sub": user.email})
        
        # Optionally revoke the old refresh token
        revoke_token(token_data.refresh_token)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )

@app.post("/auth/revoke")
def revoke_token_endpoint(
    token_data: TokenRevoke,
    current_user: User = Depends(get_current_user)
):
    """Revoke a token (logout)"""
    success = revoke_token(token_data.token)
    if success:
        return {"message": "Token revoked successfully"}
    else:
        return {"message": "Token revocation failed or token already invalid"}

@app.post("/auth/logout")
def logout_endpoint(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Logout current user by revoking their token"""
    token = credentials.credentials
    success = revoke_token(token)
    if success:
        return {"message": "Logged out successfully"}
    else:
        return {"message": "Logout failed"}

# Role Management (Moderator only)
@app.put("/admin/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    current_moderator: User = Depends(get_current_active_moderator),
    db: Session = Depends(get_db)
):
    """Update a user's role (moderators only)"""
    # Find the target user
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent moderators from changing their own role (security best practice)
    target_user_id = getattr(target_user, 'id', None)
    current_moderator_id = getattr(current_moderator, 'id', None)
    if target_user_id == current_moderator_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot change your own role"
        )
    
    # Update the role
    setattr(target_user, 'role', role_update.role)
    
    db.commit()
    db.refresh(target_user)
    
    return target_user

# Forum Posts endpoints
@app.get("/posts", response_model=List[PostResponse])
def get_posts(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Get all forum posts"""
    posts = db.query(Post).offset(skip).limit(limit).all()
    return posts

@app.post("/posts", response_model=PostResponse)
def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new forum post"""
    db_post = Post(
        title=post_data.title,
        content=post_data.content,
        author_id=current_user.id
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    return db_post

@app.get("/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """Get a specific post"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.put("/posts/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    post_update: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a forum post"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if user owns the post or is a moderator
    post_author_id = getattr(post, 'author_id', None)
    current_user_id = getattr(current_user, 'id', None)
    current_user_role = getattr(current_user, 'role', None)
    if post_author_id != current_user_id and current_user_role != UserRole.moderator:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this post"
        )
    
    if post_update.title:
        setattr(post, 'title', post_update.title)
    if post_update.content:
        setattr(post, 'content', post_update.content)
    
    db.commit()
    db.refresh(post)
    
    return post

@app.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a forum post"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if user owns the post or is a moderator
    post_author_id = getattr(post, 'author_id', None)
    current_user_id = getattr(current_user, 'id', None)
    current_user_role = getattr(current_user, 'role', None)
    if post_author_id != current_user_id and current_user_role != UserRole.moderator:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this post"
        )
    
    db.delete(post)
    db.commit()
    
    return {"message": "Post deleted successfully"}

# Forum Comments endpoints
@app.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
def get_post_comments(post_id: int, db: Session = Depends(get_db)):
    """Get all comments for a post"""
    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    return comments

@app.post("/posts/{post_id}/comments", response_model=CommentResponse)
def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a comment on a post"""
    # Check if post exists
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db_comment = Comment(
        content=comment_data.content,
        post_id=post_id,
        author_id=current_user.id
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return db_comment

@app.put("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a comment"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if user owns the comment or is a moderator
    comment_author_id = getattr(comment, 'author_id', None)
    current_user_id = getattr(current_user, 'id', None)
    current_user_role = getattr(current_user, 'role', None)
    if comment_author_id != current_user_id and current_user_role != UserRole.moderator:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this comment"
        )
    
    if comment_update.content:
        setattr(comment, 'content', comment_update.content)
    
    db.commit()
    db.refresh(comment)
    
    return comment

@app.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a comment"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if user owns the comment or is a moderator
    comment_author_id = getattr(comment, 'author_id', None)
    current_user_id = getattr(current_user, 'id', None)
    current_user_role = getattr(current_user, 'role', None)
    if comment_author_id != current_user_id and current_user_role != UserRole.moderator:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this comment"
        )
    
    db.delete(comment)
    db.commit()
    
    return {"message": "Comment deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)