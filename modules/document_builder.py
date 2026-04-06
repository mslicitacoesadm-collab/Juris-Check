from __future__ import annotations

from io import BytesIO
import re
from typing import Any, Dict, List, Tuple

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _analysis_piece_type(analysis: Dict[str, Any] | None) -> str:
    if not isinstance(analysis, dict):
        return 'Não identificado'
    piece = analysis.get('piece_type')
    if isinstance(piece, dict):
        return piece.get('tipo', 'Não identificado')
    if isinstance(piece, str) and piece.strip():
        return piece.strip()
    return 'Não identificado'


def _coerce_title_and_analysis(title_or_analysis: Any, maybe_analysis: Any) -> tuple[str, Dict[str, Any]]:
    title = 'Peça revisada'
    analysis: Dict[str, Any] = {}
    if isinstance(title_or_analysis, dict) and isinstance(maybe_analysis, str):
        analysis = title_or_analysis
        title = maybe_analysis or title
    elif isinstance(title_or_analysis, str) and isinstance(maybe_analysis, dict):
        title = title_or_analysis or title
        analysis = maybe_analysis
    elif isinstance(title_or_analysis, dict):
        analysis = title_or_analysis
    elif isinstance(maybe_analysis, dict):
        analysis = maybe_analysis
        if isinstance(title_or_analysis, str) and title_or_analysis.strip():
            title = title_or_analysis.strip()
    elif isinstance(title_or_analysis, str) and title_or_analysis.strip():
        title = title_or_analysis.strip()
    return title, analysis


def _replacement_marker(old: str, new: str) -> str:
    return f"{new} [corrigido pelo sistema; original: {old}]"


def _replace_sentence_with_context(text: str, raw: str, rewrite: str) -> tuple[str, int]:
    if not text or not raw or not rewrite:
        return text, 0
    pattern = re.compile(rf"[^.!?\n]*{re.escape(raw)}[^.!?\n]*[.!?]?", re.I)
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        count += 1
        return rewrite

    updated = pattern.sub(repl, text, count=1)
    return updated, count


def apply_citation_corrections(text: str, citation_results: List[Dict[str, Any]]) -> Tuple[str, str, List[Dict[str, Any]]]:
    base = text or ''
    revised_clean = base
    revised_marked = base
    logs: List[Dict[str, Any]] = []
    for item in sorted(citation_results, key=lambda x: len(x.get('raw', '')), reverse=True):
        raw = (item.get('raw') or '').strip()
        replacement = (item.get('substituicao_textual') or '').strip()
        contextual = (item.get('redacao_sugerida') or '').strip()
        if not raw or not replacement:
            continue
        if item.get('status') not in {'divergente', 'valida_pouco_compativel'}:
            continue

        mode = 'substituicao_simples'
        count_clean = 0
        if contextual and len(contextual) <= 520:
            revised_clean_ctx, count_clean = _replace_sentence_with_context(revised_clean, raw, contextual)
            revised_marked_ctx, count_marked = _replace_sentence_with_context(revised_marked, raw, _replacement_marker(raw, contextual))
            if count_clean > 0 and count_marked > 0:
                revised_clean = revised_clean_ctx
                revised_marked = revised_marked_ctx
                mode = 'reescrita_contextual'

        if count_clean <= 0:
            count_clean = revised_clean.lower().count(raw.lower())
            if count_clean <= 0:
                continue
            revised_clean = revised_clean.replace(raw, replacement)
            revised_marked = revised_marked.replace(raw, _replacement_marker(raw, replacement))

        logs.append({
            'original': raw,
            'substituicao': contextual if mode == 'reescrita_contextual' else replacement,
            'ocorrencias': count_clean,
            'status': item.get('status_label', ''),
            'tese': item.get('tese', ''),
            'tipo': item.get('tipo_citacao', ''),
            'modo': mode,
        })
    return revised_clean, revised_marked, logs


def _thesis_section(thesis_results: List[Dict[str, Any]]) -> str:
    if not thesis_results:
        return ''
    lines = ['\nVI. DOS PRECEDENTES SUGERIDOS PELO SISTEMA\n']
    for idx, item in enumerate(thesis_results[:2], start=1):
        lines.append(f"6.{idx}. {item.get('tese', 'Tese jurídica')}\n")
        for sug in item.get('sugestoes', [])[:2]:
            par = sug.get('paragrafo_aplicado') or sug.get('citacao_curta')
            if par:
                lines.append(par)
                lines.append('')
    return '\n'.join(lines).strip()


def build_revised_versions(original_text: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    clean_text, marked_text, replacements = apply_citation_corrections(original_text, analysis.get('citation_results', []))
    thesis_addition = _thesis_section(analysis.get('thesis_results', []))
    for key, current in {'clean_text': clean_text, 'marked_text': marked_text}.items():
        revised = current
        if thesis_addition and 'V. DOS PEDIDOS' in revised:
            revised = revised.replace('V. DOS PEDIDOS', thesis_addition + '\n\nV. DOS PEDIDOS', 1)
        elif thesis_addition:
            revised = revised.rstrip() + '\n\n' + thesis_addition
        if key == 'clean_text':
            clean_text = revised
        else:
            marked_text = revised
    return {'clean_text': clean_text, 'marked_text': marked_text, 'replacement_log': replacements}


def build_revised_text(original_text: str, analysis: Dict[str, Any]) -> str:
    return build_revised_versions(original_text, analysis)['clean_text']


def _add_rich_paragraph(doc: Document, text: str, marked: bool = False) -> None:
    p = doc.add_paragraph()
    if not marked or '[corrigido pelo sistema; original:' not in text:
        p.add_run(text)
        return
    remaining = text
    while '[corrigido pelo sistema; original:' in remaining:
        before, marker = remaining.split('[corrigido pelo sistema; original:', 1)
        if before:
            p.add_run(before.rstrip())
        body, sep, rest = marker.partition(']')
        highlighted = p.add_run('[corrigido pelo sistema: ' + body.strip() + ']')
        highlighted.bold = True
        highlighted.font.highlight_color = WD_COLOR_INDEX.YELLOW
        remaining = rest.lstrip()
    if remaining:
        p.add_run(remaining)


def build_docx_bytes(revised_text: str, title_or_analysis: Any = None, analysis: Dict[str, Any] | None = None, marked: bool = False) -> bytes:
    title, analysis = _coerce_title_and_analysis(title_or_analysis, analysis)
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    doc.add_heading(title, level=1)
    info = doc.add_paragraph()
    info.add_run('Tipo identificado: ').bold = True
    info.add_run(_analysis_piece_type(analysis))

    replacement_log = (analysis or {}).get('replacement_log', []) if isinstance(analysis, dict) else []
    if replacement_log:
        doc.add_paragraph('Auditoria de substituições', style='Heading 2')
        for item in replacement_log:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(item.get('original', '')).italic = True
            p.add_run(' → ')
            r = p.add_run(item.get('substituicao', ''))
            r.bold = True
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    doc.add_paragraph('')
    for part in revised_text.split('\n'):
        if part.strip():
            _add_rich_paragraph(doc, part.strip(), marked=marked)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def build_pdf_bytes(revised_text: str, title_or_analysis: Any = None, analysis: Dict[str, Any] | None = None) -> bytes:
    title, analysis = _coerce_title_and_analysis(title_or_analysis, analysis)
    bio = BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [Paragraph(f'<b>{title}</b>', styles['Title']), Spacer(1, 12)]
    story.append(Paragraph(f"<b>Tipo identificado:</b> {_analysis_piece_type(analysis)}", styles['Normal']))
    replacement_log = (analysis or {}).get('replacement_log', []) if isinstance(analysis, dict) else []
    if replacement_log:
        story.append(Spacer(1, 10))
        story.append(Paragraph('<b>Auditoria de substituições</b>', styles['Heading2']))
        for item in replacement_log:
            safe = f"{item.get('original','')} → {item.get('substituicao','')}"
            safe = safe.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe, styles['Normal']))
    story.append(Spacer(1, 10))
    safe_text = revised_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for para in safe_text.split('\n'):
        if para.strip():
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 6))
    doc.build(story)
    return bio.getvalue()
