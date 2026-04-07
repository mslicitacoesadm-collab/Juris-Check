from __future__ import annotations

from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in analysis.get('citation_results', []):
        suggestion = item.get('correcao_sugerida') or {}
        rows.append({
            'linha': item.get('linha'),
            'tipo': item.get('kind'),
            'citacao_encontrada': item.get('raw'),
            'status': item.get('status_label'),
            'tese': item.get('tese'),
            'grau_confianca': item.get('grau_confianca'),
            'motivo_match': item.get('motivo_match', ''),
            'sugestao': suggestion.get('citacao_curta') or item.get('substituicao_textual') or '',
        })
    return rows
