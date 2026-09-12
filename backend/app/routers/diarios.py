from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.diario import Diario, VersionDiario
from app.models.user import User
from app.schemas.diario import CierreDiario, DiarioIn, LoteDiarios, ReabrirDiario
from app.services.diario_service import finalizar_diario, lock_diario, upsert_diario, utc

router = APIRouter(prefix="/api/diarios", tags=["diarios"])


def version_out(rep):
    return {
        "version": rep.version, "fecha": rep.datos["fecha"], "hora": rep.datos["hora"],
        "png_url": f"/api/diarios/{rep.diario_id}/versiones/{rep.version}/imagen",
        "png_sha256": rep.png_sha256, "content_hash": rep.content_hash,
        "fecha_generacion": utc(rep.fecha_generacion).isoformat(),
        "generado_por": rep.generado_por,
    }


def diario_out(db, item):
    versions = db.scalars(select(VersionDiario).where(VersionDiario.diario_id == item.id)
                          .order_by(VersionDiario.version)).all()
    return {
        "id": item.id, "datos": item.datos, "estado": item.estado,
        "version": item.version, "created_by": item.created_by,
        "client_updated_at": utc(item.client_updated_at).isoformat(),
        "server_updated_at": utc(item.updated_at).isoformat(),
        "versiones": [version_out(v) for v in versions],
    }


def required(item):
    if item is None:
        raise HTTPException(404, "Reporte diario no encontrado")
    return item


@router.get("")
def listar(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [diario_out(db, item) for item in db.scalars(select(Diario).order_by(Diario.updated_at.desc()))]


@router.post("/sync")
def sincronizar(data: LoteDiarios, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = []
    for entry in sorted(data.diarios, key=lambda entry: str(entry.id)):
        item, status = upsert_diario(db, entry, user.username)
        results.append({"status": status, "diario": diario_out(db, item)})
    db.commit()
    return {"results": results}


@router.get("/{diario_id}")
def obtener(diario_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return diario_out(db, required(db.get(Diario, str(diario_id))))


@router.put("/{diario_id}")
def guardar(diario_id: UUID, data: DiarioIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if diario_id != data.id:
        raise HTTPException(400, "El id no coincide con la URL")
    item, status = upsert_diario(db, data, user.username)
    result = {"status": status, "diario": diario_out(db, item)}
    db.commit()
    return result


@router.post("/{diario_id}/finalizar")
def finalizar(diario_id: UUID, data: CierreDiario, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = required(lock_diario(db, str(diario_id)))
    if utc(item.client_updated_at) != utc(data.client_updated_at):
        raise HTTPException(409, "El reporte cambió en otro dispositivo. Sincronice y revise los datos")
    if item.estado == "FINALIZADA" and item.version == data.version + 1:
        result = diario_out(db, item)  # Reintento del mismo cierre.
        db.commit()
        return result
    if item.estado != "BORRADOR" or item.version != data.version:
        raise HTTPException(409, "La versión cambió. Sincronice y revise el reporte")
    finalizar_diario(db, item, user.username)
    result = diario_out(db, item)
    db.commit()
    return result


@router.post("/{diario_id}/reabrir")
def reabrir(diario_id: UUID, data: ReabrirDiario, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = required(lock_diario(db, str(diario_id)))
    if item.version != data.version:
        raise HTTPException(409, "La versión cambió. Sincronice el reporte")
    if item.estado == "FINALIZADA":
        item.estado = "BORRADOR"
        item.client_updated_at = datetime.now(timezone.utc)
        item.updated_at = item.client_updated_at
    result = diario_out(db, item)
    db.commit()
    return result


@router.get("/{diario_id}/versiones")
def versiones(diario_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return diario_out(db, required(db.get(Diario, str(diario_id))))["versiones"]


@router.get("/{diario_id}/versiones/{version}/imagen")
def imagen(diario_id: UUID, version: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = db.scalar(select(VersionDiario).where(VersionDiario.diario_id == str(diario_id), VersionDiario.version == version))
    if rep is None:
        raise HTTPException(404, "Versión no encontrada")
    return FileResponse(rep.png_path, media_type="image/png",
                        filename=f"reporte-diario-{rep.datos['fecha']}-{rep.datos['hora'].replace(':', '')}-v{version}.png")
