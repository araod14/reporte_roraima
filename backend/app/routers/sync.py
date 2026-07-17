from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.sync import SyncBatchIn, SyncBatchOut, SyncItemResult
from app.services.inspeccion_service import upsert_inspeccion

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/batch", response_model=SyncBatchOut)
def sync_batch(
    payload: SyncBatchIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> SyncBatchOut:
    """Sincronización por lotes. Idempotente por UUID: reenviar el mismo lote no
    genera duplicados. Devuelve el resultado por cada inspección."""
    results: list[SyncItemResult] = []
    for insp_in in payload.inspecciones:
        insp, status = upsert_inspeccion(db, insp_in, current.username)
        results.append(
            SyncItemResult(
                id=insp.id,
                status=status,
                server_updated_at=insp.updated_at.isoformat() if insp.updated_at else None,
            )
        )
    return SyncBatchOut(results=results)
