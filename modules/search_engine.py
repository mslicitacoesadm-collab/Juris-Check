from __future__ import annotations

import re
from heapq import nsmallest
from pathlib import Path
from typing import Dict, Iterable, List

from .base_db import open_db

STOPWORDS = {
    'de','da','do','das','dos','e','em','para','por','com','sem','na','no','nas','nos','ao','aos',
    'as','os','o','a','um','uma','que','se','ou','à','às','art','arts','tcu','acordao','acórdão'
}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or '')]
    return [t for t in tokens if t not in STOPWORDS]


def to_match_query(text: str) -> str:
    tokens = tokenize(text)
    if not tokens:
        return ''
    uniq = []
    seen = set()
    for tok in tokens[:18]:
        if tok not in seen:
            seen.add(tok)
            uniq.append(tok)
    return ' OR '.join(f'"{tok}"' for tok in uniq)


def search_candidates(db_files: Iterable[Path], query_text: str, top_k: int = 3) -> List[Dict]:
    match_query = to_match_query(query_text)
    if not match_query:
        return []

    candidates: List[Dict] = []
    for db in db_files:
        conn = open_db(db)
        try:
            rows = conn.execute(
                '''
                SELECT r.*, bm25(records_fts) as score
                FROM records_fts
                JOIN records r ON r.id = records_fts.id
                WHERE records_fts MATCH ?
                ORDER BY score
                LIMIT ?
                ''',
                (match_query, max(top_k * 3, 8)),
            ).fetchall()
            for row in rows:
                item = dict(row)
                item['score'] = float(item.get('score') or 0.0)
                item['paragrafo_sugerido'] = (
                    f"Conforme o {item.get('numero_acordao','')} - {item.get('colegiado','')}, "
                    f"de relatoria de {item.get('relator','')}, "
                    f"há aderência jurisprudencial ao argumento desenvolvido, especialmente porque "
                    f"{(item.get('sumario') or item.get('decisao') or item.get('assunto') or 'o precedente trata do núcleo do tema discutido na peça').strip()}"
                )
                candidates.append(item)
        finally:
            conn.close()

    dedup = {}
    for item in candidates:
        dedup[item['id']] = item if item['id'] not in dedup or item['score'] < dedup[item['id']]['score'] else dedup[item['id']]
    return nsmallest(top_k, dedup.values(), key=lambda x: x['score'])
