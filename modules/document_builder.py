from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _ensure_analysis(analysis: Any) -> Dict[str, Any]:
    return analysis if isinstance(analysis, dict) else {}


def _replace_raw_once(text: str, raw: str, replacement: str) -> str:
    if not raw or not replacement:
        return text
    return re.sub(re.escape(raw), replacement, text, count=1, flags=re.I)


def build_marked_text(original_text: str, analysis: Dict[str, Any]) -> str:
    analysis = _ensure_analysis(analysis)
    updated = original_text or ''
    for item in analysis.get('citation_results', []):
        replacement = item.get('substituicao_textual')
        raw = item.get('raw')
        if replacement and raw and item.get('status') in {'divergente', 'valida_pouco_compativel'}:
            marked = f"[[CORRIGIDO: {replacement}]]"
            updated = _replace_raw_once(updated, raw, marked)
    return updated


def build_revised_text(original_text: str, analysis: Dict[str, Any]) -> str:
    analysis = _ensure_analysis(analysis)
    updated = original_text or ''
    for item in analysis.get('citation_results', []):
        replacement = item.get('substituicao_textual')
        raw = item.get('raw')
        if replacement and raw and item.get('status') in {'divergente', 'valida_pouco_compativel'}:
            updated = _replace_raw_once(updated, raw, replacement)
    return updated


def _resolve_title_and_analysis(arg2: Any = None, arg3: Any = None) -> tuple[Dict[str, Any], str]:
    analysis: Dict[str, Any] = {}
    title = 'Peça revisada'
    if isinstance(arg2, dict):
        analysis = arg2
        if isinstance(arg3, str) and arg3.strip():
            title = arg3
    elif isinstance(arg2, str):
        title = arg2 or title
        if isinstance(arg3, dict):
            analysis = arg3
    elif isinstance(arg3, dict):
        analysis = arg3
    return analysis, title


def build_docx_bytes(revised_text: str, arg2: Any = None, arg3: Any = None) -> bytes:
    analysis, title = _resolve_title_and_analysis(arg2, arg3)
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    doc.add_heading(title, level=1)
    info = doc.add_paragraph()
    info.add_run('Tipo identificado: ').bold = True
    piece_type = analysis.get('piece_type', {}) if isinstance(analysis, dict) else {}
    info.add_run((piece_type or {}).get('tipo', 'Não identificado'))
    doc.add_paragraph('')
    for part in (revised_text or '').split('\n'):
        if part.strip():
            doc.add_paragraph(part.strip())
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def build_pdf_bytes(revised_text: str, arg2: Any = None, arg3: Any = None) -> bytes:
    analysis, title = _resolve_title_and_analysis(arg2, arg3)
    bio = BytesIO()
    pdf = SimpleDocTemplate(bio, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [Paragraph(f'<b>{title}</b>', styles['Title']), Spacer(1, 12)]
    piece_type = analysis.get('piece_type', {}) if isinstance(analysis, dict) else {}
    story.append(Paragraph(f"<b>Tipo identificado:</b> {(piece_type or {}).get('tipo', 'Não identificado')}", styles['Normal']))
    story.append(Spacer(1, 10))
    safe_text = (revised_text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for para in safe_text.split('\n'):
        if para.strip():
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 6))
    pdf.build(story)
    return bio.getvalue()
