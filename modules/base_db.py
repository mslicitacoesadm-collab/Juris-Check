from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = '*.db'

TABLE_PRIORITY = ('acordaos', 'records', 'jurisprudencia', 'sumula')
TYPE_LABELS = {
    'acordaos': 'acordao',
    'records': 'acordao',
    'jurisprudencia': 'jurisprudencia',
    'sumula': 'sumula',
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
    schema: Dict[str, Any] = {'table': None, 'columns': set(), 'fts_table': None, 'metadata': False, 'record_type': None}
    try:
        conn = open_db(db_path)
        try:
            tables = {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for candidate in TABLE_PRIORITY:
                if candidate in tables:
                    schema['table'] = candidate
                    schema['record_type'] = TYPE_LABELS[candidate]
                    break
            if schema['table']:
                cols = conn.execute(f"PRAGMA table_info({schema['table']})").fetchall()
                schema['columns'] = {c['name'] for c in cols}
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



def _strip_html(text: Any) -> str:
    val = str(text or '')
    val = re.sub(r'<[^>]+>', ' ', val)
    return re.sub(r'\s+', ' ', val).strip()



def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    record_type = schema.get('record_type') or 'acordao'
    get = raw.get

    if record_type == 'sumula':
        numero = str(get('numero') or '')
        ano = str(get('anoaprovacao') or '')
        titulo = f"Súmula TCU {numero}".strip()
        texto_principal = _strip_html(get('enunciado') or '')
        excerto = _strip_html(get('excerto') or '')
        assunto = ' · '.join(x for x in [get('area'), get('tema'), get('subtema')] if x)
        tags = ' '.join(x for x in [get('indexacao'), get('indexadoresconsolidados'), get('tema'), get('subtema')] if x)
        return {
            'id': get('id') or '',
            'tipo': 'sumula',
            'titulo': titulo,
            'numero_identificador': numero,
            'numero_acordao': '',
            'numero_acordao_num': '',
            'ano_acordao': '',
            'numero_sumula': numero,
            'ano_sumula': ano,
            'colegiado': get('colegiado') or '',
            'data_sessao': get('datasessaoformatada') or '',
            'relator': get('autortese') or '',
            'processo': get('tipoprocesso') or '',
            'assunto': assunto,
            'sumario': texto_principal,
            'ementa_match': ' '.join(x for x in [texto_principal, excerto, assunto, tags] if x).strip(),
            'decisao': excerto,
            'url_oficial': '',
            'status': 'ativo' if str(get('vigente') or 'true').lower() != 'false' else 'inativo',
            'tags': _strip_html(tags),
            'origem_aprovacao': f"Acórdão {get('numaprovacao') or ''}/{get('anoaprovacao') or ''}".strip(),
            'area': get('area') or '',
            'tema': get('tema') or '',
            'subtema': get('subtema') or '',
        }

    if record_type == 'jurisprudencia':
        numero = str(get('numacordao') or '')
        ano = str(get('anoacordao') or '')
        titulo = f"Jurisprudência selecionada {numero}/{ano}".strip()
        enunciado = _strip_html(get('enunciado') or '')
        excerto = _strip_html(get('excerto') or '')
        assunto = ' · '.join(x for x in [get('area'), get('tema'), get('subtema')] if x)
        tags = ' '.join(x for x in [get('indexacao'), get('indexadoresconsolidados'), get('tema'), get('subtema')] if x)
        return {
            'id': get('id') or '',
            'tipo': 'jurisprudencia',
            'titulo': titulo,
            'numero_identificador': f"{numero}/{ano}" if numero and ano else numero,
            'numero_acordao': numero,
            'numero_acordao_num': numero,
            'ano_acordao': ano,
            'numero_sumula': str(get('numsumula') or ''),
            'ano_sumula': '',
            'colegiado': get('colegiado') or '',
            'data_sessao': get('datasessaoformatada') or '',
            'relator': get('autortese') or '',
            'processo': get('tipoprocesso') or '',
            'assunto': assunto,
            'sumario': enunciado,
            'ementa_match': ' '.join(x for x in [enunciado, excerto, assunto, tags] if x).strip(),
            'decisao': excerto,
            'url_oficial': '',
            'status': 'ativo',
            'tags': _strip_html(tags),
            'area': get('area') or '',
            'tema': get('tema') or '',
            'subtema': get('subtema') or '',
        }

    data = {
        'id': get('id') or get('rowid') or '',
        'tipo': 'acordao',
        'titulo': get('titulo') or '',
        'numero_identificador': f"{get('numero_acordao_num') or get('numero_acordao') or ''}/{get('ano_acordao') or ''}".strip('/'),
        'numero_acordao': get('numero_acordao') or '',
        'numero_acordao_num': str(get('numero_acordao_num') or ''),
        'ano_acordao': str(get('ano_acordao') or ''),
        'numero_sumula': '',
        'ano_sumula': '',
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
        'area': '',
        'tema': '',
        'subtema': '',
    }
    if not data['decisao'] and 'acordao_texto' in schema.get('columns', set()):
        data['decisao'] = (get('acordao_texto') or '')[:2000]
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
    elif 'vigente' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE COALESCE(vigente,'true') != 'false'").fetchone()
    else:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
    return int(row['n'] or 0)



def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    total_registros = 0
    total_bases = 0
    por_tipo = {'acordao': 0, 'jurisprudencia': 0, 'sumula': 0}
    bases_validas = []
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
                por_tipo[schema.get('record_type') or 'acordao'] += n
                bases_validas.append({'arquivo': db.name, 'tipo': schema.get('record_type')})
            finally:
                conn.close()
        except Exception:
            continue
    return {'total_registros': total_registros, 'total_bases': total_bases, 'bases_validas': bases_validas, 'por_tipo': por_tipo}



def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None, tipo: str | None = None) -> Dict[str, Any] | None:
    numero = str(numero or '').strip()
    ano = str(ano or '').strip() or None
    if not numero:
        return None
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        cols = schema.get('columns', set())
        record_type = schema.get('record_type')
        if tipo and record_type != tipo:
            continue
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                row = None
                if record_type == 'sumula' and 'numero' in cols:
                    sql = f"SELECT * FROM {table} WHERE CAST(numero AS TEXT)=? LIMIT 1"
                    row = conn.execute(sql, [numero]).fetchone()
                elif 'numero_acordao_num' in cols:
                    sql = f"SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=?"
                    params: list[Any] = [numero]
                    if ano and 'ano_acordao' in cols:
                        sql += ' AND CAST(ano_acordao AS TEXT)=?'
                        params.append(ano)
                    sql += ' LIMIT 1'
                    row = conn.execute(sql, params).fetchone()
                elif record_type == 'jurisprudencia' and 'numacordao' in cols:
                    sql = f"SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=?"
                    params = [numero]
                    if ano and 'anoacordao' in cols:
                        sql += ' AND CAST(anoacordao AS TEXT)=?'
                        params.append(ano)
                    sql += ' LIMIT 1'
                    row = conn.execute(sql, params).fetchone()
                if row:
                    return row_to_normalized_dict(row, schema)
            finally:
                conn.close()
        except Exception:
            continue
    return None
