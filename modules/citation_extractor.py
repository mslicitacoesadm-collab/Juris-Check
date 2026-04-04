from __future__ import annotations

import re
from typing import Dict, List

ROMAN_HEADING = re.compile(r'^(?:[IVXLC]+\.|\d+(?:\.\d+)*)\s+', re.I)

CITATION_PATTERNS = [
    re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))?', re.I),
    re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))', re.I),
]

PIECE_PATTERNS = {
    'recurso': [
        r'recurso administrativo', r'interpor o presente recurso', r'decis[aã]o recorrida', r'provimento do recurso',
        r'reformar a decis[aã]o', r'ato de desclassifica[cç][aã]o',
    ],
    'contrarrazao': [
        r'contrarraz[õo]es', r'em face do recurso interposto', r'n[aã]o provimento do recurso',
        r'manuten[cç][aã]o da decis[aã]o', r'impugna os argumentos recursais',
    ],
    'impugnacao': [
        r'impugna[cç][aã]o ao edital', r'impugnar o edital', r'cl[aá]usula restritiva',
        r'retifica[cç][aã]o do edital', r'suspens[aã]o do certame',
    ],
}

THESIS_KEYWORDS = {
    'formalismo_moderado': ['formalismo moderado', 'erro formal', 'v[ií]cio san[aá]vel', 'falha formal', 'baixa materialidade'],
    'diligencia': ['dilig[eê]ncia', 'saneamento', 'oportunidade de comprova[cç][aã]o', 'esclarecimentos'],
    'inexequibilidade': ['inexequ[ií]vel', 'inexequibilidade', 'exequibilidade', 'proposta inexequ[ií]vel'],
    'vinculacao_edital': ['vincula[cç][aã]o ao edital', 'instrumento convocat[oó]rio', 'exig[eê]ncia n[aã]o prevista', 'n[aã]o prevista no edital'],
    'competitividade': ['competitividade', 'ampla disputa', 'restri[cç][aã]o indevida', 'redu[cç][aã]o da competitividade'],
    'habilitacao_capacidade': ['habilita[cç][aã]o', 'capacidade t[eé]cnica', 'atestado', 'qualifica[cç][aã]o t[eé]cnica'],
    'julgamento_objetivo': ['julgamento objetivo', 'crit[eé]rio subjetivo', 'subjetiva', 'razoabilidade', 'proporcionalidade'],
}

USELESS_BLOCK_PATTERNS = [
    r'da tempestividade', r'do cabimento', r'dos pedidos', r'nestes termos', r'pede deferimento',
    r'qualifica[cç][aã]o da parte', r'secret[aá]rio',
]


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def classify_piece_type(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {k: 0 for k in PIECE_PATTERNS}
    hits = {k: [] for k in PIECE_PATTERNS}
    for kind, patterns in PIECE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower, re.I):
                scores[kind] += 2
                hits[kind].append(pat)
    # structural hints
    if 'recurso' in lower and 'contrarraz' not in lower:
        scores['recurso'] += 1
    if 'contrarraz' in lower:
        scores['contrarrazao'] += 3
    if 'impugna' in lower and 'edital' in lower:
        scores['impugnacao'] += 3
    best = max(scores, key=scores.get)
    confidence = 'alta' if scores[best] >= 4 else 'média' if scores[best] >= 2 else 'baixa'
    labels = {'recurso': 'Recurso administrativo', 'contrarrazao': 'Contrarrazão', 'impugnacao': 'Impugnação'}
    return {
        'tipo': labels[best],
        'chave': best,
        'confianca': confidence,
        'score': scores[best],
        'fundamentos': ', '.join(hits[best][:4]) or 'classificação por estrutura textual',
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
                raw = normalize_space(match.group(0))
                key = (numero, ano, raw.lower())
                if key in seen:
                    continue
                seen.add(key)
                context = ' '.join(x for x in lines[max(0, idx-1): min(len(lines), idx+3)] if x)
                citations.append({
                    'raw': raw,
                    'numero_acordao_num': numero,
                    'ano_acordao': ano,
                    'contexto': normalize_space(context),
                    'linha': idx + 1,
                })
    return citations


def detect_thesis(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {}
    for thesis, patterns in THESIS_KEYWORDS.items():
        score = 0
        for pat in patterns:
            if re.search(pat, lower, re.I):
                score += 2
        scores[thesis] = score
    best = max(scores, key=scores.get) if scores else 'geral'
    label_map = {
        'formalismo_moderado': 'Formalismo moderado',
        'diligencia': 'Diligência prévia',
        'inexequibilidade': 'Inexequibilidade',
        'vinculacao_edital': 'Vinculação ao edital',
        'competitividade': 'Competitividade',
        'habilitacao_capacidade': 'Habilitação e capacidade técnica',
        'julgamento_objetivo': 'Julgamento objetivo',
        'geral': 'Tese geral',
    }
    return {'chave': best, 'label': label_map.get(best, 'Tese geral'), 'score': scores.get(best, 0)}


def split_into_argument_blocks(text: str, max_blocks: int = 16) -> List[Dict[str, str]]:
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
        if len(' '.join(current)) > 850:
            blocks.append(normalize_space(' '.join(current)))
            current = []
    if current:
        blocks.append(normalize_space(' '.join(current)))

    results = []
    for block in blocks:
        lower = block.lower()
        if len(block) < 120:
            continue
        if any(re.search(pat, lower, re.I) for pat in USELESS_BLOCK_PATTERNS):
            continue
        thesis = detect_thesis(block)
        if thesis['score'] <= 0:
            continue
        preview = block[:360].rsplit(' ', 1)[0] + '...' if len(block) > 360 else block
        results.append({'texto': block, 'tese': thesis['label'], 'tese_chave': thesis['chave'], 'preview': preview})
        if len(results) >= max_blocks:
            break
    return results


def short_quote_from_text(text: str, max_chars: int = 220) -> str:
    text = normalize_space(text)
    if not text:
        return ''
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(' ', 1)[0].strip()
    return clipped + '...'
