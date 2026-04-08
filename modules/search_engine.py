
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from modules.base_db import detect_schema, exact_lookup, open_db, row_to_normalized_dict
from modules.citation_extractor import THESIS_EXPANSIONS, THESIS_KEYWORDS, detect_thesis, short_quote_from_text, tokenize


KIND_LABELS = {'acordao': 'Acórdão', 'jurisprudencia': 'Jurisprudência', 'sumula': 'Súmula'}
STOPWORDS = {'para','com','sem','dos','das','que','por','uma','não','nao','nos','nas','como','mais','menos','entre','pela','pelo','sobre','deve','deverá','devera','aos','das','sua','seu','este','esta','esse','essa','ser','foi','art','lei'}


def semantic_terms(query_text: str, thesis_key: str | None) -> List[str]:
    terms = [t for t in tokenize(query_text) if t not in STOPWORDS]
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        for phrase in THESIS_KEYWORDS[thesis_key] + THESIS_EXPANSIONS.get(thesis_key, []):
            terms.extend(tokenize(phrase))
    seen = set(); ordered = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered[:48]


def _fts_query(terms: List[str]) -> str:
    clean = []
    for t in terms[:8]:
        t = ''.join(ch for ch in t if ch.isalnum() or ch in {'_', '-'})
        if t:
            clean.append(f'"{t}"')
    return ' OR '.join(clean)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def fetch_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, limit_each: int = 24) -> List[Dict]:
    terms = semantic_terms(query_text, thesis_key)
    results: List[Dict] = []
    has_intelligent = any(detect_schema(str(db)).get('is_intelligent') for db in db_files)
    for db in db_files:
        schema = detect_schema(str(db))
        kind = schema.get('kind')
        if has_intelligent and not schema.get('is_intelligent'):
            continue
        if kinds and kind not in kinds and not schema.get('is_intelligent'):
            continue
        table = schema.get('table')
        if not table:
            continue
        try:
            conn = open_db(db)
            try:
                if schema.get('is_intelligent'):
                    params = []
                    where = []
                    if kinds:
                        placeholders = ','.join(['?'] * len(kinds))
                        where.append(f"tipo IN ({placeholders})")
                        params.extend(sorted(kinds))
                    if thesis_key:
                        where.append('(tema_principal = ? OR texto_indexavel LIKE ? OR tese_central LIKE ?)')
                        thesis_text = thesis_key.replace('_', ' ')
                        params.extend([thesis_key, f'%{thesis_text}%', f'%{thesis_text}%'])
                    if terms:
                        text_cond = ' OR '.join(['texto_indexavel LIKE ?' for _ in terms[:8]])
                        where.append(f'({text_cond})')
                        params.extend([f'%{t}%' for t in terms[:8]])
                    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
                    sql = f"SELECT * FROM precedentes_inteligentes {where_sql} ORDER BY score_confianca_interno DESC, grau_utilidade DESC LIMIT {limit_each}"
                    rows = conn.execute(sql, params).fetchall()
                    if not rows and schema.get('fts_table') and terms:
                        fts = _fts_query(terms)
                        if fts:
                            fts_sql = """SELECT p.*
                                         FROM precedentes_fts f
                                         JOIN precedentes_inteligentes p ON p.id = f.rowid
                                         WHERE precedentes_fts MATCH ?
                                         ORDER BY p.score_confianca_interno DESC, p.grau_utilidade DESC
                                         LIMIT ?"""
                            rows = conn.execute(fts_sql, (fts, limit_each)).fetchall()
                    for row in rows:
                        item = row_to_normalized_dict(row, schema)
                        item['_source_db'] = db.name
                        results.append(item)
                    continue

                cols = schema.get('columns', set())
                text_cols = [c for c in ['tema', 'assunto', 'subtema', 'sumario', 'ementa_match', 'texto_match', 'decisao', 'acordao_texto', 'enunciado', 'excerto', 'paragrafolc', 'indexadoresconsolidados', 'indexacao', 'referencialegal', 'tags', 'area'] if c in cols]
                if not text_cols:
                    continue
                sql_text = " || ' ' || ".join([f"COALESCE(CAST({c} AS TEXT),'')" for c in text_cols])
                cond_terms = terms[:8] if terms else []
                where = ' OR '.join([f"lower({sql_text}) LIKE ?" for _ in cond_terms]) or '1=1'
                params = [f"%{t}%" for t in cond_terms]
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
    parts = [
        record.get('tema'),
        record.get('subtema'),
        record.get('resumo'),
        record.get('excerto'),
        record.get('tags'),
        record.get('colegiado'),
        record.get('tribunal'),
        record.get('tese_central'),
        record.get('ementa_resumida'),
        record.get('trecho_chave'),
        ' '.join(record.get('fundamentos_legais') or []),
        ' '.join(record.get('palavras_chave') or []),
        ' '.join(record.get('aplicavel_em') or []),
        record.get('resumo_uso_pratico'),
        record.get('texto_indexavel'),
    ]
    return ' '.join(str(x or '') for x in parts)


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
    raw_query = (query_text or '').lower()

    score_numero = 0.18 if str(record.get('numero') or '').lower() in raw_query and str(record.get('numero') or '').strip() else 0.0
    score_ano = 0.07 if str(record.get('ano') or '').lower() in raw_query and str(record.get('ano') or '').strip() else 0.0
    score_colegiado = 0.05 if str(record.get('colegiado') or '').lower() in raw_query and str(record.get('colegiado') or '').strip() else 0.0
    score_textual = overlap_score(query_terms, record_terms)
    score_tese = phrase_bonus(query_text, record, thesis_key)
    score_utilidade = min(_safe_float(record.get('grau_utilidade')) * 0.12, 0.12)
    score_confianca = min(_safe_float(record.get('score_confianca_interno')) * 0.08, 0.08)
    score_uso = 0.04 if record.get('aplicavel_em') else 0.0

    base = score_textual + score_numero + score_ano + score_colegiado + score_tese + score_utilidade + score_confianca + score_uso
    if len(record_terms) > 120:
        base += 0.015
    return min(base, 0.99)


def build_short_reference(record: Dict) -> str:
    tribunal = record.get('tribunal') or 'TCM/BA'
    if record.get('tipo') == 'Súmula':
        return f"{tribunal}, Súmula nº {record.get('numero')}"
    return f"{tribunal}, {record.get('tipo')} nº {record.get('numero')}/{record.get('ano')} - {record.get('colegiado')}"


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
    if record.get('resumo_uso_pratico'):
        motivos.append(record['resumo_uso_pratico'])
    if not motivos and record.get('tese_central'):
        motivos = [record['tese_central']]
    if not motivos:
        motivos = [thesis_label.lower()]
    motivos = '; '.join(list(dict.fromkeys(motivos))[:2])
    return f"Aderência maior por tratar de {motivos} e dialogar com o contexto da tese analisada."


def suggest_rewrite(context: str, record: Dict, thesis_label: str) -> str:
    short = short_quote_from_text(record.get('trecho_chave') or record.get('excerto') or record.get('resumo') or '', 260)
    ref = build_short_reference(record)
    thesis = (thesis_label or 'a tese discutida').lower()
    base = (
        f"No ponto referente a {thesis}, a fundamentação pode ser aprimorada com a invocação de {ref}, "
        f"pois esse precedente indica, em síntese, que {short.lower()}"
    )
    if record.get('resumo_uso_pratico'):
        base += f" {record['resumo_uso_pratico']}"
    if not base.endswith('.'):
        base += '.'
    return base


def search_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, kinds: set[str] | None = None, top_k: int = 5) -> List[Dict]:
    raw = fetch_candidates(db_files, query_text, thesis_key, kinds=kinds, limit_each=max(30, top_k * 12))
    seen = set(); scored = []
    thesis = detect_thesis(query_text)
    for rec in raw:
        uniq = (rec.get('tipo'), rec.get('numero'), rec.get('ano'), rec.get('colegiado'))
        if uniq in seen:
            continue
        seen.add(uniq)
        score = score_record(rec, query_text, thesis_key)
        if score < 0.16:
            continue
        rec['compat_score'] = score
        rec['citacao_curta'] = build_short_reference(rec)
        rec['fundamento_curto'] = short_quote_from_text(rec.get('trecho_chave') or rec.get('resumo') or rec.get('excerto') or '', 230)
        rec['motivo_match'] = explain_match(rec, thesis.get('label', 'tese geral'), query_text, thesis_key)
        scored.append(rec)
    scored.sort(key=lambda x: (x['compat_score'], _safe_float(x.get('score_confianca_interno')), _safe_float(x.get('grau_utilidade'))), reverse=True)
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
