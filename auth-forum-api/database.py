# Database configuration for Auth Forum API

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use the same PostgreSQL database but different schema/table prefix
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Create engine with configuration for PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=False  # Set to True for SQL query logging
)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()