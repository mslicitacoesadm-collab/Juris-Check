from __future__ import annotations
import re

REF_RE = re.compile(r'(?P<kind>Ac[oó]rd[aã]o|S[úu]mula|Jurisprud[eê]ncia)\s*(?:n[ºo.]*)?\s*(?P<num>\d{1,6})(?:[./-](?P<year>\d{4}))?(?:\s*[-–]\s*(?P<court>TCU|STJ|STF|Plen[aá]rio|1[ªa]\s*C[aâ]mara|2[ªa]\s*C[aâ]mara))?', re.I)


def _clean(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()


def classify_piece_type(text: str):
    t = (text or '').lower()
    if 'impugna' in t: tipo = 'Impugnação'
    elif 'contrarraz' in t: tipo = 'Contrarrazões'
    elif 'recurso' in t: tipo = 'Recurso administrativo'
    else: tipo = 'Peça jurídica'
    return {'tipo': tipo, 'confidence': 'média'}


def detect_thesis(text: str):
    low = (text or '').lower()
    mapping = [
        ('inexequibilidade', 'Inexequibilidade e diligência'),
        ('diligência', 'Diligência saneadora'),
        ('falha sanável', 'Falha sanável'),
        ('formalismo', 'Formalismo moderado'),
        ('lote único', 'Parcelamento/lote único'),
        ('qualificação técnica', 'Qualificação técnica'),
        ('habilitação', 'Habilitação'),
    ]
    for k, v in mapping:
        if k in low: return v
    return 'Tese geral de licitações'


def extract_references_with_context(text: str):
    refs = []
    txt = text or ''
    for m in REF_RE.finditer(txt):
        start, end = max(0, m.start()-320), min(len(txt), m.end()+320)
        before = txt[:m.start()]
        line = before.count('\n') + 1
        kind = m.group('kind').lower()
        if 'súm' in kind or 'sum' in kind: kind_norm = 'sumula'
        elif 'juris' in kind: kind_norm = 'jurisprudencia'
        else: kind_norm = 'acordao'
        refs.append({
            'raw': _clean(m.group(0)),
            'kind': kind_norm,
            'numero': m.group('num') or '',
            'ano': m.group('year') or '',
            'colegiado': _clean(m.group('court') or ''),
            'contexto': _clean(txt[start:end]),
            'linha': line,
            'tese': detect_thesis(txt[start:end]),
        })
    # dedup preservando ordem
    seen, out = set(), []
    for r in refs:
        key = (r['kind'], r['numero'], r['ano'], r['raw'].lower())
        if key not in seen:
            seen.add(key); out.append(r)
    return out


def split_into_argument_blocks(text: str, max_blocks: int = 6):
    parts = [p.strip() for p in re.split(r'\n\s*\n+', text or '') if len(p.strip()) > 80]
    if not parts:
        parts = [text[:1800]] if text else []
    out = []
    for p in parts[:max_blocks]:
        tese = detect_thesis(p)
        out.append({'texto': p, 'text': p, 'tese': tese, 'title': tese, 'tese_chave': tese.lower(), 'preview': _clean(p[:360]), 'fundamentos': tese})
    return out


def parse_manual_query(query: str):
    m = REF_RE.search(query or '')
    if m:
        return {'kind': 'acordao', 'numero': m.group('num'), 'ano': m.group('year') or '', 'colegiado': m.group('court') or '', 'thesis_label': detect_thesis(query)}
    return {'kind': 'tese', 'numero': '', 'ano': '', 'colegiado': '', 'thesis_label': detect_thesis(query)}
