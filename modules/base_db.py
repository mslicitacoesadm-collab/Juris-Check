from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = '*.db'

TABLE_CONFIG = {
    'acordaos': {
        'tipo': 'ACÓRDÃO',
        'numero_fields': ['numero_acordao', 'numero_acordao_num'],
        'ano_fields': ['ano_acordao'],
        'text_fields': ['assunto', 'sumario', 'ementa_match', 'decisao', 'tags', 'texto_match', 'acordao_texto'],
    },
    'jurisprudencia': {
        'tipo': 'JURISPRUDÊNCIA',
        'numero_fields': ['numacordao'],
        'ano_fields': ['anoacordao'],
        'text_fields': ['area', 'tema', 'subtema', 'enunciado', 'excerto', 'indexacao', 'indexadoresconsolidados', 'paragrafolc', 'referencialegal'],
    },
    'sumula': {
        'tipo': 'SÚMULA',
        'numero_fields': ['numero'],
        'ano_fields': ['anoaprovacao'],
        'text_fields': ['area', 'tema', 'subtema', 'enunciado', 'excerto', 'indexacao', 'indexadoresconsolidados', 'referencialegal'],
    },
    'records': {
        'tipo': 'ACÓRDÃO',
        'numero_fields': ['numero_acordao', 'numero_acordao_num'],
        'ano_fields': ['ano_acordao'],
        'text_fields': ['assunto', 'sumario', 'ementa_match', 'decisao', 'tags', 'texto_match', 'acordao_texto'],
    },
}


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
    schema: Dict[str, Any] = {
        'table': None,
        'columns': set(),
        'fts_table': None,
        'metadata': False,
        'record_type': 'ACÓRDÃO',
    }
    try:
        conn = open_db(db_path)
        try:
            tables = {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for candidate in ('acordaos', 'jurisprudencia', 'sumula', 'records'):
                if candidate in tables:
                    schema['table'] = candidate
                    break
            if schema['table']:
                cols = conn.execute(f"PRAGMA table_info({schema['table']})").fetchall()
                schema['columns'] = {c['name'] for c in cols}
                schema['record_type'] = TABLE_CONFIG.get(schema['table'], {}).get('tipo', 'ACÓRDÃO')
            for candidate in ('records_fts', 'acordaos_fts'):
                if candidate in tables:
                    schema['fts_table'] = candidate
                    break
            schema['metadata'] = 'metadata' in tables
        finally:
            conn.close()
    except Exception:
        pass
    return schema


def _get(raw: Dict[str, Any], *keys: str, default: Any = '') -> Any:
    for key in keys:
        if key in raw and raw.get(key) not in (None, ''):
            return raw.get(key)
    return default


def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    table = schema.get('table')
    record_type = TABLE_CONFIG.get(table, {}).get('tipo', 'ACÓRDÃO')
    numero = str(_get(raw, 'numero_acordao_num', 'numacordao', 'numero', 'numero_acordao', default='')).strip()
    ano = str(_get(raw, 'ano_acordao', 'anoacordao', 'anoaprovacao', default='')).strip()
    colegiado = str(_get(raw, 'colegiado', default='')).strip()
    assunto = str(_get(raw, 'assunto', 'tema', default='')).strip()
    subtema = str(_get(raw, 'subtema', default='')).strip()
    sumario = str(_get(raw, 'sumario', 'enunciado', default='')).strip()
    decisao = str(_get(raw, 'decisao', 'excerto', 'paragrafolc', default='')).strip()
    if not decisao and 'acordao_texto' in schema.get('columns', set()):
        decisao = str(raw.get('acordao_texto') or '')[:1600]
    ementa = str(_get(raw, 'ementa_match', 'texto_match', 'excerto', 'paragrafolc', default='')).strip()
    tags = str(_get(raw, 'tags', 'indexacao', 'indexadoresconsolidados', default='')).strip()
    area = str(_get(raw, 'area', default='')).strip()
    tema = str(_get(raw, 'tema', default='')).strip()
    titulo = str(_get(raw, 'titulo', default='')).strip()
    if not titulo:
        if record_type == 'SÚMULA':
            titulo = f'Súmula TCU {numero}' if numero else 'Súmula TCU'
        elif record_type == 'JURISPRUDÊNCIA':
            titulo = f'Jurisprudência Selecionada {numero}/{ano}'.strip('/')
        else:
            titulo = f'Acórdão {numero}/{ano}'.strip('/')
    if not ementa:
        ementa = ' '.join(x for x in [area, tema, subtema, assunto, sumario, decisao] if x).strip()
    if record_type == 'SÚMULA':
        citacao_curta = f'TCU, Súmula nº {numero}'
    elif record_type == 'JURISPRUDÊNCIA':
        sufixo = f' - {colegiado}' if colegiado else ''
        citacao_curta = f'TCU, Jurisprudência Selecionada vinculada ao Acórdão nº {numero}/{ano}{sufixo}' if numero else titulo
    else:
        sufixo = f' - {colegiado}' if colegiado else ''
        citacao_curta = f'TCU, Acórdão nº {numero}/{ano}{sufixo}' if ano else f'TCU, Acórdão nº {numero}{sufixo}'
    return {
        'id': _get(raw, 'id', 'rowid', default=''),
        'tipo': record_type,
        'titulo': titulo,
        'numero_precedente': numero,
        'ano_precedente': ano,
        'numero_acordao': f'{numero}/{ano}' if numero and ano and record_type != 'SÚMULA' else numero,
        'numero_acordao_num': numero,
        'ano_acordao': ano,
        'colegiado': colegiado,
        'data_sessao': _get(raw, 'data_sessao', 'datasessaoformatada', 'aprovacao', default=''),
        'relator': _get(raw, 'relator', 'autortese', default=''),
        'processo': _get(raw, 'processo', 'tipoprocesso', default=''),
        'assunto': ' · '.join(x for x in [area, tema, subtema, assunto] if x),
        'sumario': sumario,
        'ementa_match': ementa,
        'decisao': decisao,
        'url_oficial': _get(raw, 'url_oficial', default=''),
        'status': (str(_get(raw, 'status', 'situacao', 'vigente', default='ativo')) or 'ativo').strip().lower(),
        'tags': tags,
        'area': area,
        'tema': tema,
        'subtema': subtema,
        'raw_numsumula': str(_get(raw, 'numsumula', default='')).strip(),
        'citacao_base': citacao_curta,
    }


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
    total_bases = 0
    bases_validas = []
    tipos = {'ACÓRDÃO': 0, 'JURISPRUDÊNCIA': 0, 'SÚMULA': 0}
    for db in find_db_files(base_dir):
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                total_bases += 1
                n = _count_records(conn, table, schema.get('columns', set()))
                total_registros += n
                tipos[schema.get('record_type', 'ACÓRDÃO')] = tipos.get(schema.get('record_type', 'ACÓRDÃO'), 0) + n
                bases_validas.append({'arquivo': db.name, 'tipo': schema.get('record_type', 'ACÓRDÃO'), 'registros': n})
            finally:
                conn.close()
        except Exception:
            continue
    return {'total_registros': total_registros, 'total_bases': total_bases, 'bases_validas': bases_validas, 'por_tipo': tipos}


def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None, tipo: str | None = None) -> Dict[str, Any] | None:
    numero = str(numero or '').strip()
    ano = str(ano or '').strip() or None
    tipo = (tipo or '').upper().strip() or None
    if not numero:
        return None
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        cols = schema.get('columns', set())
        record_type = schema.get('record_type', 'ACÓRDÃO')
        if not table or (tipo and tipo != record_type):
            continue
        config = TABLE_CONFIG.get(table, {})
        numero_fields = [f for f in config.get('numero_fields', []) if f in cols]
        ano_fields = [f for f in config.get('ano_fields', []) if f in cols]
        if not numero_fields:
            continue
        num_where = ' OR '.join([f"CAST({field} AS TEXT) = ?" for field in numero_fields])
        params: List[Any] = [numero] * len(numero_fields)
        sql = f"SELECT * FROM {table} WHERE ({num_where})"
        if ano and ano_fields:
            ano_where = ' OR '.join([f"CAST({field} AS TEXT) = ?" for field in ano_fields])
            sql += f" AND ({ano_where})"
            params.extend([ano] * len(ano_fields))
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
