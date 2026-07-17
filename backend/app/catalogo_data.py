"""Catálogo fijo de elementos (orden exacto del formato en papel).

Cada entrada: (instalacion, sistema, nombre, tipo, ups_dobles).
Tipos: SIMPLE | CCC | UPS.
"""

from app.models.catalogo import TIPO_CCC, TIPO_SIMPLE, TIPO_UPS

# (instalacion, sistema, [nombres], tipo, ups_dobles_por_defecto)
_GRUPOS = [
    ("SDC", "LCN", [
        "LCNE-A - ISH2", "LCNE-B - ISH2", "GUS1A01", "GUS1A02", "GUS1A03", "HG41",
        "HG42", "GUS1B01", "GUS1B02", "GUS1B03", "GUS1C01", "GUS1C02", "GUS1C03",
        "LCNE-A - SE5", "LCNE-B - SE5", "GUS1D01", "GUS1D02", "GUS1D03",
        "LCNE-A - ISH1", "LCNE-B - ISH1", "GUS1H01", "GUS1E01", "GUS1E02", "GUS1E03",
        "APP51", "APP52", "HM61",
    ], TIPO_SIMPLE, False),
    ("SDC", "PCN", ["PANZPDC01", "PANZFSS01", "PANZFSS02", "PANZFSS03"], TIPO_SIMPLE, False),
    ("SDC", "MANT", ["Electricidad"], TIPO_SIMPLE, False),
    ("SDC", "SSLL", ["Aire Acond.", "Iluminación", "Limpieza"], TIPO_SIMPLE, False),

    ("ISH-1", "LCN", ["NIM 31", "NIM 32", "U1-LCNE-A", "U1-LCNE-B"], TIPO_SIMPLE, False),
    ("ISH-1", "FSC", ["01SM41", "01SM43", "01SM45", "01SM47"], TIPO_SIMPLE, False),
    ("ISH-1", "MANT", ["Electricidad"], TIPO_SIMPLE, False),
    ("ISH-1", "SSLL", ["Aire Acond.", "Iluminación", "Limpieza"], TIPO_SIMPLE, False),
    ("ISH-1", "AIT", ["Panalarm"], TIPO_SIMPLE, False),
    ("ISH-1", "UCN", ["01HPM9/10", "01HPM11/12", "01HPM13/14", "01HPM15/16"], TIPO_UPS, False),
    ("ISH-1", "PLC", ["Demin Water", "01PLC01", "Raw Water", "01PLC04", "01PLC05"], TIPO_UPS, False),

    ("ISH-2", "LCN", [
        "NIM 33", "NIM 34", "U2-LCNE-A", "U2-LCNE-B",
        "NIM 35", "NIM 36", "U3-LCNE-A", "U3-LCNE-B",
    ], TIPO_SIMPLE, False),
    ("ISH-2", "FSC", ["02SM41", "02SM43", "02SM45", "02SM47"], TIPO_SIMPLE, False),
    ("ISH-2", "AIT", ["Panalarm"], TIPO_SIMPLE, False),
    ("ISH-2", "MANT", ["Electricidad"], TIPO_SIMPLE, False),
    ("ISH-2", "SSLL", ["Aire Acond.", "Iluminación", "Limpieza"], TIPO_SIMPLE, False),
    ("ISH-2", "CCC", ["PIC13084A/B", "FIC13001A/B", "FIC13002A/B"], TIPO_CCC, False),
    ("ISH-2", "UCN", [
        "02HPM9/10", "02HPM11/12", "02HPM13/14", "02HPM15/16",
        "03HPM17/18", "03HPM19/20", "03HPM21/22", "03HPM23/24", "03HPM25/26",
    ], TIPO_UPS, False),
    ("ISH-2", "PLC", [
        "IDP COKE", "PSA Viejo", "02PLC01", "01PLC01", "PSA Nuevo",
        "Dresser H2", "Elliot Wet Gas", "HIBON BLOWERS", "02PLC10",
    ], TIPO_UPS, False),
]

# Elementos UPS con 4 fuentes/baterías/fan en vez de 2.
_UPS_DOBLES = {("ISH-2", "PLC", "02PLC01")}


def catalogo_rows() -> list[dict]:
    """Devuelve las filas del catálogo con codigo y orden calculados."""
    rows: list[dict] = []
    orden = 0
    for instalacion, sistema, nombres, tipo, _ in _GRUPOS:
        for nombre in nombres:
            ups_dobles = (instalacion, sistema, nombre) in _UPS_DOBLES
            rows.append({
                "codigo": f"{instalacion}|{sistema}|{nombre}",
                "instalacion": instalacion,
                "sistema": sistema,
                "nombre": nombre,
                "tipo": tipo,
                "ups_dobles": ups_dobles,
                "orden": orden,
            })
            orden += 1
    return rows
