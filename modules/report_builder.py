from __future__ import annotations


def risk_level(analysis: dict) -> tuple[str, str]:
    results = analysis.get('citation_results', []) or []
    issues = [r for r in results if r.get('status') != 'valida_compatível']
    not_found = [r for r in issues if r.get('status') == 'divergente']
    if not results:
        return 'INDETERMINADO', 'Nenhuma citação formal foi detectada para validação automática.'
    if not_found or len(issues) >= 3:
        return 'ALTO', 'Há referências não localizadas ou múltiplos pontos que exigem revisão antes do protocolo.'
    if issues:
        return 'MÉDIO', 'Foram encontrados pontos que merecem conferência técnica e possível substituição/reforço.'
    return 'BAIXO', 'As referências detectadas foram localizadas na base disponível; mantenha revisão jurídica final.'


def build_export_rows(analysis: dict):
    rows = []
    for idx, r in enumerate(analysis.get('citation_results', []) or [], start=1):
        sug = r.get('correcao_sugerida') or r.get('matched_record') or {}
        rows.append({
            'item': idx,
            'referencia_encontrada': r.get('raw', ''),
            'linha_aproximada': r.get('linha', ''),
            'status': r.get('status_label', ''),
            'confianca': r.get('grau_confianca', ''),
            'diagnostico': r.get('tipo_erro', ''),
            'correcao_ou_reforco_sugerido': sug.get('citacao_curta', '') if isinstance(sug, dict) else '',
            'fundamento_resumido': sug.get('fundamento_curto', '') if isinstance(sug, dict) else '',
            'acao_recomendada': recommended_action(r),
        })
    return rows


def recommended_action(item: dict) -> str:
    status = item.get('status')
    if status == 'valida_compatível':
        return 'Manter referência; revisar apenas coerência textual do argumento.'
    if status == 'valida_pouco_compativel':
        return 'Conferir número original; considerar substituir ou reforçar pela sugestão indicada.'
    return 'Revisar manualmente a citação; não protocolar sem conferência da fonte.'


def build_audit_summary(analysis: dict) -> dict:
    results = analysis.get('citation_results', []) or []
    issues = [r for r in results if r.get('status') != 'valida_compatível']
    valid = [r for r in results if r.get('status') == 'valida_compatível']
    risk, reason = risk_level(analysis)
    return {
        'tipo_peca': (analysis.get('piece_type') or {}).get('tipo', 'Peça jurídica'),
        'total_referencias': len(results),
        'referencias_validadas': len(valid),
        'pontos_revisao': len(issues),
        'teses_sugeridas': len(analysis.get('thesis_results', []) or []),
        'risco': risk,
        'justificativa_risco': reason,
    }
