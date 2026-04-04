from __future__ import annotations

from io import BytesIO

import docx
import pdfplumber


def read_uploaded_file(uploaded_file) -> str:
    suffix = uploaded_file.name.lower().split('.')[-1]
    data = uploaded_file.read()
    uploaded_file.seek(0)

    if suffix == 'txt':
        for enc in ('utf-8', 'utf-8-sig', 'latin-1'):
            try:
                return data.decode(enc)
            except Exception:
                continue
        return data.decode('utf-8', errors='ignore')

    if suffix == 'docx':
        doc = docx.Document(BytesIO(data))
        return '\n'.join(p.text for p in doc.paragraphs if p.text and p.text.strip())

    if suffix == 'pdf':
        texts = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ''
                if txt.strip():
                    texts.append(txt)
        return '\n'.join(texts)

    raise ValueError('Formato não suportado. Use PDF, DOCX ou TXT.')
