from datetime import date, datetime

from pydantic import BaseModel, Field


class RegistroIn(BaseModel):
    id: str  # UUID de cliente
    catalogo_codigo: str

    estado: str | None = None  # OK | MALO | OBSERVACION
    comentario: str | None = None
    valor_a: str | None = None
    valor_b: str | None = None

    fuente_1: bool | None = None
    bateria_1: bool | None = None
    fan_1: bool | None = None
    fuente_2: bool | None = None
    bateria_2: bool | None = None
    fan_2: bool | None = None
    fuente_3: bool | None = None
    bateria_3: bool | None = None
    fan_3: bool | None = None
    fuente_4: bool | None = None
    bateria_4: bool | None = None
    fan_4: bool | None = None


class RegistroOut(RegistroIn):
    class Config:
        from_attributes = True


class InspeccionIn(BaseModel):
    id: str  # UUID de cliente
    fecha: date
    inspeccionado_por_nombre: str = ""
    verificado_por_nombre: str = ""
    aprobado_por_nombre: str = ""
    observaciones_generales: str = ""
    client_updated_at: datetime | None = None
    registros: list[RegistroIn] = Field(default_factory=list)


class InspeccionOut(BaseModel):
    id: str
    fecha: date
    inspeccionado_por_nombre: str
    verificado_por_nombre: str
    aprobado_por_nombre: str
    observaciones_generales: str
    estado: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    registros: list[RegistroOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class InspeccionListItem(BaseModel):
    id: str
    fecha: date
    estado: str
    created_by: str
    updated_at: datetime

    class Config:
        from_attributes = True
