from __future__ import annotations

import re
from typing import Dict, List

CITATION_PATTERNS = [
    re.compile(r'(?i)ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[/\\-]\s*(?P<ano>20\d{2})'),
    re.compile(r'(?i)ac[óo]rd[aã]o\s*(?:n[ºo°]\s*)?(?P<num>\d{1,5})\s*[-–]\s*(?:tcu\s*[-–]\s*)?(?P<colegiado>plen[aá]rio|1[ªa]\s*c[aâ]mara|2[ªa]\s*c[aâ]mara)'),
]


def extract_citations(text: str) -> List[Dict[str, str]]:
    found = []
    seen = set()
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text or ''):
            raw = match.group(0).strip()
            numero = (match.groupdict().get('num') or '').strip()
            ano = (match.groupdict().get('ano') or '').strip()
            key = (raw.lower(), numero, ano)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                'raw': raw,
                'numero_acordao_num': numero,
                'ano_acordao': ano,
            })
    return found


def split_into_blocks(text: str, max_blocks: int = 25) -> List[str]:
    chunks = []
    current = []
    for line in (text or '').splitlines():
        clean = line.strip()
        if not clean:
            if current:
                chunks.append(' '.join(current).strip())
                current = []
            continue
        current.append(clean)
        if len(' '.join(current)) > 900:
            chunks.append(' '.join(current).strip())
            current = []
    if current:
        chunks.append(' '.join(current).strip())
    return [c for c in chunks[:max_blocks] if c]
