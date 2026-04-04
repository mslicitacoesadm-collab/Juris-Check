from __future__ import annotations

import re
from heapq import nsmallest
from typing import Dict, Iterable, List

from .base_db import detect_schema, normalize_row, open_db

STOPWORDS = {
    'de','da','do','das','dos','e','em','para','por','com','sem','na','no','nas','nos','ao','aos',
    'as','os','o','a','um','uma','que','se','ou','à','às','art','arts','tcu','acordao','acórdão'
}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or '')]
    return [t for t in tokens if t not in STOPWORDS]


def to_match_tokens(text: str) -> List[str]:
    tokens = tokenize(text)
    uniq: List[str] = []
    seen = set()
    for tok in tokens[:18]:
        if tok not in seen:
            seen.add(tok)
            uniq.append(tok)
    return uniq


def _fts_search(conn, tokens: List[str], limit: int):
    match_query = ' OR '.join(f'"{tok}"' for tok in tokens)
    return conn.execute(
        """
        SELECT r.*, bm25(records_fts) as score
        FROM records_fts
        JOIN records r ON r.id = records_fts.id
        WHERE records_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (match_query, limit),
    ).fetchall()


def _like_search(conn, tokens: List[str], limit: int):
    clauses = []
    params = []
    for tok in tokens[:8]:
        like = f'%{tok}%'
        clauses.append('(titulo LIKE ? OR assunto LIKE ? OR sumario LIKE ? OR ementa_match LIKE ? OR decisao LIKE ?)')
        params.extend([like, like, like, like, like])
    if not clauses:
        return []
    sql = f"""
        SELECT * FROM acordaos
        WHERE {' OR '.join(clauses)}
        LIMIT ?
    """
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def search_candidates(db_files: Iterable, query_text: str, top_k: int = 3) -> List[Dict]:
    tokens = to_match_tokens(query_text)
    if not tokens:
        return []

    candidates: List[Dict] = []
    for db in db_files:
        conn = open_db(db)
        try:
            schema = detect_schema(conn)
            if schema == 'records':
                rows = _fts_search(conn, tokens, max(top_k * 3, 8))
                for row in rows:
                    item = normalize_row(row, schema)
                    item['score'] = float(dict(row).get('score') or 0.0)
                    item['paragrafo_sugerido'] = (
                        f"Conforme o {item.get('numero_acordao','')} - {item.get('colegiado','')}, "
                        f"de relatoria de {item.get('relator','')}, há aderência jurisprudencial ao argumento desenvolvido, "
                        f"especialmente porque {(item.get('sumario') or item.get('decisao') or item.get('assunto') or 'o precedente trata do núcleo do tema discutido na peça').strip()}"
                    )
                    candidates.append(item)
            elif schema == 'acordaos':
                rows = _like_search(conn, tokens, max(top_k * 8, 20))
                for row in rows:
                    item = normalize_row(row, schema)
                    haystack = ' '.join([
                        item.get('titulo',''), item.get('assunto',''), item.get('sumario',''),
                        item.get('ementa_match',''), item.get('decisao',''), ' '.join(item.get('tags',[]))
                    ]).lower()
                    score = sum(1 for tok in tokens if tok in haystack)
                    if score <= 0:
                        continue
                    item['score'] = -float(score)
                    item['paragrafo_sugerido'] = (
                        f"Conforme o {item.get('numero_acordao','')} - {item.get('colegiado','')}, "
                        f"de relatoria de {item.get('relator','')}, há aderência jurisprudencial ao argumento desenvolvido, "
                        f"especialmente porque {(item.get('sumario') or item.get('decisao') or item.get('assunto') or 'o precedente trata do núcleo do tema discutido na peça').strip()}"
                    )
                    candidates.append(item)
        finally:
            conn.close()

    dedup = {}
    for item in candidates:
        prev = dedup.get(item['id'])
        if prev is None or item['score'] < prev['score']:
            dedup[item['id']] = item
    return nsmallest(top_k, dedup.values(), key=lambda x: x['score'])
