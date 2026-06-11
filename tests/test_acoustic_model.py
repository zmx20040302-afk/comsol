import unittest
from pathlib import Path


class AcousticModelTest(unittest.TestCase):
    def test_model_contains_required_grounded_settings(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "acoustic_rectangular_cavity" / "acoustic_rectangular_cavity.java").read_text(
            encoding="utf-8"
        )
        for required in (
            '"PressureAcoustics"',
            '"Eigenfrequency"',
            '"soundspeed"',
            '"density"',
            '"FreeTri"',
            '"f10_ref"',
            '"f01_ref"',
        ):
            self.assertIn(required, text)

    def test_reference_frequencies(self):
        c_air = 343.0
        lx = 4.0
        ly = 3.0
        expected = [
            c_air / (2 * lx),
            c_air / (2 * ly),
            c_air / 2 * ((1 / lx) ** 2 + (1 / ly) ** 2) ** 0.5,
            c_air / lx,
        ]
        reference = [42.875, 57.167, 71.458, 85.750]
        for calculated, documented in zip(expected, reference):
            self.assertAlmostEqual(calculated, documented, places=3)

    def test_matlab_livelink_builder_contains_required_settings(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "acoustic_rectangular_cavity" / "build_acoustic_rectangular_cavity.m").read_text(
            encoding="utf-8"
        )
        for required in (
            "PressureAcoustics",
            "Eigenfrequency",
            "soundspeed",
            "density",
            "FreeTri",
            "model.save",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
