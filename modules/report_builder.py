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
            'aderencia_1': (item.get('suggestions') or [{}])[0].get('relevance', '') if item.get('suggestions') else '',
        })
    for block in analysis.get('block_results', []):
        rows.append({
            'tipo': 'bloco',
            'referencia': f"Bloco {block.get('block_index')}",
            'status': 'Sugestão encontrada',
            'base_encontrada': '',
            'sugestao_1': (block.get('suggestions') or [{}])[0].get('numero_acordao', '') if block.get('suggestions') else '',
            'aderencia_1': (block.get('suggestions') or [{}])[0].get('relevance', '') if block.get('suggestions') else '',
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
        if item.get('matched_record'):
            rec = item['matched_record']
            lines.append(f"  - Base confirmada: {rec.get('numero_acordao','')} | {rec.get('colegiado','')}")
        elif item.get('suggestions'):
            best = item['suggestions'][0]
            lines.append(f"  - Sugestão principal: {best.get('numero_acordao','')} | aderência {best.get('relevance','')}")
    lines.append('')
    lines.append('## Sugestões por bloco')
    for block in analysis.get('block_results', []):
        lines.append(f"### Bloco {block.get('block_index')}")
        lines.append(block.get('block_text', ''))
        for sug in block.get('suggestions', []):
            lines.append(f"- {sug.get('numero_acordao','')} | {sug.get('colegiado','')} | {sug.get('relator','')} | aderência {sug.get('relevance','')}")
    return '\n'.join(lines)
