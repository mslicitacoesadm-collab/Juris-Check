from __future__ import annotations

import re
from typing import Dict, List

from .thesis_analyzer import infer_theses_for_block

CITATION_PATTERN = re.compile(r'(?i)ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\-–]\s*(?P<ano>20\d{2})')
TITLE_RE = re.compile(r'^(?:[IVXLCDM]+\.|\d+(?:\.\d+)*\.?|[A-ZÇÁÀÃÉÊÍÓÔÕÚ0-9\s\-]{8,})$')

NEGATIVE_BLOCKS = (
    'tempestividade', 'cabimento', 'dos pedidos', 'pede deferimento', 'nestes termos',
    'síntese dos fatos', 'sintese dos fatos', 'qualificação', 'qualificacao'
)


def extract_citations(text: str) -> List[Dict[str, str]]:
    found = []
    seen = set()
    for match in CITATION_PATTERN.finditer(text or ''):
        raw = match.group(0).strip()
        numero = (match.group('num') or '').strip()
        ano = (match.group('ano') or '').strip()
        key = (numero, ano)
        if key in seen:
            continue
        seen.add(key)
        found.append({'raw': raw, 'numero_acordao_num': numero, 'ano_acordao': ano})
    return found


def _is_heading(line: str) -> bool:
    clean = ' '.join(line.split()).strip()
    if not clean or len(clean) > 120:
        return False
    return bool(TITLE_RE.match(clean))


def split_sections(text: str) -> List[dict]:
    lines = [line.strip() for line in (text or '').splitlines()]
    sections: List[dict] = []
    current_title = 'Trecho inicial'
    current_lines: List[str] = []

    for line in lines:
        if not line:
            if current_lines:
                current_lines.append('')
            continue
        if _is_heading(line):
            if current_lines:
                sections.append({'titulo': current_title, 'texto': '\n'.join(current_lines).strip()})
                current_lines = []
            current_title = line
            continue
        current_lines.append(line)
    if current_lines:
        sections.append({'titulo': current_title, 'texto': '\n'.join(current_lines).strip()})
    return sections


def _compact_paragraphs(text: str) -> List[str]:
    paragraphs = []
    bucket: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            if bucket:
                paragraphs.append(' '.join(bucket).strip())
                bucket = []
            continue
        bucket.append(' '.join(line.split()))
        if len(' '.join(bucket)) > 700:
            paragraphs.append(' '.join(bucket).strip())
            bucket = []
    if bucket:
        paragraphs.append(' '.join(bucket).strip())
    return paragraphs


def build_argument_blocks(text: str, max_blocks: int = 14) -> List[dict]:
    sections = split_sections(text)
    blocks: List[dict] = []
    order = 0
    for section in sections:
        title = section['titulo']
        title_lower = title.lower()
        for paragraph in _compact_paragraphs(section['texto']):
            lower = paragraph.lower()
            if len(paragraph) < 120:
                continue
            if any(neg in lower or neg in title_lower for neg in NEGATIVE_BLOCKS):
                continue
            theses = infer_theses_for_block(f'{title}\n{paragraph}')
            if not theses:
                continue
            order += 1
            blocks.append({
                'id': f'bloco_{order}',
                'titulo_secao': title,
                'texto': paragraph,
                'theses': theses,
                'score': sum(t['score'] for t in theses),
            })
    blocks.sort(key=lambda x: (x['score'], len(x['texto'])), reverse=True)
    return blocks[:max_blocks]
