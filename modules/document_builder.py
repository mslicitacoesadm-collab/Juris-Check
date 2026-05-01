from __future__ import annotations
from io import BytesIO
import re


def build_revised_text(piece_text, analysis, mode='premium'):
    text=piece_text or ''
    notes=[]
    for item in analysis.get('citation_results',[]):
        if item.get('status')!='valida_compatível':
            sug=item.get('correcao_sugerida')
            if sug:
                notes.append(f"[AJUSTE RECOMENDADO] Substituir/validar {item.get('raw')} por {sug.get('citacao_curta')}. Fundamento: {sug.get('fundamento_curto','')[:500]}")
            else:
                notes.append(f"[ERRO RELEVANTE] Referência não localizada: {item.get('raw')}. Recomenda-se conferência manual antes do protocolo.")
    if mode=='simple':
        return text + ('\n\n' + '\n'.join(notes) if notes else '')
    header='RELATÓRIO DE REVISÃO AUTOMATIZADA - DECIFRA LICITAÇÕES\n\n'
    intro='A seguir consta a peça com observações técnicas de validação de precedentes. As marcações indicam pontos que merecem ajuste antes do protocolo.\n\n'
    return header+intro+text+'\n\n---\nOBSERVAÇÕES TÉCNICAS\n'+'\n'.join(notes or ['Nenhuma divergência relevante foi identificada.'])


def build_marked_text(piece_text, analysis):
    text=piece_text or ''
    for item in analysis.get('citation_results',[]):
        raw=item.get('raw')
        if raw and item.get('status')!='valida_compatível':
            text=text.replace(raw, f'[[REVISAR: {raw}]]', 1)
    return build_revised_text(text, analysis, mode='premium')


def build_docx_bytes(text, analysis, title='Documento revisado', marked=False):
    try:
        from docx import Document
        from docx.shared import Pt
        doc=Document(); doc.add_heading(title, 0)
        p=doc.add_paragraph('Gerado pelo DECIFRA Licitações / Atlas dos Acórdãos. Revise antes de protocolar.')
        p.runs[0].font.size=Pt(9)
        for para in (text or '').split('\n'):
            doc.add_paragraph(para)
        bio=BytesIO(); doc.save(bio); return bio.getvalue()
    except Exception:
        return (text or '').encode('utf-8')


def build_pdf_bytes(text, analysis, title='Documento revisado'):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        bio=BytesIO(); doc=SimpleDocTemplate(bio, pagesize=A4)
        styles=getSampleStyleSheet(); story=[Paragraph(title, styles['Title']), Spacer(1,12)]
        safe=(text or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        for para in safe.split('\n'):
            story.append(Paragraph(para or ' ', styles['BodyText']))
        doc.build(story); return bio.getvalue()
    except Exception:
        return (text or '').encode('utf-8')
