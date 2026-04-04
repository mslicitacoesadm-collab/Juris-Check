from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = 'acordaos_*.db'


def find_db_files(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted(base_dir.glob(DB_GLOB))


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def detect_schema(conn: sqlite3.Connection) -> str:
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'records' in names:
        return 'records'
    if 'acordaos' in names:
        return 'acordaos'
    return 'unknown'


def _normalize_tags(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    txt = str(raw).strip()
    if not txt:
        return []
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in txt.split(',') if x.strip()]


def normalize_row(row: sqlite3.Row | Dict[str, Any], schema: str) -> Dict[str, Any]:
    item = dict(row)
    if schema == 'acordaos':
        item = {
            'id': item.get('id', ''),
            'tipo': item.get('tipo', ''),
            'titulo': item.get('titulo', ''),
            'numero_acordao': item.get('numero_acordao', ''),
            'numero_acordao_num': item.get('numero_acordao_num', ''),
            'ano_acordao': item.get('ano_acordao', ''),
            'colegiado': item.get('colegiado', ''),
            'data_sessao': item.get('data_sessao', ''),
            'relator': item.get('relator', ''),
            'processo': item.get('processo', ''),
            'assunto': item.get('assunto', ''),
            'sumario': item.get('sumario', ''),
            'ementa_match': item.get('ementa_match', ''),
            'decisao': item.get('decisao', ''),
            'url_oficial': item.get('url_oficial', ''),
            'status': item.get('status', ''),
            'tags': _normalize_tags(item.get('tags_json', '')),
        }
    else:
        item['tags'] = _normalize_tags(item.get('tags', ''))
    return item


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    dbs = find_db_files(base_dir)
    total_registros = 0
    anos = []
    detalhes = []
    for db in dbs:
        try:
            conn = open_db(db)
            schema = detect_schema(conn)
            ano = '?'
            total = 0
            if schema == 'records':
                row = conn.execute('SELECT ano, total_registros FROM metadata LIMIT 1').fetchone()
                if row:
                    ano = str(row['ano'])
                    total = int(row['total_registros'] or 0)
            elif schema == 'acordaos':
                meta = {r['chave']: r['valor'] for r in conn.execute('SELECT chave, valor FROM metadata').fetchall()}
                ano = str(meta.get('ano', '?'))
                total = int(meta.get('total_registros', 0) or 0)
                if not total:
                    total = int(conn.execute('SELECT COUNT(*) FROM acordaos').fetchone()[0])
            total_registros += total
            if ano and ano != '?':
                anos.append(ano)
            detalhes.append({'arquivo': db.name, 'ano': ano, 'total_registros': total, 'schema': schema})
            conn.close()
        except Exception:
            detalhes.append({'arquivo': db.name, 'ano': '?', 'total_registros': 0, 'schema': 'erro'})
    anos = sorted({a for a in anos if a})
    return {'total_bases': len(dbs), 'total_registros': total_registros, 'anos': anos, 'detalhes': detalhes}


def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None) -> Dict[str, Any] | None:
    if not numero:
        return None
    for db in db_files:
        conn = open_db(db)
        try:
            schema = detect_schema(conn)
            if schema == 'records':
                sql = 'SELECT * FROM records WHERE numero_acordao_num = ?'
                params: List[Any] = [numero]
                if ano:
                    sql += ' AND ano_acordao = ?'
                    params.append(ano)
                sql += ' LIMIT 1'
                row = conn.execute(sql, params).fetchone()
            elif schema == 'acordaos':
                sql = 'SELECT * FROM acordaos WHERE numero_acordao_num = ?'
                params = [numero]
                if ano:
                    sql += ' AND ano_acordao = ?'
                    params.append(ano)
                sql += ' LIMIT 1'
                row = conn.execute(sql, params).fetchone()
            else:
                row = None
            if row:
                return normalize_row(row, schema)
        finally:
            conn.close()
    return None
