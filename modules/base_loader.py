import json
from pathlib import Path
from typing import Any, Dict, List

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
    if not isinstance(record["tags"], list):
        record["tags"] = []

    for key in REQUIRED_KEYS:
        if key != "tags":
            value = record.get(key, "")
            record[key] = "" if value is None else str(value).strip()

    status = record["status"].strip().lower()
    if status in {"oficializado", "ativo"}:
        status = "ativo"
    elif status in {"sigiloso", "sigilo"}:
        status = "sigiloso"
    elif not status:
        status = "desconhecido"
    record["status"] = status

    record["texto_indexacao"] = " ".join(
        part
        for part in [
            record["titulo"],
            record["assunto"],
            record["sumario"],
            record["ementa_match"],
            record["decisao"],
            " ".join(record["tags"]),
        ]
        if part
    ).strip()
    return record



def _load_json_file(path: Path) -> List[Dict[str, Any]]:
    content = path.read_text(encoding="utf-8-sig").strip()
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

    records: List[Dict[str, Any]] = []
    seen_ids = set()
    for path in sorted(data_dir.rglob("*")):
        if path.name.startswith("manifesto_"):
            continue
        if path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            for raw in _load_json_file(path):
                record = _normalize_record(raw)
                record_id = record.get("id") or f"{record.get('numero_acordao','')}-{record.get('processo','')}"
                if record_id in seen_ids:
                    continue
                seen_ids.add(record_id)
                records.append(record)
        except Exception:
            continue
    return records



def summarize_base(data_dir: Path, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    anos = sorted({r.get("ano_acordao", "") for r in records if r.get("ano_acordao")})
    total_arquivos = len(
        [
            p
            for p in data_dir.rglob("*")
            if p.suffix.lower() in {".json", ".jsonl"} and not p.name.startswith("manifesto_")
        ]
    )
    return {
        "total_registros": len(records),
        "total_arquivos": total_arquivos,
        "anos": anos,
    }
