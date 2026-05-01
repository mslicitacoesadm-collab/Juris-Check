from __future__ import annotations
from pathlib import Path
import sqlite3, re, html

COLS = ['id','tipo','titulo','numero_acordao','numero_acordao_num','ano_acordao','colegiado','data_sessao','relator','processo','sumario','ementa','texto_indexado','inteiro_teor','tags']


def _norm(s: str) -> str:
    s = (s or '').lower()
    repl = {'á':'a','à':'a','â':'a','ã':'a','é':'e','ê':'e','í':'i','ó':'o','ô':'o','õ':'o','ú':'u','ç':'c'}
    for a,b in repl.items(): s=s.replace(a,b)
    return re.sub(r'\s+', ' ', s).strip()


def _clean_html(s: str, limit: int = 900) -> str:
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:limit]


def _connect(path: Path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=2)


def _row_to_record(row):
    d = dict(zip(COLS, row[:len(COLS)]))
    cit = d.get('numero_acordao') or d.get('titulo') or d.get('id') or 'Precedente'
    coleg = d.get('colegiado') or 'TCU'
    fundamento = d.get('ementa') or d.get('sumario') or d.get('texto_indexado') or d.get('inteiro_teor') or ''
    return {
        'id': d.get('id',''), 'tipo': d.get('tipo','ACÓRDÃO'), 'titulo': d.get('titulo',''),
        'numero_acordao': d.get('numero_acordao',''), 'numero_acordao_num': d.get('numero_acordao_num',''),
        'ano_acordao': d.get('ano_acordao',''), 'colegiado': coleg, 'relator': d.get('relator',''),
        'citacao_curta': f"Acórdão {cit} - {coleg}" if re.search(r'\d', cit) else str(cit),
        'fundamento_curto': _clean_html(fundamento, 950), 'tema': _clean_html((d.get('sumario') or d.get('ementa') or ''), 180),
        'compat_score': 0.0, 'motivo_match': '', 'lookup_layer': '', 'lookup_layer_label': ''
    }


def _query_exact(db_path: Path, numero: str, ano: str = ''):
    if not numero: return []
    out = []
    try:
        con = _connect(db_path); cur = con.cursor()
        where = 'numero_acordao_num = ?'
        params = [str(numero)]
        if ano:
            where += ' AND ano_acordao = ?'; params.append(str(ano))
        sql = f"SELECT id,tipo,titulo,numero_acordao,numero_acordao_num,ano_acordao,colegiado,data_sessao,relator,processo,sumario,ementa,texto_indexado,inteiro_teor,tags FROM acordaos WHERE {where} LIMIT 8"
        for row in cur.execute(sql, params).fetchall():
            out.append(_row_to_record(row))
    except Exception:
        pass
    finally:
        try: con.close()
        except Exception: pass
    return out


def _keywords(q: str):
    toks = [t for t in re.findall(r'[a-zA-ZÀ-ÿ0-9]{4,}', _norm(q)) if t not in {'para','pela','pelo','como','sobre','deve','esta','esse','essa','acordao','sumula'}]
    return toks[:8]


def _query_text(db_path: Path, query: str, top_k=5):
    words = _keywords(query)
    if not words: return []
    out=[]
    try:
        con=_connect(db_path); cur=con.cursor()
        # LIKE simples, estável e compatível com as bases brutas
        clause = ' OR '.join(['texto_indexado LIKE ? OR ementa LIKE ? OR sumario LIKE ? OR titulo LIKE ?' for _ in words[:4]])
        params=[]
        for w in words[:4]:
            like=f'%{w}%'; params += [like,like,like,like]
        sql=f"SELECT id,tipo,titulo,numero_acordao,numero_acordao_num,ano_acordao,colegiado,data_sessao,relator,processo,sumario,ementa,texto_indexado,inteiro_teor,tags FROM acordaos WHERE {clause} LIMIT {int(top_k)*2}"
        for row in cur.execute(sql, params).fetchall():
            rec=_row_to_record(row)
            hay=_norm(' '.join(str(x or '') for x in row))
            score=sum(1 for w in words if w in hay)/max(1,len(words))
            rec['compat_score']=round(min(.98,.45+score*.5),2)
            rec['motivo_match']='Correspondência por palavras-chave da tese informada.'
            rec['lookup_layer']='texto'
            rec['lookup_layer_label']='Busca por tese'
            out.append(rec)
    except Exception:
        pass
    finally:
        try: con.close()
        except Exception: pass
    return sorted(out, key=lambda r:r.get('compat_score',0), reverse=True)[:top_k]


def search_candidates(db_paths, query_text: str, thesis_key: str = '', kinds=None, top_k: int = 4):
    allrec=[]
    for p in db_paths:
        allrec += _query_text(Path(p), query_text + ' ' + (thesis_key or ''), top_k=top_k)
        if len(allrec) >= top_k: break
    return allrec[:top_k]


def search_manual_precedents(db_paths, query_text: str, kinds=None, top_k: int = 8):
    m = re.search(r'(?:ac[oó]rd[aã]o\s*)?(\d{1,6})[./-](\d{4})', query_text or '', re.I)
    matches=[]; mode='tese'; layer='Busca por tese'
    if m:
        mode='referencia_especifica'; layer='Número/ano exato'
        for p in db_paths:
            matches += _query_exact(Path(p), m.group(1), m.group(2))
            if len(matches)>=top_k: break
        for r in matches:
            r['compat_score']=.99; r['motivo_match']='Número e ano encontrados na base local.'; r['lookup_layer_label']=layer
    if not matches:
        matches = search_candidates(db_paths, query_text, '', kinds, top_k)
        layer='Busca por tese'
    return {'search_mode': mode, 'lookup_layer_label': layer, 'matches': matches[:top_k]}


def validate_reference(db_paths, citation: dict, top_k: int = 4):
    numero = citation.get('numero','')
    ano = citation.get('ano','')
    exact=[]
    for p in db_paths:
        exact += _query_exact(Path(p), numero, ano)
        if exact: break
    ctx = citation.get('contexto','') or citation.get('tese','') or citation.get('raw','')
    suggestions = exact[:top_k] if exact else search_candidates(db_paths, ctx, citation.get('tese',''), None, top_k)
    if exact:
        status='valida_compatível'; label='Validada na base'; erro='Referência localizada por número/ano.'; conf='Alta'
        matched=exact[0]; corr=None
        matched['compat_score']=.99; matched['motivo_match']='Referência explícita encontrada na base.'
    elif suggestions:
        status='valida_pouco_compativel'; label='Ajuste recomendado'; erro='Não localizei o número exato; há precedente próximo por tese.'; conf='Média'
        matched=None; corr=suggestions[0]
    else:
        status='divergente'; label='Não localizada'; erro='Referência não localizada na base disponível.'; conf='Baixa'
        matched=None; corr=None
    par=''
    if corr:
        par=f"Sugere-se substituir ou reforçar a citação por {corr.get('citacao_curta')}, por apresentar aderência temática ao argumento identificado. {corr.get('fundamento_curto','')}"
    return {**citation, 'status':status, 'status_label':label, 'tipo_erro':erro, 'grau_confianca':conf, 'matched_record':matched, 'correcao_sugerida':corr, 'suggestions':suggestions, 'motivo_match': erro, 'camada_busca':'Exata' if exact else 'Tese', 'paragrafo_reescrito':par}
