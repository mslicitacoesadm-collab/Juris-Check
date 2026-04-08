from __future__ import annotations

from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    summary = analysis.get('summary') or {}
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
            'score_contexto': item.get('score_contexto', 0.0),
            'motivo_match': item.get('motivo_match', ''),
            'precedente_localizado': matched.get('citacao_curta') or '',
            'precedente_localizado_aderencia': matched.get('compat_label') or '',
            'sugestao': suggestion.get('citacao_curta') or item.get('substituicao_textual') or '',
            'sugestao_aderencia': suggestion.get('compat_label') or '',
            'texto_pronto_sugerido': suggestion.get('texto_pronto') or '',
            'nota_auditoria': item.get('nota_auditoria', ''),
            'paragrafo_reescrito': item.get('paragrafo_reescrito', ''),
            'contexto_lido': item.get('contexto', ''),
            'risco_geral_peca': summary.get('risco', ''),
            'confiabilidade_geral_peca': summary.get('confiabilidade', ''),
            'pronto_para_protocolo': summary.get('pronto_protocolo', ''),
        })
    return rows
