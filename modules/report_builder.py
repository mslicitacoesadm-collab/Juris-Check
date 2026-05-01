def build_export_rows(analysis):
    rows=[]
    for item in analysis.get('citation_results',[]):
        sug=item.get('correcao_sugerida') or {}
        rows.append({'referencia':item.get('raw',''),'linha':item.get('linha',''),'status':item.get('status_label',''),'confianca':item.get('grau_confianca',''),'tipo_erro':item.get('tipo_erro',''),'sugestao':sug.get('citacao_curta',''),'fundamento':sug.get('fundamento_curto','')})
    return rows
