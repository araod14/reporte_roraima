"""Generación de reportes (HTML + PDF) con hash de integridad y QR.

Regla clave: los archivos se generan UNA sola vez al finalizar y nunca se
regeneran. Regenerar produciría bytes distintos (timestamps internos del PDF) y
rompería la validez del hash. Los endpoints sólo sirven el archivo guardado.
"""

import base64
import hashlib
import io
import json
import os
from datetime import datetime, timezone

import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.core.config import settings
from app.models.catalogo import TIPO_UPS, CatalogoElemento
from app.models.inspeccion import ESTADO_FINALIZADA, Inspeccion
from app.models.reporte import Reporte

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

# Orden de instalaciones y sistemas para agrupar el reporte.
_INSTALACION_ORDER = ["SDC", "ISH-1", "ISH-2"]
_SISTEMA_ORDER = ["LCN", "PCN", "MANT", "SSLL", "FSC", "AIT", "CCC", "UCN", "PLC"]

_ESTADO_PROBLEMA = {"MALO"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _qr_data_uri(url: str) -> str:
    qr = qrcode.make(url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _registro_dict(reg) -> dict:
    """Serializa un registro a un dict plano y estable (para hash y template)."""
    return {
        "estado": reg.estado,
        "comentario": reg.comentario,
        "valor_a": reg.valor_a,
        "valor_b": reg.valor_b,
        "fuente_1": reg.fuente_1,
        "bateria_1": reg.bateria_1,
        "fan_1": reg.fan_1,
        "fuente_2": reg.fuente_2,
        "bateria_2": reg.bateria_2,
        "fan_2": reg.fan_2,
        "fuente_3": reg.fuente_3,
        "bateria_3": reg.bateria_3,
        "fan_3": reg.fan_3,
        "fuente_4": reg.fuente_4,
        "bateria_4": reg.bateria_4,
        "fan_4": reg.fan_4,
    }


def build_context(db: Session, inspeccion: Inspeccion) -> tuple[dict, str]:
    """Construye el contexto del reporte y el content_hash de los datos.

    Devuelve (context, content_hash). El context ya está agrupado por
    instalación -> sistema y contiene el resumen ejecutivo.
    """
    catalogo = {c.codigo: c for c in db.query(CatalogoElemento).all()}
    registros = {r.catalogo_codigo: r for r in inspeccion.registros}

    # --- datos canónicos para el hash (orden estable por código) ---
    canonical = {
        "id": inspeccion.id,
        "fecha": inspeccion.fecha.isoformat(),
        "inspeccionado_por": inspeccion.inspeccionado_por_nombre,
        "verificado_por": inspeccion.verificado_por_nombre,
        "aprobado_por": inspeccion.aprobado_por_nombre,
        "observaciones": inspeccion.observaciones_generales,
        "registros": {
            codigo: _registro_dict(registros[codigo])
            for codigo in sorted(registros.keys())
        },
    }
    content_hash = _sha256_bytes(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )

    # --- agrupación para el template ---
    def _cat_sort_key(cod: str):
        c = catalogo.get(cod)
        if not c:
            return (99, 99, 9999)
        inst = _INSTALACION_ORDER.index(c.instalacion) if c.instalacion in _INSTALACION_ORDER else 98
        sis = _SISTEMA_ORDER.index(c.sistema) if c.sistema in _SISTEMA_ORDER else 98
        return (inst, sis, c.orden)

    grupos: dict[tuple[str, str], dict] = {}
    resumen: list[dict] = []

    for codigo in sorted(catalogo.keys(), key=_cat_sort_key):
        cat = catalogo[codigo]
        reg = registros.get(codigo)
        if reg is None:
            continue  # elemento sin capturar en esta inspección
        elem = {
            "nombre": cat.nombre,
            "tipo": cat.tipo,
            "ups_dobles": cat.ups_dobles,
            **_registro_dict(reg),
        }
        key = (cat.instalacion, cat.sistema)
        if key not in grupos:
            grupos[key] = {
                "instalacion": cat.instalacion,
                "sistema": cat.sistema,
                "tipo": cat.tipo,
                "elementos": [],
            }
        grupos[key]["elementos"].append(elem)

        if cat.tipo != TIPO_UPS and reg.estado in _ESTADO_PROBLEMA:
            resumen.append(
                {
                    "instalacion": cat.instalacion,
                    "sistema": cat.sistema,
                    "nombre": cat.nombre,
                    "estado": reg.estado,
                    "comentario": reg.comentario,
                }
            )

    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda g: (
            _INSTALACION_ORDER.index(g["instalacion"]) if g["instalacion"] in _INSTALACION_ORDER else 98,
            _SISTEMA_ORDER.index(g["sistema"]) if g["sistema"] in _SISTEMA_ORDER else 98,
        ),
    )

    context = {
        "inspeccion": inspeccion,
        "grupos": grupos_ordenados,
        "resumen": resumen,
        "n_problemas": len(resumen),
    }
    return context, content_hash


def _next_version(db: Session, inspeccion_id: str) -> int:
    versiones = [r.version for r in db.query(Reporte).filter(Reporte.inspeccion_id == inspeccion_id).all()]
    return (max(versiones) + 1) if versiones else 1


def generar_reporte(db: Session, inspeccion: Inspeccion, generado_por: str) -> Reporte:
    """Genera (una sola vez) el HTML y el PDF de una nueva versión del reporte."""
    version = _next_version(db, inspeccion.id)
    context, content_hash = build_context(db, inspeccion)
    hash_short = content_hash[:12]

    verificar_url = f"{settings.BASE_URL.rstrip('/')}/verificar/{inspeccion.id}/{version}"
    qr_uri = _qr_data_uri(verificar_url)

    with open(os.path.join(_STATIC_DIR, "reporte.css"), encoding="utf-8") as f:
        css_content = f.read()

    template = _env.get_template("reporte.html.j2")
    html_str = template.render(
        **context,
        css_content=css_content,
        version=version,
        content_hash=content_hash,
        hash_short=hash_short,
        qr_uri=qr_uri,
        verificar_url=verificar_url,
        generado_por=generado_por,
        fecha_generacion=datetime.now(timezone.utc),
    )

    # Directorio del reporte
    out_dir = os.path.join(settings.REPORTS_DIR, inspeccion.id)
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"v{version}.html")
    pdf_path = os.path.join(out_dir, f"v{version}.pdf")

    # Escribir HTML (bytes exactos que luego se sirven y se hashean)
    html_bytes = html_str.encode("utf-8")
    with open(html_path, "wb") as f:
        f.write(html_bytes)

    # Generar PDF desde el MISMO HTML
    pdf_bytes = HTML(string=html_str, base_url=_STATIC_DIR).write_pdf()
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    reporte = Reporte(
        inspeccion_id=inspeccion.id,
        version=version,
        pdf_path=pdf_path,
        html_path=html_path,
        pdf_sha256=_sha256_bytes(pdf_bytes),
        html_sha256=_sha256_bytes(html_bytes),
        content_hash=content_hash,
        pdf_hash_short=hash_short,
        generado_por=generado_por,
    )
    inspeccion.estado = ESTADO_FINALIZADA
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte
