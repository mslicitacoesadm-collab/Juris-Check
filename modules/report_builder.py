from __future__ import annotations

from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in analysis.get('citation_results', []):
        rows.append({
            'tipo': 'citacao',
            'referencia': item.get('raw', ''),
            'status': item.get('status_label', ''),
            'base_encontrada': (item.get('matched_record') or {}).get('numero_acordao', ''),
            'sugestao_1': (item.get('suggestions') or [{}])[0].get('numero_acordao', '') if item.get('suggestions') else '',
        })
    for block in analysis.get('block_results', []):
        rows.append({
            'tipo': 'bloco',
            'referencia': f"Bloco {block.get('block_index')}",
            'status': 'Sugestão encontrada',
            'base_encontrada': '',
            'sugestao_1': (block.get('suggestions') or [{}])[0].get('numero_acordao', '') if block.get('suggestions') else '',
        })
    return rows


def build_markdown_report(file_name: str, analysis: Dict[str, Any]) -> str:
    lines = [
        '# Relatório de análise jurisprudencial',
        '',
        f'**Arquivo analisado:** {file_name}',
        '',
        analysis.get('summary_markdown', ''),
        '',
        '## Citações',
    ]
    for item in analysis.get('citation_results', []):
        lines.append(f"- `{item.get('raw','')}` → **{item.get('status_label','')}**")
    lines.append('')
    lines.append('## Sugestões por bloco')
    for block in analysis.get('block_results', []):
        lines.append(f"### Bloco {block.get('block_index')}")
        lines.append(block.get('block_text', ''))
        for sug in block.get('suggestions', []):
            lines.append(f"- {sug.get('numero_acordao','')} | {sug.get('colegiado','')} | {sug.get('relator','')}")
    return '\n'.join(lines)
