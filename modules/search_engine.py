from __future__ import annotations
from pathlib import Path
import sqlite3, re, math

TEXT_COLS = ('citacao','citacao_curta','ementa','fundamento','fundamento_curto','texto','tema','numero','ano','orgao','colegiado')

def _tokens(s):
    return set(re.findall(r'[a-záéíóúâêôãõç0-9]{3,}', (s or '').lower()))

def _score(q, text):
    qt=_tokens(q); tt=_tokens(text)
    if not qt or not tt: return 0.0
    return min(1.0, len(qt & tt)/max(3, len(qt))*1.15)

def _tables(con):
    try: return [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
    except Exception: return []

def _columns(con, table):
    try: return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
    except Exception: return []

def _row_to_record(row, cols, table, q=''):
    d=dict(zip(cols,row))
    def first(*names):
        for n in names:
            if n in d and d[n] not in (None,''): return str(d[n])
        return ''
    numero=first('numero','num','acordao','nr_acordao')
    ano=first('ano','exercicio')
    cit=first('citacao_curta','citacao','referencia','titulo')
    if not cit:
        cit = f"{table} {numero}/{ano}" if numero or ano else table
    fund=first('fundamento_curto','fundamento','ementa','texto','conteudo','descricao')
    tema=first('tema','assunto','tese','categoria')
    full=' '.join(str(x or '') for x in row)
    return {'citacao_curta':cit[:220], 'fundamento_curto':fund[:1200], 'tema':tema[:200], 'compat_score':_score(q, full) if q else .55, 'motivo_match':'Correspondência textual/semântica encontrada na base local.', 'lookup_layer':'base_local', 'lookup_layer_label':'Base local'}

def _search_db(db_path: Path, query: str, limit=20, exact_num='', exact_year='', kinds=None):
    recs=[]
    try:
        con=sqlite3.connect(str(db_path), timeout=2)
        for t in _tables(con):
            if kinds:
                tl=t.lower()
                if not any(k in tl for k in kinds) and not ('acordao' in kinds and ('acord' in tl or 'preced' in tl)):
                    pass
            cols=_columns(con,t)
            if not cols: continue
            sel=', '.join([f'"{c}"' for c in cols[:35]])
            where=[]; params=[]
            searchable=[c for c in cols if any(x in c.lower() for x in TEXT_COLS)] or cols[:8]
            if exact_num:
                clauses=[]
                for c in searchable:
                    clauses.append(f'CAST("{c}" AS TEXT) LIKE ?'); params.append(f'%{exact_num}%')
                where.append('('+' OR '.join(clauses)+')')
            if exact_year:
                clauses=[]
                for c in searchable:
                    clauses.append(f'CAST("{c}" AS TEXT) LIKE ?'); params.append(f'%{exact_year}%')
                where.append('('+' OR '.join(clauses)+')')
            if not where and query:
                words=list(_tokens(query))[:6]
                clauses=[]
                for w in words:
                    sub=[]
                    for c in searchable[:8]:
                        sub.append(f'CAST("{c}" AS TEXT) LIKE ?'); params.append(f'%{w}%')
                    clauses.append('('+' OR '.join(sub)+')')
                where=clauses[:3]
            sql=f'SELECT {sel} FROM "{t}"'
            if where: sql+=' WHERE '+ ' AND '.join(where)
            sql+=f' LIMIT {max(5,limit)}'
            try:
                for row in con.execute(sql, params).fetchmany(limit):
                    recs.append(_row_to_record(row, cols[:35], t, query))
            except Exception:
                continue
        con.close()
    except Exception:
        pass
    recs.sort(key=lambda r: r.get('compat_score',0), reverse=True)
    return recs[:limit]

def search_candidates(db_paths, query_text, thesis_key='', kinds=None, top_k=4):
    q=f'{query_text} {thesis_key}'
    out=[]
    for p in db_paths[:12]:
        out.extend(_search_db(Path(p), q, limit=top_k*2, kinds=kinds))
        if len(out)>=top_k*3: break
    out.sort(key=lambda r:r.get('compat_score',0), reverse=True)
    return out[:top_k]

def validate_reference(db_paths, citation, top_k=4):
    raw=citation.get('raw','')
    exact_num=citation.get('numero','')
    exact_year=citation.get('ano','')
    q=' '.join([raw, citation.get('contexto',''), citation.get('tese','')])
    matches=[]
    for p in db_paths[:12]:
        matches.extend(_search_db(Path(p), q, limit=top_k*2, exact_num=exact_num, exact_year=exact_year, kinds={citation.get('kind','acordao')}))
        if len(matches)>=top_k*3: break
    matches.sort(key=lambda r:r.get('compat_score',0), reverse=True)
    best=matches[0] if matches else None
    status='divergente'; label='Erro relevante'; conf='Baixa confiança'; tipo='Citação não localizada na base'
    if best:
        if best.get('compat_score',0)>=0.52:
            status='valida_compatível'; label='Validada'; conf='Alta confiança'; tipo='Referência localizada e compatível'
        elif best.get('compat_score',0)>=0.25:
            status='valida_pouco_compativel'; label='Ajuste recomendado'; conf='Média confiança'; tipo='Referência localizada com baixa aderência contextual'
    return {**citation, 'status':status, 'status_label':label, 'grau_confianca':conf, 'tipo_erro':tipo, 'matched_record':best, 'candidates':matches[:top_k], 'correcao_sugerida':best, 'motivo_match': best.get('motivo_match') if best else 'Não houve correspondência suficientemente segura na base local.', 'camada_busca': best.get('lookup_layer_label') if best else 'Busca sem match', 'paragrafo_reescrito': _rewrite_paragraph(citation, best)}

def _rewrite_paragraph(citation, best):
    if not best: return 'Sugere-se substituir ou remover a referência até validação manual do precedente aplicável.'
    return f"Diante do entendimento consolidado em {best['citacao_curta']}, recomenda-se ajustar a fundamentação para vincular a tese ao contexto do caso concreto, destacando que {best.get('fundamento_curto','o precedente reforça a necessidade de decisão motivada e aderente à legislação aplicável')}."

def search_manual_precedents(db_paths, query_text, kinds=None, top_k=8):
    from modules.citation_extractor import parse_manual_query
    parsed=parse_manual_query(query_text)
    exact_num=parsed.get('numero',''); exact_year=parsed.get('ano','')
    matches=[]
    for p in db_paths[:12]:
        matches.extend(_search_db(Path(p), query_text, limit=top_k*2, exact_num=exact_num, exact_year=exact_year, kinds=kinds))
        if len(matches)>=top_k*3: break
    matches.sort(key=lambda r:r.get('compat_score',0), reverse=True)
    return {'search_mode':'referencia_especifica' if exact_num else 'tese', 'lookup_layer_label':'Referência exata' if exact_num else 'Busca por tese', 'matches':matches[:top_k]}
