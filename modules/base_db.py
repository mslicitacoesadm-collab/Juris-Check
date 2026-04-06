from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

DB_GLOB = '*.db'
HTML_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')


def find_db_files(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    files = [p for p in base_dir.glob(DB_GLOB) if p.is_file()]
    return sorted(files)



def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn



def _clean_text(value: Any) -> str:
    text = str(value or '')
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = HTML_RE.sub(' ', text)
    return WS_RE.sub(' ', text).strip()


@lru_cache(maxsize=256)
def detect_schema(db_path_str: str) -> Dict[str, Any]:
    db_path = Path(db_path_str)
    schema: Dict[str, Any] = {
        'table': None,
        'columns': set(),
        'fts_table': None,
        'metadata': False,
        'source_type': 'desconhecido',
    }
    try:
        conn = open_db(db_path)
        try:
            tables = {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for candidate, source_type in (
                ('records', 'acordao'),
                ('acordaos', 'acordao'),
                ('jurisprudencia', 'jurisprudencia'),
                ('sumula', 'sumula'),
            ):
                if candidate in tables:
                    schema['table'] = candidate
                    schema['source_type'] = source_type
                    break
            if schema['table']:
                cols = conn.execute(f"PRAGMA table_info({schema['table']})").fetchall()
                schema['columns'] = {c['name'] for c in cols}
            for candidate in ('records_fts', 'acordaos_fts', 'jurisprudencia_fts', 'sumula_fts'):
                if candidate in tables:
                    schema['fts_table'] = candidate
                    break
            schema['metadata'] = 'metadata' in tables
        finally:
            conn.close()
    except Exception:
        pass
    return schema



def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    get = raw.get
    source_type = schema.get('source_type', 'acordao')

    if source_type == 'jurisprudencia':
        numero = str(get('numacordao') or '').strip()
        ano = str(get('anoacordao') or '').strip()
        tema = ' · '.join(x for x in [_clean_text(get('area')), _clean_text(get('tema')), _clean_text(get('subtema'))] if x)
        enunciado = _clean_text(get('enunciado'))
        excerto = _clean_text(get('excerto'))
        return {
            'id': get('key') or get('id') or '',
            'tipo': 'JURISPRUDÊNCIA',
            'tipo_precedente': 'jurisprudencia',
            'titulo': tema or f'Jurisprudência {numero}/{ano}',
            'numero_acordao': f'{numero}/{ano}' if numero and ano else numero,
            'numero_acordao_num': numero,
            'ano_acordao': ano,
            'numero_sumula': str(get('numsumula') or '').strip(),
            'colegiado': _clean_text(get('colegiado')),
            'data_sessao': _clean_text(get('datasessaoformatada')),
            'relator': _clean_text(get('autortese')),
            'processo': '',
            'assunto': tema,
            'sumario': enunciado,
            'ementa_match': excerto or enunciado,
            'decisao': excerto,
            'url_oficial': '',
            'status': 'ativo',
            'tags': _clean_text(get('indexadoresconsolidados') or get('indexacao')),
            'tema': _clean_text(get('tema')),
            'subtema': _clean_text(get('subtema')),
            'area': _clean_text(get('area')),
            'texto_base': ' '.join(x for x in [tema, enunciado, excerto, _clean_text(get('paragrafolc')), _clean_text(get('referencialegal')), _clean_text(get('indexadoresconsolidados'))] if x),
        }

    if source_type == 'sumula':
        numero = str(get('numero') or '').strip()
        tema = ' · '.join(x for x in [_clean_text(get('area')), _clean_text(get('tema')), _clean_text(get('subtema'))] if x)
        enunciado = _clean_text(get('enunciado'))
        excerto = _clean_text(get('excerto'))
        vigente = str(get('vigente') or '').strip().lower()
        status = 'ativo' if vigente in {'true', '1', 'sim', 'ativo', ''} else 'inativo'
        return {
            'id': get('key') or get('id') or '',
            'tipo': 'SÚMULA',
            'tipo_precedente': 'sumula',
            'titulo': tema or f'Súmula TCU {numero}',
            'numero_acordao': f'Súmula {numero}',
            'numero_acordao_num': numero,
            'ano_acordao': str(get('anoaprovacao') or '').strip(),
            'numero_sumula': numero,
            'colegiado': _clean_text(get('colegiado')),
            'data_sessao': _clean_text(get('datasessaoformatada')),
            'relator': _clean_text(get('autortese')),
            'processo': '',
            'assunto': tema,
            'sumario': enunciado,
            'ementa_match': excerto or enunciado,
            'decisao': excerto,
            'url_oficial': '',
            'status': status,
            'tags': _clean_text(get('indexadoresconsolidados') or get('indexacao')),
            'tema': _clean_text(get('tema')),
            'subtema': _clean_text(get('subtema')),
            'area': _clean_text(get('area')),
            'texto_base': ' '.join(x for x in [tema, enunciado, excerto, _clean_text(get('referencialegal')), _clean_text(get('indexadoresconsolidados'))] if x),
        }

    data = {
        'id': get('id') or get('rowid') or '',
        'tipo': _clean_text(get('tipo') or 'ACÓRDÃO'),
        'tipo_precedente': 'acordao',
        'titulo': _clean_text(get('titulo')),
        'numero_acordao': _clean_text(get('numero_acordao')),
        'numero_acordao_num': str(get('numero_acordao_num') or ''),
        'ano_acordao': str(get('ano_acordao') or ''),
        'numero_sumula': '',
        'colegiado': _clean_text(get('colegiado')),
        'data_sessao': _clean_text(get('data_sessao')),
        'relator': _clean_text(get('relator')),
        'processo': _clean_text(get('processo')),
        'assunto': _clean_text(get('assunto')),
        'sumario': _clean_text(get('sumario')),
        'ementa_match': _clean_text(get('ementa_match') or get('texto_match')),
        'decisao': _clean_text(get('decisao')),
        'url_oficial': _clean_text(get('url_oficial')),
        'status': _clean_text(get('status') or get('situacao')).lower(),
        'tags': _clean_text(get('tags') or get('tags_json')),
    }
    if not data['decisao'] and 'acordao_texto' in schema.get('columns', set()):
        data['decisao'] = _clean_text(get('acordao_texto'))[:1600]
    if not data['ementa_match']:
        data['ementa_match'] = ' '.join(x for x in [data['assunto'], data['sumario'], data['decisao']] if x).strip()
    if data['status'] in {'oficializado', 'ativo'}:
        data['status'] = 'ativo'
    elif data['status'] == 'sigiloso':
        data['status'] = 'sigiloso'
    else:
        data['status'] = data['status'] or 'ativo'
    data['texto_base'] = ' '.join(x for x in [data['assunto'], data['sumario'], data['ementa_match'], data['decisao'], data['tags']] if x)
    return data



def _count_records(conn: sqlite3.Connection, table: str, columns: set[str]) -> int:
    if 'status' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE COALESCE(status,'ativo') != 'inativo'").fetchone()
    elif 'situacao' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE COALESCE(situacao,'OFICIALIZADO') IN ('OFICIALIZADO','SIGILOSO')").fetchone()
    elif 'vigente' in columns:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table} WHERE LOWER(COALESCE(vigente,'true')) IN ('true','1','sim','ativo')").fetchone()
    else:
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
    return int(row['n'] or 0)



def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    total_registros = 0
    total_bases = 0
    bases_validas = []
    por_tipo = {'acordao': 0, 'jurisprudencia': 0, 'sumula': 0}
    for db in find_db_files(base_dir):
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                total_bases += 1
                qtd = _count_records(conn, table, schema.get('columns', set()))
                total_registros += qtd
                por_tipo[schema.get('source_type', 'acordao')] = por_tipo.get(schema.get('source_type', 'acordao'), 0) + qtd
                bases_validas.append({'arquivo': db.name, 'tipo': schema.get('source_type', 'desconhecido'), 'registros': qtd})
            finally:
                conn.close()
        except Exception:
            continue
    return {'total_registros': total_registros, 'total_bases': total_bases, 'bases_validas': bases_validas, 'por_tipo': por_tipo}



def exact_lookup(db_files: Iterable[Path], numero: str, ano: str | None = None, precedent_type: str | None = None) -> Dict[str, Any] | None:
    numero = str(numero or '').strip()
    ano = str(ano or '').strip() or None
    if not numero:
        return None
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        cols = schema.get('columns', set())
        source_type = schema.get('source_type')
        if not table:
            continue
        if precedent_type and source_type != precedent_type:
            continue
        try:
            conn = open_db(db)
            try:
                row = None
                if source_type == 'sumula' and 'numero' in cols:
                    row = conn.execute(f"SELECT * FROM {table} WHERE numero = ? LIMIT 1", [numero]).fetchone()
                elif source_type == 'jurisprudencia' and 'numacordao' in cols:
                    sql = f"SELECT * FROM {table} WHERE numacordao = ?"
                    params: list[Any] = [numero]
                    if ano and 'anoacordao' in cols:
                        sql += ' AND anoacordao = ?'
                        params.append(ano)
                    sql += ' LIMIT 1'
                    row = conn.execute(sql, params).fetchone()
                elif source_type == 'acordao' and 'numero_acordao_num' in cols:
                    sql = f"SELECT * FROM {table} WHERE numero_acordao_num = ?"
                    params = [numero]
                    if ano and 'ano_acordao' in cols:
                        sql += ' AND ano_acordao = ?'
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
