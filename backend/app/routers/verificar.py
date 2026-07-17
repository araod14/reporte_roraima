from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.inspeccion import Inspeccion
from app.models.reporte import Reporte

router = APIRouter(tags=["verificar"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/verificar/{inspeccion_id}/{version}", response_class=HTMLResponse)
def verificar(
    inspeccion_id: str,
    version: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Página pública (sin auth) para confirmar la autenticidad de un reporte.

    Muestra los metadatos y hashes registrados y permite arrastrar el PDF
    recibido para comparar su SHA-256 contra el que quedó guardado al finalizar.
    """
    rep = (
        db.query(Reporte)
        .filter(Reporte.inspeccion_id == inspeccion_id, Reporte.version == version)
        .first()
    )
    insp = db.get(Inspeccion, inspeccion_id)
    base = settings.BASE_URL.rstrip("/")
    return templates.TemplateResponse(
        "verificar.html.j2",
        {
            "request": request,
            "reporte": rep,
            "inspeccion": insp,
            "pdf_url": f"{base}/reports/{inspeccion_id}/v{version}.pdf" if rep else None,
            "html_url": f"{base}/reports/{inspeccion_id}/v{version}.html" if rep else None,
        },
    )
