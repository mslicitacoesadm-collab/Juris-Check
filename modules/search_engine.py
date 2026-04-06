from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

from .base_db import detect_schema, exact_lookup, open_db, row_to_normalized_dict
from .citation_extractor import THESIS_KEYWORDS, detect_thesis, short_quote_from_text

STOPWORDS = {'a','o','e','de','do','da','dos','das','em','no','na','nos','nas','por','para','com','sem','ao','aos','as','os','um','uma','que','se','ou','como','mais','menos','ser','foi','sua','seu','suas','seus','art','lei','item','subitem','recurso','peça','julgamento','tribunal','união','uniao','tcu'}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.I)


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or '') if t.lower() not in STOPWORDS]


def expand_query(text: str, thesis_key: str | None = None, max_terms: int = 18) -> List[str]:
    terms: List[str] = []
    seen = set()
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        for term in THESIS_KEYWORDS[thesis_key]:
            for tok in tokenize(term):
                if tok not in seen:
                    seen.add(tok); terms.append(tok)
    for tok in tokenize(text):
        if tok not in seen:
            seen.add(tok); terms.append(tok)
        if len(terms) >= max_terms:
            break
    return terms[:max_terms]


def _text_fields_expr(kind: str, cols: set[str]) -> str:
    candidates = {
        'acordao': ['assunto', 'sumario', 'ementa_match', 'texto_match', 'decisao', 'acordao_texto', 'tags'],
        'jurisprudencia': ['tema', 'subtema', 'enunciado', 'excerto', 'indexacao', 'indexadoresconsolidados', 'referencialegal'],
        'sumula': ['tema', 'subtema', 'enunciado', 'excerto', 'indexacao', 'indexadoresconsolidados', 'referencialegal'],
    }
    parts = [f"COALESCE({c}, '')" for c in candidates.get(kind, []) if c in cols]
    return " || ' ' || ".join(parts) if parts else "''"


def fetch_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, limit_each: int = 24) -> List[Dict]:
    terms = expand_query(query_text, thesis_key)
    if not terms:
        return []
    out: List[Dict] = []
    for db in db_files:
        schema = detect_schema(str(db))
        kind = schema.get('kind')
        if kinds and kind not in kinds:
            continue
        table = schema.get('table')
        cols = schema.get('columns', set())
        if not table:
            continue
        expr = _text_fields_expr(kind, cols)
        ors = ' OR '.join([f'LOWER({expr}) LIKE ?' for _ in terms[:8]])
        params = [f'%{t.lower()}%' for t in terms[:8]]
        try:
            conn = open_db(db)
            try:
                rows = conn.execute(f'SELECT * FROM {table} WHERE {ors} LIMIT ?', params + [limit_each]).fetchall()
                for row in rows:
                    item = row_to_normalized_dict(row, schema)
                    item['_source_db'] = db.name
                    out.append(item)
            finally:
                conn.close()
        except Exception:
            continue
    return out


def _record_text(record: Dict) -> str:
    return ' '.join(filter(None, [record.get('tema',''), record.get('subtema',''), record.get('resumo',''), record.get('excerto',''), record.get('tags','')]))


def score_record(record: Dict, query_text: str, thesis_key: str | None = None) -> float:
    q_tokens = set(expand_query(query_text, thesis_key))
    r_tokens = set(tokenize(_record_text(record)))
    if not q_tokens or not r_tokens:
        return 0.0
    overlap = q_tokens & r_tokens
    coverage = len(overlap) / max(1, len(q_tokens))
    density = len(overlap) / max(1, len(r_tokens))
    score = coverage * 0.72 + density * 0.18
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        expanded = {tok for term in THESIS_KEYWORDS[thesis_key] for tok in tokenize(term)}
        if overlap & expanded:
            score += 0.10
    if record.get('tipo') == 'Súmula':
        score += 0.03
    return round(score, 4)


def build_short_reference(record: Dict) -> str:
    if record.get('tipo') == 'Súmula':
        return f"Súmula TCU nº {record.get('numero')}"
    return f"TCU, {record.get('tipo')} nº {record.get('numero')}/{record.get('ano')} - {record.get('colegiado')}"


def suggest_rewrite(context: str, record: Dict, thesis_label: str) -> str:
    short = short_quote_from_text(record.get('excerto') or record.get('resumo') or '', 240)
    ref = build_short_reference(record)
    base = f"No ponto relativo a {thesis_label.lower()}, mostra-se mais adequado invocar {ref}, pois o precedente registra que {short.lower()}"
    if not base.endswith('.'):
        base += '.'
    return base


def search_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, top_k: int = 5) -> List[Dict]:
    raw = fetch_candidates(db_files, query_text, thesis_key, kinds=kinds, limit_each=max(24, top_k * 10))
    seen = set(); scored = []
    for rec in raw:
        uniq = (rec.get('tipo'), rec.get('numero'), rec.get('ano'))
        if uniq in seen:
            continue
        seen.add(uniq)
        score = score_record(rec, query_text, thesis_key)
        if score < 0.14:
            continue
        rec['compat_score'] = score
        rec['citacao_curta'] = build_short_reference(rec)
        rec['fundamento_curto'] = short_quote_from_text(rec.get('resumo') or rec.get('excerto') or '', 220)
        scored.append(rec)
    scored.sort(key=lambda x: x['compat_score'], reverse=True)
    return scored[:top_k]


def validate_reference(db_files: Iterable[Path], citation: Dict, top_k: int = 3) -> Dict:
    thesis = detect_thesis(citation.get('contexto', ''))
    exact = exact_lookup(db_files, citation.get('kind', ''), citation.get('numero', ''), citation.get('ano') or None)
    result = {
        'kind': citation.get('kind'), 'raw': citation.get('raw', ''), 'contexto': citation.get('contexto', ''), 'linha': citation.get('linha'),
        'tese': thesis.get('label', 'Tese geral'), 'status': 'nao_localizada', 'status_label': 'Não localizada na base',
        'matched_record': None, 'alternativas': [], 'correcao_sugerida': None, 'substituicao_textual': None,
        'score_contexto': 0.0, 'grau_confianca': 'Não validada', 'paragrafo_reescrito': '',
    }
    if exact:
        score = score_record(exact, citation.get('contexto', '') or citation.get('raw', ''), thesis.get('chave'))
        exact['compat_score'] = score
        exact['citacao_curta'] = build_short_reference(exact)
        result['matched_record'] = exact
        result['score_contexto'] = score
        if score >= 0.28:
            result['status'] = 'valida_compatível'
            result['status_label'] = 'Válida e compatível com a tese'
            result['grau_confianca'] = 'Alta confiança' if score >= 0.42 else 'Média confiança'
            result['paragrafo_reescrito'] = citation.get('contexto', '')
        else:
            result['status'] = 'valida_pouco_compativel'
            result['status_label'] = 'Número válido, mas fundamento fraco para a tese'
            result['grau_confianca'] = 'Baixa confiança'
    kinds = {citation.get('kind')} if citation.get('kind') else None
    alts = search_candidates(db_files, citation.get('contexto', '') or citation.get('raw', ''), thesis.get('chave'), kinds=kinds, top_k=top_k)
    if result['status'] != 'valida_compatível':
        result['alternativas'] = [a for a in alts if (not exact) or a.get('numero') != exact.get('numero')][:top_k]
        if result['alternativas']:
            best = result['alternativas'][0]
            result['correcao_sugerida'] = best
            if result['status'] == 'nao_localizada':
                result['status'] = 'divergente'
                result['status_label'] = 'Citação divergente ou inadequada'
                result['grau_confianca'] = 'Baixa confiança'
            result['substituicao_textual'] = build_short_reference(best)
            result['paragrafo_reescrito'] = suggest_rewrite(citation.get('contexto', ''), best, thesis.get('label', 'Tese geral'))
    return result
