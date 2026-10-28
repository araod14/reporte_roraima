from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class LibraryDocument(Base):
    __tablename__ = "library_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pages: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_pages: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LibraryChunk(Base):
    __tablename__ = "library_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("library_documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(2), default="en")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    __table_args__ = (UniqueConstraint("document_id", "page", "content_hash", name="uq_library_chunk_page_hash"),)


class LibraryConversation(Base):
    __tablename__ = "library_conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Nueva conversación")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LibraryMessage(Base):
    __tablename__ = "library_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("library_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    usage_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InventoryState(Base):
    __tablename__ = "inventory_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet: Mapped[str] = mapped_column(String(100), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    part_number: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sap_pz: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sap_pdvsa: Mapped[str] = mapped_column(Text, default="", nullable=False)
    manufacturer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    quantity: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    equipment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(Text, default="", nullable=False)
    shelf: Mapped[str] = mapped_column(Text, default="", nullable=False)
    __table_args__ = (UniqueConstraint("sheet", "row_number", name="uq_inventory_sheet_row"),)
