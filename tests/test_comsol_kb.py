import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from comsol_kb import (
    build_index,
    merge_case_indexes,
    recommend,
    validation_and_query_risks,
    write_master_summary,
)


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

    def test_invalid_json_template_is_indexed_as_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "cloud_template"
            case.mkdir()
            (case / "template.json").write_text(
                '{"instance": "compute", // replace before deployment\n}',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertIn("replace before deployment", index["cases"][0]["searchable_text"])

    def test_deployment_and_geometry_workflows_do_not_invent_physics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cloud = root / "通过 Amazon EC2™ 运行 COMSOL® 软件"
            geometry = root / "蒸汽重整器几何"
            cloud.mkdir()
            geometry.mkdir()
            (cloud / "guide.md").write_text(
                "示例背景提到固体力学、材料和求解器。instance=8",
                encoding="utf-8",
            )
            (geometry / "guide.md").write_text(
                "几何教程背景提到传热材料和稳态求解器。",
                encoding="utf-8",
            )
            index = build_index([cloud, geometry], root / "index.json")
            cases = {item["name"]: item for item in index["cases"]}
            for name in cases:
                self.assertEqual(cases[name]["fields"]["physics"], [])
                self.assertEqual(cases[name]["fields"]["materials"], [])
                self.assertEqual(cases[name]["fields"]["solver"], [])
            self.assertEqual(cases[cloud.name]["parameters"], [])

    def test_merges_indexes_deduplicates_cases_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "稳态传导传热 - 二维"
            case.mkdir()
            (case / "model.md").write_text("物理场：传热\n结果：温度", encoding="utf-8")
            first = root / "first.json"
            second = root / "second.json"
            build_index(case, first)
            build_index(case, second)
            master = root / "master.json"
            payload = merge_case_indexes([first, second], master)
            self.assertEqual(len(payload["cases"]), 1)
            summary = root / "summary.md"
            write_master_summary(payload, summary)
            text = summary.read_text(encoding="utf-8")
            self.assertIn("COMSOL 案例总知识库", text)
            self.assertIn("稳态传导传热 - 二维", text)

    def test_large_text_dataset_is_recorded_as_asset_without_indexing_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "scanned_data"
            case.mkdir()
            data = case / "human_femur.txt"
            data.write_text("not applicable " + ("0 " * 10_000_000), encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = index["cases"][0]
            self.assertIn(str(Path("scanned_data") / "human_femur.txt"), item["assets"])
            self.assertFalse(item["fields"]["applicability"])

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

    def test_internal_mph_localization_text_is_not_applicability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "chemical_etching"
            case.mkdir()
            (case / "model.mph").write_text(
                '<param T="33" param="textCompressibilityMixtureModel2" '
                'value="1|1,not applicable to mixture model"></param>',
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

    def test_extracts_image_sequence_export_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "image_export"
            case.mkdir()
            (case / "model.java").write_text(
                'model.result().export("anim1").set("type", "imageseq");\n'
                'model.result().export("anim1").set("imagefilename", "C:\\\\COMSOL\\\\my_image.png");\n'
                'model.result().export("anim1").set("parameter", "xcut");\n'
                'model.result().export("anim1").set("pstart", -3.5);\n'
                'model.result().export("anim1").set("pstop", 8);\n',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("export.anim1.type", "imageseq"), parameters)
            self.assertIn(("export.anim1.imagefilename", "C:\\COMSOL\\my_image.png"), parameters)
            self.assertIn(("export.anim1.parameter", "xcut"), parameters)
            self.assertIn(("export.anim1.pstart", "-3.5"), parameters)
            self.assertIn(("export.anim1.pstop", "8"), parameters)

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

    def test_geometry_tutorial_background_does_not_invent_model_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "wheel_rim"
            case.mkdir()
            (case / "tutorial.md").write_text(
                "Results and Discussion\n"
                "This could be important for certain physics.\n"
                "The entire rim is made of the same material.\n"
                "Set up selections to use for the physics definitions.\n"
                "Selections streamline the material and physics setup.\n",
                encoding="utf-8",
            )
            (case / "model.mph").write_text(
                '<MultiphysicsCouplingList tag="multiphysics"></MultiphysicsCouplingList>\n'
                '<SolverSequenceList tag="sol"></SolverSequenceList>\n'
                '<GroupList tag="group" name="Loads and Constraints"></GroupList>',
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            fields = index["cases"][0]["fields"]
            self.assertFalse(fields["physics"])
            self.assertFalse(fields["materials"])
            self.assertFalse(fields["boundary_conditions"])
            self.assertFalse(fields["solver"])
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

    def test_normalizes_java_and_matlab_string_array_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "chemical_etching"
            case.mkdir()
            (case / "model.java").write_text(
                'model.component("comp1").physics("spf").feature("wallbc2").'
                'set("utr", new String[]{"1[mm/s]", "0", "0"});',
                encoding="utf-8",
            )
            (case / "model.m").write_text(
                "model.component('comp1').physics('spf').feature('wallbc2')."
                "set('utr', {'1[mm/s]' '0' '0'});",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            item = recommend(index, "chemical etching", 1)["recommendations"][0]
            self.assertEqual(item["parameter_changes"]["conflicts"], {})

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

    def test_chemical_etching_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("如何模拟铜的湿法化学蚀刻？")
        self.assertIn("r_surface=-kf*cCuCl2", risks[0])
        self.assertIn("v_surface=-r_surface*M_Cu/rho_Cu", risks[1])
        self.assertIn("J0=r_surface", steps[1])
        self.assertIn("超弹性", steps[3])
        self.assertIn("tmax=3[h]", steps[4])

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

    def test_ultrafast_heat_transfer_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("飞秒激光加热引起的超快传热")
        self.assertIn("POS、HOS、PTS、HTS", risks[0])
        self.assertIn("同名参数和方程", risks[1])
        self.assertIn("0.1*t_p", steps[1])
        self.assertIn("T_HTS_e/T_HTS_l", steps[2])

    def test_shell_diffusion_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("钢罐中的壳扩散")
        self.assertIn("不是物质扩散", risks[0])
        self.assertIn("sigma*d", risks[1])
        self.assertIn("4.032e6", steps[1])
        self.assertIn("电流守恒", steps[2])

    def test_current_density_is_not_material_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "surface_conduction"
            case.mkdir()
            (case / "notes.md").write_text(
                "显示局部电流密度大小和表面电势分布。",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertEqual(index["cases"][0]["fields"]["materials"], [])

    def test_golf_ball_trajectory_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks(
            "如何计算高尔夫球在空气阻力下的落地点？"
        )
        self.assertIn("不求解高尔夫球周围的三维空气流场", risks[0])
        self.assertIn("构建历史", risks[2])
        self.assertIn("U0*cos(alpha)", steps[0])
        self.assertIn("d=4.267 cm", steps[1])
        self.assertIn("Stop Condition", steps[3])

    def test_mph_section_headers_are_not_geometry_or_mesh_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "global_ode"
            case.mkdir()
            (case / "model.mph").write_text(
                "-- Geometry -->\n-- Geometry tags -->\n-- Extended mesh -->\n"
                "<GeomList tag=\"geom\" name=\"Geometry Parts\">\n"
                "-- Geometry frame coordinates -->\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertEqual(index["cases"][0]["fields"]["geometry"], [])
            self.assertEqual(index["cases"][0]["fields"]["mesh"], [])
            self.assertEqual(index["cases"][0]["fields"]["physics"], [])

    def test_dg_flux_features_are_boundary_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "shock_tube"
            case.mkdir()
            (case / "model.m").write_text(
                "model.component('comp1').physics('wahw')."
                "create('iflux1', 'IntFluxBoundary', 0);",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            self.assertTrue(index["cases"][0]["fields"]["boundary_conditions"])

    def test_tubular_reactor_surrogate_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("管式反应器代理模型 App")
        self.assertIn("只预测训练时配置的温度 T 和转化率 xA", risks[0])
        self.assertIn("71518–79205", risks[1])
        self.assertIn("100 次", risks[2])
        self.assertIn("dnn1_1", steps[1])
        self.assertIn("留出参数点", steps[2])

    def test_extracts_surrogate_training_bounds_and_solve_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "surrogate"
            case.mkdir()
            (case / "model.m").write_text(
                "model.study('std1').feature('sm').setEntry("
                "'lboundselection', 'col1', '71518');\n"
                "model.study('std1').feature('sm').setEntry("
                "'uboundselection', 'col1', '79205');\n"
                "model.study('std1').feature('sm').set('nsolvenonadp', 100);\n",
                encoding="utf-8",
            )
            index = build_index(root, root / "index.json")
            parameters = {
                (item["name"], item["value"]) for item in index["cases"][0]["parameters"]
            }
            self.assertIn(("study.sm.lboundselection.col1", "71518"), parameters)
            self.assertIn(("study.sm.uboundselection.col1", "79205"), parameters)
            self.assertIn(("study.sm.nsolvenonadp", "100"), parameters)

    def test_silicon_wafer_laser_heating_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks(
            "如何模拟旋转硅晶片受到移动高斯激光加热？"
        )
        self.assertIn("不求解电磁波", risks[0])
        self.assertIn("同一参数 emissivity", risks[1])
        self.assertIn("一个扫掠单元", risks[3])
        self.assertIn("积分 q0", steps[1])
        self.assertIn("T_diff", steps[3])

    def test_transient_stepped_heating_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks(
            "如何使用显式事件模拟热载荷从100 W突降到10 W？"
        )
        self.assertIn("起始为 100 W", risks[0])
        self.assertIn("降为 10 W", risks[0])
        self.assertIn("总功率", risks[1])
        self.assertIn("不包含 0.25 s", risks[2])
        self.assertIn("HighLoad 的初值为 1", steps[0])
        self.assertIn("rtol=0.01 与 0.001", steps[3])

    def test_thermostat_query_uses_specific_validation(self):
        risks, steps = validation_and_query_risks(
            "如何使用带滞回的恒温器控制加热器开关？"
        )
        self.assertIn("55", risks[0])
        self.assertIn("45", risks[0])
        self.assertIn("T_s=intop1(T)", steps[0])
        self.assertIn("HeaterState", steps[1])
        self.assertIn("eventtol", steps[2])

    def test_new_batch_cases_use_specific_validation(self):
        risks, steps = validation_and_query_risks("积分-偏微分方程")
        self.assertIn("intop1", risks[0])
        self.assertIn("Q_source", steps[0])

        risks, steps = validation_and_query_risks("基于扫描数据生成可供仿真的网格")
        self.assertIn("human_femur.txt", risks[0])
        self.assertIn("Hausdorff", steps[3])

        risks, steps = validation_and_query_risks("激波管")
        self.assertIn("DG", risks[0])
        self.assertIn("CFL_cond=0.3", steps[2])

        risks, steps = validation_and_query_risks("集群设置验证")
        self.assertIn("集群", risks[0])
        self.assertIn("Sweep.mph", steps[1])

        risks, steps = validation_and_query_risks("借助变形几何接口修改导入的 CAD 几何")
        self.assertIn("wrench.mphbin", risks[0])
        self.assertIn("0/2/4 cm", steps[1])

        risks, steps = validation_and_query_risks("科赫雪花建模")
        self.assertIn("物理场", risks[0])
        self.assertIn("周长", steps[1])

        risks, steps = validation_and_query_risks("馈线夹的变形")
        self.assertIn("两个载荷工况", risks[0])
        self.assertIn("Ffeeder=2000 N", steps[0])

    def test_second_batch_cases_use_specific_validation(self):
        risks, steps = validation_and_query_risks("两种载荷工况下的锥形悬臂梁")
        self.assertIn("平面应力", risks[0])
        self.assertIn("10 MN/m", steps[1])

        risks, steps = validation_and_query_risks("轮辋几何虚拟操作")
        self.assertIn("Remove Details", risks[0])
        self.assertIn("skewness", steps[1])

        risks, steps = validation_and_query_risks("螺旋静态混合器")
        self.assertIn("层流", risks[0])
        self.assertIn("D1=1e-10", steps[1])

        risks, steps = validation_and_query_risks("洛伦兹吸引子")
        self.assertIn("Global Equations", risks[0])
        self.assertIn("Tfinal=35", steps[1])

        risks, steps = validation_and_query_risks("曼德勃罗集和柏林噪声")
        self.assertIn("两个不同示例", risks[0])
        self.assertIn("octaves=5", steps[1])

        risks, steps = validation_and_query_risks("母线板焦耳热")
        self.assertIn("20 mV", risks[0])
        self.assertIn("能量平衡", steps[2])

        risks, steps = validation_and_query_risks("母线板装配的焦耳热")
        self.assertIn("接触电阻", risks[0])
        self.assertIn("Jan=8000", steps[0])

        risks, steps = validation_and_query_risks("母线板装配几何系列教程")
        self.assertIn("不包含", risks[0])
        self.assertIn("a_c_w", steps[2])

        risks, steps = validation_and_query_risks("起搏器电极")
        self.assertIn("0.4 S/m", risks[0])
        self.assertIn("V0=1 V", steps[0])

    def test_busbar_assembly_query_prefers_assembly_case(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            single = root / "母线板焦耳热"
            assembly = root / "母线板装配的焦耳热"
            single.mkdir()
            assembly.mkdir()
            (single / "model.md").write_text("焦耳热 温度 参数", encoding="utf-8")
            (assembly / "model.md").write_text("焦耳热 温度 参数", encoding="utf-8")
            index = build_index([single, assembly], root / "index.json")
            result = recommend(index, "评估母线板装配参数变化对焦耳热温度的影响", 1)
            self.assertEqual(result["recommendations"][0]["case_name"], "母线板装配的焦耳热")

    def test_third_batch_cases_use_specific_validation(self):
        cases = [
            ("起搏器电极模型中添加注释", "Annotation", "数值结果应保持不变"),
            ("汽车消声器", "PlaneWaveRadiation", "功率平衡"),
            ("浅水方程", "深度平均", "总质量守恒"),
            ("求解模型后保存数据的作业序列6.3", "C:\\COMSOL\\myfile.mph", "重新打开"),
            ("球对称传递", "Rp", "能量守恒"),
            ("曲线数字化仪", "数字化工具", "标定"),
            ("曲轴子模型分析", "切割边界", "应力连续性"),
            ("热控制器，降阶模型", "6 模态", "开关时刻"),
            ("热烧蚀除料建模6.2", "DeformedGeometry", "除料深度"),
            ("热微执行器的简化模型", "微米级", "d=3 um"),
            ("热执行器", "焦耳热模型", "thermal_actuator_jh"),
            ("热执行器代理模型 App", "DNN", "留出未训练点"),
            ("如何生成随机非均匀材料数据6.2", "多个示例", "多组随机实现"),
        ]
        for query, risk_text, step_text in cases:
            with self.subTest(query=query):
                risks, steps = validation_and_query_risks(query)
                self.assertTrue(any(risk_text in item for item in risks))
                self.assertTrue(any(step_text in item for item in steps))

    def test_image_export_case_uses_specific_validation(self):
        risks, steps = validation_and_query_risks("如何在求解后自动导出图像仅6.3")
        self.assertTrue(any("不是瞬态时间动画" in item for item in risks))
        self.assertTrue(any("type=imageseq" in item for item in steps))
        self.assertTrue(any("Solutionseq" in item and "Exportseq" in item for item in steps))

    def test_fourth_batch_categories_use_grounded_validation(self):
        cases = [
            ("使用 Microsoft® Azure 运行 COMSOL® 软件", "不是 COMSOL 物理模型", "许可证"),
            ("在 COMSOL Multiphysics 中编辑与修复面网格", "不提供可直接复用的完整物理场", "非流形边"),
            ("用 Hodgkin-Huxley 模型模拟动作电位", "临床诊断", "门控变量"),
            ("已实施反应延迟的恒温器", "延迟", "超调"),
            ("瞬态声压级6.3", "FFT", "Parseval"),
            ("涡轮增压器转子的特征值分析", "线性化", "刚体模态"),
            ("圆柱绕流", "雷诺数", "质量流量"),
            ("碳纤维编织结构的各向异性传热", "不同传热机制", "能量平衡"),
            ("锥形量子点", "数学 PDE", "伪解"),
        ]
        for query, risk_text, step_text in cases:
            with self.subTest(query=query):
                risks, steps = validation_and_query_risks(query)
                self.assertTrue(any(risk_text in item for item in risks))
                self.assertTrue(any(step_text in item for item in steps))

    def test_conflict_risk_summary_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "history_case"
            case.mkdir()
            lines = []
            for index in range(10):
                lines.append(f'model.param().set("p{index}", "1");')
                lines.append(f'model.param().set("p{index}", "2");')
            (case / "model.java").write_text("\n".join(lines), encoding="utf-8")
            index = build_index(root, root / "index.json")
            item = recommend(index, "history", 1)["recommendations"][0]
            conflict_risk = next(risk for risk in item["risks"] if "同名参数" in risk)
            self.assertIn("另有 2 个冲突项", conflict_risk)


if __name__ == "__main__":
    unittest.main()
