from __future__ import annotations
from io import BytesIO
import re


def build_revised_text(piece_text: str, analysis: dict, mode: str = 'premium') -> str:
    text = piece_text or ''
    notes=[]
    for r in analysis.get('citation_results', []):
        if r.get('correcao_sugerida'):
            notes.append(f"[DECIFRA] {r.get('raw')}: {r.get('tipo_erro')} Sugestão: {r['correcao_sugerida'].get('citacao_curta','')}.")
    if not notes: return text
    return text + "\n\n---\nAPONTAMENTOS DECIFRA\n" + '\n'.join(notes)


def build_marked_text(piece_text: str, analysis: dict) -> str:
    text = piece_text or ''
    for r in analysis.get('citation_results', []):
        raw = r.get('raw')
        if raw and r.get('status') != 'valida_compatível':
            text = text.replace(raw, f"[[REVISAR: {raw}]]", 1)
    return build_revised_text(text, analysis)


def build_docx_bytes(text: str, analysis: dict, title: str = 'DECIFRA - Relatório', marked: bool = False):
    from docx import Document
    from docx.shared import Pt
    doc=Document()
    doc.add_heading(title, level=1)
    p=doc.add_paragraph('Relatório técnico de apoio. Revise juridicamente antes do protocolo.')
    p.runs[0].font.size = Pt(9)
    doc.add_heading('Resumo da auditoria', level=2)
    for r in analysis.get('citation_results', []):
        doc.add_paragraph(f"{r.get('raw','')} — {r.get('status_label','')} — {r.get('tipo_erro','')}", style=None)
    doc.add_heading('Texto revisado', level=2)
    for para in re.split(r'\n+', text or ''):
        if para.strip(): doc.add_paragraph(para.strip())
    bio=BytesIO(); doc.save(bio); return bio.getvalue()


def build_pdf_bytes(text: str, analysis: dict, title: str = 'DECIFRA - Relatório'):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    bio=BytesIO(); doc=SimpleDocTemplate(bio, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=45, bottomMargin=45)
    styles=getSampleStyleSheet(); story=[Paragraph(title, styles['Title']), Spacer(1,12)]
    story.append(Paragraph('Relatório técnico de apoio. Revise juridicamente antes do protocolo.', styles['Normal']))
    story.append(Spacer(1,12)); story.append(Paragraph('Resumo da auditoria', styles['Heading2']))
    for r in analysis.get('citation_results', []):
        story.append(Paragraph(f"{r.get('raw','')} — {r.get('status_label','')} — {r.get('tipo_erro','')}", styles['Normal']))
    story.append(Spacer(1,12)); story.append(Paragraph('Texto revisado', styles['Heading2']))
    for para in re.split(r'\n+', (text or '')[:50000]):
        if para.strip(): story.append(Paragraph(para.strip().replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'), styles['Normal']))
    doc.build(story); return bio.getvalue()
