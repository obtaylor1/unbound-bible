#!/usr/bin/env python3
"""
Dead Sea Scrolls Reference Model

This model stores metadata-only references to Dead Sea Scrolls fragments,
respecting the Israel Antiquities Authority's rights while providing
scholarly links to the Leon Levy DSS Digital Library.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, backend_path)

from models import Base

class DssReference(Base):
    """
    Dead Sea Scrolls Reference Model
    
    Stores metadata-only references to DSS fragments with links to
    the official Israel Antiquities Authority digital library.
    No actual manuscript text is stored to respect copyright.
    """
    __tablename__ = "dss_references"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # DSS fragment identification
    fragment_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Biblical scripture reference (e.g., "1QIsa 40:3-5")
    scripture_ref = Column(String(100), nullable=False, index=True)
    
    # Official IAA Leon Levy DSS Digital Library URL
    iaa_url = Column(Text, nullable=False)
    
    # Additional metadata for scholarly reference
    cave_number = Column(String(10), nullable=True)
    scroll_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<DssReference(fragment_id='{self.fragment_id}', scripture_ref='{self.scripture_ref}')>"