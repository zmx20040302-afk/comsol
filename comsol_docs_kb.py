import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path


CORE_DOCUMENTS = {
    "ApplicationProgrammingGuide.pdf",
    "COMSOL_ApplicationBuilderManual.pdf",
    "COMSOL_MultiphysicsInstallationGuide.pdf",
    "COMSOL_PostprocessingAndVisualization.pdf",
    "COMSOL_ProgrammingReferenceManual.pdf",
    "COMSOL_ReferenceManual.pdf",
    "COMSOL_SpecializedTechniquesForPostprocessingAndVisualization.pdf",
    "IntroductionToApplicationBuilder.pdf",
    "IntroductionToCOMSOLMultiphysics.pdf",
    "IntroductionToLiveLinkForMATLAB.pdf",
    "LiveLinkForMATLABUsersGuide.pdf",
}

MODULE_ALIASES = {
    "Acoustics_Module": ("acoustic", "acoustics", "sound", "声学"),
    "CFD_Module": ("cfd", "laminar", "turbulent", "fluid flow", "层流", "湍流"),
    "Heat_Transfer_Module": ("heat transfer", "thermal", "传热", "热传导"),
    "LiveLink_for_MATLAB": ("matlab", "mphstart", "mphload", "mphsave", "mphplot"),
    "Structural_Mechanics_Module": ("solid mechanics", "structural", "stress", "结构", "应力"),
}


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_./+-]{2,}", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(run[index : index + 2] for index in range(max(1, len(run) - 1)))
    return latin + chinese


def clean_page_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def catalog(source: Path) -> list[dict]:
    documents = []
    for path in sorted(source.rglob("*.pdf")):
        documents.append(
            {
                "document_id": hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12],
                "module": path.parent.name,
                "name": path.name,
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "core": path.name in CORE_DOCUMENTS,
            }
        )
    return documents


def build_index(source: Path, output: Path, scope: str) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Building the documentation index requires pypdf.") from exc

    documents = catalog(source)
    selected = documents if scope == "all" else [item for item in documents if item["core"]]
    pages: list[dict] = []
    for document in selected:
        reader = PdfReader(document["path"])
        document["pages"] = len(reader.pages)
        for number, page in enumerate(reader.pages, start=1):
            text = clean_page_text(page.extract_text() or "")
            if len(text) < 40:
                continue
            pages.append(
                {
                    "document_id": document["document_id"],
                    "module": document["module"],
                    "document": document["name"],
                    "path": document["path"],
                    "page": number,
                    "text": text,
                }
            )

    token_counts = [Counter(tokenize(item["text"])) for item in pages]
    doc_freq = Counter(token for counts in token_counts for token in counts)
    count = len(pages)
    idf = {
        token: math.log((count + 1) / (frequency + 1)) + 1
        for token, frequency in doc_freq.items()
    }
    vectors = []
    for counts in token_counts:
        vector = {
            token: (1 + math.log(frequency)) * idf[token]
            for token, frequency in counts.items()
        }
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        vectors.append({token: round(value / norm, 7) for token, value in vector.items()})

    payload = {
        "schema_version": 1,
        "source_root": str(source.resolve()),
        "scope": scope,
        "policy": "Only cite settings and operations supported by indexed COMSOL 6.4 documentation pages.",
        "documents": documents,
        "indexed_document_ids": [item["document_id"] for item in selected],
        "pages": pages,
        "idf": idf,
        "vectors": vectors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def similarity(question: str, idf: dict, vector: dict) -> float:
    counts = Counter(tokenize(question))
    query = {
        token: (1 + math.log(frequency)) * idf[token]
        for token, frequency in counts.items()
        if token in idf
    }
    norm = math.sqrt(sum(value * value for value in query.values())) or 1
    return sum((value / norm) * vector.get(token, 0) for token, value in query.items())


def module_boost(question: str, page: dict) -> float:
    lowered = question.lower()
    score = 0.0
    for phrase in MODULE_ALIASES.get(page["module"], ()):
        if phrase in lowered:
            score += 0.2
    document_words = set(tokenize(page["document"].replace("UsersGuide", " ")))
    query_words = set(tokenize(question))
    score += min(0.15, 0.03 * len(document_words & query_words))
    return score


def query(index_path: Path, question: str, top_k: int) -> dict:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    ranked = sorted(
        (
            (similarity(question, payload["idf"], vector) + module_boost(question, page), page)
            for page, vector in zip(payload["pages"], payload["vectors"])
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:top_k]
    return {
        "query": question,
        "policy": payload["policy"],
        "results": [
            {
                "score": round(score, 4),
                "module": page["module"],
                "document": page["document"],
                "page": page["page"],
                "path": page["path"],
                "excerpt": clean_page_text(page["text"][:1200]),
            }
            for score, page in ranked
        ],
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="Searchable COMSOL PDF documentation index.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("source", type=Path)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--scope", choices=("core", "all"), default="core")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("question")
    query_parser.add_argument("--index", type=Path, required=True)
    query_parser.add_argument("--top-k", type=int, default=5)

    args = parser.parse_args()
    if args.command == "build":
        result = build_index(args.source, args.output, args.scope)
        print(
            json.dumps(
                {
                    "index": str(args.output.resolve()),
                    "catalog_documents": len(result["documents"]),
                    "indexed_documents": len(result["indexed_document_ids"]),
                    "indexed_pages": len(result["pages"]),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps(query(args.index, args.question, args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
