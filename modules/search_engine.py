from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple
from pathlib import Path

from .base_db import detect_schema, exact_lookup, open_db, row_to_normalized_dict
from .citation_extractor import THESIS_KEYWORDS, detect_thesis, short_quote_from_text

STOPWORDS = {
    'a','o','e','de','do','da','dos','das','em','no','na','nos','nas','por','para','com','sem','ao','aos','as','os',
    'um','uma','uns','umas','que','se','ou','como','mais','menos','ser','foi','sua','seu','suas','seus',
    'art','lei','nº','n°','item','subitem','recurso','contrarrazões','peça','julgamento',
    'tribunal','união','uniao','tcu','plenario','plenário','câmara','camara'
}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.I)
LICIT_TERMS = {'licitação','licitacao','pregão','pregao','edital','proposta','competitividade','diligência','diligencia','desclassificação','desclassificacao','habilitação','habilitacao'}


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or '') if t.lower() not in STOPWORDS]



def make_match_query(text: str, thesis_key: str | None = None, max_terms: int = 16) -> Tuple[str, List[str]]:
    tokens = tokenize(text)
    weighted = []
    seen = set()
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        for term in THESIS_KEYWORDS[thesis_key]:
            term = re.sub(r'[^a-zà-ÿ0-9 ]', ' ', term.lower()).strip()
            for sub in term.split():
                if len(sub) >= 4 and sub not in seen:
                    weighted.append(sub)
                    seen.add(sub)
    for tok in tokens:
        if tok not in seen:
            weighted.append(tok)
            seen.add(tok)
        if len(weighted) >= max_terms:
            break
    query = ' OR '.join(f'"{t}"' for t in weighted[:max_terms])
    return query, weighted[:max_terms]



def _table_text_expr(schema: Dict) -> str:
    cols = schema.get('columns', set())
    parts = []
    for col in ['assunto', 'sumario', 'ementa_match', 'decisao', 'tags', 'texto_match', 'acordao_texto']:
        if col in cols:
            parts.append(f"COALESCE({col}, '')")
    return " || ' ' || ".join(parts) if parts else "''"



def _normalize_colegiado(value: str) -> str:
    v = (value or '').lower().strip()
    v = v.replace('1ª câmara', 'primeira câmara').replace('2ª câmara', 'segunda câmara')
    v = v.replace('1a camara', 'primeira camara').replace('2a camara', 'segunda camara')
    return v



def fetch_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, limit_each: int = 18) -> List[Dict]:
    match_query, weighted_terms = make_match_query(query_text, thesis_key)
    if not weighted_terms:
        return []
    out: List[Dict] = []
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                rows = []
                if schema.get('fts_table') and match_query:
                    fts = schema['fts_table']
                    try:
                        sql = f"SELECT r.*, bm25({fts}) as rank_score FROM {fts} JOIN {table} r ON r.id = {fts}.id WHERE {fts} MATCH ? LIMIT ?"
                        rows = conn.execute(sql, (match_query, limit_each)).fetchall()
                    except Exception:
                        rows = []
                if not rows:
                    text_expr = _table_text_expr(schema)
                    ors = ' OR '.join([f"LOWER({text_expr}) LIKE ?" for _ in weighted_terms[:6]])
                    params = [f"%{t.lower()}%" for t in weighted_terms[:6]]
                    sql = f"SELECT * FROM {table} WHERE {ors} LIMIT ?"
                    rows = conn.execute(sql, params + [limit_each]).fetchall()
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
    return ' '.join([
        record.get('assunto', ''), record.get('sumario', ''), record.get('ementa_match', ''), record.get('decisao', ''), record.get('tags', ''),
    ])



def risk_from_score(score: float) -> tuple[str, str]:
    if score >= 0.46:
        return 'baixo', '#166534'
    if score >= 0.28:
        return 'médio', '#92400e'
    return 'alto', '#991b1b'



def _score_record(record: Dict, query_text: str, thesis_key: str | None = None, colegiado_hint: str | None = None) -> float:
    q_tokens = set(tokenize(query_text))
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        q_tokens |= {re.sub(r'[^a-zà-ÿ0-9]', '', t.lower()) for t in THESIS_KEYWORDS[thesis_key] if len(t) >= 4}
    q_tokens = {t for t in q_tokens if t}
    if not q_tokens:
        return 0.0
    record_text = _record_text(record)
    r_tokens = set(tokenize(record_text))
    if not r_tokens:
        return 0.0
    overlap = q_tokens & r_tokens
    coverage = len(overlap) / max(1, len(q_tokens))
    density = len(overlap) / max(1, len(r_tokens))
    licit_overlap = len((q_tokens & LICIT_TERMS) & r_tokens)
    score = coverage * 0.66 + density * 0.18 + min(licit_overlap, 4) * 0.04

    if thesis_key and overlap & {re.sub(r'[^a-zà-ÿ0-9]', '', t.lower()) for t in THESIS_KEYWORDS.get(thesis_key, set())}:
        score += 0.10
    if overlap & LICIT_TERMS:
        score += 0.07
    if any(term in record_text.lower() for term in ['pregão', 'pregao', 'licitação', 'licitacao', 'edital']):
        score += 0.04
    if record.get('status') == 'sigiloso':
        score -= 0.08
    if not record.get('sumario') and not record.get('assunto'):
        score -= 0.07
    if colegiado_hint and _normalize_colegiado(record.get('colegiado', '')) == _normalize_colegiado(colegiado_hint):
        score += 0.05
    return score



def build_short_suggestion(record: Dict) -> str:
    base_text = record.get('sumario') or record.get('decisao') or record.get('assunto') or record.get('ementa_match') or ''
    quote = short_quote_from_text(base_text, 235)
    return f"TCU, Acórdão nº {record.get('numero_acordao')} - {record.get('colegiado')}: \"{quote}\""



def build_thesis_paragraph(record: Dict, thesis_label: str) -> str:
    quote = short_quote_from_text(record.get('sumario') or record.get('decisao') or record.get('ementa_match') or '', 260)
    if not quote:
        quote = 'o precedente reforça a tese jurídica discutida no tópico.'
    return (
        f"No ponto relativo a {thesis_label.lower()}, é pertinente registrar o entendimento do TCU no Acórdão nº {record.get('numero_acordao')} - {record.get('colegiado')}, segundo o qual \"{quote}\", reforçando a coerência do argumento sustentado na peça."
    )



def search_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, top_k: int = 2, colegiado_hint: str | None = None) -> List[Dict]:
    raw = fetch_candidates(db_files, query_text, thesis_key, limit_each=max(18, top_k * 10))
    scored = []
    seen = set()
    for rec in raw:
        key = rec.get('id') or rec.get('numero_acordao')
        if key in seen:
            continue
        seen.add(key)
        score = _score_record(rec, query_text, thesis_key, colegiado_hint)
        if score < 0.17:
            continue
        rec['compat_score'] = round(score, 4)
        rec['citacao_curta'] = build_short_suggestion(rec)
        rec['risco'], rec['risco_color'] = risk_from_score(score)
        scored.append(rec)
    scored.sort(key=lambda x: x['compat_score'], reverse=True)
    return scored[:top_k]



def validate_citation(db_files: Iterable[Path], citation: Dict, top_k: int = 2) -> Dict:
    exact = exact_lookup(db_files, citation.get('numero_acordao_num', ''), citation.get('ano_acordao') or None)
    context = citation.get('contexto', '')
    thesis = detect_thesis(context)
    thesis_key = thesis.get('chave')
    colegiado_hint = citation.get('colegiado_citado') or None
    result = {
        'raw': citation.get('raw', ''),
        'contexto': context,
        'linha': citation.get('linha'),
        'tese': thesis.get('label', ''),
        'status': 'nao_localizada',
        'status_label': 'Não localizada na base',
        'matched_record': None,
        'alternativas': [],
        'correcao_sugerida': None,
        'substituicao_textual': None,
        'score_contexto': 0.0,
        'risco': 'alto',
    }

    if exact:
        score = _score_record(exact, context or citation.get('raw', ''), thesis_key, colegiado_hint)
        exact['compat_score'] = round(score, 4)
        exact['citacao_curta'] = build_short_suggestion(exact)
        exact['risco'], exact['risco_color'] = risk_from_score(score)
        result['matched_record'] = exact
        result['score_contexto'] = round(score, 4)
        result['risco'] = exact['risco']
        if score >= 0.30:
            result['status'] = 'valida_compatível'
            result['status_label'] = 'Válida e compatível'
        else:
            result['status'] = 'valida_pouco_compativel'
            result['status_label'] = 'Número válido, mas contexto fraco'
            alts = search_candidates(db_files, context or citation.get('raw', ''), thesis_key, top_k=top_k, colegiado_hint=colegiado_hint)
            result['alternativas'] = [a for a in alts if a.get('numero_acordao') != exact.get('numero_acordao')][:top_k]
            if result['alternativas']:
                result['correcao_sugerida'] = result['alternativas'][0]
    else:
        alts = search_candidates(db_files, context or citation.get('raw', ''), thesis_key, top_k=top_k, colegiado_hint=colegiado_hint)
        result['alternativas'] = alts
        if alts:
            result['status'] = 'divergente'
            result['status_label'] = 'Citação divergente ou inadequada'
            result['correcao_sugerida'] = alts[0]
            result['score_contexto'] = alts[0].get('compat_score', 0.0)
            result['risco'] = alts[0].get('risco', 'médio')

    if result['correcao_sugerida']:
        cor = result['correcao_sugerida']
        result['substituicao_textual'] = f"TCU, Acórdão nº {cor.get('numero_acordao')} - {cor.get('colegiado')}"
    return result
