import json
from pathlib import Path
from typing import Dict, List, Any

REQUIRED_KEYS = [
    "id",
    "tipo",
    "titulo",
    "numero_acordao",
    "numero_acordao_num",
    "ano_acordao",
    "colegiado",
    "data_sessao",
    "relator",
    "processo",
    "assunto",
    "sumario",
    "ementa_match",
    "decisao",
    "url_oficial",
    "status",
    "tags",
]

def _normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    record = {key: raw.get(key, "") for key in REQUIRED_KEYS}
    record["tags"] = raw.get("tags") or []
    if isinstance(record["tags"], str):
        record["tags"] = [t.strip() for t in record["tags"].split(",") if t.strip()]
    for key in REQUIRED_KEYS:
        if key != "tags":
            record[key] = str(record.get(key, "")).strip()
    record["status"] = record["status"].lower()
    record["texto_indexacao"] = " ".join(
        [
            record["titulo"],
            record["assunto"],
            record["sumario"],
            record["ementa_match"],
            record["decisao"],
            " ".join(record["tags"]),
        ]
    ).strip()
    return record

def _load_json_file(path: Path) -> List[Dict[str, Any]]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in content.splitlines() if line.strip()]
    data = json.loads(content)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("registros"), list):
        return data["registros"]
    if isinstance(data, dict):
        return [data]
    return []

def load_acordaos(data_dir: Path) -> List[Dict[str, Any]]:
    if not data_dir.exists():
        return []
    records = []
    for path in sorted(data_dir.rglob("*")):
        if path.name.startswith("manifesto_"):
            continue
        if path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            for raw in _load_json_file(path):
                records.append(_normalize_record(raw))
        except Exception:
            continue
    return records

def summarize_base(data_dir: Path, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    anos = sorted({r.get("ano_acordao", "") for r in records if r.get("ano_acordao")})
    total_arquivos = len([
        p for p in data_dir.rglob("*")
        if p.suffix.lower() in {".json", ".jsonl"} and not p.name.startswith("manifesto_")
    ])
    return {
        "total_registros": len(records),
        "total_arquivos": total_arquivos,
        "anos": anos,
    }
