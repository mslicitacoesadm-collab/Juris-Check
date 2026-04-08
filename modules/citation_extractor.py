from __future__ import annotations

import re
import unicodedata
from typing import Dict, List


ACORDAO_RE = re.compile(
    r"(?i)(?:tcu\s*,?\s*)?(?:ac[óo]rd[aã]o(?:\s+de\s+rela[cç][aã]o)?|ac)\s*(?:n[ºo°.]?\s*)?(?P<num>\d{1,5}(?:\.\d{3})?)\s*[/\\-]\s*(?P<ano>19\d{2}|20\d{2})(?:\s*[–-]\s*(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara|primeira\s*c[aâ]mara|segunda\s*c[aâ]mara))?",
    re.I,
)
JURIS_RE = re.compile(r"(?i)jurisprud[êe]ncia\s*(?:n[ºo°.]?\s*)?(?P<num>\d{1,5}(?:\.\d{3})?)\s*[/\\-]\s*(?P<ano>19\d{2}|20\d{2})")
SUMULA_RE = re.compile(r"(?i)(?:s[úu]mula\s*(?:tcu)?\s*(?:n[ºo°.]?\s*)?)(?P<num>\d{1,4})")
GENERIC_REF_RE = re.compile(r"(?i)(?P<num>\d{1,5}(?:\.\d{3})?)\s*[/\\-]\s*(?P<ano>19\d{2}|20\d{2})")

THESIS_KEYWORDS = {
    'formalismo_moderado': ['formalismo moderado', 'erro formal', 'vício sanável', 'vicio sanavel', 'falha sanável', 'falha sanavel', 'mero formalismo', 'rigor excessivo'],
    'diligencia': ['diligência', 'diligencia', 'saneamento', 'esclarecimentos', 'sanar', 'oportunidade de comprovação', 'oportunidade de comprovacao', 'prévia diligência', 'previa diligencia'],
    'inexequibilidade': ['inexequível', 'inexequivel', 'inexequibilidade', 'exequibilidade', 'exequível', 'execução contratual', 'preço inexequível', 'preco inexequivel'],
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
    'recurso': [('recurso administrativo', 4), ('decisão recorrida', 3), ('decisao recorrida', 3), ('provimento do recurso', 4), ('razões recursais', 3), ('razoes recursais', 3)],
    'contrarrazao': [('contrarrazões', 6), ('contrarrazoes', 6), ('não provimento do recurso', 5), ('nao provimento do recurso', 5), ('manutenção da decisão', 4), ('manutencao da decisao', 4)],
    'impugnacao': [('impugnação ao edital', 7), ('impugnacao ao edital', 7), ('retificação do edital', 5), ('retificacao do edital', 5), ('suspensão do certame', 4), ('suspensao do certame', 4)],
    'representacao': [('representação', 4), ('representacao', 4), ('tribunal de contas', 2), ('medida cautelar', 3)],
    'diligencia_resposta': [('em resposta à diligência', 5), ('em resposta a diligencia', 5), ('atendimento à diligência', 5), ('atendimento a diligencia', 5)],
}


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def strip_accents(text: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text or '') if not unicodedata.combining(ch))


def normalize_simple(text: str) -> str:
    return normalize_space(strip_accents(text).lower())


def normalize_num(token: str) -> str:
    return re.sub(r'\D', '', token or '')


def normalize_colegiado(text: str) -> str:
    txt = normalize_simple(text)
    txt = txt.replace('1a camara', 'primeira camara').replace('2a camara', 'segunda camara')
    txt = txt.replace('1ª camara', 'primeira camara').replace('2ª camara', 'segunda camara')
    if 'plenario' in txt:
        return 'plenario'
    if 'primeira camara' in txt:
        return 'primeira camara'
    if 'segunda camara' in txt:
        return 'segunda camara'
    return txt


def tokenize(text: str) -> List[str]:
    return re.findall(r'[a-zà-ÿ0-9]{3,}', (text or '').lower())


def classify_piece_type(text: str) -> Dict[str, str | int]:
    lower = normalize_simple(text)
    scores = {k: 0 for k in PIECE_SIGNAL_MAP}
    for kind, patterns in PIECE_SIGNAL_MAP.items():
        for pat, weight in patterns:
            if normalize_simple(pat) in lower:
                scores[kind] += weight
    best = max(scores, key=scores.get)
    labels = {
        'recurso': 'Recurso administrativo',
        'contrarrazao': 'Contrarrazão',
        'impugnacao': 'Impugnação',
        'representacao': 'Representação',
        'diligencia_resposta': 'Resposta à diligência',
    }
    confidence = 'alta' if scores[best] >= 6 else 'média' if scores[best] >= 3 else 'baixa'
    return {'tipo': labels[best], 'chave': best, 'confianca': confidence, 'score': scores[best], 'fundamentos': 'classificação por sinais textuais ponderados'}


def parse_manual_query(text: str) -> Dict[str, str | bool | list]:
    raw = normalize_space(text)
    lower = normalize_simple(raw)
    kind = 'acordao'
    if 'sumula' in lower or 'súmula' in raw.lower():
        kind = 'sumula'
    elif 'jurisprud' in lower:
        kind = 'jurisprudencia'
    elif 'acord' in lower or 'ac ' in lower or ' tcu ' in f' {lower} ':
        kind = 'acordao'

    tribunal = 'TCU' if 'tcu' in lower else ''
    colegiado = ''
    for token in ['plenário', 'plenario', '1ª câmara', '1a camara', 'primeira câmara', 'primeira camara', '2ª câmara', '2a camara', 'segunda câmara', 'segunda camara']:
        if normalize_simple(token) in lower:
            colegiado = token
            break

    numero = ''
    ano = ''
    explicit = False
    m = SUMULA_RE.search(raw) if kind == 'sumula' else None
    if m:
        numero = normalize_num(m.group('num'))
        explicit = True
    else:
        for pat in [ACORDAO_RE, JURIS_RE, GENERIC_REF_RE]:
            m = pat.search(raw)
            if m:
                numero = normalize_num(m.groupdict().get('num') or '')
                ano = normalize_num(m.groupdict().get('ano') or '')
                if not colegiado:
                    colegiado = m.groupdict().get('colegiado') or ''
                explicit = True
                break

    residual = lower
    if numero and ano:
        residual = residual.replace(f'{numero}/{ano}', ' ')
        residual = residual.replace(f'{numero}-{ano}', ' ')
    for word in ['acordao', 'acordão', 'sumula', 'súmula', 'jurisprudencia', 'nº', 'n°', 'numero', 'tcu']:
        residual = residual.replace(normalize_simple(word), ' ')
    residual = normalize_space(residual)
    thesis = detect_thesis(raw)
    return {
        'raw': raw,
        'kind': kind,
        'numero': numero,
        'ano': ano,
        'tribunal': tribunal,
        'colegiado': colegiado,
        'colegiado_norm': normalize_colegiado(colegiado),
        'reference_mode': bool(numero),
        'exact_reference_detected': explicit,
        'residual_text': residual,
        'thesis_key': thesis.get('chave', 'geral'),
        'thesis_label': thesis.get('label', 'Tese geral'),
        'fundamentos_tese': thesis.get('fundamentos', []),
    }


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
                numero = normalize_num((m.groupdict().get('num') or '').strip())
                ano = normalize_num((m.groupdict().get('ano') or '').strip())
                colegiado = normalize_space(m.groupdict().get('colegiado') or '')
                raw = normalize_space(m.group(0))
                key = (kind, numero, ano, normalize_colegiado(colegiado), raw.lower(), idx)
                if key in seen:
                    continue
                seen.add(key)
                refs.append({'kind': kind, 'raw': raw, 'numero': numero, 'ano': ano, 'colegiado': colegiado, 'contexto': normalize_space(context), 'linha': idx + 1})
    return refs


def detect_thesis(text: str) -> Dict[str, str | int]:
    lower = normalize_simple(text)
    scores = {k: 0 for k in THESIS_KEYWORDS}
    hits = {k: [] for k in THESIS_KEYWORDS}
    for thesis, patterns in THESIS_KEYWORDS.items():
        for pat in patterns:
            norm = normalize_simple(pat)
            if norm in lower:
                gain = 3 if ' ' in norm else 2
                scores[thesis] += gain
                hits[thesis].append(pat)
        for pat in THESIS_EXPANSIONS.get(thesis, []):
            if normalize_simple(pat) in lower:
                scores[thesis] += 1
                hits[thesis].append(pat)
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
