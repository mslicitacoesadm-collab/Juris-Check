from __future__ import annotations

from typing import Dict, List


def build_markdown_report(file_name: str, doc_type: str, analysis: Dict) -> str:
    lines = [
        f'# Relatório de análise - {file_name}',
        '',
        f'**Tipo provável da peça:** {doc_type}',
        f"**Citações detectadas:** {analysis['stats']['citacoes_detectadas']}",
        f"**Citações confirmadas:** {analysis['stats']['citacoes_validas']}",
        f"**Teses jurídicas mapeadas:** {analysis['stats']['teses_detectadas']}",
        '',
        '## Teses jurídicas identificadas',
        '',
    ]
    for thesis in analysis['thesis_results']:
        lines.append(f"### {thesis['titulo']}")
        lines.append(f"Trecho-base: {thesis['trecho_resumo']}")
        for sug in thesis['suggestions']:
            lines.append(f"- {sug['paragrafo_sugerido']}")
        lines.append('')
    return '\n'.join(lines)


def build_export_rows(analysis: Dict) -> List[Dict]:
    rows: List[Dict] = []
    for thesis in analysis['thesis_results']:
        for sug in thesis['suggestions']:
            rows.append({
                'tese': thesis['titulo'],
                'trecho_base': thesis['trecho_resumo'],
                'numero_acordao': sug.get('numero_acordao', ''),
                'colegiado': sug.get('colegiado', ''),
                'citacao_curta': sug.get('paragrafo_sugerido', ''),
                'aderencia': sug.get('relevance', ''),
            })
    return rows
