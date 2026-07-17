from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ESTADO_BORRADOR = "BORRADOR"
ESTADO_FINALIZADA = "FINALIZADA"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Inspeccion(Base):
    __tablename__ = "inspecciones"

    # UUID generado en el cliente (idempotente para sync offline).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    fecha: Mapped[date] = mapped_column(Date)
    inspeccionado_por_nombre: Mapped[str] = mapped_column(String(120), default="")
    verificado_por_nombre: Mapped[str] = mapped_column(String(120), default="")
    aprobado_por_nombre: Mapped[str] = mapped_column(String(120), default="")
    observaciones_generales: Mapped[str] = mapped_column(Text, default="")

    estado: Mapped[str] = mapped_column(String(12), default=ESTADO_BORRADOR)

    created_by: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    # Timestamp del cliente al editar (para resolver "gana el más reciente").
    client_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    registros: Mapped[list["Registro"]] = relationship(
        back_populates="inspeccion",
        cascade="all, delete-orphan",
        order_by="Registro.catalogo_codigo",
    )
    reportes: Mapped[list["Reporte"]] = relationship(back_populates="inspeccion")


class Registro(Base):
    """Valores capturados para un elemento del catálogo en una inspección."""

    __tablename__ = "registros"
    __table_args__ = (
        UniqueConstraint("inspeccion_id", "catalogo_codigo", name="uq_registro_elemento"),
    )

    # UUID de cliente (idempotente).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspeccion_id: Mapped[str] = mapped_column(
        ForeignKey("inspecciones.id", ondelete="CASCADE"), index=True
    )
    catalogo_codigo: Mapped[str] = mapped_column(String(120), index=True)

    # SIMPLE / CCC
    estado: Mapped[str | None] = mapped_column(String(12), nullable=True)  # OK|MALO|OBSERVACION
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_a: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valor_b: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # UPS (fuente/batería/fan). 1..2 siempre; 3..4 solo en ups_dobles.
    fuente_1: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bateria_1: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fan_1: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuente_2: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bateria_2: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fan_2: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuente_3: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bateria_3: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fan_3: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuente_4: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bateria_4: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fan_4: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    inspeccion: Mapped["Inspeccion"] = relationship(back_populates="registros")
