from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .base_db import detect_schema, exact_lookup, open_db, row_to_normalized_dict
from .citation_extractor import THESIS_KEYWORDS, detect_thesis, short_quote_from_text

STOPWORDS = {'a','o','e','de','do','da','dos','das','em','no','na','nos','nas','por','para','com','sem','ao','aos','as','os','um','uma','uns','umas','que','se','ou','como','mais','menos','ser','foi','sua','seu','suas','seus','art','lei','nº','n°','item','subitem','recurso','contrarrazões','peça','julgamento','tribunal','união','uniao','tcu','plenario','plenário','câmara','camara'}
TOKEN_RE = re.compile(r'[a-zà-ÿ0-9]{3,}', re.I)



def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or '') if t.lower() not in STOPWORDS]



def make_match_query(text: str, thesis_key: str | None = None, max_terms: int = 18) -> Tuple[List[str], List[str]]:
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
    return weighted[:max_terms], weighted[:max_terms]



def _table_text_expr(schema: Dict) -> str:
    cols = schema.get('columns', set())
    parts = []
    for col in ['assunto', 'sumario', 'ementa_match', 'decisao', 'tags', 'texto_match', 'acordao_texto', 'tema', 'subtema', 'enunciado', 'excerto', 'indexacao', 'indexadoresconsolidados']:
        if col in cols:
            parts.append(f"COALESCE({col}, '')")
    return " || ' ' || ".join(parts) if parts else "''"



def _normalize_colegiado(value: str) -> str:
    v = (value or '').lower().strip()
    return v.replace('1ª câmara', 'primeira câmara').replace('2ª câmara', 'segunda câmara').replace('1a camara', 'primeira camara').replace('2a camara', 'segunda camara')



def fetch_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, limit_each: int = 20, tipo: str | None = None) -> List[Dict]:
    weighted_terms, _ = make_match_query(query_text, thesis_key)
    if not weighted_terms:
        return []
    out: List[Dict] = []
    for db in db_files:
        schema = detect_schema(str(db))
        table = schema.get('table')
        if not table:
            continue
        if tipo and schema.get('record_type') != tipo:
            continue
        try:
            conn = open_db(db)
            try:
                rows = []
                text_expr = _table_text_expr(schema)
                ors = ' OR '.join([f"LOWER({text_expr}) LIKE ?" for _ in weighted_terms[:8]])
                params = [f"%{t.lower()}%" for t in weighted_terms[:8]]
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
    return ' '.join([record.get('assunto', ''), record.get('sumario', ''), record.get('ementa_match', ''), record.get('decisao', ''), record.get('tags', ''), record.get('tema', ''), record.get('subtema', '')])



def risk_from_score(score: float) -> tuple[str, str]:
    if score >= 0.50:
        return 'baixo', '#166534'
    if score >= 0.30:
        return 'médio', '#92400e'
    return 'alto', '#991b1b'



def build_short_suggestion(record: Dict) -> str:
    if record.get('tipo') == 'sumula':
        return f"Súmula TCU {record.get('numero_sumula')} · {short_quote_from_text(record.get('sumario') or record.get('ementa_match') or '')}"
    if record.get('tipo') == 'jurisprudencia':
        return f"Jurisprudência {record.get('numero_acordao')}/{record.get('ano_acordao')} · {short_quote_from_text(record.get('sumario') or record.get('ementa_match') or '')}"
    return f"TCU, Acórdão nº {record.get('numero_acordao_num') or record.get('numero_acordao')}/{record.get('ano_acordao')} - {record.get('colegiado')} · {short_quote_from_text(record.get('sumario') or record.get('ementa_match') or '')}"



def score_record_compat(record: Dict, query_text: str, thesis_key: str | None = None, colegiado_hint: str | None = None) -> float:
    query_tokens = set(tokenize(query_text))
    rec_text = _record_text(record).lower()
    rec_tokens = set(tokenize(rec_text))
    inter = len(query_tokens & rec_tokens)
    base = inter / max(len(query_tokens), 1)
    if thesis_key and thesis_key in THESIS_KEYWORDS:
        thesis_hits = sum(1 for term in THESIS_KEYWORDS[thesis_key] if re.search(term, rec_text, re.I))
        base += min(thesis_hits * 0.08, 0.32)
    if colegiado_hint and _normalize_colegiado(colegiado_hint) and _normalize_colegiado(colegiado_hint) == _normalize_colegiado(record.get('colegiado', '')):
        base += 0.05
    if record.get('tipo') == 'sumula':
        base += 0.04
    return min(base, 0.99)



def search_candidates(db_files: Iterable[Path], query_text: str, thesis_key: str | None = None, top_k: int = 5, colegiado_hint: str | None = None, tipo: str | None = None) -> List[Dict]:
    candidates = fetch_candidates(db_files, query_text, thesis_key=thesis_key, limit_each=max(10, top_k * 5), tipo=tipo)
    scored = []
    seen = set()
    for item in candidates:
        ident = (item.get('tipo'), item.get('numero_sumula') or item.get('numero_acordao_num') or item.get('numero_acordao'), item.get('ano_acordao'))
        if ident in seen:
            continue
        seen.add(ident)
        score = score_record_compat(item, query_text, thesis_key, colegiado_hint)
        item['compat_score'] = round(score, 4)
        item['citacao_curta'] = build_short_suggestion(item)
        item['risco'], item['risco_color'] = risk_from_score(score)
        scored.append(item)
    scored.sort(key=lambda x: x.get('compat_score', 0.0), reverse=True)
    return scored[:top_k]



def build_thesis_paragraph(record: Dict, tese_label: str) -> str:
    if record.get('tipo') == 'sumula':
        base = f"Como reforço da tese de {tese_label.lower()}, recomenda-se a invocação da Súmula TCU {record.get('numero_sumula')}, cujo enunciado converge com o argumento desenvolvido na peça."
    elif record.get('tipo') == 'jurisprudencia':
        base = f"A tese de {tese_label.lower()} pode ser fortalecida com a jurisprudência selecionada {record.get('numero_acordao')}/{record.get('ano_acordao')}, em linha com o entendimento resumido pelo TCU para hipóteses semelhantes."
    else:
        base = f"Para reforçar a tese de {tese_label.lower()}, é pertinente mencionar o TCU, Acórdão nº {record.get('numero_acordao_num') or record.get('numero_acordao')}/{record.get('ano_acordao')} - {record.get('colegiado')}, por tratar de situação compatível com a controvérsia analisada."
    excerto = short_quote_from_text(record.get('sumario') or record.get('ementa_match') or record.get('decisao') or '', max_chars=280)
    return f"{base} Em síntese, o precedente registra que {excerto.lower()}"



def validate_citation(db_files: Iterable[Path], citation: Dict, top_k: int = 3) -> Dict:
    context = citation.get('contexto', '')
    thesis = detect_thesis(context)
    thesis_key = thesis.get('chave') or None
    colegiado_hint = citation.get('colegiado_citado') or None
    result = dict(citation)
    result['tese'] = thesis.get('label')
    result['status'] = 'nao_localizada'
    result['status_label'] = 'Não localizada'
    result['matched_record'] = None
    result['alternativas'] = []
    result['correcao_sugerida'] = None
    result['score_contexto'] = 0.0
    result['risco'] = 'alto'

    citation_type = citation.get('tipo_citacao', 'acordao')
    exact = None
    if citation_type == 'sumula' and citation.get('numero_sumula'):
        exact = exact_lookup(db_files, citation.get('numero_sumula'), tipo='sumula')
    elif citation.get('numero_acordao_num'):
        exact = exact_lookup(db_files, citation.get('numero_acordao_num'), citation.get('ano_acordao'), tipo='acordao')

    if exact:
        score = score_record_compat(exact, context or citation.get('raw', ''), thesis_key, colegiado_hint)
        exact['compat_score'] = round(score, 4)
        exact['citacao_curta'] = build_short_suggestion(exact)
        exact['risco'], exact['risco_color'] = risk_from_score(score)
        result['matched_record'] = exact
        result['score_contexto'] = round(score, 4)
        result['risco'] = exact['risco']
        if score >= 0.32:
            result['status'] = 'valida_compatível'
            result['status_label'] = 'Válida e compatível'
        else:
            result['status'] = 'valida_pouco_compativel'
            result['status_label'] = 'Número válido, mas contexto fraco'
            alts = search_candidates(db_files, context or citation.get('raw', ''), thesis_key=thesis_key, top_k=top_k, colegiado_hint=colegiado_hint)
            result['alternativas'] = [a for a in alts if (a.get('tipo'), a.get('numero_identificador')) != (exact.get('tipo'), exact.get('numero_identificador'))][:top_k]
            if result['alternativas']:
                result['correcao_sugerida'] = result['alternativas'][0]
    else:
        alts = search_candidates(db_files, context or citation.get('raw', ''), thesis_key=thesis_key, top_k=top_k, colegiado_hint=colegiado_hint)
        result['alternativas'] = alts
        if alts:
            result['status'] = 'divergente'
            result['status_label'] = 'Citação divergente ou inadequada'
            result['correcao_sugerida'] = alts[0]
            result['score_contexto'] = alts[0].get('compat_score', 0.0)
            result['risco'] = alts[0].get('risco', 'médio')

    if result['correcao_sugerida']:
        cor = result['correcao_sugerida']
        if cor.get('tipo') == 'sumula':
            result['substituicao_textual'] = f"Súmula TCU {cor.get('numero_sumula')}"
        elif cor.get('tipo') == 'jurisprudencia':
            result['substituicao_textual'] = f"Jurisprudência {cor.get('numero_acordao')}/{cor.get('ano_acordao')}"
        else:
            result['substituicao_textual'] = f"TCU, Acórdão nº {cor.get('numero_acordao_num') or cor.get('numero_acordao')}/{cor.get('ano_acordao')} - {cor.get('colegiado')}"
    return result
