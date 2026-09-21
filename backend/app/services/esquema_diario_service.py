"""Vista pública del esquema GUS basada en una versión diaria congelada."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.models.diario import VersionDiario

_BASE = Path(__file__).resolve().parent.parent
_env = Environment(loader=FileSystemLoader(_BASE / "templates"), autoescape=True)
_CSS = (_BASE / "static" / "esquema_diario.css").read_text(encoding="utf-8")

_GROUPS = (
    ("supervisor", "GUS supervisor", ("H01",)),
    ("ingenieria", "GUS de ingeniería", ("E01", "E02", "E03")),
    ("consola-d", "Consola D", ("D01", "D02", "D03")),
    ("consola-c", "Consola C", ("C01", "C02", "C03")),
    ("consola-a", "Consola A", ("A01", "A02", "A03")),
    ("consola-b", "Consola B", ("B01", "B02", "B03")),
)


def _state(value, allowed):
    return value if value in allowed else None


def render_esquema_diario(version: VersionDiario | None) -> str:
    datos = version.datos if version else {}
    gus = datos.get("gus") or {}
    groups = [
        {"class_name": class_name, "title": title, "items": [
            {"name": f"GUS1{suffix}", "state": _state(gus.get(f"SDC|LCN|GUS1{suffix}"),
                                                    ("OK", "MALO", "OBSERVACION"))}
            for suffix in codes]}
        for class_name, title, codes in _GROUPS
    ]
    signals = [
        {"label": label, "state": _state(datos.get(key), allowed)}
        for label, key, allowed in (
            ("Cable A", "lcn_a", ("OK", "SUSPECT")),
            ("Cable B", "lcn_b", ("OK", "SUSPECT")),
            ("UCN 01", "ucn1", ("OK", "FAIL")),
            ("UCN 02", "ucn2", ("OK", "FAIL")),
            ("UCN 03", "ucn3", ("OK", "FAIL")),
        )
    ]
    temperatures = [
        {"label": label, "value": datos.get(key)}
        for label, key in (("Temperatura ISH 1", "temperatura_ish1"),
                           ("Temperatura ISH 2", "temperatura_ish2"))
    ]
    return _env.get_template("esquema_diario.html.j2").render(
        css_content=_CSS, has_report=version is not None, groups=groups,
        signals=signals, temperatures=temperatures, fecha=datos.get("fecha"),
        hora=datos.get("hora"), responsable=datos.get("responsable"),
        observaciones=datos.get("observaciones"),
    )
