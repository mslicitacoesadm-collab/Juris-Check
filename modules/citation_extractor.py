from __future__ import annotations

import re
from typing import Dict, List

ROMAN_HEADING = re.compile(r'^(?:[IVXLC]+\.|\d+(?:\.\d+)*)\s+', re.I)

CITATION_PATTERNS = [
    ('acordao', re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))?', re.I)),
    ('acordao', re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))', re.I)),
    ('sumula', re.compile(r'(?i)s[úu]mula\s*(?:tcu\s*)?(?:n[ºo°]\s*)?(?P<num>\d{1,4})', re.I)),
]

PIECE_SIGNAL_MAP = {
    'recurso': {'positive': [(r'interpor o presente recurso administrativo', 6), (r'recurso administrativo', 4), (r'decis[aã]o recorrida', 4), (r'provimento do recurso', 3), (r'reformar a decis[aã]o', 4), (r'ato recorrido', 3), (r'recorrente', 2), (r'raz[oõ]es recursais', 3)], 'negative': [(r'contrarraz[õo]es', -8), (r'n[aã]o provimento do recurso', -6), (r'impugna[cç][aã]o ao edital', -7)]},
    'contrarrazao': {'positive': [(r'apresenta\s+contrarraz[õo]es', 8), (r'contrarraz[õo]es', 7), (r'em face do recurso interposto', 5), (r'n[aã]o provimento do recurso', 7), (r'manuten[cç][aã]o da decis[aã]o', 7), (r'recorrido', 4)], 'negative': [(r'interpor o presente recurso administrativo', -8), (r'impugna[cç][aã]o ao edital', -7)]},
    'impugnacao': {'positive': [(r'impugna[cç][aã]o ao edital', 9), (r'impugnar o edital', 7), (r'cl[aá]usula restritiva', 5), (r'retifica[cç][aã]o do edital', 6), (r'suspens[aã]o do certame', 5), (r'ilegalidade do instrumento convocat[oó]rio', 5)], 'negative': [(r'contrarraz[õo]es', -8), (r'provimento do recurso', -4)]},
}

THESIS_KEYWORDS = {
    'formalismo_moderado': ['formalismo moderado', 'erro formal', 'v[ií]cio san[aá]vel', 'falha san[aá]vel', 'falha formal', 'baixa materialidade', 'excesso de formalismo'],
    'diligencia': ['dilig[eê]ncia', 'saneamento', 'oportunidade de comprova[cç][aã]o', 'esclarecimentos', 'sanar', 'franqueada oportunidade'],
    'inexequibilidade': ['inexequ[ií]vel', 'inexequibilidade', 'exequibilidade', 'proposta inexequ[ií]vel', 'planilha de custos'],
    'vinculacao_edital': ['vincula[cç][aã]o ao edital', 'instrumento convocat[oó]rio', 'exig[eê]ncia n[aã]o prevista', 'n[aã]o prevista no edital'],
    'competitividade': ['competitividade', 'ampla disputa', 'restri[cç][aã]o indevida', 'redu[cç][aã]o da competitividade', 'proposta mais vantajosa'],
    'habilitacao_capacidade': ['habilita[cç][aã]o', 'capacidade t[eé]cnica', 'atestado', 'qualifica[cç][aã]o t[eé]cnica'],
    'julgamento_objetivo': ['julgamento objetivo', 'crit[eé]rio subjetivo', 'subjetiva', 'razoabilidade', 'proporcionalidade'],
}

THESIS_LABEL_MAP = {
    'formalismo_moderado': 'Formalismo moderado e falha sanável',
    'diligencia': 'Necessidade de diligência',
    'inexequibilidade': 'Inexequibilidade e defesa da proposta',
    'vinculacao_edital': 'Vinculação ao edital',
    'competitividade': 'Competitividade e proposta mais vantajosa',
    'habilitacao_capacidade': 'Habilitação e capacidade técnica',
    'julgamento_objetivo': 'Julgamento objetivo',
    'geral': 'Tese geral',
}

USELESS_BLOCK_PATTERNS = [r'da tempestividade', r'do cabimento', r'dos pedidos', r'nestes termos', r'pede deferimento', r'qualifica[cç][aã]o da parte', r'síntese dos fatos', r'da tempestividade e do cabimento']



def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()



def classify_piece_type(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {k: 0 for k in PIECE_SIGNAL_MAP}
    hits = {k: [] for k in PIECE_SIGNAL_MAP}
    for kind, rules in PIECE_SIGNAL_MAP.items():
        for pat, weight in rules['positive']:
            if re.search(pat, lower, re.I):
                scores[kind] += weight
                hits[kind].append(re.sub(r'\\', '', pat))
        for pat, weight in rules['negative']:
            if re.search(pat, lower, re.I):
                scores[kind] += weight
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0
    delta = best_score - second_score
    confidence = 'alta' if best_score >= 8 and delta >= 3 else 'média' if best_score >= 4 else 'baixa'
    labels = {'recurso': 'Recurso administrativo', 'contrarrazao': 'Contrarrazão', 'impugnacao': 'Impugnação'}
    return {'tipo': labels[best], 'chave': best, 'confianca': confidence, 'score': best_score, 'fundamentos': ', '.join(hits[best][:5]) or 'classificação por estrutura textual'}



def extract_citations_with_context(text: str) -> List[Dict[str, str]]:
    citations = []
    seen = set()
    lines = [ln.strip() for ln in (text or '').splitlines()]
    for idx, line in enumerate(lines):
        if not line:
            continue
        for citation_type, pattern in CITATION_PATTERNS:
            for match in pattern.finditer(line):
                numero = (match.groupdict().get('num') or '').strip()
                ano = (match.groupdict().get('ano') or '').strip()
                colegiado = normalize_space(match.groupdict().get('colegiado') or '')
                raw = normalize_space(match.group(0))
                key = (citation_type, numero, ano, colegiado.lower(), raw.lower())
                if key in seen:
                    continue
                seen.add(key)
                context = ' '.join(x for x in lines[max(0, idx-1): min(len(lines), idx+3)] if x)
                citations.append({'tipo_citacao': citation_type, 'raw': raw, 'numero_acordao_num': numero if citation_type == 'acordao' else '', 'ano_acordao': ano if citation_type == 'acordao' else '', 'numero_sumula': numero if citation_type == 'sumula' else '', 'colegiado_citado': colegiado, 'contexto': normalize_space(context), 'linha': idx + 1})
    return citations



def detect_thesis(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {}
    hits = {}
    for thesis, patterns in THESIS_KEYWORDS.items():
        score = 0
        matched = []
        for pat in patterns:
            if re.search(pat, lower, re.I):
                score += 2
                matched.append(re.sub(r'\\', '', pat))
        scores[thesis] = score
        hits[thesis] = matched
    best = max(scores, key=scores.get) if scores else 'geral'
    return {'chave': best if scores.get(best, 0) > 0 else 'geral', 'label': THESIS_LABEL_MAP.get(best, 'Tese geral') if scores.get(best, 0) > 0 else THESIS_LABEL_MAP['geral'], 'score': scores.get(best, 0), 'fundamentos': hits.get(best, [])}



def split_into_argument_blocks(text: str, max_blocks: int = 12) -> List[Dict[str, str]]:
    blocks: List[str] = []
    current: List[str] = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            if current:
                blocks.append(normalize_space(' '.join(current)))
                current = []
            continue
        if ROMAN_HEADING.match(line) and current:
            blocks.append(normalize_space(' '.join(current)))
            current = [line]
        else:
            current.append(line)
        if len(' '.join(current)) > 1200:
            blocks.append(normalize_space(' '.join(current)))
            current = []
    if current:
        blocks.append(normalize_space(' '.join(current)))

    scored = []
    for block in blocks:
        lower = block.lower()
        if len(block) < 120:
            continue
        if any(re.search(pat, lower, re.I) for pat in USELESS_BLOCK_PATTERNS):
            continue
        thesis = detect_thesis(block)
        keyword_bonus = 1 if any(k in lower for k in ['acórdão', 'acordao', 'súmula', 'sumula', 'tcu']) else 0
        density = thesis['score'] + keyword_bonus + min(len(block) // 350, 2)
        if density <= 1:
            continue
        preview = block[:380].rsplit(' ', 1)[0] + '...' if len(block) > 380 else block
        scored.append({'texto': block, 'tese': thesis['label'], 'tese_chave': thesis['chave'], 'preview': preview, 'fundamentos': ', '.join(thesis['fundamentos'][:4]), 'score_tese': density})
    scored.sort(key=lambda x: x['score_tese'], reverse=True)
    return scored[:max_blocks]



def extract_piece_structure(text: str) -> Dict[str, object]:
    raw_lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    paragraphs = [normalize_space(p) for p in re.split(r'\n\s*\n+', text or '') if normalize_space(p)]
    citations = extract_citations_with_context(text)
    blocks = split_into_argument_blocks(text)
    principal = blocks[0] if blocks else {'tese': 'Tese geral', 'preview': normalize_space(text)[:420]}
    return {
        'titulo_inicial': raw_lines[0][:160] if raw_lines else '',
        'total_linhas': len(raw_lines),
        'total_paragrafos': len(paragraphs),
        'paragrafos_chave': paragraphs[:3],
        'citacoes': citations,
        'blocos_argumentativos': blocks,
        'tese_principal': principal.get('tese', 'Tese geral'),
        'resumo_inicial': principal.get('preview', ''),
    }



def short_quote_from_text(text: str, max_chars: int = 240) -> str:
    text = normalize_space(text)
    if not text:
        return ''
    first_sentence = re.split(r'(?<=[\.!?;])\s+', text)[0]
    if 60 <= len(first_sentence) <= max_chars:
        return first_sentence
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(' ', 1)[0].strip() + '...'
