import unittest

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
            is_hpm=True,
        )

        self.assertEqual(state, "ok")
        self.assertEqual(observation, "Faltan: B1, F2")

    def test_second_active_source_is_enough(self):
        state, _ = _ups_visual_state(
            {"fuente_2": True}, False, is_hpm=True
        )

        self.assertEqual(state, "ok")

    def test_batteries_without_a_source_are_bad(self):
        state, observation = _ups_visual_state(
            {"bateria_1": True, "bateria_2": True}, False, is_hpm=True
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
            is_hpm=True,
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
            is_hpm=False,
        )

        self.assertEqual(state, "malo")
        self.assertIsNone(observation)


if __name__ == "__main__":
    unittest.main()
