from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer



def _replace_citations(text: str, citation_results: List[Dict[str, Any]]) -> str:
    updated = text
    for item in citation_results:
        replacement = item.get('substituicao_textual')
        raw = item.get('raw')
        if replacement and raw and item.get('status') in {'divergente', 'valida_pouco_compativel'}:
            updated = re.sub(re.escape(raw), replacement, updated, count=1, flags=re.I)
    return updated



def _thesis_section(thesis_results: List[Dict[str, Any]]) -> str:
    if not thesis_results:
        return ''
    lines = ['\nVI. DAS TESES DE REFORÇO SUGERIDAS PELO SISTEMA\n']
    for idx, item in enumerate(thesis_results[:2], start=1):
        lines.append(f"{6}.{idx}. {item.get('tese','Tese jurídica')}\n")
        for sug in item.get('sugestoes', [])[:2]:
            par = sug.get('paragrafo_aplicado') or sug.get('citacao_curta')
            lines.append(par)
            lines.append('')
    return '\n'.join(lines).strip()



def build_revised_text(original_text: str, analysis: Dict[str, Any]) -> str:
    revised = _replace_citations(original_text, analysis.get('citation_results', []))
    thesis_addition = _thesis_section(analysis.get('thesis_results', []))
    if thesis_addition and 'V. DOS PEDIDOS' in revised:
        revised = revised.replace('V. DOS PEDIDOS', thesis_addition + '\n\nV. DOS PEDIDOS', 1)
    elif thesis_addition:
        revised = revised.rstrip() + '\n\n' + thesis_addition
    return revised



def build_docx_bytes(revised_text: str, analysis: Dict[str, Any], title: str = 'Peça revisada') -> bytes:
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    doc.add_heading(title, level=1)
    info = doc.add_paragraph()
    info.add_run('Tipo identificado: ').bold = True
    info.add_run(analysis.get('piece_type', {}).get('tipo', 'Não identificado'))

    doc.add_paragraph('')
    for part in revised_text.split('\n'):
        if part.strip():
            doc.add_paragraph(part.strip())
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()



def build_pdf_bytes(revised_text: str, analysis: Dict[str, Any], title: str = 'Peça revisada') -> bytes:
    bio = BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [Paragraph(f'<b>{title}</b>', styles['Title']), Spacer(1, 12)]
    story.append(Paragraph(f"<b>Tipo identificado:</b> {analysis.get('piece_type', {}).get('tipo', 'Não identificado')}", styles['Normal']))
    story.append(Spacer(1, 10))
    safe_text = revised_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for para in safe_text.split('\n'):
        if para.strip():
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 6))
    doc.build(story)
    return bio.getvalue()
