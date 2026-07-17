from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.reporte import Reporte
from app.models.user import User
from app.schemas.reporte import ReporteOut

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def reporte_to_out(rep: Reporte) -> ReporteOut:
    base = settings.BASE_URL.rstrip("/")
    return ReporteOut(
        inspeccion_id=rep.inspeccion_id,
        version=rep.version,
        fecha_generacion=rep.fecha_generacion,
        generado_por=rep.generado_por,
        pdf_sha256=rep.pdf_sha256,
        html_sha256=rep.html_sha256,
        content_hash=rep.content_hash,
        pdf_hash_short=rep.pdf_hash_short,
        pdf_url=f"{base}/reports/{rep.inspeccion_id}/v{rep.version}.pdf",
        html_url=f"{base}/reports/{rep.inspeccion_id}/v{rep.version}.html",
        verificar_url=f"{base}/verificar/{rep.inspeccion_id}/{rep.version}",
    )


@router.get("/{inspeccion_id}", response_model=list[ReporteOut])
def listar_reportes(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ReporteOut]:
    reportes = (
        db.query(Reporte)
        .filter(Reporte.inspeccion_id == inspeccion_id)
        .order_by(Reporte.version)
        .all()
    )
    return [reporte_to_out(r) for r in reportes]
