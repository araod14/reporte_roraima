from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, FiniteFloat, field_validator


class DatosDiario(BaseModel):
    fecha: date
    hora: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    responsable: str = Field(default="", max_length=120)
    lcn_a: Literal["OK", "SUSPECT"] | None = None
    lcn_b: Literal["OK", "SUSPECT"] | None = None
    gus: dict[str, Literal["OK", "MALO", "OBSERVACION"]] = Field(default_factory=dict)
    temperatura_ish1: FiniteFloat | None = None
    temperatura_ish2: FiniteFloat | None = None
    observaciones: str = Field(default="", max_length=1000)


class DiarioIn(BaseModel):
    id: UUID
    datos: DatosDiario
    version: int = Field(default=0, ge=0)
    client_updated_at: datetime

    @field_validator("client_updated_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Se requiere zona horaria")
        return value


class CierreDiario(BaseModel):
    version: int = Field(ge=0)
    client_updated_at: datetime


class ReabrirDiario(BaseModel):
    version: int = Field(ge=1)


class LoteDiarios(BaseModel):
    diarios: list[DiarioIn] = Field(max_length=100)
