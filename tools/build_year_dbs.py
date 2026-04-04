from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

REQUIRED_KEYS = [
    'id','tipo','titulo','numero_acordao','numero_acordao_num','ano_acordao','colegiado','data_sessao','relator',
    'processo','assunto','sumario','ementa_match','decisao','url_oficial','status','tags'
]


def safe_text(v: Any) -> str:
    return '' if v is None else str(v).strip()


def safe_tags(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        txt = v.strip()
        if txt.startswith('[') and txt.endswith(']'):
            try:
                parsed = json.loads(txt)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
        return [x.strip() for x in txt.split(',') if x.strip()]
    return []


def normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    rec = {k: raw.get(k, '') for k in REQUIRED_KEYS}
    for k in REQUIRED_KEYS:
        if k != 'tags':
            rec[k] = safe_text(rec[k])
    rec['tags'] = safe_tags(raw.get('tags'))
    status = rec['status'].lower()
    if status in {'oficializado', 'ativo'}:
        rec['status'] = 'ativo'
    elif status in {'sigilo', 'sigiloso'}:
        rec['status'] = 'sigiloso'
    else:
        rec['status'] = status or 'desconhecido'
    if not rec['decisao']:
        rec['decisao'] = safe_text(raw.get('acordao_texto', ''))[:3000]
    search_text = ' '.join(p for p in [rec['titulo'], rec['assunto'], rec['sumario'], rec['ementa_match'], rec['decisao'], ' '.join(rec['tags'])] if p).strip()
    rec['search_text'] = search_text
    return rec


def iter_json_records(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding='utf-8-sig', errors='ignore').strip()
    if not text:
        return []
    if path.suffix.lower() == '.jsonl':
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get('registros'), list):
        return parsed['registros']
    if isinstance(parsed, dict):
        return [parsed]
    return []


def build_db(records: List[Dict[str, Any]], ano: str, output_path: Path) -> None:
    if output_path.exists():
        output_path.unlink()
    conn = sqlite3.connect(str(output_path))
    cur = conn.cursor()
    cur.execute('PRAGMA journal_mode=WAL;')
    cur.execute('PRAGMA synchronous=NORMAL;')
    cur.execute(
        '''CREATE TABLE records (
            id TEXT PRIMARY KEY,
            tipo TEXT,
            titulo TEXT,
            numero_acordao TEXT,
            numero_acordao_num TEXT,
            ano_acordao TEXT,
            colegiado TEXT,
            data_sessao TEXT,
            relator TEXT,
            processo TEXT,
            assunto TEXT,
            sumario TEXT,
            ementa_match TEXT,
            decisao TEXT,
            url_oficial TEXT,
            status TEXT,
            tags TEXT
        )'''
    )
    cur.execute("CREATE VIRTUAL TABLE records_fts USING fts5(id UNINDEXED, titulo, assunto, sumario, ementa_match, decisao, tags)")
    cur.execute('CREATE TABLE metadata (ano TEXT, total_registros INTEGER)')
    rows = []
    fts_rows = []
    seen = set()
    for rec in records:
        rec_id = rec['id'] or f"{rec['numero_acordao']}-{rec['processo']}"
        if not rec_id or rec_id in seen:
            continue
        seen.add(rec_id)
        rows.append((
            rec_id, rec['tipo'], rec['titulo'], rec['numero_acordao'], rec['numero_acordao_num'], rec['ano_acordao'],
            rec['colegiado'], rec['data_sessao'], rec['relator'], rec['processo'], rec['assunto'], rec['sumario'],
            rec['ementa_match'], rec['decisao'], rec['url_oficial'], rec['status'], json.dumps(rec['tags'], ensure_ascii=False)
        ))
        fts_rows.append((rec_id, rec['titulo'], rec['assunto'], rec['sumario'], rec['ementa_match'], rec['decisao'], ' '.join(rec['tags'])))
    cur.executemany('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    cur.executemany('INSERT INTO records_fts VALUES (?,?,?,?,?,?,?)', fts_rows)
    cur.execute('INSERT INTO metadata VALUES (?,?)', (ano, len(rows)))
    cur.execute('CREATE INDEX idx_num_ano ON records(numero_acordao_num, ano_acordao)')
    cur.execute('CREATE INDEX idx_num ON records(numero_acordao_num)')
    conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Converte JSONs essenciais em bancos SQLite por ano para o app Streamlit.')
    parser.add_argument('input_dir', help='Pasta com arquivos JSON/JSONL da base essencial')
    parser.add_argument('output_dir', help='Pasta de saída dos .db')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path in sorted(input_dir.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.jsonl'} or path.name.startswith('manifesto_'):
            continue
        print(f'Lendo {path.name}...')
        for raw in iter_json_records(path):
            if not isinstance(raw, dict):
                continue
            rec = normalize_record(raw)
            ano = rec.get('ano_acordao', '').strip()
            if not ano:
                continue
            grouped[ano].append(rec)

    for ano, records in sorted(grouped.items()):
        out = output_dir / f'acordaos_{ano}.db'
        print(f'Gerando {out.name} com {len(records)} registros...')
        build_db(records, ano, out)
    print('Concluído.')


if __name__ == '__main__':
    main()
