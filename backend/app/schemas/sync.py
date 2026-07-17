from pydantic import BaseModel, Field

from app.schemas.inspeccion import InspeccionIn


class SyncBatchIn(BaseModel):
    inspecciones: list[InspeccionIn] = Field(default_factory=list)


class SyncItemResult(BaseModel):
    id: str
    status: str  # created | updated | skipped_finalizada | skipped_older
    server_updated_at: str | None = None


class SyncBatchOut(BaseModel):
    results: list[SyncItemResult]
