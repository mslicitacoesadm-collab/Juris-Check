from __future__ import annotations

import re
from typing import Dict, List

ACORDAO_RE = re.compile(r'(?i)(?:tcu\s*,?\s*)?ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))?', re.I)
JURIS_RE = re.compile(r'(?i)jurisprud[êe]ncia\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})')
SUMULA_RE = re.compile(r'(?i)(?:s[úu]mula\s*(?:tcu)?\s*(?:n[ºo°]\s*)?)(?P<num>\d{1,4})')

THESIS_KEYWORDS = {
    'formalismo_moderado': ['formalismo moderado', 'erro formal', 'vício sanável', 'vicio sanavel', 'falha sanável', 'falha sanavel', 'mero formalismo', 'rigor excessivo'],
    'diligencia': ['diligência', 'diligencia', 'saneamento', 'esclarecimentos', 'sanar', 'oportunidade de comprovação', 'oportunidade de comprovacao', 'prévia diligência', 'previa diligencia'],
    'inexequibilidade': ['inexequível', 'inexequivel', 'inexequibilidade', 'exequibilidade', 'exequível', 'execução contratual'],
    'vinculacao_edital': ['vinculação ao edital', 'vinculacao ao edital', 'instrumento convocatório', 'instrumento convocatorio', 'exigência não prevista', 'exigencia nao prevista', 'lei interna do certame'],
    'competitividade': ['competitividade', 'ampla disputa', 'restrição indevida', 'restricao indevida', 'proposta mais vantajosa', 'vantajosidade', 'isonomia', 'seleção da proposta mais vantajosa'],
    'habilitacao_capacidade': ['habilitação', 'habilitacao', 'capacidade técnica', 'capacidade tecnica', 'atestado', 'qualificação técnica', 'qualificacao tecnica', 'aptidão', 'acervo técnico', 'acervo tecnico'],
    'julgamento_objetivo': ['julgamento objetivo', 'critério subjetivo', 'criterio subjetivo', 'razoabilidade', 'proporcionalidade', 'motivação suficiente', 'motivacao suficiente'],
}
THESIS_EXPANSIONS = {
    'formalismo_moderado': ['aproveitamento da proposta', 'saneamento', 'erro sanável', 'ausência de prejuízo'],
    'diligencia': ['esclarecimento', 'complementação documental', 'vedação ao formalismo excessivo', 'saneamento de falhas'],
    'competitividade': ['ampla concorrência', 'interesse público', 'vantajosidade', 'economia processual'],
    'habilitacao_capacidade': ['objeto similar', 'compatibilidade do atestado', 'qualificação econômico-financeira'],
}
THESIS_LABEL_MAP = {
    'formalismo_moderado': 'Formalismo moderado',
    'diligencia': 'Diligência prévia',
    'inexequibilidade': 'Inexequibilidade',
    'vinculacao_edital': 'Vinculação ao edital',
    'competitividade': 'Competitividade e vantajosidade',
    'habilitacao_capacidade': 'Habilitação e capacidade técnica',
    'julgamento_objetivo': 'Julgamento objetivo',
    'geral': 'Tese geral',
}
PIECE_SIGNAL_MAP = {
    'recurso': [('recurso administrativo', 4), ('decisão recorrida', 3), ('provimento do recurso', 4), ('razões recursais', 3)],
    'contrarrazao': [('contrarrazões', 6), ('não provimento do recurso', 5), ('manutenção da decisão', 4)],
    'impugnacao': [('impugnação ao edital', 7), ('retificação do edital', 5), ('suspensão do certame', 4)],
}


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def tokenize(text: str) -> List[str]:
    return re.findall(r'[a-zà-ÿ0-9]{3,}', (text or '').lower())


def classify_piece_type(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {'recurso': 0, 'contrarrazao': 0, 'impugnacao': 0}
    for kind, patterns in PIECE_SIGNAL_MAP.items():
        for pat, weight in patterns:
            if pat in lower:
                scores[kind] += weight
    best = max(scores, key=scores.get)
    labels = {'recurso': 'Recurso administrativo', 'contrarrazao': 'Contrarrazão', 'impugnacao': 'Impugnação'}
    confidence = 'alta' if scores[best] >= 6 else 'média' if scores[best] >= 3 else 'baixa'
    return {'tipo': labels[best], 'chave': best, 'confianca': confidence, 'score': scores[best], 'fundamentos': 'classificação por sinais textuais'}


def extract_references_with_context(text: str) -> List[Dict[str, str]]:
    refs = []
    seen = set()
    lines = [ln.strip() for ln in (text or '').splitlines()]
    for idx, line in enumerate(lines):
        if not line:
            continue
        context = ' '.join(x for x in lines[max(0, idx-1): min(len(lines), idx+3)] if x)
        for kind, pattern in [('acordao', ACORDAO_RE), ('jurisprudencia', JURIS_RE), ('sumula', SUMULA_RE)]:
            for m in pattern.finditer(line):
                numero = (m.groupdict().get('num') or '').strip()
                ano = (m.groupdict().get('ano') or '').strip()
                colegiado = normalize_space(m.groupdict().get('colegiado') or '')
                raw = normalize_space(m.group(0))
                key = (kind, numero, ano, colegiado.lower(), raw.lower(), idx)
                if key in seen:
                    continue
                seen.add(key)
                refs.append({'kind': kind, 'raw': raw, 'numero': numero, 'ano': ano, 'colegiado': colegiado, 'contexto': normalize_space(context), 'linha': idx + 1})
    return refs


def detect_thesis(text: str) -> Dict[str, str | int]:
    lower = (text or '').lower()
    scores = {k: 0 for k in THESIS_KEYWORDS}
    hits = {k: [] for k in THESIS_KEYWORDS}
    for thesis, patterns in THESIS_KEYWORDS.items():
        for pat in patterns:
            if pat in lower:
                gain = 3 if ' ' in pat else 2
                scores[thesis] += gain
                hits[thesis].append(pat)
        for pat in THESIS_EXPANSIONS.get(thesis, []):
            if pat in lower:
                scores[thesis] += 1
                hits[thesis].append(pat)
    # small cross-signal bonus
    if scores['formalismo_moderado'] and scores['diligencia']:
        scores['formalismo_moderado'] += 2
        scores['diligencia'] += 2
    if scores['competitividade'] and scores['diligencia']:
        scores['competitividade'] += 1
    best = max(scores, key=scores.get) if scores else 'geral'
    if scores.get(best, 0) == 0:
        best = 'geral'
    return {'chave': best, 'label': THESIS_LABEL_MAP.get(best, 'Tese geral'), 'score': scores.get(best, 0), 'fundamentos': hits.get(best, [])}


def split_into_argument_blocks(text: str, max_blocks: int = 10) -> List[Dict[str, str]]:
    raw_blocks = re.split(r'\n\s*\n+', text or '')
    blocks: List[Dict[str, str]] = []
    for order, raw in enumerate(raw_blocks):
        block = normalize_space(raw)
        if len(block) < 120:
            continue
        thesis = detect_thesis(block)
        if thesis['chave'] == 'geral' and len(block) < 220:
            continue
        preview = block[:320].rsplit(' ', 1)[0] + '...' if len(block) > 320 else block
        blocks.append({
            'id': order,
            'texto': block,
            'tese': thesis['label'],
            'tese_chave': thesis['chave'],
            'preview': preview,
            'score_tese': thesis['score'],
            'fundamentos': ', '.join(thesis['fundamentos'][:5]),
        })
        if len(blocks) >= max_blocks:
            break
    return blocks


def short_quote_from_text(text: str, max_chars: int = 220) -> str:
    clean = re.sub(r'<[^>]+>', ' ', text or '')
    clean = normalize_space(clean)
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rsplit(' ', 1)[0] + '...'
