from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
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


def _replace_context_once(text: str, old_context: str, new_context: str) -> str:
    if not old_context or not new_context:
        return text
    if old_context in text:
        return text.replace(old_context, new_context, 1)
    return text


def _build_audit_block(item: Dict[str, Any]) -> str:
    partes = [
        '[[AUDITORIA DE CITAÇÃO]]',
        f"Status: {item.get('status_label', 'Não classificado')}",
        f"Problema: {item.get('problema_classificado', 'Sem classificação')}",
        f"Confiança: {item.get('grau_confianca', 'Não informada')}",
        f"Referência encontrada: {item.get('raw', '')}",
    ]
    if item.get('substituicao_textual'):
        partes.append(f"Correção implantada: {item.get('substituicao_textual')}")
    if item.get('motivo_match'):
        partes.append(f"Motivo técnico: {item.get('motivo_match')}")
    if item.get('nota_auditoria'):
        partes.append(f"Nota de auditoria: {item.get('nota_auditoria')}")
    if item.get('paragrafo_reescrito'):
        partes.append(f"Redação sugerida: {item.get('paragrafo_reescrito')}")
    return '\n'.join(partes)


def build_marked_text(original_text: str, analysis: Dict[str, Any]) -> str:
    analysis = _ensure_analysis(analysis)
    updated = original_text or ''
    for item in analysis.get('citation_results', []):
        raw = item.get('raw')
        rewritten = item.get('paragrafo_reescrito')
        context = item.get('contexto')
        if item.get('status') not in {'divergente', 'valida_pouco_compativel'}:
            continue
        audit_block = _build_audit_block(item)
        if rewritten and context:
            marked = f"{audit_block}\n\n[[TRECHO ORIGINAL]] {context}\n\n[[TRECHO AJUSTADO]] {rewritten}"
            updated = _replace_context_once(updated, context, marked)
        elif raw:
            marked = f"{audit_block}\n\n[[MARCAÇÃO NO TEXTO]] {raw}"
            updated = _replace_raw_once(updated, raw, marked)
    return updated


def build_revised_text(original_text: str, analysis: Dict[str, Any], mode: str = 'premium') -> str:
    analysis = _ensure_analysis(analysis)
    updated = original_text or ''
    for item in analysis.get('citation_results', []):
        raw = item.get('raw')
        replacement = item.get('substituicao_textual')
        rewritten = item.get('paragrafo_reescrito')
        context = item.get('contexto')
        if item.get('status') not in {'divergente', 'valida_pouco_compativel'}:
            continue
        if mode in {'contextual', 'premium'} and rewritten and context:
            updated = _replace_context_once(updated, context, rewritten)
        elif replacement and raw:
            updated = _replace_raw_once(updated, raw, replacement)
    return updated


def build_reinforced_text(original_text: str, analysis: Dict[str, Any], limit: int = 4) -> str:
    analysis = _ensure_analysis(analysis)
    updated = build_revised_text(original_text, analysis, mode='premium')
    inserted = 0
    for bloco in analysis.get('thesis_results', []):
        if inserted >= limit:
            break
        sugestoes = bloco.get('sugestoes') or []
        texto_bloco = bloco.get('texto') or ''
        if not texto_bloco or not sugestoes:
            continue
        snippet = sugestoes[0].get('texto_pronto') or ''
        citacao = sugestoes[0].get('citacao_curta') or ''
        if not snippet or snippet in updated:
            continue
        reforco = f"\n\n[[REFORÇO AUTOMÁTICO V18 — {bloco.get('tese', 'Tese')}]]\n{snippet}\n[[PRECEDENTE-BASE]] {citacao}\n"
        if texto_bloco in updated:
            updated = updated.replace(texto_bloco, texto_bloco + reforco, 1)
            inserted += 1
    return updated


def build_client_report_text(analysis: Dict[str, Any], file_name: str = 'peça') -> str:
    analysis = _ensure_analysis(analysis)
    summary = analysis.get('summary') or {}
    piece_type = analysis.get('piece_type') or {}
    lines = [
        'RELATÓRIO PREMIUM DE AUDITORIA JURÍDICA',
        'Atlas dos Acórdãos V18',
        '',
        f"Arquivo analisado: {file_name}",
        f"Tipo identificado: {piece_type.get('tipo', 'Não identificado')}",
        f"Confiança da classificação: {piece_type.get('confianca', 'não informada')}",
        '',
        '1. RESUMO EXECUTIVO',
        f"- Citações auditadas: {summary.get('total_citacoes', 0)}",
        f"- Validadas: {summary.get('validas', 0)}",
        f"- Com ajuste recomendado: {summary.get('ajustes', 0)}",
        f"- Divergentes: {summary.get('erros', 0)}",
        f"- Não mapeadas: {summary.get('nao_mapeadas', 0)}",
        f"- Confiabilidade geral: {summary.get('confiabilidade', 0)}%",
        f"- Risco da peça: {str(summary.get('risco', 'não definido')).upper()}",
        f"- Pode protocolar agora: {summary.get('pronto_protocolo', 'não definido').upper()}",
        '',
        '2. LEITURA ESTRATÉGICA',
        summary.get('recomendacao', 'Sem recomendação executiva disponível.'),
        '',
        '3. TESES MAIS RELEVANTES',
    ]
    thesis_results = analysis.get('thesis_results') or []
    if thesis_results:
        for idx, bloco in enumerate(thesis_results[:5], start=1):
            sug = (bloco.get('sugestoes') or [{}])[0]
            lines.extend([
                f"{idx}. {bloco.get('tese', 'Tese não identificada')}",
                f"   - tese secundária: {bloco.get('tese_secundaria') or 'não identificada'}",
                f"   - fundamentos detectados: {bloco.get('fundamentos') or 'sem indicadores claros'}",
                f"   - precedente prioritário: {sug.get('citacao_curta') or 'não sugerido'}",
                f"   - texto de reforço: {sug.get('texto_pronto') or 'não disponível'}",
            ])
    else:
        lines.append('Nenhum bloco robusto de tese foi detectado para reforço automático.')

    lines.extend(['', '4. PONTOS CRÍTICOS DE CITAÇÃO'])
    critical = [x for x in analysis.get('citation_results', []) if x.get('status') in {'divergente', 'valida_pouco_compativel'}]
    if critical:
        for idx, item in enumerate(critical[:10], start=1):
            lines.extend([
                f"{idx}. Linha {item.get('linha', '-')}: {item.get('raw', '')}",
                f"   - status: {item.get('status_label', '')}",
                f"   - problema: {item.get('problema_classificado', '')}",
                f"   - sugestão principal: {(item.get('correcao_sugerida') or {}).get('citacao_curta') or item.get('substituicao_textual') or 'não disponível'}",
                f"   - nota técnica: {item.get('nota_auditoria', '')}",
            ])
    else:
        lines.append('Não foram detectados pontos críticos relevantes nas citações identificadas.')

    lines.extend([
        '',
        '5. ORIENTAÇÃO FINAL',
        summary.get('orientacao_cliente', 'Proceder com revisão humana final antes do protocolo.'),
    ])
    return '\n'.join(lines)


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


def _analysis_summary(analysis: Dict[str, Any]) -> Dict[str, int]:
    items = analysis.get('citation_results', []) if isinstance(analysis, dict) else []
    return {
        'total': len(items),
        'validas': sum(1 for x in items if x.get('status') == 'valida_compatível'),
        'ajustes': sum(1 for x in items if x.get('status') == 'valida_pouco_compativel'),
        'erros': sum(1 for x in items if x.get('status') == 'divergente'),
    }


def _summary_text(summary: Dict[str, Any]) -> str:
    if not summary:
        return 'Resumo não disponível.'
    return (
        f"Referências analisadas: {summary.get('total_citacoes', 0)} | "
        f"Validadas: {summary.get('validas', 0)} | "
        f"Ajustes: {summary.get('ajustes', 0)} | "
        f"Erros: {summary.get('erros', 0)} | "
        f"Confiabilidade geral: {summary.get('confiabilidade', 0)}% | "
        f"Risco da peça: {str(summary.get('risco', 'não definido')).upper()} | "
        f"Pode protocolar: {str(summary.get('pronto_protocolo', 'não definido')).upper()}"
    )


def _add_heading_box(doc: Document, title: str, subtitle: str = '') -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(16)
    if subtitle:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run(subtitle)
        r2.italic = True
        r2.font.size = Pt(10)


def build_docx_bytes(revised_text: str, arg2: Any = None, arg3: Any = None, marked: bool = False) -> bytes:
    analysis, title = _resolve_title_and_analysis(arg2, arg3)
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    _add_heading_box(doc, title, 'Atlas dos Acórdãos V18 · revisão técnica, reforço automático e relatório premium')
    piece_type = analysis.get('piece_type', {}) if isinstance(analysis, dict) else {}
    summary_counts = _analysis_summary(analysis)
    summary_exec = analysis.get('summary') or {}

    info = doc.add_paragraph()
    info.add_run('Tipo identificado: ').bold = True
    info.add_run((piece_type or {}).get('tipo', 'Não identificado'))
    info.add_run(' | Confiança: ').bold = True
    info.add_run((piece_type or {}).get('confianca', 'não informada'))

    doc.add_paragraph(_summary_text(summary_exec or {
        'total_citacoes': summary_counts['total'],
        'validas': summary_counts['validas'],
        'ajustes': summary_counts['ajustes'],
        'erros': summary_counts['erros'],
        'confiabilidade': 0,
        'risco': 'não definido',
        'pronto_protocolo': 'não definido',
    }))

    if summary_exec.get('recomendacao'):
        rec = doc.add_paragraph()
        rec.add_run('Recomendação executiva: ').bold = True
        rec.add_run(summary_exec['recomendacao'])

    if marked:
        doc.add_heading('Quadro executivo de intervenções', level=2)
        for idx, item in enumerate(analysis.get('citation_results', []), start=1):
            if item.get('status') not in {'divergente', 'valida_pouco_compativel'}:
                continue
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f'Item {idx}: ').bold = True
            p.add_run(item.get('raw', 'Referência sem texto'))
            doc.add_paragraph(f"Status: {item.get('status_label', '')}")
            doc.add_paragraph(f"Problema identificado: {item.get('problema_classificado', 'Sem classificação')}")
            if item.get('substituicao_textual'):
                doc.add_paragraph(f"Correção aplicada: {item.get('substituicao_textual')}")
            if item.get('motivo_match'):
                doc.add_paragraph(f"Motivo técnico: {item.get('motivo_match')}")
            if item.get('nota_auditoria'):
                doc.add_paragraph(f"Nota de auditoria: {item.get('nota_auditoria')}")
            if item.get('paragrafo_reescrito'):
                doc.add_paragraph(f"Texto sugerido para implantação: {item.get('paragrafo_reescrito')}")
        doc.add_section(WD_SECTION.NEW_PAGE)
        doc.add_heading('Texto marcado para revisão', level=2)
    else:
        doc.add_heading('Versão consolidada da peça', level=2)

    for part in (revised_text or '').split('\n'):
        if not part.strip():
            continue
        p = doc.add_paragraph()
        run = p.add_run(part.strip())
        if marked and ('[[AUDITORIA DE CITAÇÃO]]' in part or '[[TRECHO ORIGINAL]]' in part or '[[TRECHO AJUSTADO]]' in part or '[[MARCAÇÃO NO TEXTO]]' in part or '[[REFORÇO AUTOMÁTICO V18' in part):
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            run.bold = True

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
    summary = _analysis_summary(analysis)
    exec_sum = analysis.get('summary') or {}
    story.append(Paragraph(f"<b>Tipo identificado:</b> {(piece_type or {}).get('tipo', 'Não identificado')}", styles['Normal']))
    story.append(Paragraph(f"<b>Auditoria:</b> {summary['total']} referências, {summary['validas']} validadas, {summary['ajustes']} com ajuste e {summary['erros']} divergentes.", styles['Normal']))
    if exec_sum:
        story.append(Paragraph(f"<b>Confiabilidade geral:</b> {exec_sum.get('confiabilidade', 0)}% | <b>Risco:</b> {str(exec_sum.get('risco','')).upper()} | <b>Pode protocolar:</b> {str(exec_sum.get('pronto_protocolo','')).upper()}", styles['Normal']))
        story.append(Paragraph(f"<b>Recomendação executiva:</b> {exec_sum.get('recomendacao', '—')}", styles['Normal']))
    story.append(Spacer(1, 10))
    safe_text = (revised_text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for para in safe_text.split('\n'):
        if para.strip():
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 6))
    pdf.build(story)
    return bio.getvalue()
