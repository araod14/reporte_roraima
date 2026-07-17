from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Reporte(Base):
    """Una versión finalizada de un reporte. Nunca se sobreescribe."""

    __tablename__ = "reportes"
    __table_args__ = (
        UniqueConstraint("inspeccion_id", "version", name="uq_reporte_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspeccion_id: Mapped[str] = mapped_column(
        ForeignKey("inspecciones.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)

    pdf_path: Mapped[str] = mapped_column(String(255))
    html_path: Mapped[str] = mapped_column(String(255))

    pdf_sha256: Mapped[str] = mapped_column(String(64))
    html_sha256: Mapped[str] = mapped_column(String(64))
    # Hash sobre el JSON canónico de los datos congelados (estampable en el PDF).
    content_hash: Mapped[str] = mapped_column(String(64))
    pdf_hash_short: Mapped[str] = mapped_column(String(16))

    fecha_generacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    generado_por: Mapped[str] = mapped_column(String(50))

    inspeccion: Mapped["Inspeccion"] = relationship(back_populates="reportes")
