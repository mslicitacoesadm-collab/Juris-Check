from __future__ import annotations
import io, zipfile, re


def _read_docx(file_obj):
    data=file_obj.getvalue() if hasattr(file_obj,'getvalue') else file_obj.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml=z.read('word/document.xml').decode('utf-8', errors='ignore')
    xml=re.sub(r'<w:tab\/>',' ',xml)
    xml=re.sub(r'</w:p>','\n',xml)
    return re.sub(r'<[^>]+>','',xml)


def _read_pdf(file_obj):
    data=file_obj.getvalue() if hasattr(file_obj,'getvalue') else file_obj.read()
    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        return '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception:
        return ''


def read_uploaded_file(uploaded_file):
    name=(uploaded_file.name or '').lower()
    if name.endswith('.txt'):
        raw=uploaded_file.getvalue() if hasattr(uploaded_file,'getvalue') else uploaded_file.read()
        for enc in ('utf-8','latin-1','cp1252'):
            try: return raw.decode(enc)
            except Exception: pass
        return raw.decode('utf-8', errors='ignore')
    if name.endswith('.docx'):
        return _read_docx(uploaded_file)
    if name.endswith('.pdf'):
        return _read_pdf(uploaded_file)
    return ''
