from __future__ import annotations
from io import BytesIO


def read_uploaded_file(uploaded_file):
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    data = uploaded_file.read()
    if name.endswith('.txt'):
        for enc in ('utf-8','latin-1','cp1252'):
            try: return data.decode(enc)
            except Exception: pass
        return data.decode('utf-8', errors='ignore')
    if name.endswith('.docx'):
        try:
            from docx import Document
            doc = Document(BytesIO(data))
            return '\n'.join(p.text for p in doc.paragraphs if p.text)
        except Exception as e:
            return f''
    if name.endswith('.pdf'):
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            return '\n'.join((page.extract_text() or '') for page in reader.pages)
        except Exception:
            return ''
    return ''
