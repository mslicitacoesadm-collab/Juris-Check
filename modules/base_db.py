from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

from modules.citation_extractor import normalize_colegiado, normalize_num, normalize_simple

DB_GLOB = '*.db'
TABLES = ('precedentes_inteligentes', 'acordaos', 'records', 'jurisprudencia', 'sumula')
FTS_TABLES = ('precedentes_fts', 'acordaos_fts', 'records_fts', 'jurisprudencia_fts', 'sumula_fts')


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
    schema: Dict[str, Any] = {'table': None, 'columns': set(), 'fts_table': None, 'kind': 'desconhecido', 'is_intelligent': False}
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
                if schema['table'] == 'precedentes_inteligentes':
                    schema['kind'] = 'inteligente'; schema['is_intelligent'] = True
                elif schema['table'] in {'acordaos', 'records'}:
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


def _json_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    txt = str(value).strip()
    if not txt:
        return []
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in txt.split(',') if x.strip()]


def row_to_normalized_dict(row: sqlite3.Row | Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(row)
    kind = schema.get('kind', 'desconhecido')
    if kind == 'inteligente':
        tipo = str(raw.get('tipo') or '').lower().strip()
        label = {'acordao': 'Acórdão', 'jurisprudencia': 'Jurisprudência', 'sumula': 'Súmula'}.get(tipo, 'Precedente')
        data = {
            'id': raw.get('id') or '', 'id_unico': raw.get('id_unico') or '', 'tipo': label, 'tipo_base': tipo,
            'numero': str(raw.get('numero') or ''), 'numero_num': str(raw.get('numero') or ''), 'ano': str(raw.get('ano') or ''),
            'tribunal': raw.get('tribunal') or 'TCM/BA', 'colegiado': raw.get('colegiado') or '', 'tema': raw.get('tema_principal') or '',
            'subtema': ', '.join(_json_list(raw.get('subtemas_json'))), 'resumo': raw.get('ementa_resumida') or raw.get('resumo_uso_pratico') or '',
            'excerto': raw.get('trecho_chave') or raw.get('texto_base') or '',
            'tags': ' '.join(_json_list(raw.get('palavras_chave_json')) + _json_list(raw.get('fundamentos_legais_json')) + _json_list(raw.get('contexto_licitatorio_json'))).strip(),
            'fonte_db': raw.get('origem_db') or raw.get('_source_db') or '', 'tese_central': raw.get('tese_central') or '', 'ementa_resumida': raw.get('ementa_resumida') or '',
            'trecho_chave': raw.get('trecho_chave') or '', 'fundamentos_legais': _json_list(raw.get('fundamentos_legais_json')), 'palavras_chave': _json_list(raw.get('palavras_chave_json')),
            'lado_favorecido': _json_list(raw.get('lado_favorecido_json')), 'tipo_de_uso': _json_list(raw.get('tipo_de_uso_json')), 'aplicavel_em': _json_list(raw.get('aplicavel_em_json')),
            'contexto_licitatorio': _json_list(raw.get('contexto_licitatorio_json')), 'grau_utilidade': float(raw.get('grau_utilidade') or 0.0), 'score_confianca_interno': float(raw.get('score_confianca_interno') or 0.0),
            'resumo_uso_pratico': raw.get('resumo_uso_pratico') or '', 'texto_base': raw.get('texto_base') or '', 'texto_indexavel': raw.get('texto_indexavel') or '', 'origem_tabela': raw.get('origem_tabela') or '', 'base_inteligente': True,
        }
    elif kind == 'acordao':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '', 'tipo': 'Acórdão', 'tipo_base': 'acordao', 'numero': str(raw.get('numero_acordao_num') or raw.get('numero_acordao') or ''), 'numero_num': str(raw.get('numero_acordao_num') or raw.get('numero_acordao') or ''),
            'ano': str(raw.get('ano_acordao') or ''), 'colegiado': raw.get('colegiado') or '', 'tribunal': 'TCU', 'tema': raw.get('assunto') or raw.get('tema') or '', 'subtema': raw.get('subtema') or '',
            'resumo': raw.get('sumario') or raw.get('ementa_match') or raw.get('texto_match') or '', 'excerto': raw.get('decisao') or raw.get('acordao_texto') or raw.get('sumario') or '', 'tags': raw.get('tags') or raw.get('tags_json') or '',
            'fonte_db': raw.get('_source_db') or '', 'tese_central': '', 'ementa_resumida': '', 'trecho_chave': '', 'fundamentos_legais': [], 'palavras_chave': [], 'lado_favorecido': [], 'tipo_de_uso': [], 'aplicavel_em': [], 'contexto_licitatorio': [], 'grau_utilidade': 0.0,
            'score_confianca_interno': 0.0, 'resumo_uso_pratico': '', 'texto_base': '', 'texto_indexavel': '', 'origem_tabela': schema.get('table') or '', 'base_inteligente': False,
        }
    elif kind == 'jurisprudencia':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '', 'tipo': 'Jurisprudência', 'tipo_base': 'jurisprudencia', 'numero': str(raw.get('numacordao') or ''), 'numero_num': str(raw.get('numacordao') or ''), 'ano': str(raw.get('anoacordao') or ''),
            'colegiado': raw.get('colegiado') or '', 'tribunal': 'TCU', 'tema': raw.get('tema') or raw.get('area') or '', 'subtema': raw.get('subtema') or '', 'resumo': raw.get('enunciado') or '', 'excerto': raw.get('excerto') or raw.get('paragrafolc') or raw.get('indexadoresconsolidados') or '',
            'tags': ' '.join(filter(None, [raw.get('indexacao') or '', raw.get('referencialegal') or ''])).strip(), 'fonte_db': raw.get('_source_db') or '', 'tese_central': '', 'ementa_resumida': '', 'trecho_chave': '', 'fundamentos_legais': [], 'palavras_chave': [], 'lado_favorecido': [], 'tipo_de_uso': [], 'aplicavel_em': [], 'contexto_licitatorio': [], 'grau_utilidade': 0.0, 'score_confianca_interno': 0.0, 'resumo_uso_pratico': '', 'texto_base': '', 'texto_indexavel': '', 'origem_tabela': schema.get('table') or '', 'base_inteligente': False,
        }
    elif kind == 'sumula':
        data = {
            'id': raw.get('id') or raw.get('rowid') or '', 'tipo': 'Súmula', 'tipo_base': 'sumula', 'numero': str(raw.get('numero') or ''), 'numero_num': str(raw.get('numero') or ''), 'ano': str(raw.get('anoaprovacao') or ''), 'colegiado': raw.get('colegiado') or '', 'tribunal': 'TCU', 'tema': raw.get('tema') or raw.get('area') or '', 'subtema': raw.get('subtema') or '', 'resumo': raw.get('enunciado') or '', 'excerto': raw.get('excerto') or raw.get('enunciado') or '', 'tags': ' '.join(filter(None, [raw.get('indexacao') or '', raw.get('referencialegal') or ''])).strip(), 'fonte_db': raw.get('_source_db') or '', 'tese_central': '', 'ementa_resumida': '', 'trecho_chave': '', 'fundamentos_legais': [], 'palavras_chave': [], 'lado_favorecido': [], 'tipo_de_uso': [], 'aplicavel_em': [], 'contexto_licitatorio': [], 'grau_utilidade': 0.0, 'score_confianca_interno': 0.0, 'resumo_uso_pratico': '', 'texto_base': '', 'texto_indexavel': '', 'origem_tabela': schema.get('table') or '', 'base_inteligente': False,
        }
    else:
        data = {'id': raw.get('id') or raw.get('rowid') or '', 'tipo': 'Precedente', 'tipo_base': 'desconhecido', 'numero': '', 'numero_num': '', 'ano': '', 'colegiado': '', 'tribunal': 'TCU', 'tema': '', 'subtema': '', 'resumo': '', 'excerto': '', 'tags': '', 'fonte_db': raw.get('_source_db') or '', 'tese_central': '', 'ementa_resumida': '', 'trecho_chave': '', 'fundamentos_legais': [], 'palavras_chave': [], 'lado_favorecido': [], 'tipo_de_uso': [], 'aplicavel_em': [], 'contexto_licitatorio': [], 'grau_utilidade': 0.0, 'score_confianca_interno': 0.0, 'resumo_uso_pratico': '', 'texto_base': '', 'texto_indexavel': '', 'origem_tabela': schema.get('table') or ''}
    data['numero_norm'] = normalize_num(str(data.get('numero') or ''))
    data['ano_norm'] = normalize_num(str(data.get('ano') or ''))
    data['colegiado_norm'] = normalize_colegiado(str(data.get('colegiado') or ''))
    data['reference_key'] = f"{data['tipo_base']}:{data['numero_norm']}:{data['ano_norm']}:{data['colegiado_norm']}"
    return data


def summarize_bases(base_dir: Path) -> Dict[str, Any]:
    summary = {'acordao': 0, 'jurisprudencia': 0, 'sumula': 0, 'inteligente': 0, 'total_bases': 0, 'bases_validas': [], 'base_inteligente_detectada': False, 'arquivo_base_inteligente': None}
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
                if schema.get('is_intelligent'):
                    summary['base_inteligente_detectada'] = True
                    summary['arquivo_base_inteligente'] = db.name
            finally:
                conn.close()
        except Exception:
            continue
    summary['total_registros'] = summary['inteligente'] if summary['base_inteligente_detectada'] else summary['acordao'] + summary['jurisprudencia'] + summary['sumula']
    return summary


def _exact_lookup_intelligent(conn, numero: str, ano: str | None, kind: str):
    sql = 'SELECT * FROM precedentes_inteligentes WHERE tipo=? AND CAST(numero AS TEXT)=?'
    params = [kind, numero]
    if ano:
        sql += ' AND CAST(ano AS TEXT)=?'
        params.append(ano)
    sql += ' ORDER BY score_confianca_interno DESC, grau_utilidade DESC LIMIT 10'
    return conn.execute(sql, params).fetchall()


def exact_lookup(db_files: Iterable[Path], ref_type: str, numero: str, ano: str | None = None, colegiado: str | None = None) -> Dict[str, Any] | None:
    result = layered_reference_lookup(db_files, ref_type, numero, ano, colegiado, limit=1)
    return result['matches'][0] if result['matches'] else None


def layered_reference_lookup(db_files: Iterable[Path], ref_type: str, numero: str, ano: str | None = None, colegiado: str | None = None, limit: int = 5) -> Dict[str, Any]:
    numero = normalize_num(str(numero or ''))
    ano = normalize_num(str(ano or '')) or None
    colegiado_norm = normalize_colegiado(colegiado or '')
    wanted = {'acordao': 'acordao', 'jurisprudencia': 'jurisprudencia', 'sumula': 'sumula'}.get(ref_type, ref_type)
    if not numero:
        return {'layer': 'sem_numero', 'matches': []}
    found = []
    seen = set()

    def add_item(item, layer, score):
        key = item.get('reference_key')
        if key in seen:
            return
        seen.add(key)
        item['lookup_layer'] = layer
        item['lookup_score'] = score
        found.append(item)

    # Camada 1: exata com ano
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                rows = []
                if schema.get('is_intelligent'):
                    rows = _exact_lookup_intelligent(conn, numero, ano, wanted)
                elif schema.get('kind') == wanted:
                    cols = schema.get('columns', set())
                    if wanted == 'sumula' and 'numero' in cols:
                        rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero AS TEXT)=? LIMIT 10', (numero,)).fetchall()
                    elif wanted == 'jurisprudencia' and 'numacordao' in cols:
                        if ano and 'anoacordao' in cols:
                            rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=? AND CAST(anoacordao AS TEXT)=? LIMIT 10', (numero, ano)).fetchall()
                        else:
                            rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=? LIMIT 10', (numero,)).fetchall()
                    elif wanted == 'acordao' and 'numero_acordao_num' in cols:
                        if ano and 'ano_acordao' in cols:
                            rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=? AND CAST(ano_acordao AS TEXT)=? LIMIT 10', (numero, ano)).fetchall()
                        else:
                            rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=? LIMIT 10', (numero,)).fetchall()
                for row in rows:
                    item = row_to_normalized_dict(row, schema)
                    item['_source_db'] = db.name
                    if ano and item.get('ano_norm') != ano:
                        continue
                    if colegiado_norm and item.get('colegiado_norm') and item.get('colegiado_norm') != colegiado_norm:
                        continue
                    add_item(item, 'exata', 1.0)
            finally:
                conn.close()
        except Exception:
            continue
    if found:
        return {'layer': 'exata', 'matches': found[:limit]}

    # Camada 2: número exato, ano relaxado
    for db in db_files:
        schema = detect_schema(str(db))
        if schema.get('kind') not in {wanted, 'inteligente'}:
            continue
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                cols = schema.get('columns', set())
                if schema.get('is_intelligent'):
                    rows = _exact_lookup_intelligent(conn, numero, None, wanted)
                elif wanted == 'sumula' and 'numero' in cols:
                    rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero AS TEXT)=? LIMIT 15', (numero,)).fetchall()
                elif wanted == 'jurisprudencia' and 'numacordao' in cols:
                    rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numacordao AS TEXT)=? LIMIT 15', (numero,)).fetchall()
                elif wanted == 'acordao' and 'numero_acordao_num' in cols:
                    rows = conn.execute(f'SELECT * FROM {table} WHERE CAST(numero_acordao_num AS TEXT)=? LIMIT 15', (numero,)).fetchall()
                else:
                    rows = []
                for row in rows:
                    item = row_to_normalized_dict(row, schema); item['_source_db']=db.name
                    score = 0.9 if ano and item.get('ano_norm') == ano else 0.78
                    if colegiado_norm and item.get('colegiado_norm') == colegiado_norm:
                        score += 0.08
                    add_item(item, 'numero_exato', score)
            finally:
                conn.close()
        except Exception:
            continue
    if found:
        found.sort(key=lambda x: (x.get('lookup_score', 0), x.get('ano_norm') == (ano or ''), x.get('colegiado_norm') == colegiado_norm), reverse=True)
        return {'layer': 'numero_exato', 'matches': found[:limit]}
    return {'layer': 'nao_encontrado', 'matches': []}
