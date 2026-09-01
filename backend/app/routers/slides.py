from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.inspeccion import Inspeccion
from app.models.user import User
from app.services.slides_service import render_slides_html, render_slides_pdf

router = APIRouter(prefix="/api/inspecciones", tags=["slides"])


def _get_insp(db: Session, inspeccion_id: str) -> Inspeccion:
    insp = db.get(Inspeccion, inspeccion_id)
    if insp is None:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")
    return insp


@router.get("/{inspeccion_id}/slides.html", response_class=HTMLResponse)
def slides_html(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> HTMLResponse:
    """Panel sinóptico interactivo (vista visual regenerable, sin hash)."""
    insp = _get_insp(db, inspeccion_id)
    return HTMLResponse(render_slides_html(db, insp, current.username))


@router.get("/{inspeccion_id}/slides.pdf")
def slides_pdf(
    inspeccion_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    """Panel sinóptico en PDF vertical, optimizado para compartir por teléfono."""
    insp = _get_insp(db, inspeccion_id)
    pdf = render_slides_pdf(db, insp, current.username)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="panel_{inspeccion_id}.pdf"'},
    )
