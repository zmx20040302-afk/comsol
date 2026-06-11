import unittest
from pathlib import Path


class ThreeDimensionalBulbModelTest(unittest.TestCase):
    def test_matlab_builder_contains_grounded_3d_settings(self):
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "electrochemical_polishing_3d_bulb"
            / "build_electrochemical_polishing_3d_bulb.m"
        )
        text = path.read_text(encoding="utf-8")
        for required in (
            "geom.create('geom1', 3)",
            "'Sphere'",
            "'Cylinder'",
            "'ConductiveMedia'",
            "'Stationary'",
            "'ElectricPotential'",
            "'Ground'",
            "'DeformingDomainDeformedGeometry'",
            "'PrescribedNormalMeshVelocityDeformedGeometry'",
            "'-K*(-ec.nJ)'",
            "'laplace'",
            "'FreeTet'",
            "'Transient'",
            "'range(0,10)'",
            "assert_nonempty_selection",
            "Build failed during stage:",
            "'25[mm]'",
            "model.save",
        ):
            self.assertIn(required, text)

    def test_builder_does_not_reuse_2d_numeric_boundary_ids(self):
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "electrochemical_polishing_3d_bulb"
            / "build_electrochemical_polishing_3d_bulb.m"
        )
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("selection.set([3 4 6 7])", text)
        self.assertNotIn("selection.set([1 2 5])", text)
        self.assertIn("selection.named", text)

    def test_diagnostic_runner_checks_builder_and_livelink(self):
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "electrochemical_polishing_3d_bulb"
            / "run_3d_bulb_diagnostic.m"
        )
        text = path.read_text(encoding="utf-8")
        for required in (
            "build_3d_bulb_log.txt",
            "which('build_electrochemical_polishing_3d_bulb')",
            "ModelUtil.getComsolVersion",
            "COMSOL LiveLink connection is not ready",
            "run_3d_bulb_diagnostic",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
