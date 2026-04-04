from __future__ import annotations

import re
import sqlite3
from heapq import nlargest
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .base_db import detect_schema, get_table_columns, normalize_row, open_db
from .thesis_analyzer import THESIS_PROFILES

STOPWORDS = {
    'de','da','do','das','dos','e','o','a','os','as','em','um','uma','para','por','com','sem','no','na','nos','nas',
    'que','ao','aos','à','às','ou','se','sua','seu','suas','seus','como','não','nao','mais','menos','já','ja','ser',
    'sobre','entre','apenas','quando','onde','pois','porque','lhe','ela','ele','eles','elas','art','arts','lei'
}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.IGNORECASE)
SPLIT_SENTENCE_RE = re.compile(r'(?<=[\.!?;])\s+')
PROCUREMENT_CORE = {
    'licitação','licitacao','pregão','pregao','edital','proposta','diligência','diligencia','inexequibilidade',
    'desclassificação','desclassificacao','habilitação','habilitacao','formalismo','competitividade','certame',
    'recurso','contrarrazão','contrarrazao','impugnação','impugnacao','planilha','custos','julgamento','saneamento'
}


def normalize_text(text: str) -> str:
    return ' '.join((text or '').lower().split())


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or '') if t.lower() not in STOPWORDS]


def thesis_terms(thesis_id: str) -> List[str]:
    profile = THESIS_PROFILES.get(thesis_id)
    if not profile:
        return []
    return [t.lower() for t in profile.keywords]


def select_query_terms(text: str, thesis_id: str | None = None, limit: int = 10) -> List[str]:
    freq: Dict[str, int] = {}
    for tok in tokenize(text):
        freq[tok] = freq.get(tok, 0) + 1
    for extra in thesis_terms(thesis_id or ''):
        for tok in tokenize(extra):
            freq[tok] = freq.get(tok, 0) + 3
    ordered = sorted(freq, key=lambda t: ((t in PROCUREMENT_CORE), freq[t], len(t)), reverse=True)
    return ordered[:limit]


def make_sql_terms(query_terms: Sequence[str]) -> List[str]:
    return [t for t in query_terms if len(t) >= 4][:6]


def row_text(item: Dict) -> str:
    parts = [item.get('titulo',''), item.get('assunto',''), item.get('sumario',''), item.get('ementa_match',''), item.get('decisao','')]
    tags = item.get('tags', [])
    if isinstance(tags, list):
        parts.extend(tags)
    return normalize_text(' '.join(str(p) for p in parts if p))


def _safe_exec(conn, sql: str, params: Sequence):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def fetch_rows(conn, db_path: Path, schema: str, sql_terms: Sequence[str], limit: int = 25):
    rows = []
    if schema == 'records':
        table = 'records'
    elif schema == 'acordaos':
        table = 'acordaos'
    else:
        return rows

    cols = set(get_table_columns(str(db_path), table))
    text_cols = [c for c in ['titulo','assunto','sumario','ementa_match','decisao','tags','tags_json'] if c in cols]
    if not text_cols or not sql_terms:
        return rows

    clauses = []
    params: List[str | int] = []
    for term in sql_terms[:6]:
        piece = ' OR '.join([f'{c} LIKE ?' for c in text_cols])
        clauses.append(f'({piece})')
        params.extend([f'%{term}%'] * len(text_cols))
    sql = f"SELECT * FROM {table} WHERE {' OR '.join(clauses)} LIMIT ?"
    params.append(limit)
    rows.extend(_safe_exec(conn, sql, params))
    return rows


def overlap_score(query_terms: Sequence[str], candidate_text: str, tags: Sequence[str], thesis_id: str | None) -> tuple[float, List[str]]:
    matched = []
    thesis_kw = set(tokenize(' '.join(thesis_terms(thesis_id or ''))))
    for term in query_terms:
        if term in candidate_text or term in tags:
            matched.append(term)
    unique = list(dict.fromkeys(matched))
    score = len(unique) / max(len(set(query_terms)), 1)
    score += 0.25 * len([t for t in unique if t in PROCUREMENT_CORE])
    score += 0.35 * len([t for t in unique if t in thesis_kw])
    return score, unique


def extract_short_quote(item: Dict, matched_terms: Sequence[str], thesis_id: str | None = None) -> str:
    source = item.get('sumario') or item.get('ementa_match') or item.get('decisao') or item.get('assunto') or ''
    text = ' '.join(str(source).split())
    if not text:
        return 'Há aderência com a tese desenvolvida na peça.'
    parts = [p.strip(' .;:-') for p in SPLIT_SENTENCE_RE.split(text) if p.strip()]
    if not parts:
        parts = [text]
    lowered_terms = [t.lower() for t in matched_terms]
    chosen = ''
    for part in parts:
        lp = part.lower()
        if any(term in lp for term in lowered_terms[:4]):
            chosen = part
            break
    if not chosen:
        chosen = parts[0]
    if len(chosen) > 340:
        chosen = chosen[:337].rsplit(' ', 1)[0] + '...'
    if chosen and chosen[-1] not in '.!?':
        chosen += '.'
    return chosen


def build_paragraph(item: Dict, quote: str) -> str:
    colegiado = item.get('colegiado', '').strip()
    citation = f"TCU, Acórdão nº {item.get('numero_acordao','')}"
    if colegiado:
        citation += f" - {colegiado}"
    return f'{citation}: "{quote}"'


def search_candidates(db_files: Iterable[Path], query_text: str, thesis_id: str | None = None, top_k: int = 2) -> List[Dict]:
    query_terms = select_query_terms(query_text, thesis_id=thesis_id)
    if len(query_terms) < 3:
        return []
    sql_terms = make_sql_terms(query_terms)
    raw: Dict[str, Dict] = {}
    for db in db_files:
        schema = detect_schema(str(db))
        if schema not in {'records','acordaos'}:
            continue
        conn = open_db(db)
        try:
            for row in fetch_rows(conn, db, schema, sql_terms, limit=22):
                item = normalize_row(row, schema)
                key = item.get('id') or f"{db.name}:{item.get('numero_acordao','')}"
                raw[key] = item
        finally:
            conn.close()

    scored = []
    for item in raw.values():
        text = row_text(item)
        tags = item.get('tags', []) if isinstance(item.get('tags', []), list) else []
        score, matched = overlap_score(query_terms, text, tags, thesis_id)
        procurement_hits = len([m for m in matched if m in PROCUREMENT_CORE])
        thesis_hits = len([m for m in matched if m in tokenize(' '.join(thesis_terms(thesis_id or '')))])
        if procurement_hits < 2:
            continue
        if thesis_id and thesis_hits < 1:
            continue
        if score < 1.0:
            continue
        quote = extract_short_quote(item, matched, thesis_id=thesis_id)
        scored.append({
            **item,
            'matched_terms': matched,
            'relevance': round(score, 3),
            'quote_curta': quote,
            'paragrafo_sugerido': build_paragraph(item, quote),
        })
    return nlargest(top_k, scored, key=lambda x: x['relevance'])
