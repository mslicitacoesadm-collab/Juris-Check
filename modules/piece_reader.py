from __future__ import annotations

from io import BytesIO
from typing import Any

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
