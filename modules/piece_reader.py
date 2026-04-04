import io

import docx
import pdfplumber

def read_uploaded_file(uploaded_file) -> str:
    suffix = uploaded_file.name.lower().split(".")[-1]

    if suffix == "txt":
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if suffix == "docx":
        data = io.BytesIO(uploaded_file.getvalue())
        document = docx.Document(data)
        return "\n".join(p.text for p in document.paragraphs)

    if suffix == "pdf":
        texts = []
        data = io.BytesIO(uploaded_file.getvalue())
        with pdfplumber.open(data) as pdf:
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
        return "\n".join(texts)

    raise ValueError(f"Formato não suportado: {suffix}")
