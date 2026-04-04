import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

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


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        if value.strip().startswith("[") and value.strip().endswith("]"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    record = {key: raw.get(key, "") for key in REQUIRED_KEYS}
    record["tags"] = _safe_tags(raw.get("tags"))

    for key in REQUIRED_KEYS:
        if key != "tags":
            record[key] = _safe_text(record.get(key, ""))

    status = record["status"].lower()
    if status in {"oficializado", "ativo"}:
        record["status"] = "ativo"
    elif status in {"sigiloso", "sigilo"}:
        record["status"] = "sigiloso"
    elif status:
        record["status"] = status
    else:
        record["status"] = "desconhecido"

    texto_indexacao = " ".join(
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
    record["texto_indexacao"] = texto_indexacao
    return record


def _iter_json_records(path: Path) -> Iterable[Dict[str, Any]]:
    content = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
    if not content:
        return []

    if path.suffix.lower() == ".jsonl":
        items = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
        return items

    parsed = json.loads(content)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("registros"), list):
        return parsed["registros"]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def find_base_files(data_dir: Path) -> List[Path]:
    if not data_dir.exists():
        return []
    return sorted(
        p
        for p in data_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".json", ".jsonl"}
        and not p.name.startswith("manifesto_")
    )


def load_acordaos(data_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen_ids = set()

    for path in find_base_files(data_dir):
        try:
            for raw in _iter_json_records(path):
                if not isinstance(raw, dict):
                    continue
                record = normalize_record(raw)
                record_id = record.get("id") or f"{record.get('numero_acordao', '')}-{record.get('processo', '')}"
                if not record_id or record_id in seen_ids:
                    continue
                seen_ids.add(record_id)
                records.append(record)
        except Exception:
            continue
    return records


def summarize_base(data_dir: Path, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    files = find_base_files(data_dir)
    anos = sorted({r.get("ano_acordao", "") for r in records if r.get("ano_acordao")})
    return {
        "total_registros": len(records),
        "total_arquivos": len(files),
        "anos": anos,
    }
