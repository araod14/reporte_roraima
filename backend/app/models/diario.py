"""Capturas diarias y sus imágenes inmutables."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class Diario(Base):
    __tablename__ = "diarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    datos: Mapped[dict] = mapped_column(JSON)
    estado: Mapped[str] = mapped_column(String(12), default="BORRADOR")
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(50))
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VersionDiario(Base):
    __tablename__ = "versiones_diario"
    __table_args__ = (UniqueConstraint("diario_id", "version", name="uq_diario_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diario_id: Mapped[str] = mapped_column(ForeignKey("diarios.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    datos: Mapped[dict] = mapped_column(JSON)
    png_path: Mapped[str] = mapped_column(String(255))
    png_sha256: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    generado_por: Mapped[str] = mapped_column(String(50))
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
