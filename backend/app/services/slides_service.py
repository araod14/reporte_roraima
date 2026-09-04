"""Vista visual "panel sinóptico" con cada equipo como tile coloreado por
estado: slides interactivos en HTML y páginas verticales legibles en PDF.

A diferencia del reporte oficial (`report_service`), esta vista es una AYUDA
VISUAL regenerable: se renderiza en cada request, no se congela en disco ni
lleva hash de integridad. No crea filas `Reporte`.
"""

import os
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.models.catalogo import CatalogoElemento
from app.models.inspeccion import Inspeccion
from app.services.report_service import (
    _INSTALACION_ORDER,
    _SISTEMA_ORDER,
    _element_visual_state,
    _registro_dict,
    _ups_visual_state,
    build_status_summary,
)

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _build_slides_data(
    db: Session, inspeccion: Inspeccion
) -> tuple[list[dict], list[dict]]:
    """Estructura para la plantilla: una entrada por instalación, con sus
    sistemas y los tiles de cada equipo (incluye equipos sin capturar)."""
    catalogo = list(db.query(CatalogoElemento).all())
    registros = {r.catalogo_codigo: r for r in inspeccion.registros}

    def _sort_key(c: CatalogoElemento):
        inst = _INSTALACION_ORDER.index(c.instalacion) if c.instalacion in _INSTALACION_ORDER else 98
        sis = _SISTEMA_ORDER.index(c.sistema) if c.sistema in _SISTEMA_ORDER else 98
        return (inst, sis, c.orden)

    catalogo.sort(key=_sort_key)

    slides: dict[str, dict] = {}

    for cat in catalogo:
        reg = registros.get(cat.codigo)
        reg_dict = _registro_dict(reg) if reg is not None else {}

        status, observacion_automatica = _element_visual_state(cat, reg)

        elem = {
            "nombre": cat.nombre,
            "tipo": cat.tipo,
            "ups_dobles": cat.ups_dobles,
            "status": status,
            "comentario": reg_dict.get("comentario"),
            "observacion_automatica": observacion_automatica,
            "valor_a": reg_dict.get("valor_a"),
            "valor_b": reg_dict.get("valor_b"),
            **{
                k: reg_dict.get(k)
                for k in reg_dict
                if k.startswith(("fuente_", "bateria_", "fan_"))
            },
        }

        slide = slides.setdefault(
            cat.instalacion,
            {
                "instalacion": cat.instalacion,
                "sistemas": {},
                "stats": {"ok": 0, "malo": 0, "obs": 0, "sindato": 0, "total": 0},
            },
        )
        sistema = slide["sistemas"].setdefault(
            cat.sistema, {"sistema": cat.sistema, "tipo": cat.tipo, "elementos": []}
        )
        sistema["elementos"].append(elem)

        slide["stats"][status] += 1
        slide["stats"]["total"] += 1

    # dict -> listas ordenadas
    ordenadas: list[dict] = []
    for inst in sorted(slides.keys(), key=lambda i: _INSTALACION_ORDER.index(i) if i in _INSTALACION_ORDER else 98):
        slide = slides[inst]
        sistemas = sorted(
            slide["sistemas"].values(),
            key=lambda s: _SISTEMA_ORDER.index(s["sistema"]) if s["sistema"] in _SISTEMA_ORDER else 98,
        )
        ordenadas.append({"instalacion": inst, "sistemas": sistemas, "stats": slide["stats"]})
    _, overview = build_status_summary(catalogo, registros)
    return ordenadas, overview


def build_slides(db: Session, inspeccion: Inspeccion) -> list[dict]:
    """Mantiene la interfaz existente para consumidores de las láminas."""
    slides, _ = _build_slides_data(db, inspeccion)
    return slides


def _render_html(db: Session, inspeccion: Inspeccion, generado_por: str) -> str:
    with open(os.path.join(_STATIC_DIR, "slides.css"), encoding="utf-8") as f:
        css_content = f.read()
    template = _env.get_template("slides.html.j2")
    slides, overview = _build_slides_data(db, inspeccion)
    return template.render(
        inspeccion=inspeccion,
        slides=slides,
        overview=overview,
        css_content=css_content,
        generado_por=generado_por,
        fecha_generacion=datetime.now(timezone.utc),
    )


def render_slides_html(db: Session, inspeccion: Inspeccion, generado_por: str) -> str:
    """HTML interactivo (self-contained) de la vista de slides."""
    return _render_html(db, inspeccion, generado_por)


def render_slides_pdf(db: Session, inspeccion: Inspeccion, generado_por: str) -> bytes:
    """PDF vertical 9:16, optimizado para lectura desde celulares."""
    with open(os.path.join(_STATIC_DIR, "slides_pdf.css"), encoding="utf-8") as f:
        css_content = f.read()
    template = _env.get_template("slides_pdf.html.j2")
    slides, overview = _build_slides_data(db, inspeccion)
    html_str = template.render(
        inspeccion=inspeccion,
        slides=slides,
        overview=overview,
        css_content=css_content,
        generado_por=generado_por,
        fecha_generacion=datetime.now(timezone.utc),
    )
    return HTML(string=html_str, base_url=_STATIC_DIR).write_pdf()
