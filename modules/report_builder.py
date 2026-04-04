from __future__ import annotations

from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in analysis.get('citation_results', []):
        rows.append({
            'tipo': 'citacao',
            'citacao_encontrada': item.get('raw', ''),
            'status': item.get('status_label', ''),
            'acordao_validado': (item.get('matched_record') or {}).get('numero_acordao', ''),
            'correcao_sugerida': (item.get('correcao_sugerida') or {}).get('numero_acordao', ''),
            'tese': item.get('tese', ''),
        })
    for item in analysis.get('thesis_results', []):
        rows.append({
            'tipo': 'tese',
            'citacao_encontrada': item.get('tese', ''),
            'status': 'Sugestão por tese',
            'acordao_validado': '',
            'correcao_sugerida': (item.get('sugestoes') or [{}])[0].get('numero_acordao', '') if item.get('sugestoes') else '',
            'tese': item.get('tese', ''),
        })
    return rows


def build_markdown_report(file_name: str, analysis: Dict[str, Any]) -> str:
    lines = [
        '# Relatório de validação jurisprudencial',
        '',
        f'**Arquivo analisado:** {file_name}',
        '',
        f"**Tipo identificado:** {analysis.get('piece_type', {}).get('tipo', 'Não identificado')}",
        f"**Confiança:** {analysis.get('piece_type', {}).get('confianca', 'baixa')}",
        '',
        '## Citações detectadas',
    ]
    for item in analysis.get('citation_results', []):
        lines.append(f"- `{item.get('raw','')}` → **{item.get('status_label','')}**")
        if item.get('correcao_sugerida'):
            lines.append(f"  - Correção sugerida: {item['correcao_sugerida'].get('numero_acordao','')}")
    lines.append('')
    lines.append('## Sugestões por tese')
    for item in analysis.get('thesis_results', []):
        lines.append(f"### {item.get('tese','')}")
        lines.append(item.get('trecho_curto',''))
        for sug in item.get('sugestoes', []):
            lines.append(f"- {sug.get('citacao_curta','')}")
    return '\n'.join(lines)
