import unittest
from pathlib import Path


class MemsAcousticChip3DTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / "mems_acoustic_chip_3d"

    def test_builder_contains_grounded_3d_settings(self):
        text = (self.root / "build_mems_acoustic_chip_3d.m").read_text(encoding="utf-8")
        for required in (
            "PressureAcoustics",
            "Eigenfrequency",
            "FreeTet",
            "Sound Hard",
            "acpr.Lp_t",
            "MEMS Chip Geometry - Display Only",
            "mphsave",
        ):
            self.assertIn(required, text)

    def test_field_test_compares_against_analytical_modes(self):
        text = (self.root / "run_mems_acoustic_field_test.m").read_text(encoding="utf-8")
        for required in (
            "mphglobal",
            "relative_error_percent",
            "writetable",
            "mphplot",
            "mphinterp",
            "shape_correlation",
        ):
            self.assertIn(required, text)

    def test_reference_frequencies(self):
        c_air = 343.0
        self.assertAlmostEqual(c_air / (2 * 2e-3), 85750.0)
        self.assertAlmostEqual(c_air / (2 * 1.5e-3), 114333.33333333333)
        self.assertAlmostEqual(c_air / (2 * 0.5e-3), 343000.0)


if __name__ == "__main__":
    unittest.main()
