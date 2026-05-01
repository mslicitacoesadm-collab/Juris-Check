from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_references_with_context, parse_manual_query, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_marked_text, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import search_candidates, search_manual_precedents, validate_reference
from modules.commercial import get_config, make_order_id, make_unlock_code, premium_active, validate_unlock_code

st.set_page_config(page_title='DECIFRA Licitações', page_icon='⚖️', layout='wide')
BASE_DIR=Path(__file__).parent
DB_DIR=BASE_DIR/'data'/'base'
LOGO_PATH=BASE_DIR/'assets'/'logo_ms.png'

for k,v in {'analysis':None,'last_file_name':'','order_id':'','unlock_code':'','premium_unlocked':False}.items():
    st.session_state.setdefault(k,v)

@st.cache_data(show_spinner=False)
def cached_summary(path, signature):
    return summarize_bases(Path(path))

def _db_signature(base_dir: Path):
    return tuple((p.name, int(p.stat().st_mtime), p.stat().st_size) for p in find_db_files(base_dir))

@st.cache_data(show_spinner=False)
def cached_validate(db_paths, citation, top_k):
    return validate_reference([Path(p) for p in db_paths], citation, top_k=top_k)

@st.cache_data(show_spinner=False)
def cached_search(db_paths, query_text, thesis_key, kinds_key, top_k):
    kinds=set(kinds_key.split(',')) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, kinds=kinds, top_k=top_k)

@st.cache_data(show_spinner=False)
def cached_manual_search(db_paths, query_text, kinds_key, top_k):
    kinds=set(kinds_key.split(',')) if kinds_key else None
    return search_manual_precedents([Path(p) for p in db_paths], query_text, kinds=kinds, top_k=top_k)

cfg=get_config(st)
db_files=find_db_files(DB_DIR)
db_paths=tuple(str(p) for p in db_files)
summary=cached_summary(str(DB_DIR), _db_signature(DB_DIR))
is_premium=premium_active(st, cfg)
if is_premium: st.session_state.premium_unlocked=True

st.markdown('''
<style>
:root{--bg:#f5f7fb;--card:#fff;--ink:#132238;--muted:#56657a;--line:#dbe4f0;--red:#b42318;--green:#067647;--blue:#123b67}
.stApp{background:var(--bg)}
.hero{padding:1.4rem 1.5rem;border-radius:26px;background:linear-gradient(135deg,#081827,#123b67 60%,#1864ab);color:#fff;border:1px solid rgba(255,255,255,.12);box-shadow:0 16px 38px rgba(9,30,66,.18)}
.hero h1{margin:0;font-size:2rem}.hero p{line-height:1.55}.card{padding:1rem;border:1px solid var(--line);border-radius:20px;background:var(--card);margin:.75rem 0;box-shadow:0 8px 22px rgba(16,24,40,.05)}
.paywall{padding:1.2rem;border-radius:22px;border:1px solid #fed7aa;background:linear-gradient(135deg,#fff7ed,#fff);box-shadow:0 8px 22px rgba(180,83,9,.08)}
.badge{display:inline-block;padding:.25rem .7rem;border-radius:999px;font-weight:800;font-size:.82rem}.small{font-size:.94rem;color:var(--muted);line-height:1.6}.metricbox{padding:1rem;border-radius:18px;background:#fff;border:1px solid var(--line)}
.blur{filter:blur(3px);user-select:none;max-height:240px;overflow:hidden;opacity:.6}.cta{font-size:1.05rem;font-weight:800;color:#7c2d12}
</style>
''', unsafe_allow_html=True)

with st.sidebar:
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown('### 💰 Modo comercial')
    if is_premium:
        st.success('Premium liberado nesta sessão.')
    else:
        st.warning(f'Análise grátis: libera 1 erro. Completa: R$ {cfg["price"]}.')
    code=st.text_input('Código de liberação', value=st.session_state.get('unlock_code',''), placeholder='DEC-XXXXXXXXXX-XXXXXXXX')
    if code:
        st.session_state.unlock_code=code.strip().upper()
        if validate_unlock_code(st.session_state.unlock_code, cfg['unlock_secret']):
            st.session_state.premium_unlocked=True; st.success('Código válido. Resultado completo liberado.')
        else:
            st.info('Cole o código após o pagamento.')
    st.divider()
    top_k=st.slider('Sugestões por referência',1,6,4)
    max_blocks=st.slider('Blocos de tese',3,12,6)
    rewrite_mode=st.radio('Nível de entrega',['Correção simples','Correção contextual','Reescrita premium'], index=2)
    st.caption('Configure PIX, WhatsApp e checkout em `.streamlit/secrets.toml`.')

c1,c2=st.columns([1,5])
with c1:
    st.markdown('<div class="metricbox"><b>Base local</b><br>'+str(summary.get('total_bases',0))+' arquivos</div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'''
    <div class="hero">
      <h1>DECIFRA Licitações</h1>
      <p><b>Evite protocolar recurso, impugnação ou contrarrazão com acórdão errado.</b></p>
      <p>O sistema audita citações, identifica risco jurídico e entrega correção pronta para copiar, exportar em DOCX/PDF e anexar ao trabalho.</p>
    </div>''', unsafe_allow_html=True)

m1,m2,m3,m4=st.columns(4)
m1.metric('Acórdãos/base', f"{summary.get('acordao',0):,}".replace(',','.'))
m2.metric('Jurisprudências', f"{summary.get('jurisprudencia',0):,}".replace(',','.'))
m3.metric('Súmulas', f"{summary.get('sumula',0):,}".replace(',','.'))
m4.metric('Status comercial', 'Premium' if is_premium else 'Grátis')

main_tab, manual_tab, launch_tab = st.tabs(['🔎 Auditar peça', '⚖️ Busca manual', '🚀 Lançamento rápido'])

with main_tab:
    st.subheader('1. Envie a peça ou cole o texto')
    uploaded_file=st.file_uploader('Arquivo da peça', type=['pdf','docx','txt'])
    manual_text=st.text_area('Ou cole o texto', height=180)
    if st.button('Auditar grátis agora', type='primary', use_container_width=True):
        if not db_files:
            st.error('Nenhuma base `.db` foi encontrada em `data/base/`.')
            st.stop()
        if uploaded_file is None and not manual_text.strip():
            st.error('Envie um arquivo ou cole o texto da peça.'); st.stop()
        piece_text=read_uploaded_file(uploaded_file) if uploaded_file else manual_text
        file_name=uploaded_file.name if uploaded_file else 'texto_colado.txt'
        st.session_state.last_file_name=file_name
        if not st.session_state.order_id: st.session_state.order_id=make_order_id(file_name)
        refs=extract_references_with_context(piece_text)
        piece_type=classify_piece_type(piece_text)
        blocks=split_into_argument_blocks(piece_text, max_blocks=max_blocks)
        with st.spinner('Auditando citações e teses...'):
            citation_results=[cached_validate(db_paths, ref, top_k) for ref in refs]
            thesis_results=[]
            for block in blocks[:max_blocks]:
                suggestions=cached_search(db_paths, block['texto'], block['tese_chave'], 'acordao,jurisprudencia,sumula', top_k)
                if suggestions: thesis_results.append({'tese':block['tese'],'preview':block['preview'],'fundamentos':block['fundamentos'],'sugestoes':suggestions[:3]})
        st.session_state.analysis={'piece_type':piece_type,'citation_results':citation_results,'thesis_results':thesis_results,'piece_text':piece_text,'rewrite_mode':rewrite_mode}

    analysis=st.session_state.analysis
    if analysis:
        errors=[x for x in analysis['citation_results'] if x['status']!='valida_compatível']
        validas=sum(1 for x in analysis['citation_results'] if x['status']=='valida_compatível')
        ajustes=sum(1 for x in analysis['citation_results'] if x['status']=='valida_pouco_compativel')
        diverg=sum(1 for x in analysis['citation_results'] if x['status']=='divergente')
        a,b,c,d=st.columns(4)
        a.metric('Tipo', analysis['piece_type']['tipo']); b.metric('Validadas', validas); c.metric('Ajustes', ajustes); d.metric('Erros relevantes', diverg)
        if not is_premium and (ajustes or diverg or analysis['thesis_results']):
            order=st.session_state.order_id or make_order_id(st.session_state.last_file_name)
            st.session_state.order_id=order
            demo_code=make_unlock_code(order, cfg['unlock_secret'])
            st.markdown(f'''
            <div class="paywall">
              <div class="cta">🔒 Resultado completo bloqueado</div>
              <p>Encontramos pontos que podem comprometer a credibilidade da peça. A versão grátis mostra apenas uma amostra.</p>
              <p><b>Pedido:</b> {order} · <b>Valor:</b> R$ {cfg['price']}</p>
              <p>Após pagamento, gere/libere o código do pedido no painel administrativo. Código técnico deste pedido: <b>{demo_code}</b></p>
            </div>''', unsafe_allow_html=True)
            if cfg['checkout_url']:
                st.link_button('Pagar e desbloquear agora', cfg['checkout_url'], use_container_width=True)
            if cfg['pix_key']:
                st.code(f'PIX: {cfg["pix_key"]}\nValor: R$ {cfg["price"]}\nPedido: {order}', language='text')
            if cfg['whatsapp']:
                st.link_button('Enviar comprovante no WhatsApp', f'https://wa.me/{cfg["whatsapp"]}?text=Quero%20liberar%20o%20pedido%20{order}', use_container_width=True)
        st.subheader('Diagnóstico')
        st.write(f"Peça identificada como **{analysis['piece_type']['tipo']}**. Referências encontradas: **{len(analysis['citation_results'])}**.")
        shown_results=analysis['citation_results'] if is_premium else analysis['citation_results'][:1]
        for item in shown_results:
            color='#067647' if item['status']=='valida_compatível' else '#b42318' if item['status']=='divergente' else '#b54708'
            st.markdown(f"<div class='card'><span class='badge' style='background:{color};color:#fff'>{item['status_label']}</span><p><b>{item.get('raw')}</b> · linha {item.get('linha')}</p><p class='small'>{item.get('motivo_match')}</p></div>", unsafe_allow_html=True)
            if item.get('correcao_sugerida'):
                st.write('**Sugestão:**', item['correcao_sugerida'].get('citacao_curta'))
                st.write(item.get('paragrafo_reescrito',''))
        if not is_premium and len(analysis['citation_results'])>1:
            st.markdown('<div class="blur">'+'\n\n'.join([x.get('raw','')+' — '+x.get('status_label','') for x in analysis['citation_results'][1:]])+'</div>', unsafe_allow_html=True)
        if is_premium:
            mode_map={'Correção simples':'simple','Correção contextual':'contextual','Reescrita premium':'premium'}
            revised_text=build_revised_text(analysis['piece_text'], analysis, mode=mode_map[rewrite_mode])
            marked_text=build_marked_text(analysis['piece_text'], analysis)
            export_rows=build_export_rows(analysis)
            st.subheader('Exportação premium')
            docx_clean=build_docx_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            docx_marked=build_docx_bytes(marked_text, analysis, 'Marcado - '+(st.session_state.last_file_name or 'peca_revisada'), marked=True)
            pdf_clean=build_pdf_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            csv_bytes=pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
            d1,d2,d3,d4=st.columns(4)
            d1.download_button('DOCX limpo', docx_clean, file_name='decifra_revisado_limpo.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d2.download_button('DOCX marcado', docx_marked, file_name='decifra_revisado_marcado.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d3.download_button('PDF limpo', pdf_clean, file_name='decifra_revisado.pdf', mime='application/pdf', use_container_width=True)
            d4.download_button('CSV auditoria', csv_bytes, file_name='decifra_auditoria.csv', mime='text/csv', use_container_width=True)
            st.text_area('Prévia revisada', revised_text[:12000], height=320)

with manual_tab:
    st.subheader('Busca manual de precedentes')
    manual_query=st.text_input('Ex.: falha sanável sem diligência | TCU Acórdão 2622/2013 | Súmula 222')
    manual_types=st.multiselect('Tipos', ['acordao','jurisprudencia','sumula'], default=['acordao','jurisprudencia','sumula'])
    if st.button('Pesquisar precedentes', use_container_width=True):
        if not manual_query.strip(): st.warning('Digite uma tese ou referência.')
        else:
            parsed=parse_manual_query(manual_query)
            result=cached_manual_search(db_paths, manual_query, ','.join(manual_types), 8 if is_premium else 2)
            st.info(f"Modo: {'referência específica' if result['search_mode']=='referencia_especifica' else 'busca por tese'} · tese: {parsed.get('thesis_label')}")
            for rec in result['matches']:
                st.markdown(f"<div class='card'><b>{rec['citacao_curta']}</b><p class='small'>{rec.get('fundamento_curto','')}</p></div>", unsafe_allow_html=True)
            if not is_premium:
                st.warning('Busca manual completa faz parte do plano premium/liberado por código.')

with launch_tab:
    st.subheader('Checklist para vender hoje')
    st.markdown(f'''
    1. Coloque no `secrets.toml` sua chave PIX, WhatsApp e preço.  
    2. Publique o app no Streamlit.  
    3. Use a chamada: **“Evite protocolar peça com acórdão errado.”**  
    4. Venda inicialmente por **R$ {cfg['price']}** por documento.  
    5. Após o comprovante, envie ao cliente o código exibido no pedido.
    ''')
    st.code('''# .streamlit/secrets.toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande-e-secreta"
DECIFRA_CHECKOUT_URL = "" # opcional: link Mercado Pago/Hotmart/Kiwify
''', language='toml')
