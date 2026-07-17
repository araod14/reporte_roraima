from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Tipos de elemento:
#   SIMPLE -> estado OK/MALO/OBSERVACION + comentario
#   CCC    -> igual que SIMPLE + valor_a / valor_b
#   UPS    -> checkboxes fuente/bateria/fan (x2, o x4 si ups_dobles)
TIPO_SIMPLE = "SIMPLE"
TIPO_CCC = "CCC"
TIPO_UPS = "UPS"


class CatalogoElemento(Base):
    """Catálogo fijo de elementos a inspeccionar (cargado por el seed)."""

    __tablename__ = "catalogo_elementos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Clave estable e idempotente: "{instalacion}|{sistema}|{nombre}"
    codigo: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    instalacion: Mapped[str] = mapped_column(String(10))  # SDC | ISH-1 | ISH-2
    sistema: Mapped[str] = mapped_column(String(10))  # LCN | PCN | MANT | ...
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(10))  # SIMPLE | CCC | UPS
    ups_dobles: Mapped[bool] = mapped_column(Boolean, default=False)
    orden: Mapped[int] = mapped_column(Integer, default=0)
