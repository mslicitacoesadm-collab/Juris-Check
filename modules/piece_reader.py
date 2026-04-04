import io

import docx
import pdfplumber


def read_uploaded_file(uploaded_file) -> str:
    suffix = uploaded_file.name.lower().split(".")[-1]

    if suffix == "txt":
        raw = uploaded_file.getvalue()
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="ignore")

    if suffix == "docx":
        data = io.BytesIO(uploaded_file.getvalue())
        document = docx.Document(data)
        return "\n".join(p.text for p in document.paragraphs if p.text)

    if suffix == "pdf":
        texts = []
        data = io.BytesIO(uploaded_file.getvalue())
        with pdfplumber.open(data) as pdf:
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
        return "\n".join(texts)

    raise ValueError(f"Formato não suportado: {suffix}")
