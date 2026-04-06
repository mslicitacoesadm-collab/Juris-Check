from __future__ import annotations

from typing import Any, Dict, List


def _precedent_ref(item: Dict[str, Any] | None) -> str:
    if not item:
        return ''
    ptype = item.get('tipo_precedente')
    if ptype == 'sumula':
        return f"Súmula TCU {item.get('numero_sumula') or item.get('numero_acordao_num')}"
    if ptype == 'jurisprudencia':
        return f"Jurisprudência TCU {item.get('numero_acordao')}"
    return item.get('numero_acordao', '')



def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in analysis.get('citation_results', []):
        rows.append({
            'tipo': 'citacao',
            'tipo_citacao': item.get('tipo_citacao', ''),
            'citacao_encontrada': item.get('raw', ''),
            'status': item.get('status_label', ''),
            'precedente_validado': _precedent_ref(item.get('matched_record')),
            'correcao_sugerida': _precedent_ref(item.get('correcao_sugerida')),
            'tese': item.get('tese', ''),
            'risco': item.get('risco', ''),
            'score_contexto': item.get('score_contexto', ''),
        })
    for item in analysis.get('thesis_results', []):
        for idx, sug in enumerate(item.get('sugestoes', [])[:3], start=1):
            rows.append({
                'tipo': f'tese_{idx}',
                'tipo_citacao': sug.get('tipo_precedente', ''),
                'citacao_encontrada': item.get('tese', ''),
                'status': 'Sugestão por tese',
                'precedente_validado': '',
                'correcao_sugerida': _precedent_ref(sug),
                'tese': item.get('tese', ''),
                'risco': sug.get('risco', ''),
                'score_contexto': sug.get('compat_score', ''),
            })
    return rows



def build_markdown_report(file_name: str, analysis: Dict[str, Any]) -> str:
    lines = [
        '# Relatório premium de validação jurisprudencial',
        '',
        f'**Arquivo analisado:** {file_name}',
        '',
        f"**Tipo identificado:** {analysis.get('piece_type', {}).get('tipo', 'Não identificado')}",
        f"**Confiança:** {analysis.get('piece_type', {}).get('confianca', 'baixa')}",
        '',
        '## Citações auditadas',
    ]
    for item in analysis.get('citation_results', []):
        lines.append(f"- `{item.get('raw','')}` → **{item.get('status_label','')}** · risco: **{item.get('risco','-')}**")
        if item.get('correcao_sugerida'):
            lines.append(f"  - Correção sugerida: {_precedent_ref(item['correcao_sugerida'])}")
    lines.append('')
    lines.append('## Reforços por tese')
    for item in analysis.get('thesis_results', []):
        lines.append(f"### {item.get('tese','')}")
        lines.append(item.get('trecho_curto',''))
        for sug in item.get('sugestoes', [])[:3]:
            lines.append(f"- {sug.get('citacao_curta','')}")
    return '\n'.join(lines)
