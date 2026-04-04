from __future__ import annotations

import json
import re
import sqlite3
from heapq import nlargest
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .base_db import detect_schema, get_table_columns, normalize_row, open_db

STOPWORDS = {
    'de','da','do','das','dos','e','em','para','por','com','sem','na','no','nas','nos','ao','aos',
    'as','os','o','a','um','uma','que','se','ou','à','às','art','arts','tcu','acordao','acórdão',
    'tribunal','uniao','união','camara','câmara','plenario','plenário','processo','item','itens',
    'subitem','caput','inciso','alinea','alínea','lei','regimento','interno','sessao','sessão',
    'ministro','ministra','relator','relatora','face','autos','presente','ante','razoes','razões',
    'fundamento','fundamentos','termos','peça','peca','peças','pecas'
}
DOMAIN_TERMS = {
    'licitacao','licitação','pregao','pregão','edital','proposta','inexequibilidade','diligencia',
    'diligência','desclassificacao','desclassificação','habilitacao','habilitação','formalismo',
    'planilha','custos','atestado','competitividade','certame','impugnacao','impugnação',
    'recurso','contrarrazao','contrarrazão','saneamento','sobrepreco','sobrepreço','lote','item',
    'fornecedor','empresa','julgamento','amostra','qualificacao','qualificação','dispensa',
    'registro','precos','preços','ata','adjudicacao','adjudicação','homologacao','homologação'
}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.IGNORECASE)


def normalize_text(text: str) -> str:
    return ' '.join((text or '').lower().split())


def tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or '')]
    return [t for t in tokens if t not in STOPWORDS and len(t) >= 3]


def select_query_terms(text: str, limit: int = 6) -> List[str]:
    tokens = tokenize(text)
    freq: Dict[str, int] = {}
    for tok in tokens:
        freq[tok] = freq.get(tok, 0) + 1
    ordered = sorted(freq, key=lambda t: (1 if t in DOMAIN_TERMS else 0, min(len(t), 12), freq[t]), reverse=True)
    return ordered[:limit]


def make_fts_queries(text: str) -> List[str]:
    terms = select_query_terms(text)
    if not terms:
        return []
    strict = [t for t in terms if t in DOMAIN_TERMS][:4]
    broad = terms[:5]
    queries = []
    if len(strict) >= 2:
        queries.append(' AND '.join(f'"{t}"' for t in strict))
    if len(broad) >= 3:
        queries.append(' AND '.join(f'"{t}"' for t in broad[:3]))
    queries.append(' OR '.join(f'"{t}"' for t in broad))
    dedup, seen = [], set()
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            dedup.append(q)
    return dedup


def parse_tags(raw_tags) -> List[str]:
    if not raw_tags:
        return []
    if isinstance(raw_tags, list):
        return [str(x).strip().lower() for x in raw_tags if str(x).strip()]
    txt = str(raw_tags).strip()
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return [str(x).strip().lower() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip().lower() for x in txt.split(',') if x.strip()]


def row_text(row: Dict) -> str:
    pieces = [
        row.get('titulo', ''), row.get('assunto', ''), row.get('sumario', ''),
        row.get('ementa_match', ''), row.get('decisao', ''), row.get('tags', ''), row.get('tags_json', '')
    ]
    return normalize_text(' '.join(str(p) for p in pieces if p))


def overlap_score(query_terms: Sequence[str], candidate_text: str, candidate_tags: Sequence[str]) -> Tuple[float, List[str]]:
    matched = []
    for term in query_terms:
        if term in candidate_text or term in candidate_tags:
            matched.append(term)
    unique = list(dict.fromkeys(matched))
    score = len(unique) / max(len(set(query_terms)), 1)
    bonus = 0.18 * len([t for t in unique if t in DOMAIN_TERMS])
    return min(score + bonus, 1.5), unique


def theme_penalty(query_terms: Sequence[str], matched_terms: Sequence[str]) -> float:
    domain_query = [t for t in query_terms if t in DOMAIN_TERMS]
    return 0.55 if domain_query and not any(t in matched_terms for t in domain_query) else 0.0


def build_suggested_paragraph(item: Dict, matched_terms: Sequence[str]) -> str:
    base = item.get('sumario') or item.get('assunto') or item.get('decisao') or 'o precedente guarda aderência com o núcleo do tema discutido.'
    match_note = f" Pontos de aderência identificados: {', '.join(matched_terms[:4])}." if matched_terms else ''
    return (
        f"Conforme o {item.get('numero_acordao','')} - {item.get('colegiado','')}, de relatoria de {item.get('relator','')}, "
        f"o entendimento do TCU pode reforçar a argumentação da peça, especialmente porque {base.strip()}" + match_note
    )


def _safe_exec(conn, sql: str, params: Sequence, fallback_sql: str | None = None, fallback_params: Sequence | None = None):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        if fallback_sql:
            try:
                return conn.execute(fallback_sql, fallback_params or params).fetchall()
            except sqlite3.OperationalError:
                return []
        return []


def fetch_rows(conn, db_path: Path, schema: str, queries: Sequence[str], limit: int = 20):
    rows = []
    if schema == 'records':
        record_cols = set(get_table_columns(str(db_path), 'records'))
        has_fts_table = bool(get_table_columns(str(db_path), 'records_fts'))
        if has_fts_table:
            for q in queries:
                rows.extend(_safe_exec(
                    conn,
                    '''
                    SELECT r.*, bm25(records_fts) as fts_score
                    FROM records_fts
                    JOIN records r ON r.id = records_fts.id
                    WHERE records_fts MATCH ?
                    ORDER BY fts_score
                    LIMIT ?
                    ''',
                    (q, limit),
                ))
        if not rows:
            text_cols = [c for c in ['titulo', 'assunto', 'sumario', 'ementa_match', 'decisao'] if c in record_cols]
            if not text_cols:
                return rows
            for q in queries:
                like_terms = [t.strip('" ') for t in q.replace(' AND ', ' ').replace(' OR ', ' ').split() if t.strip('" ')]
                if not like_terms:
                    continue
                clauses = []
                params = []
                for term in like_terms[:6]:
                    piece = ' OR '.join([f'{c} LIKE ?' for c in text_cols])
                    clauses.append(f'({piece})')
                    params.extend([f'%{term}%'] * len(text_cols))
                sql = f"SELECT *, 0.0 as fts_score FROM records WHERE {' OR '.join(clauses)} LIMIT ?"
                params.append(limit)
                rows.extend(_safe_exec(conn, sql, params))

    elif schema == 'acordaos':
        acordao_cols = set(get_table_columns(str(db_path), 'acordaos'))
        text_cols = [c for c in ['titulo', 'assunto', 'sumario', 'ementa_match', 'decisao', 'tags_json'] if c in acordao_cols]
        if not text_cols:
            return rows
        for q in queries:
            like_terms = [t.strip('" ') for t in q.replace(' AND ', ' ').replace(' OR ', ' ').split() if t.strip('" ')]
            if not like_terms:
                continue
            clauses = []
            params = []
            for term in like_terms[:6]:
                piece = ' OR '.join([f'{c} LIKE ?' for c in text_cols])
                clauses.append(f'({piece})')
                params.extend([f'%{term}%'] * len(text_cols))
            sql = f"SELECT *, 0.0 as fts_score FROM acordaos WHERE {' OR '.join(clauses)} LIMIT ?"
            params.append(limit)
            rows.extend(_safe_exec(conn, sql, params))
    return rows


def search_candidates(db_files: Iterable[Path], query_text: str, top_k: int = 3) -> List[Dict]:
    queries = make_fts_queries(query_text)
    query_terms = select_query_terms(query_text, limit=8)
    if not queries or not query_terms:
        return []

    raw_candidates: Dict[str, Dict] = {}
    for db in db_files:
        schema = detect_schema(str(db))
        if schema not in {'records', 'acordaos'}:
            continue
        conn = open_db(db)
        try:
            for row in fetch_rows(conn, db, schema, queries, limit=20):
                item = dict(row)
                item['fts_score'] = float(item.get('fts_score') or 0.0)
                key = item.get('id') or f"{db.name}:{item.get('numero_acordao','')}:{item.get('processo','')}"
                existing = raw_candidates.get(key)
                if existing is None or item['fts_score'] < existing['fts_score']:
                    raw_candidates[key] = item
        finally:
            conn.close()

    reranked = []
    for item in raw_candidates.values():
        candidate_text = row_text(item)
        candidate_tags = parse_tags(item.get('tags') or item.get('tags_json'))
        overlap, matched_terms = overlap_score(query_terms, candidate_text, candidate_tags)
        if len(matched_terms) < 2:
            continue
        relevance = overlap - theme_penalty(query_terms, matched_terms) - min(abs(float(item.get('fts_score', 0.0))) / 25.0, 0.35)
        if relevance < 0.22:
            continue
        item = normalize_row(item, 'acordaos' if 'tags_json' in item else 'records')
        item['matched_terms'] = matched_terms
        item['relevance'] = round(relevance, 3)
        item['paragrafo_sugerido'] = build_suggested_paragraph(item, matched_terms)
        reranked.append(item)

    return nlargest(top_k, reranked, key=lambda x: x['relevance'])
