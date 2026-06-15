#!/usr/bin/env python3
"""Evidence-grounded local knowledge base for COMSOL cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

SUPPORTED = {
    ".pdf", ".md", ".markdown", ".json", ".csv", ".txt",
    ".mph", ".ppa", ".pptx", ".java", ".m",
}
ASSETS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}
MAX_TEXT_INDEX_BYTES = 20_000_000
DEPLOYMENT_ONLY_CASES = {
    "使用 Microsoft® Azure 运行 COMSOL® 软件",
    "通过 Amazon EC2™ 运行 COMSOL® 软件",
    "jsonscripts",
    "COMSOL_json",
}
GEOMETRY_MESH_ONLY_CASES = {
    "在 COMSOL Multiphysics 中编辑与修复面网格",
    "蒸汽重整器几何",
    "支架几何的扫掠网格",
    "使用插值和图像数据为不规则形状建模",
    "使用网格划分序列",
}
FIELDS = {
    "physics": ("物理场", "physics", "interface", "方程", "传热", "流体", "结构", "电磁"),
    "geometry": (
        "几何", "geometry", "geom(", "sphere", "create_cheese",
        "recursive", "recursion", "menger", "sierpinski", "create_sponge",
        "create_carpet", '"block"', "'block'", '"square"', "'square'",
        "尺寸", "半径", "直径", "长度", "宽度", "高度", "厚度",
    ),
    "materials": (
        "材料", "material", "密度", "导热", "弹性模量", "泊松比",
        "relpermittivity", "relative permittivity", "介电常数",
    ),
    "boundary_conditions": (
        "边界条件", "boundary condition", "入口", "出口", "载荷", "约束", "温度",
        "fluxsource", "no flux", "noflux", "dirichletboundary", "fixedconstraint",
        "boundaryload", "fluxboundary", "concentration", "fixed", '"ground"',
        "electricpotential", "perfectmagneticconductor", "heatfluxboundary",
        "electric insulation",
        "thermalinsulation", "temperatureboundary", "outflow", "convectiveoutflow",
        "bodyload", "displacement1",
        "point source", "pointsource", "point source term", "pointsourceterm",
        "prescribednormalmeshvelocitydeformedgeometry",
        "prescribednormalmeshdisplacementdeformedgeometry",
        "prescribednormalvelocity", "deformingdomaindeformedgeometry",
        "wallbc", "slidingwall", "pressurepointconstraint",
        "intfluxboundary", "fluxboundaryloadfactor",
    ),
    "mesh": ("网格", "mesh", "单元", "element"),
    "solver": (
        "求解器", "solver", "study", "研究", "稳态", "瞬态", "频域",
        "batchsweep", "batch sweep", "parametric", "批处理扫描", "eigenfrequency",
    ),
    "results": (
        "结果", "result", "plot", "曲线", "最大值", "最小值",
        "probe", "saved probe table",
    ),
    "applicability": (
        "适用范围", "applicable", "适用于", "限制条件", "适用条件",
        "不用于", "validity of reasonable frequency range", "reasonable frequency range",
        "needs to be at least", "needs to be at most",
        "singularity", "奇异性",
        "simplified electrostatic setting", "简化的静电设置",
        "quasi-static", "quasi static", "sufficiently stirred", "good stirring",
        "does not take effects from the curved boundary into account",
        "depletion rate is directly proportional to the normal current density",
        "initially at room temperature", "placed in an oven",
        "exothermal decomposition reactions", "thermal runaway",
        "simple 1d model demonstrating ultrafast heat transfer",
        "femtosecond pulsed laser heating", "conventional fourier heat conduction",
    ),
}
PARAMETER_RE = re.compile(
    r"(?P<name>[\w\u4e00-\u9fff][\w\u4e00-\u9fff .()/\-]{0,40}?)\s*"
    r"(?:=|：|:)\s*(?P<value>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*"
    r"(?P<unit>[a-zA-Zµμ°/%][a-zA-Z0-9µμ°/%^·.*\-]*)?"
)
CODE_PARAMETER_RE = re.compile(
    r"""model\.param(?:\(\s*["'][^"']+["']\s*\)|\(\))?\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*["'](?P<value>[^"']+)["']"""
)
CODE_PARAMETER_REMOVE_RE = re.compile(
    r"""model\.param(?:\(\s*["'][^"']+["']\s*\)|\(\))?\.remove\(\s*["'](?P<name>[^"']+)["']\s*\)"""
)
PHYSICS_FEATURE_SETTING_RE = re.compile(
    r"""physics\(\s*["'](?P<physics>[^"']+)["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.setIndex\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<value>[^,\r\n]+)\s*,\s*\d+\s*\)"""
)
PHYSICS_FEATURE_SET_RE = re.compile(
    r"""physics\(\s*["'](?P<physics>[^"']+)["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
COMMON_FEATURE_SET_RE = re.compile(
    r"""common\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
STUDY_FEATURE_SET_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>tlist)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+\))\s*\)"""
)
STUDY_FEATURE_INDEX_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.setIndex\(\s*["'](?P<name>pname|plistarr|punit)["']\s*,\s*["'](?P<value>[^"']*)["']\s*,\s*\d+\s*\)"""
)
STUDY_FEATURE_GENERIC_SET_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>shift|neigs|chkeigregion|rtol|tunit)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
SURROGATE_STUDY_ENTRY_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["']sm["']\s*\)"""
    r"""\.setEntry\(\s*["'](?P<name>lboundselection|uboundselection)["']\s*,\s*"""
    r"""["'](?P<column>col\d+)["']\s*,\s*["'](?P<value>[^"']+)["']\s*\)"""
)
SURROGATE_STUDY_SET_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["']sm["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>nsolvenonadp|errorhandling)["']\s*,\s*"""
    r"""(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
MESH_NESTED_FEATURE_SET_RE = re.compile(
    r"""mesh\(\s*["'](?P<mesh>[^"']+)["']\s*\)\.feature\(\s*["'](?P<parent>[^"']+)["']\s*\)"""
    r"""\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
MESH_FEATURE_SET_RE = re.compile(
    r"""mesh\(\s*["'](?P<mesh>[^"']+)["']\s*\)\.feature\(\s*["'](?P<feature>[^"']+)["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
MESH_AUTO_SIZE_RE = re.compile(
    r"""mesh\(\s*["'](?P<mesh>[^"']+)["']\s*\)\.autoMeshSize\(\s*(?P<value>\d+)\s*\)"""
)
MATERIAL_PROPERTY_RE = re.compile(
    r"""material\(\s*["'](?P<material>[^"']+)["']\s*\)\.propertyGroup\(\s*["'][^"']+["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>[^"']+)["']\s*,\s*new String\[\]\s*\{\s*["'](?P<value>[^"']+)["']"""
)
BATCH_SWEEP_INDEX_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["']batsw["']\s*\)"""
    r"""\.setIndex\(\s*["'](?P<name>pname|plistarr|punit)["']\s*,\s*["'](?P<value>[^"']*)["']\s*,\s*\d+\s*\)"""
)
BATCH_SWEEP_SET_RE = re.compile(
    r"""study\(\s*["'][^"']+["']\s*\)\.feature\(\s*["']batsw["']\s*\)"""
    r"""\.set\(\s*["'](?P<name>batchdir|serverdir|clearmesh|clearsol|synchsolutions|accumtable)["']\s*,\s*(?P<value>[^)\r\n]+)\s*\)"""
)
RESULT_TABLE_FILENAME_RE = re.compile(
    r"""result\(\)\.table\(\s*["'](?P<table>[^"']+)["']\s*\)\.set\(\s*["']filename["']\s*,\s*["'](?P<value>[^"']+)["']\s*\)"""
)
RESULT_EXPORT_SET_RE = re.compile(
    r"""result(?:\(\))?\.export\(\s*["'](?P<export>[^"']+)["']\s*\)\.set\(\s*"""
    r"""["'](?P<name>imagefilename|giffilename|filename|type|sweeptype|parameter|pstart|pstop|punit|plotgroup)["']\s*,\s*"""
    r"""(?P<value>["'][^"']*["']|[^)\r\n]+)\s*\)"""
)
TAB_PARAMETER_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\t(?P<value>[^\t]+)(?:\t(?P<description>.*))?$"
)


@dataclass
class Evidence:
    source: str
    excerpt: str

    def as_dict(self) -> dict:
        return {"source": self.source, "excerpt": self.excerpt}


@dataclass
class Case:
    case_id: str
    name: str
    root: str
    files: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    fields: dict[str, list[Evidence]] = field(
        default_factory=lambda: {key: [] for key in FIELDS}
    )
    parameters: list[dict] = field(default_factory=list)
    searchable_text: str = ""

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "root": self.root,
            "files": self.files,
            "assets": self.assets,
            "fields": {
                key: [item.as_dict() for item in values]
                for key, values in self.fields.items()
            },
            "parameters": self.parameters,
            "searchable_text": self.searchable_text,
        }


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("读取 PDF 需要安装 pypdf") from exc
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def flatten_json(value, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lines.extend(flatten_json(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            lines.extend(flatten_json(item, f"{prefix}[{index}]"))
    else:
        lines.append(f"{prefix}: {value}")
    return lines


def read_zip_text(path: Path) -> str:
    """Extract only plainly readable text from a ZIP-based container."""
    snippets: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                suffix = Path(info.filename).suffix.lower()
                if info.file_size > 5_000_000 or suffix not in {
                    ".txt", ".xml", ".json", ".csv", ".md", ".java", ".m"
                }:
                    continue
                raw = archive.read(info)
                text = raw.decode("utf-8", errors="ignore").strip()
                if suffix == ".xml":
                    text = html.unescape(text)
                if text:
                    snippets.append(f"[ZIP entry: {info.filename}]\n{text}")
    except (zipfile.BadZipFile, OSError):
        return ""
    return "\n".join(snippets)


def read_mph_method_parameters(path: Path, source: str) -> list[dict]:
    """Read explicit method-call settings from an MPH's structured model summary."""
    try:
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("smodel.json").decode("utf-8"))
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile, OSError):
        return []

    found: list[dict] = []

    def visit(value) -> None:
        if isinstance(value, dict):
            if value.get("apiClass") == "MethodCallFeature":
                method = value.get("displayLabel") or value.get("label") or value.get("tag")
                for setting in value.get("settings", []):
                    name = setting.get("name")
                    values = setting.get("value")
                    if not name or not isinstance(values, list) or not values:
                        continue
                    item = {
                        "name": str(name),
                        "value": str(values[0]),
                        "unit": "",
                        "source": source,
                        "excerpt": f"Method call {method}: {name} = {values[0]}",
                    }
                    if item not in found:
                        found.append(item)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return found


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in {".md", ".markdown", ".txt", ".java", ".m"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".json":
        raw = path.read_text(encoding="utf-8-sig", errors="ignore")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Some deployment examples use JSON-like templates with comments or
            # placeholders. Preserve them as searchable evidence without
            # pretending they are valid structured settings.
            return raw
        return "\n".join(flatten_json(data))
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
            return "\n".join(" | ".join(row) for row in csv.reader(handle))
    if suffix in {".mph", ".ppa", ".pptx"}:
        return read_zip_text(path)
    return ""


def excerpts(text: str) -> Iterable[str]:
    for part in re.split(r"[\r\n]+|(?<=[。！？!?])\s*|(?<=[.])\s+", text):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if 4 <= len(cleaned) <= 500:
            yield cleaned


def contains_keyword(text: str, keyword: str) -> bool:
    lowered_keyword = keyword.lower()
    if re.fullmatch(r"[a-z]+(?: [a-z]+)*", lowered_keyword):
        return re.search(rf"\b{re.escape(lowered_keyword)}\b", text) is not None
    return lowered_keyword in text


def normalize_code_setting_value(value: str) -> str:
    cleaned = value.strip().strip("\"'")
    match = re.fullmatch(
        r"(?:new\s+\w+(?:\[\])+\s*\{|\[|\{)(.*?)(?:\}|\])",
        cleaned,
    )
    if match:
        parts = [
            part.strip("\"'")
            for part in re.split(r"[\s,]+", match.group(1).strip())
            if part
        ]
        return f"[{', '.join(parts)}]"
    return cleaned


def meaningful_evidence(field_name: str, sentence: str) -> bool:
    lowered = sentence.lower()
    if field_name == "mesh" and lowered.strip() == "mesh":
        return False
    if field_name == "materials" and lowered.strip() in {"material", "materials"}:
        return False
    if field_name == "materials" and any(
        term in lowered for term in ("current density", "电流密度")
    ):
        return False
    rejected = {
        "physics": (
            "<physicslist ", "<physicsinfo physics=\"\"", "physics list is empty",
            "<componentphysicslist ", "<base t=\"50\">/physics</base>",
            "-- physics -->",
            "-- contribuing physics/multiphysics interfaces -->",
            "<multiphysicscouplinglist ", "<componentmultiphysicscouplinglist ",
            "<featureinfo ", "physics-controlled mesh", "物理场控制网格",
            "certain physics", "物理场应用", "结构力学模块",
            "material and physics assignment", "keep physics contribute to",
            "selections to use for the physics definitions",
            "material and physics setup",
            "import com.comsol.model.physics",
            "show in physics", "for the physics setup", "physics settings",
            "physics setup",
            "selections for setting up the physics",
            "assigning the material and physics definitions",
            "when you are defining, for example, physics and mesh",
            "edit physics-induced sequence",
        ),
        "materials": (
            "<materiallist ", "material frame coordinates", "<base t=\"50\">/material</base>",
            "material('mat1').selection.set([])", 'material("mat1").selection().set()',
            "<scalar name=\"root.comp1.spatial.", "<tensor name=\"root.comp1.spatial.",
            "<scalar name=", "<tensor name=", "网格密度",
            "comp1.material.relvol", "material mesh displacement",
            "lagrange multiplier (comp1.material", "<componentmateriallist",
            'value="material" name="p:smooth"',
            "entire rim is made of the same material", "整个轮辋由同一种材料",
            "material and physics assignment", "domains with similar material assignments",
            "group the feature nodes based on, for example, the material",
            "material and physics setup",
        ),
        "geometry": (
            "<scalar name=", "<tensor name=", "-- geometry -->",
            "-- geometry tags -->", "-- remesh in geometry -->",
            "<geomlist ", "<componentgeomlist ", "-- geometry frame coordinates -->",
            "-- adaptation in geometry -->", "-- whether to show the geometry list.",
        ),
        "solver": ("<studylist ", "<solversequencelist "),
        "mesh": (
            "<base t=\"50\">/mesh</base>", "mesh frame coordinates",
            "entities for mesh control", "<meshlist ", "<componentmeshlist ",
            "originalpath t=\"0\">mesh.png", "<bemfeaturelist ", "mesh_32.png",
            'mesh().create("mesh', "mesh.create('mesh",
            "<meshsequence ", "<frame tag=\"material1\" name=\"moving mesh",
            "<currentfeature t=\"50\">/mesh/", "<sequence t=\"50\">/mesh/",
            "mesh control entities to keep", "maximum element size",
            "minimum element size", "maximum element growth rate", "mesh object",
            "<mesh t=\"52\" class=\"mesh\"", "<binaryresource file=\"mesh",
            't(s("/component/comp1/mesh")) m(s("create"))',
            "when you are defining, for example, physics and mesh",
            "<scalar name=\"root.comp1.mesh.", "<tensor name=\"root.comp1.mesh.",
            "<scalar name=", "<tensor name=", "<savepointbinary ",
            "geom/mesh sequence tags of savepoints", "mesh rendering",
            "-- extended mesh -->",
            "<lastbuiltfeature ", "maximum element depth to process", "simplify mesh",
            'model.result("', "model.result('",
        ),
        "results": (
            "<results ", "name=\"results\"", "originalpath", "propertyvalue",
            "results and discussion", "结果与讨论",
            "result list", "results tag=", " result after ", "resulting entities",
            "import com.comsol.api.database.result",
            "<scalar name=\"root.comp1.", "<tensor name=\"root.comp1.",
            "<scalar name=", "<tensor name=",
        ),
        "boundary_conditions": (
            "fixed", "<scalar name=", "<tensor name=",
            "root.minput.", "minput_concentration",
            "<grouplist tag=\"group\"",
        ),
        "applicability": (
            "<param t=", "textcompressibility", "param=\"text",
        ),
    }
    return not any(marker in lowered for marker in rejected.get(field_name, ()))


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_./+-]{2,}", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese = []
    for run in chinese_runs:
        chinese.extend(run[i : i + 2] for i in range(max(1, len(run) - 1)))
    return latin + chinese


def extract_case(case_dir: Path, source_root: Path) -> Case:
    rel_root = str(case_dir.relative_to(source_root)) if case_dir != source_root else "."
    case_id = hashlib.sha256(str(case_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    case = Case(case_id=case_id, name=case_dir.name, root=rel_root)
    all_text: list[str] = [case.name]

    for path in sorted(case_dir.iterdir()):
        if not path.is_file():
            continue
        rel = str(path.relative_to(source_root))
        suffix = path.suffix.lower()
        if suffix in ASSETS:
            case.assets.append(rel)
            all_text.append(path.stem.replace("_", " "))
            continue
        if suffix not in SUPPORTED:
            continue
        case.files.append(rel)
        if (
            suffix in {".txt", ".csv", ".json", ".md", ".markdown"}
            and path.stat().st_size > MAX_TEXT_INDEX_BYTES
        ):
            # Large numeric/text datasets are model assets, not useful prose for retrieval.
            case.assets.append(rel)
            all_text.append(path.stem.replace("_", " "))
            continue
        text = read_text(path)
        # A filename is evidence about the case topic, but never about model settings.
        document_text = f"{path.stem.replace('_', ' ')}\n{text}"
        all_text.append(document_text)
        if suffix in {".java", ".m"}:
            removed_parameters = {
                match.group("name") for match in CODE_PARAMETER_REMOVE_RE.finditer(text)
            }
            for match in CODE_PARAMETER_RE.finditer(text):
                if match.group("name") in removed_parameters:
                    continue
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                if line_end == -1:
                    line_end = len(text)
                item = {
                    "name": match.group("name"),
                    "value": match.group("value"),
                    "unit": "",
                    "source": rel,
                    "excerpt": text[line_start:line_end].strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for match in PHYSICS_FEATURE_SETTING_RE.finditer(text):
                value = normalize_code_setting_value(match.group("value"))
                item = {
                    "name": (
                        f"{match.group('physics')}.{match.group('feature')}."
                        f"{match.group('name')}"
                    ),
                    "value": value,
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for match in PHYSICS_FEATURE_SET_RE.finditer(text):
                value = normalize_code_setting_value(match.group("value"))
                item = {
                    "name": (
                        f"{match.group('physics')}.{match.group('feature')}."
                        f"{match.group('name')}"
                    ),
                    "value": value,
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for regex, prefix in (
                (COMMON_FEATURE_SET_RE, "common"),
                (STUDY_FEATURE_SET_RE, "study"),
            ):
                for match in regex.finditer(text):
                    item = {
                        "name": f"{prefix}.{match.group('feature')}.{match.group('name')}",
                        "value": normalize_code_setting_value(match.group("value")),
                        "unit": "",
                        "source": rel,
                        "excerpt": match.group(0).strip(),
                    }
                    if (
                        not any(
                            existing["name"] == item["name"] and existing["value"] == item["value"]
                            for existing in case.parameters
                        )
                        and len(case.parameters) < 100
                    ):
                        case.parameters.append(item)
            for match in STUDY_FEATURE_INDEX_RE.finditer(text):
                if not match.group("value"):
                    continue
                item = {
                    "name": f"study.{match.group('feature')}.{match.group('name')}",
                    "value": match.group("value"),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for match in STUDY_FEATURE_GENERIC_SET_RE.finditer(text):
                item = {
                    "name": f"study.{match.group('feature')}.{match.group('name')}",
                    "value": normalize_code_setting_value(match.group("value")),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for regex in (SURROGATE_STUDY_ENTRY_RE, SURROGATE_STUDY_SET_RE):
                for match in regex.finditer(text):
                    column = match.groupdict().get("column")
                    name = f"study.sm.{match.group('name')}"
                    if column:
                        name += f".{column}"
                    item = {
                        "name": name,
                        "value": normalize_code_setting_value(match.group("value")),
                        "unit": "",
                        "source": rel,
                        "excerpt": match.group(0).strip(),
                    }
                    if (
                        not any(
                            existing["name"] == item["name"]
                            and existing["value"] == item["value"]
                            for existing in case.parameters
                        )
                        and len(case.parameters) < 100
                    ):
                        case.parameters.append(item)
            for regex in (MESH_NESTED_FEATURE_SET_RE, MESH_FEATURE_SET_RE):
                for match in regex.finditer(text):
                    parts = [match.group("mesh")]
                    if "parent" in match.groupdict():
                        parts.append(match.group("parent"))
                    parts.extend((match.group("feature"), match.group("name")))
                    item = {
                        "name": ".".join(parts),
                        "value": normalize_code_setting_value(match.group("value")),
                        "unit": "",
                        "source": rel,
                        "excerpt": match.group(0).strip(),
                    }
                    if (
                        not any(
                            existing["name"] == item["name"] and existing["value"] == item["value"]
                            for existing in case.parameters
                        )
                        and len(case.parameters) < 100
                    ):
                        case.parameters.append(item)
            for match in MESH_AUTO_SIZE_RE.finditer(text):
                item = {
                    "name": f"{match.group('mesh')}.autoMeshSize",
                    "value": match.group("value"),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for match in MATERIAL_PROPERTY_RE.finditer(text):
                item = {
                    "name": f"{match.group('material')}.{match.group('name')}",
                    "value": match.group("value"),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for regex, prefix in (
                (BATCH_SWEEP_INDEX_RE, "batsw"),
                (BATCH_SWEEP_SET_RE, "batsw"),
            ):
                for match in regex.finditer(text):
                    value = match.group("value").strip().strip("\"'")
                    value = value.replace("\\\\", "\\")
                    if not value:
                        continue
                    item = {
                        "name": f"{prefix}.{match.group('name')}",
                        "value": value,
                        "unit": "",
                        "source": rel,
                        "excerpt": match.group(0).strip(),
                    }
                    if (
                        not any(
                            existing["name"] == item["name"] and existing["value"] == item["value"]
                            for existing in case.parameters
                        )
                        and len(case.parameters) < 100
                    ):
                        case.parameters.append(item)
            for match in RESULT_TABLE_FILENAME_RE.finditer(text):
                item = {
                    "name": f"{match.group('table')}.filename",
                    "value": match.group("value").replace("\\\\", "\\"),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
            for match in RESULT_EXPORT_SET_RE.finditer(text):
                item = {
                    "name": f"export.{match.group('export')}.{match.group('name')}",
                    "value": normalize_code_setting_value(
                        match.group("value")
                    ).replace("\\\\", "\\"),
                    "unit": "",
                    "source": rel,
                    "excerpt": match.group(0).strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"]
                        and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
        if suffix == ".mph":
            for item in read_mph_method_parameters(path, rel):
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
        if suffix == ".txt":
            for line in text.splitlines():
                match = TAB_PARAMETER_RE.match(line.strip())
                if not match:
                    continue
                item = {
                    "name": match.group("name"),
                    "value": match.group("value").strip(),
                    "unit": "",
                    "source": rel,
                    "excerpt": line.strip(),
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
        for sentence in excerpts(text):
            lowered = sentence.lower()
            for field_name, keywords in FIELDS.items():
                if (
                    any(contains_keyword(lowered, keyword) for keyword in keywords)
                    and meaningful_evidence(field_name, sentence)
                ):
                    evidence = Evidence(rel, sentence)
                    if evidence not in case.fields[field_name] and len(case.fields[field_name]) < 500:
                        case.fields[field_name].append(evidence)
            if suffix in {".java", ".m"}:
                continue
            # Container metadata frequently contains timestamps, IDs, and encoded
            # values that resemble parameters. Without a format-aware parser they
            # are not safe modification candidates.
            if suffix in {".mph", ".ppa", ".pptx"}:
                continue
            for match in PARAMETER_RE.finditer(sentence):
                parameter_name = match.group("name").strip()
                if not re.search(r"[A-Za-z\u4e00-\u9fff]", parameter_name):
                    continue
                item = {
                    "name": parameter_name,
                    "value": match.group("value"),
                    "unit": match.group("unit") or "",
                    "source": rel,
                    "excerpt": sentence,
                }
                if (
                    not any(
                        existing["name"] == item["name"] and existing["value"] == item["value"]
                        for existing in case.parameters
                    )
                    and len(case.parameters) < 100
                ):
                    case.parameters.append(item)
    case.searchable_text = "\n".join(all_text)[:200_000]
    if case.name in DEPLOYMENT_ONLY_CASES:
        for field_name in case.fields:
            if field_name != "applicability":
                case.fields[field_name] = []
        case.parameters = []
    elif case.name in GEOMETRY_MESH_ONLY_CASES:
        for field_name in (
            "physics", "materials", "boundary_conditions", "solver", "results"
        ):
            case.fields[field_name] = []
    return case


def find_case_dirs(root: Path) -> list[Path]:
    directories = []
    for directory in [root, *sorted(p for p in root.rglob("*") if p.is_dir())]:
        if any(p.is_file() and p.suffix.lower() in SUPPORTED | ASSETS for p in directory.iterdir()):
            directories.append(directory)
    return directories


def build_index(source: Path | list[Path], output: Path) -> dict:
    sources = [source] if isinstance(source, Path) else source
    sources = [item.resolve() for item in sources]
    cases = [
        extract_case(case_dir, source_root)
        for source_root in sources
        for case_dir in find_case_dirs(source_root)
    ]
    token_counts = [Counter(tokenize(case.searchable_text)) for case in cases]
    doc_freq = Counter(token for counts in token_counts for token in counts)
    count = len(cases)
    idf = {token: math.log((count + 1) / (freq + 1)) + 1 for token, freq in doc_freq.items()}
    vectors = []
    for counts in token_counts:
        vector = {token: (1 + math.log(freq)) * idf[token] for token, freq in counts.items()}
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        vectors.append({token: value / norm for token, value in vector.items()})
    payload = {
        "schema_version": 1,
        "source_root": str(sources[0]) if len(sources) == 1 else None,
        "source_roots": [str(item) for item in sources],
        "cases": [case.as_dict() for case in cases],
        "idf": idf,
        "vectors": vectors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_payload_from_case_dicts(cases: list[dict], source_roots: list[str]) -> dict:
    token_counts = [Counter(tokenize(case.get("searchable_text", ""))) for case in cases]
    doc_freq = Counter(token for counts in token_counts for token in counts)
    count = len(cases)
    idf = {token: math.log((count + 1) / (freq + 1)) + 1 for token, freq in doc_freq.items()}
    vectors = []
    for counts in token_counts:
        vector = {token: (1 + math.log(freq)) * idf[token] for token, freq in counts.items()}
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        vectors.append({token: value / norm for token, value in vector.items()})
    return {
        "schema_version": 1,
        "source_root": None,
        "source_roots": sorted(set(source_roots)),
        "cases": cases,
        "idf": idf,
        "vectors": vectors,
    }


def merge_case_indexes(index_paths: list[Path], output: Path) -> dict:
    merged: dict[str, dict] = {}
    source_roots: list[str] = []
    for index_path in index_paths:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if "cases" not in payload:
            raise ValueError(f"{index_path} 不是案例知识库索引")
        source_roots.extend(payload.get("source_roots") or [])
        for incoming in payload["cases"]:
            name = incoming["name"]
            if name not in merged:
                merged[name] = json.loads(json.dumps(incoming, ensure_ascii=False))
                continue
            current = merged[name]
            for key in ("files", "assets"):
                current[key] = sorted(set(current.get(key, [])) | set(incoming.get(key, [])))
            for field_name in FIELDS:
                seen = {
                    (item.get("source", ""), item.get("excerpt", ""))
                    for item in current["fields"].get(field_name, [])
                }
                for item in incoming["fields"].get(field_name, []):
                    marker = (item.get("source", ""), item.get("excerpt", ""))
                    if marker not in seen and len(current["fields"][field_name]) < 500:
                        current["fields"][field_name].append(item)
                        seen.add(marker)
            seen_parameters = {
                (item.get("name", ""), item.get("value", ""), item.get("source", ""))
                for item in current.get("parameters", [])
            }
            for item in incoming.get("parameters", []):
                marker = (item.get("name", ""), item.get("value", ""), item.get("source", ""))
                if marker not in seen_parameters and len(current["parameters"]) < 200:
                    current["parameters"].append(item)
                    seen_parameters.add(marker)
            texts = [current.get("searchable_text", ""), incoming.get("searchable_text", "")]
            current["searchable_text"] = "\n".join(dict.fromkeys(texts))[:400_000]
    cases = sorted(merged.values(), key=lambda item: item["name"])
    payload = build_payload_from_case_dicts(cases, source_roots)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def case_category(name: str) -> str:
    categories = (
        ("部署、App 与自动化", ("app", "集群", "azure", "ec2", "安装", "许可", "批处理", "自动", "作业序列")),
        ("几何、CAD 与网格", ("几何", "网格", "stl", "扫描数据", "随机几何", "科赫", "递归")),
        ("声学、振动与波动", ("声", "音叉", "鼓", "激波", "衍射", "波")),
        ("结构力学", ("应力", "应变", "梁", "弹簧", "支架", "曲轴", "馈线夹", "塔桅", "转子")),
        ("传热与热耦合", ("热", "温度", "烧蚀", "干燥", "恒温器", "焦耳")),
        ("流体、传质与反应", ("流", "混合器", "反应器", "扩散", "传递", "沉降", "蚀刻", "抛光")),
        ("电磁、生物电与量子", ("电", "磁", "起搏器", "心脏", "hodgkin", "量子", "透镜")),
        ("数学、方程与数据工具", ("方程", "吸引子", "曼德勃罗", "曲线数字化", "图像到曲线", "代理模型", "降阶")),
    )
    lowered = name.lower()
    for category, terms in categories:
        if any(term in lowered for term in terms):
            return category
    return "其他案例"


def write_master_summary(index: dict, output: Path) -> None:
    grouped: dict[str, list[dict]] = {}
    for case in index["cases"]:
        grouped.setdefault(case_category(case["name"]), []).append(case)
    lines = [
        "# COMSOL 案例总知识库",
        "",
        f"- 案例总数：{len(index['cases'])}",
        f"- 来源目录数：{len(index.get('source_roots', []))}",
        "- 检索方式：本地 TF-IDF 向量检索，并保留逐条来源证据。",
        "- 安全原则：缺少直接证据的 COMSOL 设置保持未知，不进行推断或虚构。",
        "",
        "## 使用方式",
        "",
        "```powershell",
        'python comsol_kb.py query "用户问题" --index comsol_master_cases_index.json --top-k 5',
        "```",
        "",
        "查询结果包含推荐案例、可修改的已记录参数、风险点、证据缺口和验证步骤。",
        "",
        "## 案例目录",
        "",
    ]
    for category in sorted(grouped):
        cases = sorted(grouped[category], key=lambda item: item["name"])
        lines.extend((f"### {category}", "", "| 案例 | 已记录字段 | 参数数 |", "|---|---|---:|"))
        for case in cases:
            fields = "、".join(field_name for field_name, values in case["fields"].items() if values) or "仅主题证据"
            lines.append(f"| {case['name']} | {fields} | {len(case['parameters'])} |")
        lines.append("")
    lines.extend(
        (
            "## 验证原则",
            "",
            "1. 首先确认物理接口、维度假设、材料和边界选择。",
            "2. 检查质量、动量、电流或能量守恒。",
            "3. 对网格、时间步、容差和参数范围执行收敛或敏感性分析。",
            "4. 使用解析解、实验数据或可信基准案例交叉验证。",
            "5. App、云部署、几何和网格教程不得被解释为未记录的物理设置。",
            "",
            "## 官方文档库",
            "",
            "案例总库用于查找可参考模型；COMSOL 6.4 官方文档索引用于核对软件操作与 API。",
            "",
            "```powershell",
            'python comsol_docs_kb.py query "操作问题" --index comsol_64_all_docs_index.json --top-k 5',
            "```",
        )
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def similarity(query: str, idf: dict, vector: dict) -> float:
    counts = Counter(tokenize(query))
    query_vector = {
        token: (1 + math.log(freq)) * idf[token]
        for token, freq in counts.items()
        if token in idf
    }
    norm = math.sqrt(sum(value * value for value in query_vector.values())) or 1
    return sum((value / norm) * vector.get(token, 0) for token, value in query_vector.items())


def title_similarity(query: str, case_name: str) -> float:
    query_lower = query.lower()
    name_lower = case_name.lower()
    if name_lower in query_lower:
        return 1.0
    query_tokens = set(tokenize(query))
    name_tokens = set(tokenize(case_name))
    if not name_tokens:
        return 0.0
    score = len(query_tokens & name_tokens) / len(name_tokens)
    distinctive_terms = (
        "装配", "几何", "焦耳热", "电极", "混合器", "载荷工况",
        "虚拟操作", "吸引子", "噪声",
    )
    score += 0.25 * sum(
        term in query_lower and term in name_lower for term in distinctive_terms
    )
    return score


def validation_and_query_risks(query: str) -> tuple[list[str], list[str]]:
    lowered = query.lower()
    if any(term in lowered for term in ("使用 microsoft® azure", "amazon ec2", "azure 运行 comsol", "ec2™ 运行 comsol")):
        return (
            [
                "该案例是云端部署与运行说明，不是 COMSOL 物理模型；不能从云配置文档推断物理场、材料、边界条件、网格或求解器。",
                "云端可用性取决于镜像版本、许可证、网络、安全组、存储和实例规格；文档中的配置不保证当前账户仍可直接使用。",
            ],
            [
                "核对 COMSOL 版本、许可证类型、云区域、实例规格、磁盘与网络配置。",
                "先运行安装验证或已知基准模型，检查许可证、共享路径、日志、运行时间和峰值内存。",
                "仅在同一模型、同一求解器和同一精度下比较本地与云端结果及性能。",
            ],
        )
    if any(term in lowered for term in ("限时和硬件锁定的 app", "硬件锁定", "time limited", "hardware locked")):
        return (
            [
                "该案例演示 App 的限时和硬件锁定分发机制；锁定设置不改变底层模型物理，也不能作为安全性或授权合规性的唯一依据。",
                "硬件标识、系统时间和许可证环境变化可能导致 App 无法运行；不能虚构未记录的解锁或绕过设置。",
            ],
            [
                "核对 App 的到期时间、允许硬件标识、错误提示和底层模型权限。",
                "在允许与不允许的机器及到期边界前后测试启动行为，并保留发布包和日志。",
                "确认锁定前后底层模型结果一致，且分发方式符合许可证条款。",
            ],
        )
    if any(term in lowered for term in ("编辑与修复面网格", "支架几何的扫掠网格", "使用网格划分序列", "蒸汽重整器几何", "使用插值和图像数据为不规则形状建模")):
        return (
            [
                "该案例主要演示几何、导入数据或网格工作流，不提供可直接复用的完整物理场、材料和边界条件。",
                "修复、简化、扫掠或重建会改变实体拓扑与编号；后续物理选择必须重新验证，不能沿用旧编号。",
            ],
            [
                "核对输入文件、坐标单位、几何构建顺序、命名选择和最终实体数量。",
                "检查封闭性、非流形边、反向单元、最小质量、扫掠源/目标面及网格统计。",
                "加入目标物理场后执行网格收敛，并确认所有材料和边界选择仍覆盖正确实体。",
            ],
        )
    if any(term in lowered for term in ("心脏电信号", "hodgkin-huxley", "动作电位")):
        return (
            [
                "该案例属于生物电信号或动作电位数学模型；不能把模拟波形直接解释为临床诊断、安全阈值或患者特异结果。",
                "离子通道动力学、初值、刺激和时间步会显著改变波形；未记录的生理机制不能自行补入。",
            ],
            [
                "核对方程、状态变量、初值、刺激函数、单位和时间范围。",
                "检查静息电位、峰值、上升时间、复极时间及守恒/门控变量范围。",
                "执行时间步与容差收敛，并与案例给出的参考曲线或可信实验数据比较。",
            ],
        )
    if any(term in lowered for term in ("延迟微分方程", "已实施反应延迟的恒温器", "pid 控制器", "状态变量6.3")):
        return (
            [
                "该类案例依赖延迟、事件、状态变量或控制器逻辑；求解器收敛不代表切换时刻、延迟历史或控制稳定性正确。",
                "修改延迟、采样、阈值或 PID 参数可能引起振荡、超调或不稳定，不能从单次响应推断稳健性。",
            ],
            [
                "核对所有状态初值、历史函数、事件条件、延迟时间和控制器参数。",
                "绘制状态、控制输出和被控量，检查切换时刻、超调、稳态误差及输出饱和。",
                "执行时间步、容差和参数扰动测试，并与无延迟或已知极限情况比较。",
            ],
        )
    if any(term in lowered for term in ("瞬态声压级", "音叉", "同频鼓")):
        return (
            [
                "音叉和同频鼓属于结构/数学特征模态案例，瞬态声压级案例使用频域与时域 FFT 转换；三者不能互相替代为完整声辐射模型。",
                "特征频率、FFT 频率分辨率、窗函数和模态归一化会影响结果；未记录的阻尼、声辐射或测量条件不能自行假定。",
            ],
            [
                "确认目标案例使用 Eigenfrequency、Eigenvalue 或 TimeToFreqFFT/FreqToTimeFFT，并核对频率范围和输出量。",
                "对特征模态检查网格收敛、模态序号和对称性；对瞬态声压级检查采样率、记录长度、窗函数和 Parseval 能量一致性。",
                "与解析频率、实验峰值或直接时域/频域计算交叉验证。",
            ],
        )
    if any(term in lowered for term in ("涡轮增压器转子的特征值分析", "通信塔桅零件的灵敏度分析", "通信塔桅斜撑支架的刚度分析", "受载弹簧")):
        return (
            [
                "该类案例属于结构特征值、刚度、约束或灵敏度分析；结果高度依赖约束、载荷路径、材料和几何参数化。",
                "特征值或灵敏度是当前线性化与参数范围下的结果，不能自动代表失效、疲劳、接触或非线性极限。",
            ],
            [
                "核对材料、固定/载荷/全局约束、参数范围和研究类型。",
                "检查反力平衡、刚体模态、模态顺序，以及灵敏度的有限差分复核。",
                "在关键应力、位移、刚度或特征频率上执行网格和参数步长收敛。",
            ],
        )
    if any(term in lowered for term in ("圆柱绕流", "岩石裂隙流", "砂粒的自由沉降速度", "微混合器", "自由流体中的浮力流", "自然对流传热")):
        return (
            [
                "该类案例涉及层流、传质、裂隙流或浮力耦合；雷诺数、密度模型、边界位置和网格决定适用范围，不能直接外推到湍流或不同尺度。",
                "稳态求解可能隐藏非稳态失稳；瞬态求解成功也不代表质量、动量或能量守恒已经满足。",
            ],
            [
                "核对流体性质、入口/出口、壁面、重力、扩散系数和多物理场耦合。",
                "检查质量流量、压降、阻力/沉降速度、浓度或热量守恒。",
                "执行网格、时间步或稳态初值敏感性检查，并用无量纲数或基准解验证适用范围。",
            ],
        )
    if any(term in lowered for term in ("稳态传导传热", "稳态辐射传热", "轴对称瞬态传热", "真空干燥", "碳纤维编织结构的各向异性传热", "微执行器焦耳热")):
        return (
            [
                "该类案例分别涉及传导、辐射、轴对称瞬态、干燥、各向异性或焦耳热；不同传热机制和维度假设不能拼接使用。",
                "温度结果对材料热参数、辐射率、热源、边界换热和网格敏感；未记录的相变、接触热阻或温度相关性质不能自行加入。",
            ],
            [
                "核对维度假设、材料热参数、热源、温度/热流/辐射边界和研究类型。",
                "检查输入热功率、边界散热和内部能量变化的能量平衡。",
                "对温度峰值、热流和关键时间常数执行网格、时间步及参数敏感性验证。",
            ],
        )
    if any(term in lowered for term in ("衍射图样", "锥形量子点", "四极透镜", "在轨航天器")):
        return (
            [
                "该类案例使用数学 PDE、量子特征值、电磁或全局轨道方程；只能在案例明确记录的方程和假设内使用。",
                "边界截断、初值、特征值搜索范围或外场表达式会显著影响结果，不能用相似名称补全缺失设置。",
            ],
            [
                "核对控制方程、变量单位、初始/边界条件、外场和研究类型。",
                "检查守恒量、对称性、特征值排序或已知极限，并排除伪解。",
                "执行网格、时间步或特征值搜索范围收敛，与解析解或可信基准比较。",
            ],
        )
    if any(term in lowered for term in ("起搏器电极模型中添加注释", "pacemaker electrode with annotations", "添加注释")):
        return (
            [
                "该案例在起搏器电极稳态导电介质模型的结果图中添加 Annotation；注释只改变结果表达，不改变物理场、边界条件或求解结果。",
                "底层模型仍使用 ConductiveMedia、Heart Tissue、Ground 和 ElectricPotential；不能把注释文字当作新的 COMSOL 设置或验证依据。",
            ],
            [
                "核对 Heart Tissue、Ground、ElectricPotential 和结果图数据集与原起搏器电极模型一致。",
                "逐项检查 Annotation 的位置、文本、表达式和所附着的结果图，确认改变视角或数据集后仍指向正确位置。",
                "比较添加注释前后的电位、电场和积分电流，数值结果应保持不变。",
            ],
        )
    if any(term in lowered for term in ("汽车消声器", "automotive muffler", "muffler")):
        return (
            [
                "该案例使用频域 PressureAcoustics 计算汽车消声器的声压级和传递损失；未记录的平均流、热黏性损耗和结构振动不能自行加入。",
                "入口和出口使用 PlaneWaveRadiation/IncidentPressureField，平面波假设只在端口高阶模态尚未传播的频率范围内可靠。",
                "频率上升会缩短波长；网格和端口长度不足时，传递损失峰谷可能发生数值偏移。",
            ],
            [
                "核对 p0=1 Pa、入口/出口辐射条件、InteriorSoundHard 和 range(100,10,1000) Hz 扫频。",
                "按最高频率的最短波长检查空气域网格，并对关键共振和反共振频率做局部加密。",
                "比较入口与出口声功率、传递损失和声压级，检查功率平衡与网格收敛。",
            ],
        )
    if any(term in lowered for term in ("浅水方程", "shallow water equations", "shallow water")):
        return (
            [
                "该案例用 GeneralFormPDE 求解深度平均浅水方程，不是完整三维自由表面流动模型。",
                "水深正值、波速、边界反射和数值耗散对结果敏感；求解成功不能代替质量守恒验证。",
            ],
            [
                "核对 nu1=1e-6、x0=6、a=0.005、k1=0.0015、tune=0.1 及约束条件。",
                "核对瞬态时间列表 range(0,60) 和相对容差 1e-5，并监视最小水深。",
                "检查总质量守恒、波前传播速度、边界反射，并执行网格与时间步收敛检查。",
            ],
        )
    if any(term in lowered for term in ("如何在求解后自动导出图像", "自动导出图像", "micromixer image export", "image sequence export")):
        return (
            [
                "该目录包含两个微混合器图像导出变体，均通过 Animation 导出节点和作业 Sequence 的 Exportseq 在求解后导出图像序列；不能把导出成功当作物理解已验证。",
                "图像文件路径 C:\\COMSOL\\my_image.png 是机器相关路径；目录权限、同名文件覆盖和批处理运行环境会影响导出。",
                "导出使用参数 xcut 从 -3.5 mm 扫到 8 mm；图像序列表示不同切面位置，不是瞬态时间动画。",
            ],
            [
                "核对微混合器的 LaminarFlow、DilutedSpecies、ReactingFlowDS、两步稳态求解及目标浓度图组。",
                "核对 Animation 节点 type=imageseq、plotgroup、parameter=xcut、pstart=-3.5、pstop=8、punit=mm，并把 imagefilename 改为本机可写路径。",
                "核对作业 Sequence 中 Solutionseq 位于 Exportseq 之前，且 Exportseq 指向 anim1；运行作业后检查日志和导出文件数。",
                "抽查首、中、末三张图的切面位置、浓度范围、视角和图例，并与 COMSOL 图形窗口中的相同 xcut 结果逐一比较。",
            ],
        )
    if any(term in lowered for term in ("求解模型后保存数据的作业序列", "micromixer job sequence", "job sequence")):
        return (
            [
                "该目录同时包含作业序列和参数化扫描两个微混合器变体，不能把两套批处理设置合并成一个最终配置。",
                "脚本中的 C:\\COMSOL\\myfile.mph 和 C:\\COMSOL\\my_data.txt 是机器相关路径；目录存在不代表当前用户有写权限或文件不会被覆盖。",
            ],
            [
                "核对 c0=27 mol/m^3、D=4.5e-9 m^2/s、h_max=0.1 mm、U_mean=10 mm/s、a=1.4 mm 及 spf/tds 顺序求解。",
                "把保存模型和表格路径改为本机可写目录，分别运行 job sequence 与 parametric sweep，并检查日志。",
                "重新打开保存的 MPH，核对解、表格和导出数据完整性，并测试重复运行时的覆盖策略。",
            ],
        )
    if any(term in lowered for term in ("球对称传递", "spherically symmetric transport", "spherical transport")):
        return (
            [
                "该案例用一维球对称 GeneralFormPDE 表示传递过程，只适用于径向对称场；非对称边界或颗粒形状不能直接沿用。",
                "脚本构建历史中 Rp 出现 0.005 m 和 0.0025 m，必须以最终 MPH 模型树中的当前值为准。",
                "球心处的坐标奇异性和表面通量符号会直接影响守恒性。",
            ],
            [
                "核对 rho=2000、cp=300、k=0.5、Qs=0、hs=1000、Text=368、Tinit=298 及最终 Rp。",
                "核对球心条件、两个 FluxBoundary 的位置与法向符号，以及 range(0,0.25,10) 的时间列表。",
                "检查能量守恒，并与小 Biot 数集总模型或适用解析极限比较，再做径向网格和时间步收敛。",
            ],
        )
    if any(term in lowered for term in ("曲线数字化仪", "curve digitizer", "curve digitization")):
        return (
            [
                "该案例是曲线图像数字化工具，导出的模型代码未提供可复用物理场、材料、边界条件或求解器设置。",
                "数字化结果依赖坐标轴标定、线性/对数尺度、图像透视和选点误差；不能把提取曲线当作原始实验数据。",
            ],
            [
                "核对图像来源、横纵轴标定点、单位以及线性或对数尺度。",
                "用图中已知刻度和已知数据点验证映射误差，并重复选点评估人工误差。",
                "导出后检查点序、重复点、缺失区段和单位，再决定是否作为 COMSOL 插值函数输入。",
            ],
        )
    if any(term in lowered for term in ("曲轴子模型分析", "shaft submodeling", "shaft submodel")):
        return (
            [
                "该案例是结构力学子模型流程：局部模型的边界位移来自全局轴模型；若全局模型载荷、约束或切割边界改变，局部结果必须重新传递。",
                "子模型只提高局部区域的分辨率，不能修正全局模型中错误的刚度、材料、接触或载荷路径。",
                "目录未提供可直接审计的 Java/MATLAB 设置，精确材料、载荷和边界值必须在最终 MPH 或案例 PDF 中确认。",
            ],
            [
                "在全局模型中核对材料、载荷、约束、解和子模型切割边界的位置。",
                "确认局部模型导入的是匹配全局解的位移场，坐标系、单位和边界选择均一致。",
                "比较切割边界附近位移与应力连续性，并移动切割边界、细化局部网格检查热点应力收敛。",
            ],
        )
    if any(term in lowered for term in ("热控制器，降阶模型", "热控制器降阶模型", "thermal controller rom")):
        return (
            [
                "该案例比较完整瞬态热模型与 6 模态、40 模态 ROM 控制器；ROM 通常只在训练条件附近有效。",
                "控制器包含 Events、IndicatorStates 和 DiscreteStates，ROM 温度误差可能改变开关时刻并累积为不同控制轨迹。",
            ],
            [
                "核对 Tset=293.15 K、tmax=1 h、outputStep=0.1 min、tstep=0.5 s、heatSrc=7.5e6 W/m^3 及外界温度函数。",
                "核对 ModelReduction 训练表达式 Tout/HeatState，以及 6 模态和 40 模态模型的输入输出映射。",
                "在训练域内比较完整模型与两个 ROM 的 T1、T2、开关时刻和能量；在域边界和域外单独标记误差。",
            ],
        )
    if any(term in lowered for term in ("热烧蚀除料建模", "laser machining", "heat shield ablation", "thermal ablation")):
        return (
            [
                "该目录包含一维热防护烧蚀和二维激光除料两个构建历史；不能把两者的几何、热流或移动边界设置混为一个模型。",
                "模型用 HeatTransfer 与 DeformedGeometry/规定法向网格速度表示除料；网格运动不等同于已验证的真实相变、熔池或蒸汽动力学。",
                "脚本中热流、烧蚀温度和时间列表有多次修改，最终值必须从最终 MPH 当前设置确认。",
            ],
            [
                "分别核对一维与二维模型的 HeatFluxBoundary、T_ablate/T_a、升华热 H_s 和 DeformedGeometry 边界选择。",
                "检查烧蚀热流和法向网格速度的符号、单位与能量关系，并监视最小网格质量和相对体积。",
                "比较除料深度、温度峰值和输入/潜热/传导能量平衡，执行空间网格、时间步和移动边界收敛检查。",
            ],
        )
    if any(term in lowered for term in ("热执行器代理模型", "thermal actuator surrogate")):
        return (
            [
                "该 App 的 DNN 代理模型近似稳态电流、传热和固体力学多物理场，只在训练参数范围内有依据。",
                "训练范围明确包含 dw=15..40、gap=2.5..7、wv=0..50、L=150..400、DV=0.5..10；超范围预测属于外推。",
                "修改材料关系、边界条件、几何拓扑或输出定义后，原代理模型不能自动更新。",
            ],
            [
                "核对完整模型中的 ConductiveMedia、HeatTransfer、SolidMechanics、ElectromagneticHeating、5 V 基准和约束选择。",
                "核对 SurrogateModelTraining、DNN 数据文件和各输入上下界，确认输出量顺序与单位。",
                "在训练域内留出未训练点，同时运行完整模型和 DNN；比较温度、位移及目标输出误差并记录最大误差。",
            ],
        )
    if any(term in lowered for term in ("热微执行器的简化模型", "thermal actuator simplified", "simplified thermal actuator")):
        return (
            [
                "该简化模型采用稳态 ConductiveMedia、HeatTransfer、SolidMechanics 和 ElectromagneticHeating；不包含瞬态响应、接触或制造缺陷。",
                "几何和结果对微米级臂宽、间隙、长度以及换热系数高度敏感，不能只凭求解收敛判断模型可靠。",
            ],
            [
                "核对 d=3 um、dw=15 um、gap=3 um、wb=10 um、wv=25 um、L=240 um、DV=5 V 和臂数的最终值。",
                "核对 Ground/ElectricPotential、两个 HeatFluxBoundary、TemperatureBoundary、Fixed 和 Roller 选择。",
                "检查电流与能量平衡、最大温度和端部位移，并对间隙、臂根和热点区域做网格收敛。",
            ],
        )
    if any(term in lowered for term in ("热执行器", "thermal actuator")):
        return (
            [
                "该目录包含仅焦耳热模型和加入 SolidMechanics/ThermalExpansion 的完整热执行器变体；选择错误变体会遗漏位移或误把热场当作结构结果。",
                "模型为稳态电-热-结构耦合，未记录的瞬态启动、接触、塑性和温度相关材料行为不能自行假定。",
            ],
            [
                "确认使用 thermal_actuator_jh、thermal_actuator_tem 或 parameterized 变体，并核对 DV=5 V 与换热系数。",
                "完整变体中核对 ElectromagneticHeating、ThermalExpansion、Ground、ElectricPotential、Fixed 和 Roller。",
                "检查电流守恒、焦耳热与散热能量平衡、最大温度和端部位移，并执行热点和臂根网格收敛。",
            ],
        )
    if any(term in lowered for term in ("如何生成随机非均匀材料数据", "随机非均匀材料", "random nonuniform material", "random heterogeneous material")):
        return (
            [
                "该目录包含随机函数生成、规则网格导出、插值导入、渗流可视化和随机弹性模量扳手等多个示例，不能合并为单一最终物理模型。",
                "随机场结果依赖随机函数设置、频谱表达式、网格分辨率和随机种子/实现；未固定实现时不能期待逐点复现。",
                "C:\\COMSOL\\data.txt、C:\\COMSOL\\synthesized_data.txt 和 STL 导出路径均为机器相关路径。",
            ],
            [
                "明确选择生成流程或应用模型；核对 Gaussian/Uniform Random、频谱表达式和 2D/3D 网格分辨率。",
                "重新链接本地数据路径，检查插值坐标、单位、范围和缺失值；对随机材料属性检查正值及合理上下界。",
                "用多组随机实现统计目标量，检查空间分辨率与求解网格收敛；应用到扳手或传热模型时分别验证力或能量平衡。",
            ],
        )
    if any(term in lowered for term in ("两种载荷工况下的锥形悬臂梁", "锥形悬臂梁", "tapered cantilever")):
        return (
            [
                "该案例是二维平面应力静力模型，使用载荷组与约束组分别定义 Gravity 和 Force 两个载荷工况；不能把单个工况结果解释为载荷组合结果。",
                "梁厚度在平面应力设置中取 0.1，边界力使用 ForceLength；改成三维、总力或不同厚度时必须重新换算载荷。",
                "固定、滚子和点固定属于不同约束组；错误启用组合可能造成刚体运动或过约束。",
            ],
            [
                "核对平面应力、厚度 0.1、E=210 GPa、nu=0.3、rho=7000 kg/m^3，以及锥形二维几何。",
                "核对 Gravity 工况启用体力与固定约束，Force 工况启用 10 MN/m 边界力、滚子和点固定。",
                "分别比较两个工况的法向应力、剪应力和反力，并执行网格收敛与力平衡检查。",
            ],
        )
    if any(term in lowered for term in ("轮辋几何虚拟操作", "轮辋", "wheel rim", "remove details")):
        return (
            [
                "该案例演示对导入 wheel_rim.mphbin 使用 Remove Details 清理几何，以改善网格并减少单元数；虚拟操作不会修复原始 CAD 文件。",
                "被移除的小细节可能对应真实应力集中、接触面或制造特征；不能仅凭网格数量减少判断简化合理。",
                "脚本对比了不同几何清理阶段和网格，必须以最终激活的 Remove Details 选择为准。",
            ],
            [
                "核对 wheel_rim.mphbin 导入、Remove Details 中实际选择的边/面以及清理前后的几何实体数量。",
                "比较清理前后网格单元数、skewness、最低质量和构建时间，并检查是否形成非预期孔洞或拓扑变化。",
                "添加目标物理场后比较关键应力、位移或其他目标量；只有误差满足项目容差时才接受虚拟几何。",
            ],
        )
    if any(term in lowered for term in ("螺旋静态混合器", "helical static mixer", "静态混合器")):
        return (
            [
                "该案例顺序求解稳态层流和稀物质传递，用于评估低雷诺数螺旋静态混合器；不包含湍流、非牛顿流体或瞬态混合。",
                "扩散系数 D1=1e-10 m^2/s 很小，浓度结果高度依赖对流离散、网格和流场解；求解收敛不等于混合指标已收敛。",
                "改变叶片数量、尺寸、速度或黏度会改变压降与混合效果，必须同时验证流动和传质。",
            ],
            [
                "核对 n_bl=5、叶片长度 24 mm、厚度 1 mm、半径 5 mm、入口/出口长度及命名选择。",
                "核对 rho_l=1000 kg/m^3、visc_l=0.01 Pa*s、u_av=5 cm/s、c_in=1 mole/m^3 和 D1=1e-10 m^2/s。",
                "先仅求解层流，再使用该解求稀物质传递；比较压降、出口浓度分布、最大浓度和 Contact Probability 的网格收敛性。",
            ],
        )
    if any(term in lowered for term in ("洛伦兹吸引子", "lorenz attractor", "lorenz")):
        return (
            [
                "该案例用 Global Equations 求解洛伦兹常微分方程，用于展示初值敏感性和混沌行为；它不是空间 PDE 或具体物理装置模型。",
                "混沌轨迹对初始扰动、相对容差和时间范围极敏感；两条轨迹分离不表示求解器错误，也不能仅靠单条轨迹验证精度。",
            ],
            [
                "核对 a=10、b=8/3、c=28，三个状态方程及初值 -10+pert、-4.45+pert、35.1+pert。",
                "核对 range(0,0.01,Tfinal)、Tfinal=35、用户相对容差 TOL，以及 pert/TOL 的 filled 参数扫描。",
                "比较不同容差下的短期轨迹一致性、状态范围和吸引子形状，并记录扰动轨迹的分离时间。",
            ],
        )
    if any(term in lowered for term in ("曼德勃罗集和柏林噪声", "曼德勃罗", "柏林噪声", "mandelbrot", "perlin noise")):
        return (
            [
                "该目录包含两个不同示例：曼德勃罗集使用迭代参数扫描，柏林噪声使用随机函数、状态变量和多 octave 叠加；不能把两者当作同一物理模型。",
                "随机噪声结果依赖随机函数设置和状态更新顺序；未固定的随机序列可能无法逐点复现。",
                "这些案例主要演示数学函数、状态变量和可视化，不提供材料、真实边界条件或工程适用性依据。",
            ],
            [
                "曼德勃罗模型核对 n_max=25、iter=range(1,1,n_max) 和复迭代/逃逸判据。",
                "柏林噪声模型核对 octaves=5、iter=range(0,1,octaves-1)、Random/Analytic 函数及 noise 状态更新表达式。",
                "验证迭代次数、随机种子或函数设置改变时的图案稳定性、计算成本和目标统计量。",
            ],
        )
    if any(term in lowered for term in ("母线板装配几何系列教程", "busbar assembly geometry")):
        return (
            [
                "该系列教程用于构建可复用几何零件、子序列、零件实例和材料选择，不包含可直接复用的焦耳热物理设置。",
                "系列目录含多个阶段模型；参数、选择和几何序列可能代表不同教程阶段，不能混合为一个最终配置。",
                "修改零件参数后必须确认贡献选择仍正确传递到装配层，数字实体编号不可作为稳定接口。",
            ],
            [
                "核对各 Geometry Part/Subsequence 的输入参数、PartInstance 位置方向和最终装配顺序。",
                "核对 Titanium、Copper 等贡献选择在参数变化后仍覆盖正确域，并检查装配实体数量和几何构建状态。",
                "分别改变 a_c_w、r_d 等参数，验证几何无重叠、无缺失且可稳定划分网格，再用于物理模型。",
            ],
        )
    if any(term in lowered for term in ("母线板装配的焦耳热", "母线板装配", "busbar assembly joule", "busbar assembly")):
        return (
            [
                "该案例耦合稳态电流、传热与电磁加热，并对装配几何参数进行扫描；它假设材料接触处具有模型中定义的电热连续性，未明确记录的接触电阻不能自行添加。",
                "空气与电解质换热系数相差很大，边界选择错误会显著改变最高温度；参数扫描中的几何选择必须逐点验证。",
                "焦耳热和电导率可能随温度变化；案例设置之外的温度依赖、辐射或瞬态过程保持未知。",
            ],
            [
                "核对 Jan=8000 A/m^2、Ground、NormalCurrentDensity，以及 Copper/Titanium beta-21S 的电导率。",
                "核对空气侧 htca=5 W/(m^2*K)、Ta=35 degC，电解质侧 htce=3000 W/(m^2*K)、Te=100 degC 及其边界选择。",
                "核对 r_d=16:2:20 mm 与 a_c_w=60:10:90 mm 的 filled 参数扫描；逐点比较电位、总电流、焦耳热和最高温度，并做网格与能量平衡验证。",
            ],
        )
    if any(term in lowered for term in ("母线板焦耳热", "busbar joule", "busbar")):
        return (
            [
                "该案例耦合稳态电流、传热和电磁加热，使用 20 mV 电势差与对流散热；不能据此推断交流集肤效应、接触电阻或瞬态升温。",
                "最高温度对铜/钛电导率、对流系数、受热边界和局部网格敏感；电流守恒与能量平衡都必须验证。",
            ],
            [
                "核对 Vtot=20 mV、ElectricPotential、Ground、Copper 与 Titanium beta-21S 材料域。",
                "核对 htc=5 W/(m^2*K) 的 ConvectiveHeatFlux 及环境温度设置，并确认电磁加热耦合激活。",
                "执行能量平衡：检查总输入电功率与体焦耳热积分、边界散热和最高温度，并细化孔洞/材料交界附近网格。",
            ],
        )
    if any(term in lowered for term in ("起搏器电极", "pacemaker electrode", "pacemaker")):
        return (
            [
                "该案例是心脏组织中的稳态导电介质电位模型，采用均匀电导率 0.4 S/m；不包含心肌各向异性、时变刺激波形、膜电生理或安全阈值。",
                "1 V 电极电势与接地对电场强度有直接影响；结果不能直接解释为临床起搏阈值或组织安全结论。",
                "电极与对电极使用几何命名选择；修改几何后必须重新确认选择覆盖。",
            ],
            [
                "核对 Heart Tissue 电导率 0.4 S/m、Counter Electrode 的 Ground 和电极 ElectricPotential V0=1 V。",
                "核对插入的 pacemaker_electrode_geom_sequence.mph、命名选择和自动网格等级 7。",
                "检查电流守恒、电极总电流、电位与电场网格收敛，并与适用实验或文献数据独立验证。",
            ],
        )
    if any(term in lowered for term in ("积分-偏微分方程", "积分偏微分", "integro partial", "integral pde")):
        return (
            [
                "该案例用一维轴对称积分耦合算子 intop1 构造非局部辐射热源，而不是通用积分-偏微分方程求解模板；积分核、积分域和轴对称权重必须一起核对。",
                "非局部热源含 T^4，温度、发射率和积分离散误差会显著影响结果；epsilon=0 与 1 的参数扫描只用于比较案例中的辐射耦合效应。",
                "积分算子使全域温度相互耦合，局部网格或时间步看似收敛时，积分量仍可能未收敛。",
            ],
            [
                "核对 xi=abs(dest(x)-x)/D_i、积分核 k、Q_source=4/(D_o^2-D_i^2)*epsilon*sigma_const*intop1(k*T^4) 和 Q_loss。",
                "核对 intop1 选择全部一维域且启用轴对称，以及材料导热率 13、密度 8700、热容 300 的单位。",
                "核对两端温度边界、初始温度、range(0,1[min],1[h]) 和 epsilon 扫描 0、1，并对积分量、温度峰值执行网格与时间步收敛检查。",
            ],
        )
    if any(term in lowered for term in ("基于扫描数据生成可供仿真的网格", "扫描数据生成", "scanned data", "human_femur")):
        return (
            [
                "该案例演示从扫描标量数据重建可仿真网格，原始数据文件 human_femur.txt、插值坐标系和阈值决定最终表面；不能把生成网格视为真实解剖尺寸或已验证 CAD。",
                "导出脚本保留了原作者的绝对数据路径，运行前必须改为本地 human_femur.txt；路径可用不代表数据单位、方向和缩放正确。",
                "Helmholtz/PDE 平滑、Partition 数据集、表面重网格和四面体化都会改变细节；平滑后的几何与扫描数据必须定量比较。",
                "案例包含多次不同 hmax/hmin 和网格构建操作，必须以最终模型树的激活序列为准。",
            ],
            [
                "重新链接 human_femur.txt，并验证插值函数 human_femur(x,y,z) 的坐标范围、单位、方向、缺失值和阈值。",
                "核对 Coefficient Form PDE 的 Helmholtz 平滑设置、Partition 数据集与导入网格流程，记录每一步的实体数量和封闭性。",
                "核对 RemeshFaces、FreeTet 及最终 hmax/hmin；检查非流形边、孔洞、反转单元、最低质量和体积变化。",
                "将最终表面与原始等值面叠加，测量 Hausdorff 距离或关键尺寸误差，再用目标物理场做网格收敛验证。",
            ],
        )
    if any(term in lowered for term in ("激波管", "shock tube", "sod shock")):
        return (
            [
                "该案例用 Wave Form PDE 和 DG 数值通量求解一维理想气体激波管，不包含黏性、传热、真实气体或管壁边界层效应。",
                "初始压力和密度存在间断；普通连续有限元或过大的时间步会产生非物理解振荡、负密度或负压力。",
                "脚本构建历史中 tend 曾为 0.05 s，最终又设回 0.03 s；必须在最终 MPH 中确认当前时间范围。",
            ],
            [
                "核对 gamma=1.41、左侧 pin=1e5 Pa/rhoin=1 kg/m^3、右侧 pout=1e4 Pa/rhoout=0.125 kg/m^3，以及初始动量为零。",
                "核对守恒变量 rho、momentum、e，压力 p=(gamma-1)*(e-rho*u^2/2)、DG 内部通量和边界数值通量。",
                "核对 element_size=0.02、CFL_cond=0.3 和 tstep=CFL_cond*element_size/max(c+abs(u))，并监视密度和压力正值性。",
                "在 t=0.03 s 比较密度、速度、压力和 Mach 数与解析 Riemann 解，并执行网格/CFL 收敛检查。",
            ],
        )
    if any(term in lowered for term in ("集群设置验证", "cluster setup validation", "cluster validation")):
        return (
            [
                "该案例用于验证 COMSOL 集群计算与批处理文件配置；声学模型只是计算载荷，计算完成不等于集群性能、扩展效率或声学结果精度已验证。",
                "集群功能依赖许可证、共享文件系统、节点可见路径、调度器和 COMSOL 版本；单机成功不能证明集群配置正确。",
                "脚本创建 Sweep.mph 与 Stationary.mph 批处理文件，文件位置和权限必须在所有计算节点上有效。",
            ],
            [
                "核对频域压力声学模型、p0=1 Pa、100 至 1000 Hz 扫频以及 490 Hz 单点研究，确认两种任务均可独立求解。",
                "核对两个 ClusterComputing 节点及 Sweep.mph、Stationary.mph 的共享路径、读写权限和作业输出。",
                "分别用单机和集群运行，比较解、Transmission Loss、日志、失败节点信息、运行时间和峰值内存。",
            ],
        )
    if any(term in lowered for term in ("借助变形几何接口修改导入的 cad", "修改导入的 cad", "deformed geometry wrench")):
        return (
            [
                "该案例用变形几何修改导入的 wrench.mphbin，再进行固体力学分析；变形网格并不等价于重新参数化 CAD，过大变形可能破坏几何质量。",
                "脚本包含大量交互式构建历史，F、dLength、研究步骤和参数列表出现过多个版本，必须以最终 MPH 模型树为准。",
                "导入 CAD 后的边界编号和选择对重新导入、修复容差或文件版本敏感，不能直接迁移数字实体编号。",
            ],
            [
                "核对 wrench.mphbin 导入、变形几何 PrescribedDeformation/PrescribedMeshDisplacement 的选择和 dLength 参数。",
                "确认最终参数扫描与激活研究步骤；证据显示 dLength 列表曾为 1/2/3 cm，后改为 0/2/4 cm。",
                "每个变形量下检查几何雅可比、网格质量、边界选择和固体力学载荷，再比较应力与位移收敛性。",
            ],
        )
    if any(term in lowered for term in ("科赫雪花", "koch snowflake", "snowflake geometry")):
        return (
            [
                "该案例主要演示几何零件实例、旋转、移动和合并的构建过程，不包含可直接复用的物理场、材料或求解器设置。",
                "导出脚本保存了大量试建、删除和重命名历史；不能将中间 PartInstance 或参数值当作最终递归算法。",
                "科赫雪花迭代会快速增加边界数量和最小特征尺寸，较高阶次可能导致几何构建与网格成本急剧增长。",
            ],
            [
                "核对几何零件的 Length、位置和方向输入，以及最终激活的 PartInstance、Union 和内部边界设置。",
                "逐阶记录边界数、周长、面积和最小特征尺寸，并与科赫雪花理论关系比较。",
                "若添加物理场，先确定可解析的最小特征阶次，再执行几何容差与网格收敛检查。",
            ],
        )
    if any(term in lowered for term in ("馈线夹的变形", "馈线夹", "feeder clamp")):
        return (
            [
                "该案例是铝制馈线夹的三维静力结构分析，使用两个载荷工况和约束组；不能把某一工况的位移或应力直接解释为组合载荷结果。",
                "材料包含线弹性参数和 Murnaghan 常数，但必须确认最终固体力学特征实际采用的本构与几何非线性设置。",
                "总力载荷和固定边界依赖具体面选择；更换 CAD 或网格后数字边界编号不可直接沿用。",
            ],
            [
                "核对 Ffeeder=2000 N、Fscrew=0.2*4500 N、三个 TotalForce 边界载荷及其方向。",
                "核对两个固定约束组 cg1/cg2、Load case 1/2 的启用关系，以及铝材料 E=70 GPa、nu=0.33 和 Murnaghan 常数。",
                "核对 Sweep 网格与源面选择，比较两个载荷工况下 y 位移、x 位移、von Mises 应力和旋转，并执行网格收敛检查。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "化学蚀刻", "化学刻蚀", "湿法蚀刻", "chemical etching",
            "wet etching", "铜蚀刻", "铜刻蚀",
        )
    ):
        return (
            [
                "该案例是二维湿法化学蚀刻模型，耦合层流、稀物质传递和变形几何；它采用 CuCl2 单物质与线性表面动力学 r_surface=-kf*cCuCl2，不包含完整氧化还原机理、副产物传递或电化学电势。",
                "移动边界速度由 v_surface=-r_surface*M_Cu/rho_Cu 换算；反应通量、法向方向、摩尔质量和密度的单位或符号错误会直接反转或缩放蚀刻速度。",
                "案例假设 kf 与表面位置无关，并使用恒定扩散系数 D；更换蚀刻剂、铜表面状态、温度或浓度范围后，必须重新标定动力学与传质参数。",
                "腔体逐渐加深会削弱局部流动并使变形网格恶化；求解成功不等于移动边界、网格质量和蚀刻轮廓已经收敛。",
                "模型适用于受控层流下二维铜腔湿法蚀刻与形状演化研究，不能直接推断三维图形、各向异性干法蚀刻或真实掩膜选择性。",
            ],
            [
                "核对 r_surface=-kf*cCuCl2、v_surface=-r_surface*M_Cu/rho_Cu、D=1e-9[m^2/s]、kf=100[m/s]、M_Cu=65[g/mol] 和 rho_Cu=9000[kg/m^3]，并检查法向与单位。",
                "核对入口及上边界浓度 cCuCl2_bulk=1[mol/dm^3]、移动边界通量 J0=r_surface、边界 14 的 Outflow，以及层流速度场作为 TDS 对流速度。",
                "核对边界 3 的平移壁速度 1[mm/s]、边界 1 和 14 的正应力法向流动，以及移动边界选择 box1；几何改变后必须重新确认所有选择。",
                "核对变形域 2 使用超弹性平滑、移动边界使用 v_surface、其余指定网格位移边界，并监视 comp1.material.relVol 和最低网格质量。",
                "先求稳态流场且不求解变形几何，再用 range(0,0.05*tmax,tmax) 求解至 tmax=3[h]；比较浓度、速度、通量、蚀刻深度和最终轮廓的时间步与网格收敛性。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "恒温器特性建模", "恒温器", "thermostat", "带滞回", "滞回控制",
        )
    ):
        return (
            [
                "案例使用事件和离散状态实现带滞回恒温器：温度向上越过 55 degC 时关闭加热器，向下越过 45 degC 时开启加热器；不能在没有事件处理依据时改成单一阈值或普通不连续 if 表达式。",
                "测温信号为 T_s=intop1(T)，其含义取决于 intop1 的最终选择；脚本构建过程中选择曾被修改，必须在最终 MPH 模型树中确认实际测温区域。",
                "脚本保留了较多构建历史，HS/HeaterState、加热功率、事件条件、时间列表和容差均出现过不同版本，不能把中间设置当作最终有效设置。",
                "开关周期和占空比对材料热参数、1 W 加热功率、对流换热、阈值、时间步和事件容差敏感；滞回带或容差不合理可能造成抖振或漏检事件。",
                "该案例验证的是热学开关控制逻辑，不自动代表真实恒温器触点的电磁、机械寿命或接触电阻行为。",
            ],
            [
                "在最终模型中核对 T_s=intop1(T)、Upwards=T_s-55[degC]、Downwards=T_s-45[degC]，并确认 intop1 的最终选择。",
                "核对 HeaterState 初值、上阈值事件将其重置为 0、下阈值事件将其重置为 1，并确认热源为 qtot=1[W]*HeaterState。",
                "核对最终瞬态研究的时间单位、tlist，以及 rtol/eventtol；证据指向 0 至 30 min 和 0.001，但应在最终 MPH 中确认并用更严格容差复算。",
                "同时绘制 T_s 与 HeaterState，确认状态只在阈值穿越时切换，并检查温度过冲、开关周期和占空比。",
                "进行时间步与网格收敛检查，并用输入加热能量、对流散热和内部能量变化进行能量平衡验证。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "含载荷突变的瞬时加热", "载荷突变", "瞬时加热",
            "transient stepped heating", "step changes in loads",
            "热载荷突变", "载荷突降", "热载荷从", "显式事件模拟热载荷",
        )
    ):
        return (
            [
                "该案例使用显式事件和离散状态 HighLoad 实现载荷突降：HighLoad 初值为 1，边界总热率起始为 100 W；在 t=0.25 s 时事件将 HighLoad 设为 0，热率降为 10 W。不能将其误读为载荷上升。",
                "热边界使用 HeatRate，P0 表示所选边界上的总功率而不是 W/m² 热流密度；改变受热边界面积或改用 HeatFlux 时不能直接沿用数值。",
                "载荷在事件时刻不连续，事件定位、内部时间步和相对容差会影响突变后的温度响应；输出列表 range(0,0.1,1) 本身不包含 0.25 s，不能仅查看输出时刻判断事件是否被正确解析。",
                "导出历史明确比较了相对容差 0.01 与 0.001，并添加局部细网格和边界层；案例用于研究数值精度，不能把任一粗网格或宽松容差结果直接视为收敛解。",
            ],
            [
                "核对 Events 中离散状态 HighLoad 的初值为 1、Explicit Event 起始时刻为 0.25 s、重初始化值为 0，并核对热边界 P0=10[W]+90[W]*HighLoad。",
                "核对二维轴对称 2 cm×2 mm 几何、受热边界 3、辐射边界 3/4/5、辐射率 0.8，以及 HeatFluxType=HeatRate；在修改几何后重新验证边界选择和总输入功率。",
                "在事件前、事件时刻两侧和事件后保存足够密集的解，检查 HighLoad、热率与顶部中心点温度曲线；确认事件处没有被输出插值掩盖。",
                "分别比较 rtol=0.01 与 0.001、基础网格与点 3 局部细化/边界层网格下的顶部中心温度、顶部表面温度和中心线温度，直到目标量满足项目容差。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "硅晶片激光加热", "硅晶片", "silicon wafer laser",
            "laser heating wafer", "激光加热晶片",
        )
    ):
        return (
            [
                "该案例把激光直接表示为移动高斯表面热流，不求解电磁波、射线传播、穿透深度或体吸收；不能据此推断真实光场、反射率或随温度变化的光学吸收。",
                "模型使用同一参数 emissivity 同时缩放激光热流 q0=emissivity*Flux 并定义表面对环境辐射；这是一项明确建模假设，更换波长、表面处理或温度范围后必须重新验证。",
                "硅的导热率、密度和热容在案例中采用常数；高温下若材料性质、辐射率或相变不可忽略，当前结果没有充分依据。",
                "晶片厚度方向仅使用一个扫掠单元，输出时间间隔为 1 s；移动小光斑产生的局部峰值可能对空间网格、内部时间步和扫描轨迹分辨率敏感。",
            ],
            [
                "核对三维晶片几何、Rotating Domain 的 v_rotation=10 rpm，以及焦点轨迹 x_focus=r_wafer*Triangle(t/period)、y_focus=0；确认移动方向和旋转方向符合实际设备。",
                "核对高斯热流 Flux=(2*p_laser/(pi*r_spot^2))*exp(-2*r_focus^2/r_spot^2)、p_laser=10 W、r_spot=2 mm 和 q0=emissivity*Flux；对受热表面积分 q0，验证实际输入吸收功率。",
                "核对硅材料导热率 130 W/(m·K)、密度 2329 kg/m^3、热容 700 J/(kg·K)，以及表面对环境辐射使用 emissivity=0.8；未明确记录的初始温度和环境温度必须在最终 MPH 模型中确认。",
                "分别细化光斑路径附近面网格、厚度方向扫掠单元和时间步，比较 T_max、T_average、T_min、T_diff 与温度场；结果稳定后再接受模型。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "管式反应器代理模型", "反应器代理模型", "tubular reactor surrogate",
            "surrogate reactor", "代理模型 app",
        )
    ):
        return (
            [
                "该 App 的代理模型近似二维轴对称稳态有限元模型，只预测训练时配置的温度 T 和转化率 xA；它不能替代完整模型来验证新的物理场、边界条件、几何或网格。",
                "代理模型输入必须限制在训练域内：E 为 71518–79205 J/mol，ke 为 0.0559–5.6 W/(m·K)，dHrx 为 -101600–-67733 J/mol。超出范围属于外推，案例未提供可靠性依据。",
                "代理模型由 100 次非自适应求解数据训练；修改反应动力学、入口条件、冷却条件、几何、材料关系或完整模型求解设置后，原代理模型不再有充分依据，必须重新生成数据并训练。",
                "训练研究在导出模型中随后被停用，App 预览调用已训练的 DNN 函数；不能假设修改有限元参数后代理函数会自动更新。",
            ],
            [
                "核对完整模型为二维轴对称稳态模型，包含稀物质传递、流体传热和夹套温度边界 PDE；核对反应速率 rA=-A*exp(-E/R_const/T)*cA、热源 Q=(-rA)*(-dHrx) 与给定抛物线速度分布。",
                "核对代理训练输入顺序 E、ke、dHrx 及其上下界，输出为 T 和 xA，训练求解数 nsolvenonadp=100；确认 DNN 输出 dnn1_1 对应温度、dnn1_2 对应转化率。",
                "在训练域内部选取未参与训练的留出参数点，同时运行完整有限元模型与代理模型，比较温度峰值、出口径向温度曲线、出口转化率曲线及工程关注量误差。",
                "检查训练域边界附近与高温、高反应速率区域的误差；任何输入超界、完整模型改变或误差超过项目容差时，停止使用旧代理模型并重新训练。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "高尔夫球的轨迹", "高尔夫球轨迹", "golf ball trajectory",
            "高尔夫球飞行", "高尔夫球", "golf ball flight", "golf ball",
        )
    ):
        return (
            [
                "该案例使用全局方程与事件计算二维质点轨迹，不求解高尔夫球周围的三维空气流场，也不能直接给出球面局部压力、尾流或湍流结构。",
                "阻力系数、升力系数和旋转衰减均来自案例中的经验函数；更换球型、表面凹坑、环境或速度范围后，必须验证这些函数仍然适用，不能凭轨迹吻合推断流场正确。",
                "导出的 Java/MATLAB 脚本包含大量构建历史，同名发射速度、角度、转速、事件条件和时间范围存在多个值；必须以最终 MPH 模型树中的当前激活设置为准。",
                "落地点由事件条件触发，事件检测与时间步会影响携带距离；若事件条件、地面高度或求解时间范围改变，必须重新验证落地时刻和落地点。",
            ],
            [
                "核对 Events 中的 Global Equations：x、y 初值为 0，初速度分量为 U0*cos(alpha) 与 U0*sin(alpha)，并确认阻力、升力和重力项的符号及单位。",
                "核对球直径 d=4.267 cm、质量 m=45.93 g、空气密度 rho=1.2 kg/m^3、重力 g=9.8 m/s^2、空气动力黏度 mu=1.8e-5 Pa*s，以及最终使用的 U0、alpha、omega0 和 smooth。",
                "核对 U、Re、S、Cd、Cl 与旋转衰减 omega=omega0*exp(-c*U*t/d)，并确认经验常数 c=1e-4 和 CD_standard、CD_golf、CL 函数的适用范围。",
                "检查落地事件与 Stop Condition 是否在穿过地面时停止；缩小输出步长并比较飞行时间、最大高度和携带距离，同时与无阻力抛体极限或可信实验数据进行交叉验证。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "钢罐中的壳扩散", "壳扩散", "shell diffusion",
            "coefficient form boundary pde", "边界 pde",
        )
    ):
        return (
            [
                "该案例中的“壳扩散”是用边界 PDE 表示薄钢壳表面导电，不是物质扩散，也不是对钢罐实体内部进行体电流求解。",
                "薄壳近似通过系数 sigma*d 表示表面电导；修改电导率或厚度后，必须确认壳厚远小于曲率半径和局部特征尺寸，且可忽略厚度方向电势梯度。",
                "狄利克雷边界编号与导入几何及分区操作绑定；更换几何后不能沿用原边界编号，端子或接触区域的变化也会显著改变电流密度。",
            ],
            [
                "核对 Coefficient Form Boundary PDE、未知量 V、电势单位、系数 c=sigma*d 和源项 f=0，确认模型描述的是薄壳表面稳态导电。",
                "核对 sigma=4.032e6 S/m、d=1 mm、400 V 狄利克雷边界及第二组狄利克雷边界，并在图形窗口逐一验证边界选择。",
                "检查电势 V、表面电流矢量和电流密度模；对端子边界积分电流并核对电流守恒，同时在分区、开口和高曲率区域执行网格收敛检查。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "飞秒激光", "超快传热", "femtosecond laser", "ultrafast heat transfer",
        )
    ):
        return (
            [
                "该案例是飞秒脉冲激光加热的一维超快传热对比模型，包含 POS、HOS、PTS、HTS；不能据此推断横向光斑、熔化、烧蚀、等离子体或温度相关材料性质。",
                "代码包含大量交互式构建历史，同名参数和方程存在多个有来源值；必须在最终 MPH 模型树中确认当前激活的物理场、热源和参数，不能按脚本中首次出现值复现。",
                "电子-声子耦合、热波时间常数、穿透深度、脉冲能量和脉冲宽度高度敏感；飞秒尺度下时间步不足会严重改变峰值电子/晶格温度。",
            ],
            [
                "核对一维薄膜几何、T0、吸收热源 S/delta、电子-声子耦合 G，以及 POS/HOS/PTS/HTS 各自的电子和晶格温度变量与方程。",
                "核对最终使用的 Phi_p、t_p、delta、L、tau、C_e、C_l、K 和 rho；时间范围应覆盖脉冲前后，并对 0.1*t_p 与更细时间步执行收敛检查。",
                "比较 T_POS、T_PTS_e/T_PTS_l、T_HTS_e/T_HTS_l 的峰值、峰值时间和空间分布；积分激光热源并核对输入能量，同时执行空间网格收敛检查。",
            ],
        )
    if any(
        term in lowered
        for term in ("有效扩散系数", "effective diffusivity", "effective diffusion")
    ):
        return (
            [
                "该案例通过详细二维孔隙模型与一维均质化模型的出口通量匹配获得有效扩散参数；D1 不能脱离该几何、孔隙率和边界条件直接用于其他多孔材料。",
                "模型关闭对流，仅描述稀物质扩散；不能据此推断对流、吸附、反应、Knudsen 扩散或浓度相关扩散行为。",
                "孔隙几何、孔隙率 epsilon、外部传质系数 k_f 与观察时间范围都会影响拟合得到的有效扩散系数。",
            ],
            [
                "核对详细模型 D2=1e-5 m^2/s、c_max=3 mol/m^3、k_f=5 m/s、初始浓度 c0，以及指定浓度和 ExternalConvection 边界选择。",
                "核对一维模型 epsilon=0.383、D1=2.15e-6 m^2/s、扩散项 D1/epsilon 和边界系数 k_f/epsilon；确认两个模型均使用 0–100 ms 时间范围。",
                "比较二维平均通量 flux_avg 与一维通量 flux_hom 的完整时间曲线，并对详细孔隙网格、代表性体积和 D1 执行敏感性/收敛检查。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "房间的特征模态", "房间特征模态", "房间声学特征模态",
            "房间声学", "room eigenmode", "room eigenfrequency",
        )
    ):
        return (
            [
                "该案例假设房间墙壁完全刚性且家具不吸声；不能据此预测真实房间中的吸声、混响衰减、开口泄漏或结构声耦合。",
                "特征频率和模态形状高度依赖导入房间几何；替换几何后必须重新验证网格与搜索偏移，不能沿用原模态编号。",
                "当前证据仅明确空气密度、声速和默认硬声场边界；没有依据时不得添加阻抗、阻尼或吸声系数。",
            ],
            [
                "核对导入几何 eigenmodes_of_room.mphbin、Pressure Acoustics、Air 密度 1.25 kg/m^3、声速 343 m/s，以及所有边界保持默认 Sound Hard Boundary。",
                "核对 Eigenfrequency 研究和搜索偏移 shift=90 Hz；逐级细化 Free Tetrahedral 网格，检查目标特征频率及模态形状是否稳定。",
                "检查声压 acpr.p_t、声压级 acpr.Lp_t、等值面和特征频率表；对近重根模态使用场分布而非仅按频率顺序识别。",
            ],
        )
    if any(
        term in lowered
        for term in ("顶盖驱动方腔", "lid-driven cavity", "lid driven cavity", "cavity flow")
    ):
        return (
            [
                "该案例是二维、不可压、层流、稳态的单位方腔基准；不能据此推断三维效应、湍流、可压缩性或非稳态高雷诺数行为。",
                "Re 通过密度 1、顶盖速度 1 和动力黏度 1/Re 实现；修改尺寸、速度、密度或黏度时必须重新核对雷诺数定义。",
                "高 Re 下角点奇异性、边界层分辨率和稳态非线性收敛对结果敏感；求解器收敛不等同于文献基准吻合。",
            ],
            [
                "核对单位方形、顶盖边界 3 的 SlidingWall 与 uvw=1、其余默认壁面及点 1 的 PressurePointConstraint。",
                "复核 Re 扫描 100、400、1000、3200、5000、7500、10000，以及 100×100 对称指数分布映射网格（elemratio=5）。",
                "将 x=0.5 上的 u(y)、y=0.5 上的 v(x) 与两份文献表逐个 Re 比较，并检查主涡及左右角涡位置；再加密网格验证中心线速度收敛。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "非结构网格", "unstructured mesh", "element size", "单元大小",
            "free tetrahedral", "四面体网格",
        )
    ):
        return (
            [
                "该案例演示活塞几何上的非结构四面体网格尺寸控制；示例中的边界编号 8、39 和具体尺寸参数不能直接迁移到其他几何。",
                "减小最小单元尺寸、曲率因子或狭窄区域分辨率会显著增加单元数量和内存需求；仅改善局部外观不代表求解结果已收敛。",
                "网格质量指标与物理问题相关；案例使用 skewness，不能假定它足以验证所有物理场或高阶单元。",
            ],
            [
                "依次复核自动网格等级 7 与 3，以及自定义 Size 节点中的 hcurve、hmin、hnarrow 和全局 hgrad；确认 Size 节点选择的边界与目标几何特征一致。",
                "每次只改变一个尺寸控制参数，记录单元数量、最小/平均 skewness 质量、生成时间和内存占用，并检查低质量单元位置。",
                "用于实际物理模型时执行网格收敛研究：比较目标积分量、峰值和场分布；只有结果变化满足工程容差后才能接受网格。",
            ],
        )
    if any(
        term in lowered
        for term in ("电芯热失控", "热失控", "thermal runaway", "battery runaway")
    ):
        return (
            [
                "该案例描述烘箱加热诱发的圆柱电芯热失控；不能据此推断内短路、针刺、过充、排气、燃烧或传播到相邻电芯的行为。",
                "Arrhenius 频率因子、活化能、反应热和初始反应状态高度敏感；更换电芯化学体系或尺寸后必须重新标定，不能直接沿用。",
                "热失控阶段温升陡峭，时间步、相对容差和非线性求解设置可能显著影响峰值温度与起始时间。",
            ],
            [
                "核对轴对称圆柱几何、T_init=35 degC，以及 T_oven 对 150 和 155 degC 的参数扫描；确认外表面对流 h_conv=7.17 W/(m^2*K) 和辐射 eps_rad=0.8 均使用 T_oven。",
                "核对总热源 Q_tot=Qsei+Qne+Qpe+Qele、Domain ODE 状态变量 c_sei、c_neg、t_sei、alpha、c_e，以及热源仅施加于 Jelly Roll 域。",
                "比较 maxT、平均温度、四类分解热源和反应程度曲线；对 0–120 min 时间范围执行时间步与相对容差收敛检查，并记录热失控起始时间和峰值温度。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "电化学抛光", "electrochemical polishing", "electrode depletion",
            "deformed geometry", "moving boundary",
        )
    ):
        return (
            [
                "该案例采用简化消耗定律：电极法向移动速度与法向电流密度成正比；不能据此推断完整电极动力学、传质或曲率效应。",
                "增大 K、电压或计算时间可能导致变形网格畸变，必须重新验证网格质量与时间步收敛性。",
            ],
            [
                "核对 V0=30 V、电导率 10 S/m、K=1e-11 m^3/(A*s)、法向速度 -K*(-ec.nJ) 及其边界选择。",
                "在 0–10 s 内执行时间步和网格收敛检查，并监视最小网格质量与移动边界连续性。",
                "与案例基准比较：最大电流密度约 9e5 A/m^2，10 s 后最大 y 位移约 0.1 mm，并确认凸起趋于平滑。",
            ],
        )
    if any(term in lowered for term in ("许可", "license", "agreement", "协议")):
        return (
            [
                "现有证据可证明许可协议文本存在，但不能单独证明其在 App 中的触发、接受或拒绝流程。",
            ],
            [
                "在 COMSOL 中打开原案例，逐项核对推荐中引用的来源证据与应用程序内容。",
                "运行原 App，记录许可文本何时显示以及用户可执行的操作；未观察到的行为保持未知。",
                "逐字核对显示的许可文本与案例内证据，并分别记录允许继续和阻止继续的实际结果。",
            ],
        )
    if any(
        term in lowered
        for term in (
            "几何", "random geometry", "geometry", "模型方法", "递归",
            "recursive", "recursion", "menger", "sierpinski",
        )
    ):
        return (
            [],
            [
                "在 COMSOL 中打开原案例，核对模型方法和几何序列中实际存在的操作。",
                "重复运行几何生成方法，检查每次生成结果、几何构建状态和实体数量。",
                "验证生成对象满足来源中定义的实体数量、层数、边界和尺寸约束；未定义的约束保持未知。",
            ],
        )
    if any(term in lowered for term in ("点源", "point source", "pointsource")):
        return (
            [
                "点源会产生奇异解；若改变源位置、源强或几何，必须重新验证网格细化收敛性。",
            ],
            [
                "核对点源所选点实体、源项数值和全部狄利克雷边界选择。",
                "逐级执行自适应网格细化，检查点源附近网格密度以及误差量是否收敛。",
                "将数值解与来源给出的解析解比较，并复核截线误差图和域积分误差。",
            ],
        )
    if any(
        term in lowered
        for term in ("批处理", "batch sweep", "batchsweep", "批量扫描")
    ):
        return (
            [
                "批处理目录和结果文件路径被硬编码为 C:\\COMSOL；目标机器必须确认目录存在且具有写权限。",
                "扫描中关闭了解同步解；不能假设主模型会自动包含每个批处理解。",
            ],
            [
                "核对扫描参数 sn、范围 range(1,1,10) 与插值函数 int1(sn) 的十个样本映射。",
                "先运行单个 sn 样本，确认边界点探针读取 es.nD 且单位为 nC/m^2。",
                "运行完整批处理后，核对保存探针表包含十个扫描结果，并确认 C:\\COMSOL\\results.txt 成功写入。",
            ],
        )
    if any(
        term in lowered
        for term in ("电传感器", "electric sensor", "eit", "介电常数", "permittivity")
    ):
        return (
            [
                "该来源是简化静电 EIT 示范；不能据此推断真实设备的电极数量、测量协议、噪声水平或反演算法。",
            ],
            [
                "核对接地边界、电势边界及其实体编号，并确认其余外边界保持来源所述电绝缘条件。",
                "分别复算来源中的相对介电常数分布，确认高介电常数区域对应更高表面电荷密度。",
                "比较表面电荷密度 es.nD 和电场模 es.normE 图；改变几何或介电常数后执行网格收敛检查。",
            ],
        )
    return (
        [],
        [
            "在 COMSOL 中打开原案例，逐项核对推荐中引用的来源证据与模型树。",
            "只修改有来源依据的参数，并保存为新模型。",
            "重新求解后与原案例结果对比；若结果偏差无法解释，停止沿用该案例。",
        ],
    )


def evidence_priority(item: dict) -> tuple[int, int]:
    excerpt = item["excerpt"].lower()
    source = item["source"].lower()
    explicit_markers = (
        "model.component", "model.study", "model.sol", "model.param",
        "select physics", "choose ", "create(", ".set(",
        "transient", "stationary", "dilutedspecies", "generalformboundarypde",
        "characteristic impedance", "propagation constant",
        "heattransfer", "domainode", "statevariables", "updateexpression",
        "thermalinsulation", "temperatureboundary", "heatfluxboundary",
        "pressureacoustics", "eigenfrequency",
        "laplaceequation", "pointsourceterm",
        "electrostatics", "chargeconservationfluid", "relpermittivity",
        "surface charge density", "es.nd", "es.norme",
        "batchsweep", "range(1,1,10)", "boundarypoint", "saved probe table",
        "prescribednormalvelocity", "deformedgeometry", "ec.normj",
        "range(0,10)", "automeshsize(3)",
        "coefficientformboundarypde", "sigma*d", "current field",
        "current density",
        "globalequations", "implicitevent", "stopcondition",
        "spin decay", "carry distance", "lift coefficient", "drag coefficient",
        "surrogatemodeltraining", "surrogatemodelgeometrysampling",
        "dnn1_1", "dnn1_2", "nsolvenonadp",
        "explicitevent", "discretestates", "highload",
        "heaterstate", "upwards", "downwards", "intop1(t)",
        "deformingdomaindeformedgeometry", "prescribednormalmeshvelocity",
        "r_surface", "v_surface", "ccucl2",
        "heatrate", "step changes in loads",
        "axisymmetric", "lengthunit", "compositecurves", "partitionedges",
        "differenceselection", "adjacentselection", "explicitselection",
        "unionselection",
    )
    generic_markers = (
        "comsol multiphysics", "graphical user interface", "toolbar",
        "selection.set", "selection().set", "selection.set([])",
    )
    score = 0
    if source.endswith((".java", ".m")):
        score += 3
    if any(marker in excerpt for marker in explicit_markers):
        score += 3
    if any(marker in excerpt for marker in ("characteristic impedance", "propagation constant", "r, l, g, c")):
        score += 3
    if any(marker in excerpt for marker in ("heattransfer", "statevariables", "updateexpression", '"transient"', "'transient'")):
        score += 3
    if any(
        marker in excerpt
        for marker in (
            "axisymmetric", "lengthunit", "compositecurves", "partitionedges",
            "differenceselection", "adjacentselection", "explicitselection",
            "unionselection",
        )
    ):
        score += 4
    if any(
        marker in excerpt
        for marker in (
            "laplaceequation", "pointsourceterm", "meshadaptmethod",
            "errestandadap", '"circle"', "'circle'", '"point"', "'point'",
            "u+log(", "abs(u+log(",
        )
    ):
        score += 4
    if any(
        marker in excerpt
        for marker in (
            "relpermittivity", "es.nd", "es.norme", '"workplane"', "'workplane'",
            '"extrude"', "'extrude'", '"ellipse"', "'ellipse'",
            '"rectangle"', "'rectangle'",
            "batchsweep", "boundarypoint", "saved probe table",
            "range(1,1,10)", "results.txt",
            "prescribednormalvelocity", "ec.normj", "range(0,10)", "automeshsize(3)",
        )
    ):
        score += 5
    if any(
        marker in excerpt
        for marker in (
            "differenceselection", "adjacentselection", "explicitselection",
            "unionselection",
        )
    ):
        score += 2
    if any(
        marker in excerpt
        for marker in (
            "temperatureboundary", "heatfluxboundary", "convectiveoutflow",
            '"outflow"', "'outflow'", '"reactions"', "'reactions'",
            '"stationary"', "'stationary'", "conversion species", "temperature (",
            "solidmechanics", "planestress", "von mises", "rotational speed",
            "q_tot", "qsei", "qne", "qpe", "qele", "maxt",
            "surfacetoambientradiation", "convectiveheatflux",
            "domainode", "globalequations", "range(0,1,120)",
            "hcurve", "hmin", "hnarrow", "hgrad", "skewness",
            "automeshsize(7)", "automeshsize(3)", "freetet",
            "laminarflow", "slidingwall", "pressurepointconstraint",
            "elemcount", "elemratio", "growthrate", "cutline2d",
            "u vs. y", "v vs. x", "streamline",
            "dilutedspecies", "externalconvection", "flux_avg", "flux_hom",
            "pressureacoustics", "sound hard", "acpr.p_t", "acpr.lp_t",
            "eigenfrequencies", "quality factor", "damping ratio",
            "t_pos", "t_pts_e", "t_pts_l", "t_hts_e", "t_hts_l",
            "femtosecond", "ultrafast", "electron temperature", "lattice temperature",
            "coefficientformpde", "generalformpde", "s/delta",
            "thermalconductivity", "heatcapacity", "density",
            "surfacetoambientradiation", "rotatingdomain", "gaussian profile",
        )
    ):
        score += 4
    if any(
        marker in excerpt
        for marker in ("thermalconductivity", "heatcapacity", "density")
    ):
        score += 4
    if any(marker in excerpt for marker in generic_markers):
        score -= 2
    return (-score, len(item["excerpt"]))


def parameter_priority(item: dict) -> tuple[int, int]:
    source = item["source"].lower()
    name = item["name"]
    score = 0
    if source.endswith((".java", ".m", ".txt")):
        score += 4
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        score += 2
    if name.lower() in {
        "t_oven", "t_init", "h_conv", "eps_rad", "r_batt", "h_batt",
        "asei", "ane", "ae", "ape", "ea_sei", "ea_e", "ea_neg", "ea_pos",
        "hsei", "hne", "hpe", "hele",
    }:
        score += 5
    if name.lower().endswith(
        (".hcurve", ".hmin", ".hnarrow", ".hgrad", ".automeshsize")
    ):
        score += 6
    if name.lower().endswith(
        (".elemcount", ".elemratio", ".growthrate", ".symmetric", ".plistarr")
    ):
        score += 5
    if name.lower() in {"d1", "d2", "epsilon", "k_f", "c_max"}:
        score += 5
    if name.lower() in {
        "phi", "phi_p", "t_p", "delta", "g", "c_e", "c_l", "k", "rho",
        "tau", "l", "t0",
    }:
        score += 7
    if name.lower() in {"sigma", "d"}:
        score += 7
    if name.lower() in {
        "u0", "alpha", "omega0", "m", "rho", "mu", "g", "c", "smooth",
        "spinloft",
    }:
        score += 7
    if name.lower() in {
        "e", "ke", "dhrx", "a", "diff", "uk", "t0", "ta0", "ra", "l",
    }:
        score += 7
    if name.lower() in {
        "r_wafer", "thickness", "v_rotation", "period", "r_spot",
        "emissivity", "p_laser",
    }:
        score += 8
    if name.lower() in {
        "ev.expl1.start", "ht.hf1.p0", "ht.hf1.heatfluxtype",
        "study.time.rtol", "study.time.tlist",
    }:
        score += 9
    if name.lower().startswith("study.sm."):
        score += 11
    if name.lower().endswith((".r", ".c", ".f")):
        score += 5
    if name.lower().endswith((".shift", ".neigs")):
        score += 6
    if re.search(r"\s", name):
        score -= 1
    return (-score, len(name))


def recommend(index: dict, query: str, top_k: int = 3) -> dict:
    ranked = sorted(
        (
            (
                similarity(query, index["idf"], vector)
                + 0.5 * title_similarity(query, case["name"]),
                case,
            )
            for case, vector in zip(index["cases"], index["vectors"])
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:top_k]
    recommendations = []
    for score, case in ranked:
        supported_fields = {
            key: sorted(values, key=evidence_priority)[:3]
            for key, values in case["fields"].items()
            if values
        }
        gaps = [key for key, values in case["fields"].items() if not values]
        query_risks, validation_steps = validation_and_query_risks(query)
        explicit_parameters = [
            item
            for item in case["parameters"]
            if item["source"].lower().endswith((".java", ".m", ".txt"))
        ]
        recommended_parameters = explicit_parameters or case["parameters"]
        values_by_name: dict[str, set[str]] = {}
        for parameter in recommended_parameters:
            values_by_name.setdefault(parameter["name"], set()).add(parameter["value"])
        conflicts = {
            name: sorted(values)
            for name, values in values_by_name.items()
            if len(values) > 1
        }
        risks = list(query_risks)
        if conflicts:
            conflict_items = sorted(conflicts.items())
            formatted = "; ".join(
                f"{name}: {', '.join(values)}" for name, values in conflict_items[:8]
            )
            if len(conflict_items) > 8:
                formatted += f"; 另有 {len(conflict_items) - 8} 个冲突项，详见 conflicts 字段"
            risks.append(
                f"同名参数存在多个有来源值（可能来自不同模型或构建历史）：{formatted}。修改前必须在目标模型中确认当前值。"
            )
        if gaps:
            risks.append(
                f"缺少 {', '.join(gaps)} 的直接证据，不能据此复现或推断 COMSOL 设置。"
            )
        recommendations.append(
            {
                "case_id": case["case_id"],
                "case_name": case["name"],
                "similarity": round(score, 4),
                "recommendation_status": (
                    "可作为有证据的参考案例" if score > 0 and supported_fields else "仅主题相似，设置证据不足"
                ),
                "supported_evidence": supported_fields,
                "parameter_changes": (
                    {
                        "status": "仅可修改下列已记录参数；新值需由用户需求或验证确定",
                        "parameters": sorted(recommended_parameters, key=parameter_priority)[:10],
                        "conflicts": conflicts,
                    }
                    if recommended_parameters
                    else {"status": "无已记录参数，不能建议具体修改值", "parameters": [], "conflicts": {}}
                ),
                "risks": risks,
                "validation_steps": validation_steps,
            }
        )
    return {
        "query": query,
        "policy": "不推断无来源依据的 COMSOL 设置；空字段保持未知。",
        "recommendations": recommendations,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="读取案例并建立离线向量索引")
    ingest.add_argument("source", type=Path, nargs="+", help="一个或多个案例目录")
    ingest.add_argument("--output", type=Path, default=Path("data/index.json"))
    merge = sub.add_parser("merge", help="合并并去重多个案例知识库索引")
    merge.add_argument("index", type=Path, nargs="+", help="案例知识库索引")
    merge.add_argument("--output", type=Path, default=Path("data/master_index.json"))
    merge.add_argument("--summary", type=Path)
    query = sub.add_parser("query", help="检索相似案例并输出有依据的建议")
    query.add_argument("question")
    query.add_argument("--index", type=Path, default=Path("data/index.json"))
    query.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    if args.command == "ingest":
        payload = build_index(args.source, args.output.resolve())
        print(json.dumps({"index": str(args.output.resolve()), "cases": len(payload["cases"])}, ensure_ascii=False))
        return 0
    if args.command == "merge":
        payload = merge_case_indexes(args.index, args.output.resolve())
        if args.summary:
            write_master_summary(payload, args.summary.resolve())
        print(json.dumps({
            "index": str(args.output.resolve()),
            "summary": str(args.summary.resolve()) if args.summary else None,
            "cases": len(payload["cases"]),
        }, ensure_ascii=False))
        return 0
    index = json.loads(args.index.read_text(encoding="utf-8"))
    print(json.dumps(recommend(index, args.question, args.top_k), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
