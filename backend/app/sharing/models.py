import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SharedStudy(Base):
    __tablename__ = 'shared_studies'
    __table_args__ = (Index('ux_shared_studies_public_id_hash', 'public_id_hash', unique=True), Index('ix_shared_studies_public_listing', 'visibility', 'revoked_at', 'created_at'))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    source_study_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('study_sessions.id', ondelete='SET NULL'), nullable=True)
    public_id_hash: Mapped[str] = mapped_column(String(64))
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    session_type: Mapped[str] = mapped_column(String(30), default='study')
    messages_snapshot: Mapped[list] = mapped_column(JSON)
    sources_snapshot: Mapped[list] = mapped_column(JSON)
    visibility: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
