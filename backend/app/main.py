import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import auth, catalogo, inspecciones, reportes, slides, sync, verificar

app = FastAPI(
    title="Verificación Periódica ISH y SDC — API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS abierto para la PWA (en producción el mismo dominio vía Caddy).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(inspecciones.router)
app.include_router(slides.router)
app.include_router(sync.router)
app.include_router(reportes.router)
app.include_router(verificar.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


# Servir los reportes generados (PDF/HTML) directamente.
# En producción Caddy sirve /reports/* desde el volumen; esto es el respaldo
# para desarrollo local sin proxy.
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
app.mount("/reports", StaticFiles(directory=settings.REPORTS_DIR), name="reports")
