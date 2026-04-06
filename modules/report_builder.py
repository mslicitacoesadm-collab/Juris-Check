from __future__ import annotations

from typing import Any, Dict, List



def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in analysis.get('citation_results', []):
        rows.append({
            'tipo': 'citacao',
            'citacao_encontrada': item.get('raw', ''),
            'categoria': item.get('tipo_citacao', ''),
            'status': item.get('status_label', ''),
            'precedente_validado': (item.get('matched_record') or {}).get('numero_identificador', ''),
            'tipo_validado': (item.get('matched_record') or {}).get('tipo', ''),
            'correcao_sugerida': (item.get('correcao_sugerida') or {}).get('numero_identificador', ''),
            'tese': item.get('tese', ''),
            'risco': item.get('risco', ''),
            'score_contexto': item.get('score_contexto', ''),
        })
    for item in analysis.get('thesis_results', []):
        for idx, sug in enumerate(item.get('sugestoes', [])[:3], start=1):
            rows.append({
                'tipo': f'tese_{idx}',
                'citacao_encontrada': item.get('tese', ''),
                'categoria': sug.get('tipo', ''),
                'status': 'Sugestão por tese',
                'precedente_validado': '',
                'tipo_validado': '',
                'correcao_sugerida': sug.get('numero_identificador', ''),
                'tese': item.get('tese', ''),
                'risco': sug.get('risco', ''),
                'score_contexto': sug.get('compat_score', ''),
            })
    return rows



def build_markdown_report(file_name: str, analysis: Dict[str, Any]) -> str:
    lines = ['# Relatório técnico de validação de precedentes', '', f'**Arquivo analisado:** {file_name}', '', f"**Tipo identificado:** {analysis.get('piece_type', {}).get('tipo', 'Não identificado')}", f"**Confiança:** {analysis.get('piece_type', {}).get('confianca', 'baixa')}", '']
    estrutura = analysis.get('piece_structure', {})
    lines += ['## Síntese da análise', f"- Tese principal detectada: **{estrutura.get('tese_principal','-')}**", f"- Parágrafos analisados: **{estrutura.get('total_paragrafos','-')}**", f"- Citações encontradas: **{len(analysis.get('citation_results', []))}**", '']
    lines.append('## Validação das citações')
    for item in analysis.get('citation_results', []):
        lines.append(f"- `{item.get('raw','')}` → **{item.get('status_label','')}** · risco: **{item.get('risco','-')}**")
        if item.get('correcao_sugerida'):
            sug = item['correcao_sugerida']
            lines.append(f"  - Sugestão: {sug.get('tipo','')} {sug.get('numero_identificador','')}")
    lines.append('')
    lines.append('## Reforços sugeridos por tese')
    for item in analysis.get('thesis_results', []):
        lines.append(f"### {item.get('tese','')}")
        lines.append(item.get('trecho_curto',''))
        for sug in item.get('sugestoes', [])[:3]:
            lines.append(f"- {sug.get('citacao_curta','')}")
    return '\n'.join(lines)
