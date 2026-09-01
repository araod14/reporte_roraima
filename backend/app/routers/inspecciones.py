from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.inspeccion import ESTADO_BORRADOR, ESTADO_FINALIZADA, Inspeccion
from app.models.user import User
from app.routers.reportes import reporte_to_out
from app.schemas.inspeccion import InspeccionIn, InspeccionListItem, InspeccionOut
from app.schemas.reporte import ReporteOut
from app.services.inspeccion_service import upsert_inspeccion
from app.services.report_service import forced_bad_with_invalid_comment, generar_reporte

router = APIRouter(prefix="/api/inspecciones", tags=["inspecciones"])


@router.get("", response_model=list[InspeccionListItem])
def listar(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[Inspeccion]:
    return db.query(Inspeccion).order_by(Inspeccion.updated_at.desc()).all()


@router.get("/{inspeccion_id}", response_model=InspeccionOut)
def obtener(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Inspeccion:
    insp = db.get(Inspeccion, inspeccion_id)
    if insp is None:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")
    return insp


@router.put("/{inspeccion_id}", response_model=InspeccionOut)
def crear_o_actualizar(
    inspeccion_id: str,
    data: InspeccionIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Inspeccion:
    if data.id != inspeccion_id:
        raise HTTPException(status_code=400, detail="El id del cuerpo no coincide con la URL")
    insp, status = upsert_inspeccion(db, data, current.username)
    if status == "skipped_finalizada":
        raise HTTPException(status_code=409, detail="La inspección ya está finalizada (solo lectura)")
    return insp


@router.post("/{inspeccion_id}/finalizar", response_model=ReporteOut)
def finalizar(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ReporteOut:
    insp = db.get(Inspeccion, inspeccion_id)
    if insp is None:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")
    if insp.estado == ESTADO_FINALIZADA:
        raise HTTPException(
            status_code=409,
            detail="La inspección ya está finalizada. Para corregir, cree una nueva versión.",
        )
    comentario_invalido = forced_bad_with_invalid_comment(db, insp)
    if comentario_invalido:
        raise HTTPException(
            status_code=422,
            detail=(
                "Agregue un comentario de 1 a 20 palabras para los equipos "
                f"marcados MALO: {', '.join(comentario_invalido)}"
            ),
        )
    reporte = generar_reporte(db, insp, current.username)
    return reporte_to_out(reporte)


@router.post("/{inspeccion_id}/reabrir", response_model=InspeccionOut)
def reabrir(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Inspeccion:
    """Reabre una inspección finalizada para corregirla. Al volver a finalizar
    se genera una nueva versión (v2, v3…); las versiones previas y sus archivos
    y hashes quedan intactos."""
    insp = db.get(Inspeccion, inspeccion_id)
    if insp is None:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")
    insp.estado = ESTADO_BORRADOR
    db.commit()
    db.refresh(insp)
    return insp
