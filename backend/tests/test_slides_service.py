import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.catalogo import TIPO_UPS
from app.services.report_service import (
    _is_tolerant_ups,
    build_context,
    forced_bad_with_invalid_comment,
)
from app.services.slides_service import _ups_visual_state


class HpmVisualStateTests(unittest.TestCase):
    def test_one_active_source_is_ok_and_lists_missing_components(self):
        state, observation = _ups_visual_state(
            {
                "fuente_1": True,
                "bateria_1": False,
                "fuente_2": False,
                "bateria_2": True,
                "fan_1": False,
                "fan_2": False,
            },
            False,
            tolera_faltantes=True,
        )

        self.assertEqual(state, "ok")
        self.assertEqual(observation, "Faltan: B1, F2")


class TolerantUpsTests(unittest.TestCase):
    def test_plc_system_is_tolerant_even_without_plc_in_its_name(self):
        cat = SimpleNamespace(tipo=TIPO_UPS, sistema="PLC", nombre="Raw Water")

        self.assertTrue(_is_tolerant_ups(cat))

    def test_forced_bad_requires_a_comment_of_at_most_twenty_words(self):
        cat = SimpleNamespace(
            codigo="ISH-1|PLC|Raw Water",
            tipo=TIPO_UPS,
            sistema="PLC",
            nombre="Raw Water",
        )
        db = Mock()
        db.query.return_value.all.return_value = [cat]

        for comentario in (None, " ", " ".join(["palabra"] * 21)):
            inspeccion = SimpleNamespace(
                registros=[
                    SimpleNamespace(
                        catalogo_codigo=cat.codigo,
                        estado="MALO",
                        comentario=comentario,
                    )
                ]
            )
            self.assertEqual(
                forced_bad_with_invalid_comment(db, inspeccion), ["Raw Water"]
            )

        inspeccion.registros[0].comentario = "Fuente inestable"
        self.assertEqual(forced_bad_with_invalid_comment(db, inspeccion), [])

    def test_forced_bad_plc_is_included_in_official_report_summary(self):
        cat = SimpleNamespace(
            codigo="ISH-1|PLC|Raw Water",
            instalacion="ISH-1",
            sistema="PLC",
            nombre="Raw Water",
            tipo=TIPO_UPS,
            ups_dobles=False,
            orden=1,
        )
        signal_fields = {
            f"{kind}_{i}": None
            for i in range(1, 5)
            for kind in ("fuente", "bateria", "fan")
        }
        reg = SimpleNamespace(
            catalogo_codigo=cat.codigo,
            estado="MALO",
            comentario="Fuente inestable",
            valor_a=None,
            valor_b=None,
            **signal_fields,
        )
        inspeccion = SimpleNamespace(
            id="inspection-id",
            fecha=SimpleNamespace(isoformat=lambda: "2026-09-01"),
            inspeccionado_por_nombre="Operador",
            verificado_por_nombre="",
            aprobado_por_nombre="",
            observaciones_generales="",
            registros=[reg],
        )
        db = Mock()
        db.query.return_value.all.return_value = [cat]

        context, content_hash = build_context(db, inspeccion)

        self.assertEqual(context["n_problemas"], 1)
        self.assertEqual(context["resumen"][0]["nombre"], "Raw Water")
        self.assertEqual(context["resumen"][0]["comentario"], "Fuente inestable")
        self.assertEqual(len(content_hash), 64)

    def test_second_active_source_is_enough(self):
        state, _ = _ups_visual_state(
            {"fuente_2": True}, False, tolera_faltantes=True
        )

        self.assertEqual(state, "ok")

    def test_batteries_without_a_source_are_bad(self):
        state, observation = _ups_visual_state(
            {"bateria_1": True, "bateria_2": True}, False, tolera_faltantes=True
        )

        self.assertEqual(state, "malo")
        self.assertEqual(observation, "Faltan: F1, F2")

    def test_fans_do_not_affect_hpm_state_or_observation(self):
        state, observation = _ups_visual_state(
            {
                "fuente_1": True,
                "bateria_1": True,
                "fuente_2": True,
                "bateria_2": True,
                "fan_1": False,
                "fan_2": False,
            },
            False,
            tolera_faltantes=True,
        )

        self.assertEqual(state, "ok")
        self.assertIsNone(observation)

    def test_other_ups_keep_the_strict_rule(self):
        state, observation = _ups_visual_state(
            {
                "fuente_1": True,
                "bateria_1": True,
                "fan_1": True,
                "fuente_2": True,
                "bateria_2": True,
                "fan_2": False,
            },
            False,
            tolera_faltantes=False,
        )

        self.assertEqual(state, "malo")
        self.assertIsNone(observation)

    def test_manual_bad_overrides_an_active_source(self):
        state, observation = _ups_visual_state(
            {
                "estado": "MALO",
                "fuente_1": True,
                "bateria_1": True,
                "fuente_2": False,
                "bateria_2": True,
            },
            False,
            tolera_faltantes=True,
        )

        self.assertEqual(state, "malo")
        self.assertEqual(observation, "Faltan: F2")

    def test_any_source_is_enough_for_a_four_module_plc(self):
        state, _ = _ups_visual_state(
            {"fuente_4": True}, True, tolera_faltantes=True
        )

        self.assertEqual(state, "ok")


if __name__ == "__main__":
    unittest.main()
