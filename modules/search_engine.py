from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from modules.base_db import detect_schema, exact_lookup, open_db, row_to_normalized_dict
from modules.citation_extractor import THESIS_EXPANSIONS, THESIS_KEYWORDS, detect_thesis, short_quote_from_text, tokenize


KIND_LABELS = {'acordao': 'Acórdão', 'jurisprudencia': 'Jurisprudência', 'sumula': 'Súmula'}
STOPWORDS = {'para','com','sem','dos','das','que','por','uma','não','nao','nos','nas','como','mais','menos','entre','pela','pelo','sobre','deve','deverá','devera','aos','das','sua','seu','este','esta','esse','essa','ser','foi'}


def semantic_terms(query_text: str, thesis_key: str | None) -> List[str]:
    terms = [t for t in tokenize(query_text) if t not in STOPWORDS]
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        for phrase in THESIS_KEYWORDS[thesis_key] + THESIS_EXPANSIONS.get(thesis_key, []):
            terms.extend(tokenize(phrase))
    # preserve order without duplicates
    seen = set(); ordered = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered[:40]


def fetch_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, limit_each: int = 24) -> List[Dict]:
    terms = semantic_terms(query_text, thesis_key)
    results: List[Dict] = []
    for db in db_files:
        schema = detect_schema(str(db))
        kind = schema.get('kind')
        if kinds and kind not in kinds:
            continue
        table = schema.get('table')
        if not table:
            continue
        cols = schema.get('columns', set())
        text_cols = [c for c in ['tema', 'assunto', 'subtema', 'sumario', 'ementa_match', 'texto_match', 'decisao', 'acordao_texto', 'enunciado', 'excerto', 'paragrafolc', 'indexadoresconsolidados', 'indexacao', 'referencialegal', 'tags', 'area'] if c in cols]
        if not text_cols:
            continue
        sql_text = " || ' ' || ".join([f"COALESCE(CAST({c} AS TEXT),'')" for c in text_cols])
        cond_terms = terms[:8] if terms else []
        where = ' OR '.join([f"lower({sql_text}) LIKE ?" for _ in cond_terms]) or '1=1'
        params = [f"%{t}%" for t in cond_terms]
        try:
            conn = open_db(db)
            try:
                sql = f"SELECT * FROM {table} WHERE {where} LIMIT {limit_each}"
                rows = conn.execute(sql, params).fetchall()
                for row in rows:
                    item = row_to_normalized_dict(row, schema)
                    item['_source_db'] = db.name
                    results.append(item)
            finally:
                conn.close()
        except Exception:
            continue
    return results


def text_blob(record: Dict) -> str:
    return ' '.join(str(record.get(k) or '') for k in ['tema', 'subtema', 'resumo', 'excerto', 'tags', 'colegiado'])


def overlap_score(query_terms: List[str], record_terms: List[str]) -> float:
    if not query_terms or not record_terms:
        return 0.0
    q = set(query_terms)
    r = set(record_terms)
    inter = len(q & r)
    return inter / max(len(q), 1)


def phrase_bonus(query_text: str, record: Dict, thesis_key: str | None) -> float:
    lower_blob = text_blob(record).lower()
    bonus = 0.0
    for phrase in (THESIS_KEYWORDS.get(thesis_key, []) if thesis_key else []):
        if phrase in lower_blob:
            bonus += 0.055
    for phrase in (THESIS_EXPANSIONS.get(thesis_key, []) if thesis_key else []):
        if phrase in lower_blob:
            bonus += 0.03
    if record.get('tema') and str(record.get('tema')).lower() in query_text.lower():
        bonus += 0.08
    return min(bonus, 0.24)


def score_record(record: Dict, query_text: str, thesis_key: str | None = None) -> float:
    blob = text_blob(record)
    query_terms = semantic_terms(query_text, thesis_key)
    record_terms = [t for t in tokenize(blob) if t not in STOPWORDS]
    base = overlap_score(query_terms, record_terms)
    raw_query = (query_text or '').lower()
    if str(record.get('numero') or '').lower() in raw_query and str(record.get('numero') or '').strip():
        base += 0.18
    if str(record.get('ano') or '').lower() in raw_query and str(record.get('ano') or '').strip():
        base += 0.07
    if str(record.get('colegiado') or '').lower() in raw_query and str(record.get('colegiado') or '').strip():
        base += 0.05
    base += phrase_bonus(query_text, record, thesis_key)
    if len(record_terms) > 120:
        base += 0.015
    return min(base, 0.99)


def build_short_reference(record: Dict) -> str:
    if record.get('tipo') == 'Súmula':
        return f"Súmula TCU nº {record.get('numero')}"
    return f"TCU, {record.get('tipo')} nº {record.get('numero')}/{record.get('ano')} - {record.get('colegiado')}"


def explain_match(record: Dict, thesis_label: str, query_text: str, thesis_key: str | None) -> str:
    motivos = []
    blob = text_blob(record).lower()
    if thesis_key:
        for phrase in THESIS_KEYWORDS.get(thesis_key, [])[:5]:
            if phrase in blob:
                motivos.append(phrase)
        for phrase in THESIS_EXPANSIONS.get(thesis_key, [])[:3]:
            if phrase in blob:
                motivos.append(phrase)
    if not motivos:
        motivos = [thesis_label.lower()]
    motivos = ', '.join(list(dict.fromkeys(motivos))[:4])
    return f"Aderência maior por tratar de {motivos} e dialogar com o contexto da tese analisada."


def suggest_rewrite(context: str, record: Dict, thesis_label: str) -> str:
    short = short_quote_from_text(record.get('excerto') or record.get('resumo') or '', 260)
    ref = build_short_reference(record)
    thesis = (thesis_label or 'a tese discutida').lower()
    base = (
        f"No ponto referente a {thesis}, a fundamentação pode ser aprimorada com a invocação de {ref}, "
        f"pois esse precedente indica, em síntese, que {short.lower()}"
    )
    if not base.endswith('.'):
        base += '.'
    return base


def search_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, top_k: int = 5) -> List[Dict]:
    raw = fetch_candidates(db_files, query_text, thesis_key, kinds=kinds, limit_each=max(30, top_k * 12))
    seen = set(); scored = []
    thesis = detect_thesis(query_text)
    for rec in raw:
        uniq = (rec.get('tipo'), rec.get('numero'), rec.get('ano'))
        if uniq in seen:
            continue
        seen.add(uniq)
        score = score_record(rec, query_text, thesis_key)
        if score < 0.16:
            continue
        rec['compat_score'] = score
        rec['citacao_curta'] = build_short_reference(rec)
        rec['fundamento_curto'] = short_quote_from_text(rec.get('resumo') or rec.get('excerto') or '', 230)
        rec['motivo_match'] = explain_match(rec, thesis.get('label', 'tese geral'), query_text, thesis_key)
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
        'score_contexto': 0.0, 'grau_confianca': 'Não validada', 'paragrafo_reescrito': '', 'motivo_match': '',
    }
    if exact:
        score = score_record(exact, citation.get('contexto', '') or citation.get('raw', ''), thesis.get('chave'))
        exact['compat_score'] = score
        exact['citacao_curta'] = build_short_reference(exact)
        exact['motivo_match'] = explain_match(exact, thesis.get('label', 'tese geral'), citation.get('contexto', '') or citation.get('raw', ''), thesis.get('chave'))
        result['matched_record'] = exact
        result['score_contexto'] = score
        result['motivo_match'] = exact['motivo_match']
        if score >= 0.34:
            result['status'] = 'valida_compatível'
            result['status_label'] = 'Válida e compatível com a tese'
            result['grau_confianca'] = 'Alta confiança' if score >= 0.48 else 'Média confiança'
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
            result['motivo_match'] = best.get('motivo_match', '')
    return result
