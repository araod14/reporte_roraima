from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.inspeccion import ESTADO_FINALIZADA, Inspeccion, Registro
from app.schemas.inspeccion import InspeccionIn

_REGISTRO_FIELDS = (
    "estado", "comentario", "valor_a", "valor_b",
    "fuente_1", "bateria_1", "fan_1",
    "fuente_2", "bateria_2", "fan_2",
    "fuente_3", "bateria_3", "fan_3",
    "fuente_4", "bateria_4", "fan_4",
)


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def upsert_inspeccion(
    db: Session, data: InspeccionIn, username: str
) -> tuple[Inspeccion, str]:
    """Inserta o actualiza una inspección de forma idempotente (por UUID).

    Devuelve (inspeccion, status) donde status ∈
    {created, updated, skipped_finalizada, skipped_older}.
    """
    existing = db.get(Inspeccion, data.id)
    incoming_ts = _as_utc(data.client_updated_at)

    if existing is not None:
        # Una inspección finalizada es de solo lectura.
        if existing.estado == ESTADO_FINALIZADA:
            return existing, "skipped_finalizada"
        # Gana el más reciente según el reloj del cliente.
        if _as_utc(existing.client_updated_at) > incoming_ts:
            return existing, "skipped_older"
        insp = existing
        status = "updated"
    else:
        insp = Inspeccion(id=data.id, created_by=username)
        db.add(insp)
        status = "created"

    insp.fecha = data.fecha
    insp.inspeccionado_por_nombre = data.inspeccionado_por_nombre
    insp.verificado_por_nombre = data.verificado_por_nombre
    insp.aprobado_por_nombre = data.aprobado_por_nombre
    insp.observaciones_generales = data.observaciones_generales
    insp.client_updated_at = incoming_ts

    # Reemplazo total de registros (el cliente envía el estado completo).
    insp.registros.clear()
    db.flush()
    for r in data.registros:
        reg = Registro(id=r.id, inspeccion_id=insp.id, catalogo_codigo=r.catalogo_codigo)
        for field in _REGISTRO_FIELDS:
            setattr(reg, field, getattr(r, field))
        insp.registros.append(reg)

    db.commit()
    db.refresh(insp)
    return insp, status
