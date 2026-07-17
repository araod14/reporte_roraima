from datetime import datetime

from pydantic import BaseModel


class ReporteOut(BaseModel):
    inspeccion_id: str
    version: int
    fecha_generacion: datetime
    generado_por: str
    pdf_sha256: str
    html_sha256: str
    content_hash: str
    pdf_hash_short: str
    pdf_url: str
    html_url: str
    verificar_url: str

    class Config:
        from_attributes = True
