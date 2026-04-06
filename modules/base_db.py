from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = '*.db'
TABLES = ('acordaos', 'records', 'jurisprudencia', 'sumula')
FTS_TABLES = ('acordaos_fts', 'records_fts', 'jurisprudencia_fts', 'sumula_fts')


def find_db_files(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted([p for p in base_dir.glob(DB_GLOB) if p.is_file()])


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=256)
def detect_schema(db_path_str: str) -> Dict[str, Any]:
    db_path = Path(db_path_str)
    schema: Dict[str, Any] = {'table': None, 'columns': set(), 'fts_table': None, 'kind': 'desconhecido'}
    try:
        conn = open_db(db_path)
        try:
            tables = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for cand in TABLES:
                if cand in tables:
                    schema['table'] = cand
                    break
            if schema['table']:
                schema['columns'] = {r['name'] for r in conn.execute(f"PRAGMA table_info({schema['table']})").fetchall()}
                if schema['table'] in {'acordaos', 'records'}:
                    schema['kind'] = 'acordao'
                elif schema['table'] == 'jurisprudencia':
                    schema['kind'] = 'jurisprudencia'
                elif schema['table'] == 'sumula':
                    schema['kind'] = 'sumula'
            for cand in FTS_TABLES:
                if cand in tables:
                    schema['fts_table'] = cand
                    break
        finally:
            conn.close()
    except Exception:
        pass
    return schema


def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    kind = schema.get('kind', 'desconhecido')
    if kind == 'acordao':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '',
            'tipo': 'Acórdão',
            'numero': str(raw.get('numero_acordao_num') or raw.get('numero_acordao') or ''),
            'numero_num': str(raw.get('numero_acordao_num') or raw.get('numero_acordao') or ''),
            'ano': str(raw.get('ano_acordao') or ''),
            'colegiado': raw.get('colegiado') or '',
            'tema': raw.get('assunto') or raw.get('tema') or '',
            'subtema': raw.get('subtema') or '',
            'resumo': raw.get('sumario') or raw.get('ementa_match') or raw.get('texto_match') or '',
            'excerto': raw.get('decisao') or raw.get('acordao_texto') or raw.get('sumario') or '',
            'tags': raw.get('tags') or '',
            'fonte_db': raw.get('_source_db') or '',
        }
    elif kind == 'jurisprudencia':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '',
            'tipo': 'Jurisprudência',
            'numero': str(raw.get('numacordao') or ''),
            'numero_num': str(raw.get('numacordao') or ''),
            'ano': str(raw.get('anoacordao') or ''),
            'colegiado': raw.get('colegiado') or '',
            'tema': raw.get('tema') or raw.get('area') or '',
            'subtema': raw.get('subtema') or '',
            'resumo': raw.get('enunciado') or '',
            'excerto': raw.get('excerto') or raw.get('paragrafolc') or raw.get('indexadoresconsolidados') or '',
            'tags': ' '.join(filter(None, [raw.get('indexacao') or '', raw.get('referencialegal') or ''])).strip(),
            'fonte_db': raw.get('_source_db') or '',
        }
    elif kind == 'sumula':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '',
            'tipo': 'Súmula',
            'numero': str(raw.get('numero') or ''),
            'numero_num': str(raw.get('numero') or ''),
            'ano': str(raw.get('anoaprovacao') or ''),
            'colegiado': raw.get('colegiado') or '',
            'tema': raw.get('tema') or raw.get('area') or '',
            'subtema': raw.get('subtema') or '',
            'resumo': raw.get('enunciado') or '',
            'excerto': raw.get('excerto') or raw.get('enunciado') or '',
            'tags': ' '.join(filter(None, [raw.get('indexacao') or '', raw.get('referencialegal') or ''])).strip(),
            'fonte_db': raw.get('_source_db') or '',
        }
    else:
        data = {
            'id': raw.get('id') or raw.get('rowid') or '',
            'tipo': 'Precedente', 'numero': '', 'numero_num': '', 'ano': '', 'colegiado': '',
            'tema': '', 'subtema': '', 'resumo': '', 'excerto': '', 'tags': '', 'fonte_db': raw.get('_source_db') or ''
        }
    return data


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    summary = {'acordao': 0, 'jurisprudencia': 0, 'sumula': 0, 'total_bases': 0, 'bases_validas': []}
    for db in find_db_files(base_dir):
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                row = conn.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()
                kind = schema.get('kind', 'acordao')
                summary[kind] += int(row['n'] or 0)
                summary['total_bases'] += 1
                summary['bases_validas'].append(db.name)
            finally:
                conn.close()
        except Exception:
            continue
    summary['total_registros'] = summary['acordao'] + summary['jurisprudencia'] + summary['sumula']
    return summary


def exact_lookup(db_files: Iterable[Path], ref_type: str, numero: str, ano: str | None = None) -> Dict[str, Any] | None:
    numero = str(numero or '').strip()
    ano = str(ano or '').strip() or None
    if not numero:
        return None
    wanted = {'acordao': 'acordao', 'jurisprudencia': 'jurisprudencia', 'sumula': 'sumula'}.get(ref_type, ref_type)
    for db in db_files:
        schema = detect_schema(str(db))
        if schema.get('kind') != wanted:
            continue
        table = schema.get('table')
        cols = schema.get('columns', set())
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                if wanted == 'sumula' and 'numero' in cols:
                    row = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero AS TEXT)=? LIMIT 1', (numero,)).fetchone()
                elif wanted == 'jurisprudencia' and 'numacordao' in cols:
                    if ano and 'anoacordao' in cols:
                        row = conn.execute(f'SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=? AND CAST(anoacordao AS TEXT)=? LIMIT 1', (numero, ano)).fetchone()
                    else:
                        row = conn.execute(f'SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=? LIMIT 1', (numero,)).fetchone()
                elif wanted == 'acordao' and 'numero_acordao_num' in cols:
                    if ano and 'ano_acordao' in cols:
                        row = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=? AND CAST(ano_acordao AS TEXT)=? LIMIT 1', (numero, ano)).fetchone()
                    else:
                        row = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=? LIMIT 1', (numero,)).fetchone()
                else:
                    row = None
                if row:
                    item = row_to_normalized_dict(row, schema)
                    item['_source_db'] = db.name
                    return item
            finally:
                conn.close()
        except Exception:
            continue
    return None
