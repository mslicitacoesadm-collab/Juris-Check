from __future__ import annotations

from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in analysis.get('citation_results', []):
        suggestion = item.get('correcao_sugerida') or {}
        matched = item.get('matched_record') or {}
        rows.append({
            'linha': item.get('linha'),
            'tipo': item.get('kind'),
            'citacao_encontrada': item.get('raw'),
            'status': item.get('status_label'),
            'classificacao_tecnica': item.get('problema_classificado', ''),
            'tese': item.get('tese'),
            'grau_confianca': item.get('grau_confianca'),
            'motivo_match': item.get('motivo_match', ''),
            'precedente_localizado': matched.get('citacao_curta') or '',
            'sugestao': suggestion.get('citacao_curta') or item.get('substituicao_textual') or '',
            'nota_auditoria': item.get('nota_auditoria', ''),
            'paragrafo_reescrito': item.get('paragrafo_reescrito', ''),
        })
    return rows
