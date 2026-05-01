from __future__ import annotations
import re

ACORDAO_RE=re.compile(r'(?i)\b(ac[oó]rd[aã]o(?:\s+n[ºo.]*)?|ac\.?)[\s:]*([0-9\.]{1,7})\s*/\s*(20\d{2}|19\d{2})\s*(?:[-–—]?\s*(TCU|STJ|STF|TJ[A-Z]{2}|TRF\d?|Plen[aá]rio|1[ªa]\s*C[âa]mara|2[ªa]\s*C[âa]mara))?')
SUMULA_RE=re.compile(r'(?i)\b(s[uú]mula)\s*(?:n[ºo.]*)?\s*([0-9]{1,5})')


def _line_no(text, idx):
    return text[:idx].count('\n')+1


def _context(text, start, end, radius=420):
    a=max(0,start-radius); b=min(len(text),end+radius)
    return re.sub(r'\s+',' ',text[a:b]).strip()


def detect_thesis(text):
    t=text.lower()
    rules=[('Falha sanável / diligência', ['diligência','falha sanável','saneamento','erro formal']),('Exigência restritiva', ['restritiv','competitividade','exigência excessiva','desproporcional']),('Inexequibilidade', ['inexequ','preço baixo','50%','viabilidade']),('Qualificação técnica', ['qualificação técnica','atestado','capacidade técnica']),('Pesquisa de preços', ['pesquisa de preços','preço de referência','orçamento'])]
    for label, keys in rules:
        if any(k in t for k in keys): return label
    return 'Tese geral de licitações'


def classify_piece_type(text):
    t=text.lower()
    if 'impugna' in t: tipo='Impugnação ao edital'
    elif 'contrarraz' in t: tipo='Contrarrazões'
    elif 'recurso administrativo' in t or 'interpor recurso' in t: tipo='Recurso administrativo'
    elif 'parecer' in t: tipo='Parecer jurídico'
    else: tipo='Peça jurídica'
    return {'tipo':tipo,'confianca':'Alta' if tipo!='Peça jurídica' else 'Média'}


def extract_references_with_context(text):
    refs=[]
    for m in ACORDAO_RE.finditer(text or ''):
        raw=m.group(0).strip(); numero=m.group(2).replace('.',''); ano=m.group(3); orgao=(m.group(4) or 'TCU').strip()
        refs.append({'kind':'acordao','raw':raw,'numero':numero,'ano':ano,'orgao':orgao,'linha':_line_no(text,m.start()),'contexto':_context(text,m.start(),m.end()),'tese':detect_thesis(_context(text,m.start(),m.end()))})
    for m in SUMULA_RE.finditer(text or ''):
        refs.append({'kind':'sumula','raw':m.group(0).strip(),'numero':m.group(2),'ano':'','orgao':'','linha':_line_no(text,m.start()),'contexto':_context(text,m.start(),m.end()),'tese':detect_thesis(_context(text,m.start(),m.end()))})
    return refs


def split_into_argument_blocks(text, max_blocks=6):
    paras=[p.strip() for p in re.split(r'\n\s*\n+', text or '') if len(p.strip())>120]
    out=[]
    for p in paras[:max_blocks]:
        tese=detect_thesis(p)
        out.append({'texto':p,'tese':tese,'tese_chave':tese.lower(),'preview':p[:420]+'...' if len(p)>420 else p,'fundamentos':', '.join([x for x in ['Lei 14.133/2021' if '14.133' in p else '', 'TCU' if 'tcu' in p.lower() else '', 'diligência' if 'dilig' in p.lower() else ''] if x])})
    return out


def parse_manual_query(q):
    q=q or ''
    m=ACORDAO_RE.search(q)
    if m: return {'kind':'acordao','numero':m.group(2).replace('.',''),'ano':m.group(3),'colegiado':m.group(4),'thesis_label':detect_thesis(q)}
    s=SUMULA_RE.search(q)
    if s: return {'kind':'sumula','numero':s.group(2),'ano':'','colegiado':'','thesis_label':detect_thesis(q)}
    return {'kind':'tese','numero':'','ano':'','colegiado':'','thesis_label':detect_thesis(q)}
