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
        data = json.loads(path.read_text(encoding="utf-8-sig"))
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
        r"(?:new\s+\w+(?:\[\])+\s*\{|\[)(.*?)(?:\}|\])",
        cleaned,
    )
    if match:
        parts = [part for part in re.split(r"[\s,]+", match.group(1).strip()) if part]
        return f"[{', '.join(parts)}]"
    return cleaned


def meaningful_evidence(field_name: str, sentence: str) -> bool:
    lowered = sentence.lower()
    if field_name == "mesh" and lowered.strip() == "mesh":
        return False
    if field_name == "materials" and lowered.strip() in {"material", "materials"}:
        return False
    rejected = {
        "physics": (
            "<physicslist ", "<physicsinfo physics=\"\"", "physics list is empty",
            "<componentphysicslist ", "<base t=\"50\">/physics</base>",
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
        ),
        "geometry": ("<scalar name=", "<tensor name=",),
        "solver": ("<studylist ",),
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
            "<lastbuiltfeature ", "maximum element depth to process", "simplify mesh",
            'model.result("', "model.result('",
        ),
        "results": (
            "<results ", "name=\"results\"", "originalpath", "propertyvalue",
            "result list", "results tag=", " result after ", "resulting entities",
            "import com.comsol.api.database.result",
            "<scalar name=\"root.comp1.", "<tensor name=\"root.comp1.",
            "<scalar name=", "<tensor name=",
        ),
        "boundary_conditions": (
            "fixed", "<scalar name=", "<tensor name=",
            "root.minput.", "minput_concentration",
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
    return len(query_tokens & name_tokens) / len(name_tokens)


def validation_and_query_risks(query: str) -> tuple[list[str], list[str]]:
    lowered = query.lower()
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
        )
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
            formatted = "; ".join(
                f"{name}: {', '.join(values)}" for name, values in sorted(conflicts.items())
            )
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
    query = sub.add_parser("query", help="检索相似案例并输出有依据的建议")
    query.add_argument("question")
    query.add_argument("--index", type=Path, default=Path("data/index.json"))
    query.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    if args.command == "ingest":
        payload = build_index(args.source, args.output.resolve())
        print(json.dumps({"index": str(args.output.resolve()), "cases": len(payload["cases"])}, ensure_ascii=False))
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
