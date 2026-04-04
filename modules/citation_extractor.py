import re
from typing import Dict, List

CITATION_PATTERNS = [
    r"\bAc[oó]rd[aã]o\s*(?:n[ºo°]\s*)?(\d{1,5})\s*/\s*(20\d{2})",
    r"\bAc[oó]rd[aã]o\s*(\d{1,5})\s*-\s*(?:TCU\s*-\s*)?(?:Plen[aá]rio|1[ªa]\s*C[aâ]mara|2[ªa]\s*C[aâ]mara)",
    r"\b(\d{1,5})\s*/\s*(20\d{2})\s*-\s*TCU\s*-\s*(?:Plen[aá]rio|1[ªa]\s*C[aâ]mara|2[ªa]\s*C[aâ]mara)",
]

def extract_citations(text: str) -> List[Dict[str, str]]:
    citations = []
    seen = set()
    for pattern in CITATION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            numero = ""
            ano = ""
            num_match = re.search(r"(\d{1,5})\s*/\s*(20\d{2})", raw)
            if num_match:
                numero = num_match.group(1)
                ano = num_match.group(2)
            else:
                num_alt = re.search(r"Ac[oó]rd[aã]o\s*(\d{1,5})", raw, flags=re.IGNORECASE)
                if num_alt:
                    numero = num_alt.group(1)
            citations.append({
                "raw": raw,
                "numero_acordao_num": numero,
                "ano_acordao": ano,
            })
    return citations

def split_into_blocks(text: str, max_blocks: int = 25, min_chars: int = 220) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    blocks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 1 < 1200:
            current += ("\n" if current else "") + p
        else:
            if current:
                blocks.append(current.strip())
            current = p
    if current:
        blocks.append(current.strip())

    merged = []
    buffer_text = ""
    for block in blocks:
        if len(block) < min_chars:
            buffer_text += ("\n" if buffer_text else "") + block
            if len(buffer_text) >= min_chars:
                merged.append(buffer_text.strip())
                buffer_text = ""
        else:
            if buffer_text:
                merged.append(buffer_text.strip())
                buffer_text = ""
            merged.append(block)
    if buffer_text:
        merged.append(buffer_text.strip())

    return merged[:max_blocks]
