from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.catalogo import CatalogoElemento
from app.models.user import User
from app.schemas.catalogo import CatalogoElementoOut

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])


@router.get("", response_model=list[CatalogoElementoOut])
def listar_catalogo(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[CatalogoElemento]:
    return db.query(CatalogoElemento).order_by(CatalogoElemento.orden).all()
