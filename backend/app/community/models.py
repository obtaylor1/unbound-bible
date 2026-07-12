import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CommunityPost(Base):
    __tablename__ = 'community_posts'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    author = relationship('User')
    comments: Mapped[list['CommunityComment']] = relationship(back_populates='post', cascade='all, delete-orphan')


class CommunityComment(Base):
    __tablename__ = 'community_comments'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('community_posts.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    post: Mapped[CommunityPost] = relationship(back_populates='comments')
    author = relationship('User')
