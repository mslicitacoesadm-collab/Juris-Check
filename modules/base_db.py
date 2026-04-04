from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = 'acordaos_*.db'


def find_db_files(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted(p for p in base_dir.glob(DB_GLOB) if p.is_file())


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=128)
def detect_schema(db_path_str: str) -> Dict[str, Any]:
    db_path = Path(db_path_str)
    schema: Dict[str, Any] = {
        'table': None,
        'columns': set(),
        'fts_table': None,
        'metadata': False,
    }
    try:
        conn = open_db(db_path)
        try:
            tables = {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'records' in tables:
                schema['table'] = 'records'
            elif 'acordaos' in tables:
                schema['table'] = 'acordaos'
            if schema['table']:
                cols = conn.execute(f"PRAGMA table_info({schema['table']})").fetchall()
                schema['columns'] = {c['name'] for c in cols}
            if 'records_fts' in tables:
                schema['fts_table'] = 'records_fts'
            elif 'acordaos_fts' in tables:
                schema['fts_table'] = 'acordaos_fts'
            schema['metadata'] = 'metadata' in tables
        finally:
            conn.close()
    except Exception:
        pass
    return schema


def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    get = raw.get
    data = {
        'id': get('id') or get('rowid') or '',
        'tipo': get('tipo') or 'ACÓRDÃO',
        'titulo': get('titulo') or '',
        'numero_acordao': get('numero_acordao') or '',
        'numero_acordao_num': str(get('numero_acordao_num') or ''),
        'ano_acordao': str(get('ano_acordao') or ''),
        'colegiado': get('colegiado') or '',
        'data_sessao': get('data_sessao') or '',
        'relator': get('relator') or '',
        'processo': get('processo') or '',
        'assunto': get('assunto') or '',
        'sumario': get('sumario') or '',
        'ementa_match': get('ementa_match') or get('texto_match') or '',
        'decisao': get('decisao') or '',
        'url_oficial': get('url_oficial') or '',
        'status': (get('status') or get('situacao') or '').strip().lower(),
        'tags': get('tags') or '',
    }
    if not data['decisao'] and 'acordao_texto' in schema.get('columns', set()):
        data['decisao'] = (get('acordao_texto') or '')[:1400]
    if not data['ementa_match']:
        data['ementa_match'] = ' '.join(x for x in [data['assunto'], data['sumario'], data['decisao']] if x).strip()
    if data['status'] in {'oficializado', 'ativo'}:
        data['status'] = 'ativo'
    elif data['status'] == 'sigiloso':
        data['status'] = 'sigiloso'
    else:
        data['status'] = data['status'] or 'ativo'
    return data


def _count_records(conn: sqlite3.Connection, table: str, columns: set[str]) -> int:
    if 'status' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE COALESCE(status,'ativo') != 'inativo'").fetchone()
    elif 'situacao' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE COALESCE(situacao,'OFICIALIZADO') IN ('OFICIALIZADO','SIGILOSO')").fetchone()
    else:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
    return int(row['n'] or 0)


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    total_registros = 0
    anos = set()
    for db in find_db_files(base_dir):
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                if schema.get('metadata'):
                    row = conn.execute('SELECT ano, total_registros FROM metadata LIMIT 1').fetchone()
                    if row:
                        total_registros += int(row['total_registros'] or 0)
                        if row['ano']:
                            anos.add(str(row['ano']))
                        continue
                total_registros += _count_records(conn, table, schema.get('columns', set()))
                if 'ano_acordao' in schema.get('columns', set()):
                    rows = conn.execute(f"SELECT DISTINCT ano_acordao FROM {table} WHERE ano_acordao IS NOT NULL AND ano_acordao != '' LIMIT 5").fetchall()
                    for r in rows:
                        anos.add(str(r['ano_acordao']))
            finally:
                conn.close()
        except Exception:
            continue
    return {'total_registros': total_registros, 'anos': sorted(anos)}


def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None) -> Dict[str, Any] | None:
    numero = str(numero or '').strip()
    ano = str(ano or '').strip() or None
    if not numero:
        return None
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        cols = schema.get('columns', set())
        if not table or 'numero_acordao_num' not in cols:
            continue
        sql = f"SELECT * FROM {table} WHERE numero_acordao_num = ?"
        params: list[Any] = [numero]
        if ano and 'ano_acordao' in cols:
            sql += ' AND ano_acordao = ?'
            params.append(ano)
        sql += ' LIMIT 1'
        try:
            conn = open_db(db)
            try:
                row = conn.execute(sql, params).fetchone()
                if row:
                    return row_to_normalized_dict(row, schema)
            finally:
                conn.close()
        except Exception:
            continue
    return None
