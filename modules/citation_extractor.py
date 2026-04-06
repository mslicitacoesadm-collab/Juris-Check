from __future__ import annotations

import re
from typing import Dict, List

ROMAN_HEADING = re.compile(r'^(?:[IVXLC]+\.|\d+(?:\.\d+)*)\s+', re.I)

CITATION_PATTERNS = [
    re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))?', re.I),
    re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))', re.I),
]

PIECE_SIGNAL_MAP = {
    'recurso': {
        'positive': [
            (r'interpor o presente recurso administrativo', 6),
            (r'recurso administrativo', 4),
            (r'decis[aã]o recorrida', 4),
            (r'provimento do recurso', 3),
            (r'reformar a decis[aã]o', 4),
            (r'ato recorrido', 3),
            (r'recorrente', 2),
            (r'raz[oõ]es recursais', 3),
            (r'reforma da desclassifica[cç][aã]o', 3),
        ],
        'negative': [
            (r'contrarraz[õo]es', -8),
            (r'n[aã]o provimento do recurso', -6),
            (r'impugna[cç][aã]o ao edital', -7),
            (r'manuten[cç][aã]o da decis[aã]o recorrida', -5),
        ],
    },
    'contrarrazao': {
        'positive': [
            (r'apresenta\s+contrarraz[õo]es', 8),
            (r'contrarraz[õo]es', 7),
            (r'em face do recurso interposto', 5),
            (r'n[aã]o provimento do recurso', 7),
            (r'manuten[cç][aã]o da decis[aã]o', 7),
            (r'manter a decis[aã]o recorrida', 5),
            (r'recorrido', 4),
            (r'impugna os argumentos recursais', 4),
            (r'improcede o recurso', 4),
            (r'rejei[cç][aã]o do recurso', 4),
        ],
        'negative': [
            (r'interpor o presente recurso administrativo', -8),
            (r'impugna[cç][aã]o ao edital', -7),
        ],
    },
    'impugnacao': {
        'positive': [
            (r'impugna[cç][aã]o ao edital', 9),
            (r'impugnar o edital', 7),
            (r'cl[aá]usula restritiva', 5),
            (r'retifica[cç][aã]o do edital', 6),
            (r'suspens[aã]o do certame', 5),
            (r'ilegalidade do instrumento convocat[oó]rio', 5),
            (r'edital deve ser retificado', 5),
            (r'exig[eê]ncia n[aã]o prevista no edital', 4),
        ],
        'negative': [
            (r'contrarraz[õo]es', -8),
            (r'decis[aã]o recorrida', -3),
            (r'provimento do recurso', -4),
        ],
    },
}

THESIS_KEYWORDS = {
    'formalismo_moderado': ['formalismo moderado', 'erro formal', 'v[ií]cio san[aá]vel', 'falha formal', 'baixa materialidade'],
    'diligencia': ['dilig[eê]ncia', 'saneamento', 'oportunidade de comprova[cç][aã]o', 'esclarecimentos', 'sanar', 'franqueada oportunidade'],
    'inexequibilidade': ['inexequ[ií]vel', 'inexequibilidade', 'exequibilidade', 'proposta inexequ[ií]vel'],
    'vinculacao_edital': ['vincula[cç][aã]o ao edital', 'instrumento convocat[oó]rio', 'exig[eê]ncia n[aã]o prevista', 'n[aã]o prevista no edital'],
    'competitividade': ['competitividade', 'ampla disputa', 'restri[cç][aã]o indevida', 'redu[cç][aã]o da competitividade', 'proposta mais vantajosa'],
    'habilitacao_capacidade': ['habilita[cç][aã]o', 'capacidade t[eé]cnica', 'atestado', 'qualifica[cç][aã]o t[eé]cnica'],
    'julgamento_objetivo': ['julgamento objetivo', 'crit[eé]rio subjetivo', 'subjetiva', 'razoabilidade', 'proporcionalidade'],
}

THESIS_LABEL_MAP = {
    'formalismo_moderado': 'Formalismo moderado',
    'diligencia': 'Diligência prévia',
    'inexequibilidade': 'Inexequibilidade',
    'vinculacao_edital': 'Vinculação ao edital',
    'competitividade': 'Competitividade',
    'habilitacao_capacidade': 'Habilitação e capacidade técnica',
    'julgamento_objetivo': 'Julgamento objetivo',
    'geral': 'Tese geral',
}

USELESS_BLOCK_PATTERNS = [
    r'da tempestividade', r'do cabimento', r'dos pedidos', r'nestes termos', r'pede deferimento',
    r'qualifica[cç][aã]o da parte', r'ao ilustri', r'secret[aá]rio', r'síntese dos fatos', r'da ausência de prejuízo',
    r'da tempestividade e do cabimento', r'da s[íi]ntese dos fatos', r'vi\.? dos pedidos'
]


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
    fundamentos = ', '.join(hits[best][:5]) or 'classificação por estrutura textual'
    return {
        'tipo': labels[best],
        'chave': best,
        'confianca': confidence,
        'score': best_score,
        'fundamentos': fundamentos,
    }



def extract_citations_with_context(text: str) -> List[Dict[str, str]]:
    citations = []
    seen = set()
    lines = [ln.strip() for ln in (text or '').splitlines()]
    for idx, line in enumerate(lines):
        if not line:
            continue
        for pattern in CITATION_PATTERNS:
            for match in pattern.finditer(line):
                numero = (match.groupdict().get('num') or '').strip()
                ano = (match.groupdict().get('ano') or '').strip()
                colegiado = normalize_space(match.groupdict().get('colegiado') or '')
                raw = normalize_space(match.group(0))
                key = (numero, ano, colegiado.lower(), raw.lower())
                if key in seen:
                    continue
                seen.add(key)
                context = ' '.join(x for x in lines[max(0, idx-1): min(len(lines), idx+3)] if x)
                citations.append({
                    'raw': raw,
                    'numero_acordao_num': numero,
                    'ano_acordao': ano,
                    'colegiado_citado': colegiado,
                    'contexto': normalize_space(context),
                    'linha': idx + 1,
                })
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
    if not scores:
        return {'chave': 'geral', 'label': THESIS_LABEL_MAP['geral'], 'score': 0, 'fundamentos': []}
    best = max(scores, key=scores.get)
    return {'chave': best, 'label': THESIS_LABEL_MAP.get(best, 'Tese geral'), 'score': scores.get(best, 0), 'fundamentos': hits.get(best, [])}



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
        if len(' '.join(current)) > 1000:
            blocks.append(normalize_space(' '.join(current)))
            current = []
    if current:
        blocks.append(normalize_space(' '.join(current)))

    results = []
    for block in blocks:
        lower = block.lower()
        if len(block) < 140:
            continue
        if any(re.search(pat, lower, re.I) for pat in USELESS_BLOCK_PATTERNS):
            continue
        thesis = detect_thesis(block)
        if thesis['score'] <= 0:
            continue
        preview = block[:360].rsplit(' ', 1)[0] + '...' if len(block) > 360 else block
        results.append({
            'texto': block,
            'tese': thesis['label'],
            'tese_chave': thesis['chave'],
            'preview': preview,
            'fundamentos': ', '.join(thesis['fundamentos'][:3]),
            'score_tese': thesis['score'],
        })
        if len(results) >= max_blocks:
            break
    return results



def short_quote_from_text(text: str, max_chars: int = 240) -> str:
    text = normalize_space(text)
    if not text:
        return ''
    first_sentence = re.split(r'(?<=[\.!?;])\s+', text)[0]
    if 60 <= len(first_sentence) <= max_chars:
        return first_sentence
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(' ', 1)[0].strip()
    return clipped + '...'
