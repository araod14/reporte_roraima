"""Vista pública del esquema GUS basada en una versión diaria congelada."""
from datetime import datetime, timedelta, timezone
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


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _age_label(value: datetime | None, now: datetime | None = None) -> str | None:
    if value is None:
        return None
    minutes = max(0, int(((now or datetime.now(timezone.utc)) - _as_utc(value)).total_seconds() // 60))
    if minutes < 1:
        return "hace menos de 1 minuto"
    if minutes < 60:
        return f"hace {minutes} {'minuto' if minutes == 1 else 'minutos'}"
    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} {'hora' if hours == 1 else 'horas'}"
    days = hours // 24
    return f"hace {days} {'día' if days == 1 else 'días'}"


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
        {"label": label, "value": datos.get(key),
         "tone": ("empty" if datos.get(key) is None else
                  "malo" if datos[key] > 35 else "observacion" if datos[key] > 25 else "ok")}
        for label, key in (("Temperatura ISH 1", "temperatura_ish1"),
                           ("Temperatura ISH 2", "temperatura_ish2"))
    ]
    gus_items = [(group["title"], item) for group in groups for item in group["items"]]
    counts = {
        "observacion": sum(item["state"] == "OBSERVACION" for _, item in gus_items),
        "malo": sum(item["state"] == "MALO" for _, item in gus_items),
        "ucn": sum(signal["state"] == "FAIL" for signal in signals[2:]),
        "lcn": sum(signal["state"] == "SUSPECT" for signal in signals[:2]),
        "temperatura": sum(temp["tone"] in ("observacion", "malo") for temp in temperatures),
    }
    summary = [
        {"text": f'{counts["malo"]} GUS en MALO', "tone": "malo"} if counts["malo"] else None,
        {"text": f'{counts["observacion"]} GUS en observación', "tone": "observacion"} if counts["observacion"] else None,
        {"text": f'{counts["ucn"]} UCN con falla', "tone": "malo"} if counts["ucn"] else None,
        {"text": f'{counts["lcn"]} LCN sospechoso{"s" if counts["lcn"] != 1 else ""}', "tone": "observacion"} if counts["lcn"] else None,
        {"text": f'{counts["temperatura"]} temperatura{"s" if counts["temperatura"] != 1 else ""} elevada{"s" if counts["temperatura"] != 1 else ""}',
         "tone": "malo" if any(temp["tone"] == "malo" for temp in temperatures) else "observacion"} if counts["temperatura"] else None,
    ]
    summary = [entry for entry in summary if entry]
    incidents = [
        {"name": item["name"], "area": area, "state": "MALO" if item["state"] == "MALO" else "OBSERVACIÓN",
         "tone": item["state"].lower()}
        for area, item in gus_items if item["state"] in ("MALO", "OBSERVACION")
    ]
    incidents += [
        {"name": signal["label"], "area": "LCN" if index < 2 else "UCN",
         "state": "SUSPECT" if index < 2 else "FAIL", "tone": "suspect" if index < 2 else "fail"}
        for index, signal in enumerate(signals) if signal["state"] in ("SUSPECT", "FAIL")
    ]
    incidents += [
        {"name": temp["label"], "area": "Temperaturas", "state": f'{temp["value"]:g} °C',
         "tone": temp["tone"]}
        for temp in temperatures if temp["tone"] in ("observacion", "malo")
    ]
    incidents.sort(key=lambda item: item["tone"] not in ("malo", "fail"))
    return _env.get_template("esquema_diario.html.j2").render(
        css_content=_CSS, has_report=version is not None, groups=groups,
        signals=signals, temperatures=temperatures, summary=summary, incidents=incidents,
        age_label=_age_label(version.fecha_generacion) if version else None,
        stale=bool(version and datetime.now(timezone.utc) - _as_utc(version.fecha_generacion) >= timedelta(hours=24)),
        fecha=datos.get("fecha"),
        hora=datos.get("hora"), responsable=datos.get("responsable"),
        observaciones=datos.get("observaciones"),
    )
