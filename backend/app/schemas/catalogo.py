from pydantic import BaseModel


class CatalogoElementoOut(BaseModel):
    codigo: str
    instalacion: str
    sistema: str
    nombre: str
    tipo: str
    ups_dobles: bool
    orden: int

    class Config:
        from_attributes = True
