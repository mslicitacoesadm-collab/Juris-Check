from __future__ import annotations

def build_export_rows(analysis: dict):
    rows=[]
    for r in analysis.get('citation_results', []):
        sug = r.get('correcao_sugerida') or r.get('matched_record') or {}
        rows.append({
            'referencia_encontrada': r.get('raw',''),
            'linha': r.get('linha',''),
            'status': r.get('status_label',''),
            'confianca': r.get('grau_confianca',''),
            'observacao': r.get('tipo_erro',''),
            'sugestao': sug.get('citacao_curta','') if isinstance(sug, dict) else '',
        })
    return rows
