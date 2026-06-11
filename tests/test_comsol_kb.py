import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from comsol_kb import build_index, recommend, validation_and_query_risks


class KnowledgeBaseTest(unittest.TestCase):
    def test_structures_evidence_and_refuses_unsupported_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "heat_case"
            case.mkdir()
            (case / "case.md").write_text(
                "# 传热案例\n物理场：固体传热。\n几何：厚度 = 10 mm。\n结果：最高温度曲线。",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            result = recommend(index, "厚度为 10 mm 的传热模型", 1)
            item = result["recommendations"][0]
            self.assertTrue(item["supported_evidence"]["physics"])
            self.assertTrue(item["parameter_changes"]["parameters"])
            self.assertIn("materials", item["risks"][0])

    def test_reads_csv_and_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "mixed"
            case.mkdir()
            (case / "mesh.csv").write_text("类别,说明\n网格,自由三角形\n", encoding="utf-8")
            (case / "model.json").write_text(
                json.dumps({"材料": "钢", "求解器": "稳态"}, ensure_ascii=False),
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertTrue(fields["mesh"])
            self.assertTrue(fields["materials"])
            self.assertTrue(fields["solver"])

    def test_license_query_uses_app_validation_without_inventing_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "license_app"
            case.mkdir()
            (case / "license.md").write_text(
                "适用范围：发布修改后的 Application 必须遵守许可协议。",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "如何验证 App 许可协议？", 1)["recommendations"][0]
            self.assertIn("不能单独证明", item["risks"][0])
            self.assertNotIn("重新求解", " ".join(item["validation_steps"]))

    def test_solver_limit_is_not_treated_as_applicability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "solver_case"
            case.mkdir()
            (case / "case.json").write_text(
                json.dumps({"求解器": "更新步长的限制为 10"}, ensure_ascii=False),
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertFalse(index["cases"][0]["fields"]["applicability"])

    def test_builds_one_index_from_multiple_case_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "one.md").write_text("物理场：固体传热。", encoding="utf-8")
            (second / "two.md").write_text("物理场：固体力学。", encoding="utf-8")
            index = build_index([first, second], root / "index.json")
            self.assertEqual({case["name"] for case in index["cases"]}, {"first", "second"})
            self.assertEqual(len(index["source_roots"]), 2)

    def test_exact_case_title_outweighs_generic_document_terms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "Black-Scholes 方程"
            generic = root / "网格教程"
            target.mkdir()
            generic.mkdir()
            (target / "brief.md").write_text("偏微分方程案例。", encoding="utf-8")
            (generic / "long.md").write_text(
                "Black Scholes 方程 求解 " * 100,
                encoding="utf-8",
            )
            index = build_index([target, generic], root / "index.json")
            result = recommend(index, "如何求解 Black-Scholes 方程？", 1)
            self.assertEqual(result["recommendations"][0]["case_name"], "Black-Scholes 方程")

    def test_extracts_only_explicit_comsol_code_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "code_case"
            case.mkdir()
            (case / "model.java").write_text(
                'model.param().set("Rc", "2[cm]");\nmodel.study().create("std1");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertEqual(index["cases"][0]["parameters"][0]["name"], "Rc")
            self.assertEqual(index["cases"][0]["parameters"][0]["value"], "2[cm]")

    def test_explicit_code_evidence_is_ranked_above_generic_description(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "physics_case"
            case.mkdir()
            (case / "intro.md").write_text(
                "COMSOL Multiphysics is a physics simulation product.",
                encoding="utf-8",
            )
            (case / "model.java").write_text(
                'model.component("comp1").physics().create("scdeq", '
                '"StabilizedConvectionDiffusionEquation", "geom1");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "physics", 1)["recommendations"][0]
            self.assertIn("model.component", item["supported_evidence"]["physics"][0]["excerpt"])

    def test_recognizes_explicit_comsol_boundary_feature_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "boundary_case"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").physics("c").create("nflx1", "NoFlux", 0);',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertTrue(index["cases"][0]["fields"]["boundary_conditions"])

    def test_extracts_explicit_physics_feature_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "point_source"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").physics("lpeq").create('
                '"ptsrc1", "PointSourceTerm", 0);\n'
                'model.component("comp1").physics("lpeq").feature("ptsrc1").'
                'setIndex("f", 1, 0);\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertTrue(index["cases"][0]["fields"]["boundary_conditions"])
            self.assertEqual(index["cases"][0]["parameters"][0]["name"], "lpeq.ptsrc1.f")
            self.assertEqual(index["cases"][0]["parameters"][0]["value"], "1")

    def test_extracts_physics_set_and_material_property(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "electric_sensor"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").physics("es").feature("pot1").set("V0", 1);\n'
                'model.component("comp1").material("mat1").propertyGroup("def").'
                'set("relpermittivity", new String[]{"2"});\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = index["cases"][0]["parameters"]
            self.assertEqual(
                {(item["name"], item["value"]) for item in parameters},
                {("es.pot1.V0", "1"), ("mat1.relpermittivity", "2")},
            )
            self.assertTrue(index["cases"][0]["fields"]["materials"])

    def test_electric_sensor_query_uses_eit_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "electric_sensor"
            case.mkdir()
            (case / "model.md").write_text("Electrostatics electric sensor.", encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = recommend(index, "EIT permittivity sensor", 1)["recommendations"][0]
            self.assertIn("简化静电 EIT", item["risks"][0])
            self.assertIn("es.nD", item["validation_steps"][2])

    def test_extracts_batch_sweep_settings_and_output_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "batch_sweep"
            case.mkdir()
            (case / "model.java").write_text(
                'model.study("std1").feature("batsw").setIndex('
                '"plistarr", "range(1,1,10)", 0);\n'
                'model.study("std1").feature("batsw").set("batchdir", "C:\\\\COMSOL");\n'
                'model.result().table("tbl2").set("filename", "C:\\\\COMSOL\\\\results.txt");\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("batsw.plistarr", "range(1,1,10)"), parameters)
            self.assertIn(("batsw.batchdir", "C:\\COMSOL"), parameters)
            self.assertIn(("tbl2.filename", "C:\\COMSOL\\results.txt"), parameters)

    def test_batch_sweep_query_uses_batch_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "batch_sweep"
            case.mkdir()
            (case / "model.md").write_text("BatchSweep probe result.", encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = recommend(index, "batch sweep", 1)["recommendations"][0]
            self.assertIn("C:\\COMSOL", item["risks"][0])
            self.assertIn("十个扫描结果", item["validation_steps"][2])

    def test_internal_coordinate_tensors_are_not_model_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "point_source"
            case.mkdir()
            (case / "metadata.md").write_text(
                '<tensor name="root.comp1.spatial.F" description="material" plot="true">\n'
                '<tensor name="root.comp1.mesh.t" description="mesh tangent" plot="false">\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertFalse(fields["materials"])
            self.assertFalse(fields["mesh"])
            self.assertFalse(fields["results"])

    def test_generic_internal_tensors_and_mesh_savepoints_are_not_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "point_source"
            case.mkdir()
            (case / "metadata.md").write_text(
                '<tensor name="root.comp1.geometry.g" description="material geometry" plot="true">\n'
                '<tensor name="root.comp1.lpeq.nmesh" description="mesh normal" plot="false">\n'
                '<savePointBinary class="MESH" resource="mesh1.mphbin"/>\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertFalse(fields["geometry"])
            self.assertFalse(fields["materials"])
            self.assertFalse(fields["mesh"])
            self.assertFalse(fields["results"])

    def test_code_parameters_rank_above_pdf_style_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "parameter_case"
            case.mkdir()
            (case / "notes.md").write_text("Load speed = 20 m/s", encoding="utf-8")
            (case / "model.java").write_text(
                'model.param().set("LoadSpeed", "20[m/s]");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "load speed", 1)["recommendations"][0]
            self.assertEqual(item["parameter_changes"]["parameters"][0]["name"], "LoadSpeed")

    def test_extracts_tab_separated_parameter_table(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "parameter_table"
            case.mkdir()
            (case / "parameters.txt").write_text(
                "k_ads\t1e-6[m^3/(mol*s)]\tForward rate constant\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertEqual(index["cases"][0]["parameters"][0]["name"], "k_ads")
            self.assertEqual(index["cases"][0]["parameters"][0]["value"], "1e-6[m^3/(mol*s)]")

    def test_pdf_parameter_candidates_are_omitted_when_code_parameters_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "mixed_parameters"
            case.mkdir()
            (case / "notes.md").write_text("plot label = 2", encoding="utf-8")
            (case / "model.java").write_text(
                'model.param().set("D", "1e-9[m^2/s]");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = recommend(index, "parameter", 1)["recommendations"][0]["parameter_changes"]["parameters"]
            self.assertEqual([item["name"] for item in parameters], ["D"])

    def test_removed_code_parameter_is_not_recommended(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "recursive_geometry"
            case.mkdir()
            (case / "model.java").write_text(
                'model.param().set("mslevel", "2");\n'
                'model.param().remove("mslevel");\n',
                encoding="utf-8",
            )
            (case / "model.m").write_text(
                "model.param.set('mslevel', '2');\n"
                "model.param.remove('mslevel');\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertFalse(index["cases"][0]["parameters"])

    def test_recursion_limits_are_applicability_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "recursive_geometry"
            case.mkdir()
            (case / "method.md").write_text(
                "create_carpet recursion method.\n"
                'error("Carpet level needs to be at least 1.");\n'
                'error("Carpet level needs to be at most 5.");\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertTrue(fields["geometry"])
            self.assertEqual(len(fields["applicability"]), 2)

    def test_reads_explicit_mph_method_call_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "recursive_geometry"
            case.mkdir()
            model = {
                "apiClass": "MethodCallFeature",
                "displayLabel": "Create_carpet 1",
                "settings": [{"name": "level", "value": ["3", "3"]}],
            }
            with zipfile.ZipFile(case / "carpet.mph", "w") as archive:
                archive.writestr("smodel.json", json.dumps(model))
            index = build_index(root, root / "index.json")
            self.assertEqual(index["cases"][0]["parameters"][0]["name"], "level")
            self.assertEqual(index["cases"][0]["parameters"][0]["value"], "3")

    def test_recursive_query_uses_geometry_validation_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "recursive_geometry"
            case.mkdir()
            (case / "method.md").write_text("Menger recursive geometry.", encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = recommend(index, "Menger recursion level", 1)["recommendations"][0]
            self.assertIn("重复运行几何生成方法", item["validation_steps"][1])

    def test_recognizes_electromagnetic_boundaries_and_validity_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "transmission_line"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("c").physics("ec").create("gnd1", "Ground", 1);\n'
                'model.param().descr("FR", "Validity of reasonable frequency range");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertTrue(fields["boundary_conditions"])
            self.assertTrue(fields["applicability"])

    def test_empty_container_lists_are_not_treated_as_model_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "geometry_only"
            case.mkdir()
            (case / "model.md").write_text(
                '<PhysicsList tag="physics" name="Physics">\n'
                '<MaterialList tag="material" name="Materials">\n'
                '<StudyList tag="study" name="List">\n'
                'Geometry sequence is built.',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertFalse(fields["physics"])
            self.assertFalse(fields["materials"])
            self.assertFalse(fields["solver"])
            self.assertTrue(fields["geometry"])

    def test_geometry_query_uses_geometry_validation_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "random_geometry"
            case.mkdir()
            (case / "model.md").write_text("Geometry sequence.", encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = recommend(index, "如何创建随机几何？", 1)["recommendations"][0]
            self.assertIn("重复运行几何生成方法", item["validation_steps"][1])
            self.assertNotIn("重新求解", " ".join(item["validation_steps"]))

    def test_geometry_only_case_does_not_invent_physics_mesh_or_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "light_bulb_geometry"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").geom("geom1").axisymmetric(true);\n'
                'model.component("comp1").mesh().create("mesh1");\n',
                encoding="utf-8",
            )
            (case / "guide.md").write_text(
                "From the Show in physics list, choose Off.\n"
                "The domains result after a geometry operation.\n"
                '<ComponentPhysicsList tag="physics" name="Physics">\n'
                '<MeshSequence tag="mesh1" name="Mesh 1">\n'
                '<BinaryResource file="mesh1.mphbin" binarytype="MESH"/>\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertTrue(fields["geometry"])
            self.assertFalse(fields["physics"])
            self.assertFalse(fields["mesh"])
            self.assertFalse(fields["results"])

    def test_api_imports_are_not_model_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "method_only"
            case.mkdir()
            (case / "method.md").write_text(
                "import com.comsol.model.physics.*;\n"
                "import com.comsol.api.database.result.*;\n"
                "recursive geometry method.\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertFalse(fields["physics"])
            self.assertFalse(fields["results"])

    def test_reports_conflicting_explicit_parameter_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "history_case"
            case.mkdir()
            (case / "model.java").write_text(
                'model.param().set("T_init", "20[degC]");\n'
                'model.param().set("T_init", "60[degC]");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "initial temperature", 1)["recommendations"][0]
            self.assertIn("T_init", item["parameter_changes"]["conflicts"])
            self.assertIn("同名参数存在多个有来源值", item["risks"][0])

    def test_normalizes_java_and_matlab_tensor_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "electrochemical_polishing"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").physics("ec").feature("cucns1").'
                'set("sigma", new int[]{10, 0, 0, 0, 10, 0, 0, 0, 10});',
                encoding="utf-8",
            )
            (case / "model.m").write_text(
                "model.component('comp1').physics('ec').feature('cucns1')."
                "set('sigma', [10 0 0 0 10 0 0 0 10]);",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "electrochemical polishing", 1)["recommendations"][0]
            self.assertEqual(item["parameter_changes"]["conflicts"], {})
            self.assertEqual(
                index["cases"][0]["parameters"][0]["value"],
                "[10, 0, 0, 0, 10, 0, 0, 0, 10]",
            )

    def test_extracts_deformed_geometry_and_time_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "electrochemical_polishing"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").common("pnmv1").'
                'set("prescribedNormalVelocity", "-K*(-ec.nJ)");\n'
                'model.study("std1").feature("time").set("tlist", "range(0,10)");',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(
                ("common.pnmv1.prescribedNormalVelocity", "-K*(-ec.nJ)"),
                parameters,
            )
            self.assertIn(("study.time.tlist", "range(0,10)"), parameters)

    def test_electrochemical_polishing_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("电化学抛光 moving boundary")
        self.assertIn("简化消耗定律", risks[0])
        self.assertIn("-K*(-ec.nJ)", steps[0])
        self.assertIn("9e5 A/m^2", steps[2])

    def test_cell_thermal_runaway_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("如何模拟电芯热失控 thermal runaway")
        self.assertIn("烘箱加热诱发", risks[0])
        self.assertIn("Arrhenius", risks[1])
        self.assertIn("Q_tot=Qsei+Qne+Qpe+Qele", steps[1])
        self.assertIn("0–120 min", steps[2])

    def test_thermal_runaway_key_parameters_are_prioritized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "cell_thermal_runaway"
            case.mkdir()
            (case / "model.m").write_text(
                "model.param.set('d_can', '0.5[mm]');\n"
                "model.param.set('T_oven', '155[degC]');\n"
                "model.param.set('T_init', '35[degC]');\n"
                "model.param.set('h_conv', '7.17[W/(m^2*K)]');\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "thermal runaway", 1)["recommendations"][0]
            names = [
                parameter["name"]
                for parameter in item["parameter_changes"]["parameters"][:3]
            ]
            self.assertEqual(names, ["T_oven", "T_init", "h_conv"])

    def test_extracts_named_parameter_group_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "cell_thermal_runaway"
            case.mkdir()
            (case / "model.m").write_text(
                "model.param('par2').set('Asei', '1.667e15[1/s]');\n"
                "model.param('par2').set('h_conv', '7.17[W/(m^2*K)]');\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("Asei", "1.667e15[1/s]"), parameters)
            self.assertIn(("h_conv", "7.17[W/(m^2*K)]"), parameters)

    def test_extracts_unstructured_mesh_size_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "piston_mesh"
            case.mkdir()
            (case / "model.m").write_text(
                "model.component('comp1').mesh('mesh1').autoMeshSize(7);\n"
                "model.component('comp1').mesh('mesh1').feature('ftet1')."
                "feature('size1').set('hcurve', 0.45);\n"
                "model.component('comp1').mesh('mesh1').feature('ftet1')."
                "feature('size1').set('hmin', '0.0002');\n"
                "model.component('comp1').mesh('mesh1').feature('size')."
                "set('hgrad', 1.8);\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("mesh1.autoMeshSize", "7"), parameters)
            self.assertIn(("mesh1.ftet1.size1.hcurve", "0.45"), parameters)
            self.assertIn(("mesh1.ftet1.size1.hmin", "0.0002"), parameters)
            self.assertIn(("mesh1.size.hgrad", "1.8"), parameters)

    def test_unstructured_mesh_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("调整非结构网格生成器的单元大小")
        self.assertIn("边界编号 8、39", risks[0])
        self.assertIn("hcurve、hmin、hnarrow", steps[0])
        self.assertIn("网格收敛研究", steps[2])

    def test_lid_driven_cavity_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("顶盖驱动方腔流")
        self.assertIn("二维、不可压、层流、稳态", risks[0])
        self.assertIn("动力黏度 1/Re", risks[1])
        self.assertIn("u(y)", steps[2])
        self.assertIn("v(x)", steps[2])

    def test_extracts_study_parameter_sweep_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "lid_driven_cavity"
            case.mkdir()
            (case / "model.m").write_text(
                "model.study('std1').feature('stat').setIndex('pname', 'Re', 0);\n"
                "model.study('std1').feature('stat').setIndex("
                "'plistarr', '100 400 1000 3200 5000 7500 10000', 0);\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("study.stat.pname", "Re"), parameters)
            self.assertIn(
                ("study.stat.plistarr", "100 400 1000 3200 5000 7500 10000"),
                parameters,
            )

    def test_effective_diffusivity_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("多孔材料的有效扩散系数")
        self.assertIn("二维孔隙模型与一维均质化模型", risks[0])
        self.assertIn("D1/epsilon", steps[1])
        self.assertIn("flux_avg", steps[2])

    def test_room_eigenmodes_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("房间的特征模态")
        self.assertIn("墙壁完全刚性", risks[0])
        self.assertIn("shift=90 Hz", steps[1])
        self.assertIn("acpr.p_t", steps[2])

    def test_extracts_eigenfrequency_study_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "room_eigenmodes"
            case.mkdir()
            (case / "model.m").write_text(
                "model.study('std1').feature('eig').set('shift', '90');\n"
                "model.study('std1').feature('eig').set('chkeigregion', true);\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("study.eig.shift", "90"), parameters)
            self.assertIn(("study.eig.chkeigregion", "true"), parameters)


if __name__ == "__main__":
    unittest.main()
