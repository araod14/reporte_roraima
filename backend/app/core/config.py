from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (ver .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    DATABASE_URL: str = "postgresql+psycopg://roraima:roraima@localhost:5432/roraima"

    # Seguridad / JWT
    JWT_SECRET: str = "CAMBIA-ESTE-SECRETO-EN-PRODUCCION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    # URL pública base (para el QR de verificación estampado en el PDF).
    # Ej: https://reportes.midominio.com
    BASE_URL: str = "http://localhost:8000"

    # Directorio donde se guardan los reportes generados (volumen persistente).
    REPORTS_DIR: str = "/var/reports"

    # Contraseña inicial de los usuarios creados por el seed.
    SEED_PASSWORD: str = "roraima2026"

    # Biblioteca TPS: sin credenciales ni acceso por defecto.
    LIBRARY_PDF_DIR: str = "/var/tps-pdfs"
    LIBRARY_GEMINI_KEY_FILE: str = ""
    LIBRARY_GEMINI_FREE_TIER_CONFIRMED: bool = False
    LIBRARY_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
