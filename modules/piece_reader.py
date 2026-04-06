from __future__ import annotations

from io import BytesIO
from typing import Any, Dict

import docx
import pdfplumber



def read_uploaded_file(uploaded_file: Any) -> str:
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    data = uploaded_file.read()
    if not data:
        return ''
    if name.endswith('.txt'):
        return data.decode('utf-8', errors='ignore')
    if name.endswith('.docx'):
        doc = docx.Document(BytesIO(data))
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return '\n'.join(parts)
    if name.endswith('.pdf'):
        pages = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ''
                if txt.strip():
                    pages.append(txt)
        return '\n\n'.join(pages)
    raise ValueError('Formato não suportado. Use PDF, DOCX ou TXT.')



def inspect_extraction(text: str) -> Dict[str, object]:
    lines = [ln for ln in (text or '').splitlines() if ln.strip()]
    words = (text or '').split()
    avg_line = round(sum(len(ln) for ln in lines) / max(len(lines), 1), 1) if lines else 0
    quality = 'boa'
    alerts = []
    if len(words) < 80:
        quality = 'baixa'
        alerts.append('Texto extraído muito curto; o arquivo pode ser imagem ou conter pouca camada textual.')
    if avg_line > 220:
        quality = 'média' if quality == 'boa' else quality
        alerts.append('Linhas muito longas sugerem quebra irregular na extração.')
    if not lines:
        quality = 'baixa'
        alerts.append('Nenhum texto foi extraído do documento.')
    return {'palavras': len(words), 'linhas': len(lines), 'media_linha': avg_line, 'qualidade': quality, 'alertas': alerts}
