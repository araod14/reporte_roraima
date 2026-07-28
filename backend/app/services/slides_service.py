"""Vista visual "panel sinóptico": 3 slides (una por instalación) con cada
equipo como tile coloreado por estado.

A diferencia del reporte oficial (`report_service`), esta vista es una AYUDA
VISUAL regenerable: se renderiza en cada request, no se congela en disco ni
lleva hash de integridad. No crea filas `Reporte`.
"""

import os
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.models.catalogo import TIPO_UPS, CatalogoElemento
from app.models.inspeccion import Inspeccion
from app.services.report_service import (
    _INSTALACION_ORDER,
    _SISTEMA_ORDER,
    _registro_dict,
)

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ups_status(reg_dict: dict, ups_dobles: bool) -> str:
    """Deriva el estado de un UPS a partir de sus fuente/batería/fan.

    ok  -> todas las señales de los pares (2, o 4 si ups_dobles) en True
    malo -> alguna señal en False
    """
    pares = 4 if ups_dobles else 2
    campos = []
    for i in range(1, pares + 1):
        campos += [reg_dict.get(f"fuente_{i}"), reg_dict.get(f"bateria_{i}"), reg_dict.get(f"fan_{i}")]
    return "ok" if all(bool(v) for v in campos) else "malo"


def _simple_status(estado: str | None) -> str:
    return {"OK": "ok", "MALO": "malo", "OBSERVACION": "obs"}.get(estado or "", "sindato")


def build_slides(db: Session, inspeccion: Inspeccion) -> list[dict]:
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

        if reg is None:
            status = "sindato"
        elif cat.tipo == TIPO_UPS:
            status = _ups_status(reg_dict, cat.ups_dobles)
        else:
            status = _simple_status(reg_dict.get("estado"))

        elem = {
            "nombre": cat.nombre,
            "tipo": cat.tipo,
            "ups_dobles": cat.ups_dobles,
            "status": status,
            "comentario": reg_dict.get("comentario"),
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
    return ordenadas


def _render_html(db: Session, inspeccion: Inspeccion, generado_por: str) -> str:
    with open(os.path.join(_STATIC_DIR, "slides.css"), encoding="utf-8") as f:
        css_content = f.read()
    template = _env.get_template("slides.html.j2")
    return template.render(
        inspeccion=inspeccion,
        slides=build_slides(db, inspeccion),
        css_content=css_content,
        generado_por=generado_por,
        fecha_generacion=datetime.now(timezone.utc),
    )


def render_slides_html(db: Session, inspeccion: Inspeccion, generado_por: str) -> str:
    """HTML interactivo (self-contained) de la vista de slides."""
    return _render_html(db, inspeccion, generado_por)


def render_slides_pdf(db: Session, inspeccion: Inspeccion, generado_por: str) -> bytes:
    """PDF apaisado (3 páginas) de la vista de slides."""
    html_str = _render_html(db, inspeccion, generado_por)
    return HTML(string=html_str, base_url=_STATIC_DIR).write_pdf()
