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
from modules.commercial import (
    get_config, make_order_id, make_unlock_code, premium_active, validate_unlock_code,
    create_mp_preference, verify_mp_payment
)

st.set_page_config(page_title='DECIFRA Licitações', page_icon='⚖️', layout='wide')
BASE_DIR=Path(__file__).parent
DB_DIR=BASE_DIR/'data'/'base'
LOGO_PATH=BASE_DIR/'assets'/'logo_ms.png'

for k,v in {
    'analysis':None,'last_file_name':'','order_id':'','unlock_code':'','premium_unlocked':False,
    'mp_preference':None,'payment_checked':False
}.items():
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
summary=cached_summary(str(DB_DIR), _db_signature(DB_DIR)) if DB_DIR.exists() else {}

# Retorno do Mercado Pago: confere payment_id/collection_id e libera automaticamente se aprovado.
qp = st.query_params
payment_id = qp.get('payment_id') or qp.get('collection_id')
return_order = qp.get('external_reference') or qp.get('decifra_order') or st.session_state.get('order_id')
if payment_id and not st.session_state.payment_checked:
    ok, payment = verify_mp_payment(cfg, str(payment_id), str(return_order or ''))
    st.session_state.payment_checked = True
    if ok:
        st.session_state.premium_unlocked = True
        if return_order:
            st.session_state.order_id = str(return_order)
            st.session_state.unlock_code = make_unlock_code(str(return_order), cfg['unlock_secret'])

is_premium=premium_active(st, cfg)
if is_premium: st.session_state.premium_unlocked=True

st.markdown('''
<style>
:root{--bg:#07111f;--panel:#0d1b2e;--panel2:#111f35;--card:#ffffff;--soft:#f6f8fb;--ink:#101828;--muted:#65758b;--line:#d9e2ef;--gold:#d7a84f;--gold2:#f2d28b;--green:#067647;--red:#b42318;--amber:#b54708;--blue:#123b67}
.stApp{background:linear-gradient(180deg,#07111f 0,#0b1424 320px,#f4f7fb 321px,#f4f7fb 100%);}
.block-container{padding-top:1.2rem;max-width:1180px}.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;color:#fff}.brand{font-weight:900;letter-spacing:.08em;font-size:1.05rem}.pill{display:inline-flex;gap:.45rem;align-items:center;padding:.42rem .8rem;border:1px solid rgba(255,255,255,.18);border-radius:999px;background:rgba(255,255,255,.07);color:#fff;font-size:.86rem}.hero{padding:2rem;border-radius:30px;background:radial-gradient(circle at 75% 20%,rgba(215,168,79,.28),transparent 34%),linear-gradient(135deg,#0d1b2e,#123b67 70%,#16213a);color:#fff;border:1px solid rgba(255,255,255,.12);box-shadow:0 22px 60px rgba(3,13,31,.30);position:relative;overflow:hidden}.hero h1{font-size:2.35rem;line-height:1.03;margin:0 0 .8rem;font-weight:900;letter-spacing:-.04em}.hero p{font-size:1.06rem;line-height:1.55;color:#e7eef8;max-width:760px}.hero strong{color:#fff}.gold{color:var(--gold2)}.main-card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:1.1rem;box-shadow:0 18px 45px rgba(16,24,40,.08);margin-top:1rem}.compact-card{background:#fff;border:1px solid var(--line);border-radius:22px;padding:1rem;box-shadow:0 10px 28px rgba(16,24,40,.055);margin:.7rem 0}.result-card{background:#fff;border-left:5px solid #d0d5dd;border-radius:18px;padding:1rem;margin:.7rem 0;box-shadow:0 8px 18px rgba(16,24,40,.045)}.paywall{padding:1.15rem;border-radius:24px;border:1px solid #f3d18a;background:linear-gradient(135deg,#fff8e8,#fff);box-shadow:0 14px 34px rgba(180,83,9,.11);margin:1rem 0}.paywall h3{margin:.1rem 0 .45rem;color:#7a4b00}.small{font-size:.92rem;color:var(--muted);line-height:1.55}.badge{display:inline-flex;padding:.25rem .7rem;border-radius:999px;font-size:.78rem;font-weight:800;color:#fff}.blur{filter:blur(4px);user-select:none;max-height:160px;overflow:hidden;opacity:.45;border-radius:18px;border:1px dashed #ccd6e3;padding:1rem;background:#f8fafc}.stTabs [data-baseweb="tab-list"]{display:none}.footer-note{font-size:.85rem;color:#98a2b3}.clean-title{font-size:1.15rem;font-weight:850;color:#101828;margin:.2rem 0 .5rem}.metric-wrap{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:18px;padding:.75rem;color:#fff}.premium-line{height:1px;background:linear-gradient(90deg,transparent,#d7a84f,transparent);margin:1rem 0}.hide-noise [data-testid="stSidebar"]{display:none}
</style>
''', unsafe_allow_html=True)

st.markdown('<div class="topbar"><div class="brand">DECIFRA LICITAÇÕES</div><div class="pill">⚖️ Auditoria jurídica automatizada</div></div>', unsafe_allow_html=True)

h1,h2 = st.columns([1.8,1])
with h1:
    st.markdown(f'''
    <div class="hero">
      <div class="pill" style="margin-bottom:1rem;color:#fff">Produto comercial pronto para cobrança por documento</div>
      <h1>Evite protocolar uma peça com <span class="gold">acórdão errado</span>.</h1>
      <p>O DECIFRA audita recursos, impugnações e contrarrazões, identifica citações frágeis e entrega uma versão revisada para exportar em DOCX/PDF.</p>
      <div class="premium-line"></div>
      <p><strong>Fluxo simples:</strong> envie a peça → veja uma amostra grátis → desbloqueie o relatório completo.</p>
    </div>
    ''', unsafe_allow_html=True)
with h2:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
    st.metric('Preço de lançamento', f'R$ {cfg["price"]}')
    st.metric('Status', 'Premium liberado' if is_premium else 'Amostra grátis')
    st.caption('Tudo na página principal. Sem menu lateral, sem excesso de texto.')
    st.markdown('</div>', unsafe_allow_html=True)

if payment_id:
    if st.session_state.premium_unlocked:
        st.success('Pagamento aprovado no Mercado Pago. Resultado completo liberado automaticamente.')
    elif st.session_state.payment_checked:
        st.warning('Pagamento ainda não aprovado ou não confirmado. Se pagou, aguarde alguns instantes e atualize a página.')

# Configuração discreta para operador
with st.expander('⚙️ Configuração rápida do operador', expanded=False):
    st.caption('Use esta área apenas internamente. Para o cliente final, deixe recolhida.')
    code_col, ops_col = st.columns([1,1])
    with code_col:
        code=st.text_input('Código de liberação manual', value=st.session_state.get('unlock_code',''), placeholder='DEC-XXXXXXXXXX-XXXXXXXX')
        if code:
            st.session_state.unlock_code=code.strip().upper()
            if validate_unlock_code(st.session_state.unlock_code, cfg['unlock_secret']):
                st.session_state.premium_unlocked=True
                st.success('Código válido. Resultado completo liberado.')
            else:
                st.info('Código ainda não validado.')
    with ops_col:
        top_k=st.slider('Sugestões por referência',1,6,4)
        max_blocks=st.slider('Blocos de tese',3,12,6)
        rewrite_mode=st.selectbox('Entrega', ['Reescrita premium','Correção contextual','Correção simples'], index=0)
else:
    top_k=4; max_blocks=6; rewrite_mode='Reescrita premium'

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="clean-title">1. Envie a peça para auditoria</div>', unsafe_allow_html=True)
up1, up2 = st.columns([1,1])
with up1:
    uploaded_file=st.file_uploader('Arquivo PDF, DOCX ou TXT', type=['pdf','docx','txt'], label_visibility='collapsed')
with up2:
    manual_text=st.text_area('Ou cole o texto aqui', height=125, placeholder='Cole o trecho do recurso, impugnação ou contrarrazão...', label_visibility='collapsed')

run = st.button('Auditar peça agora', type='primary', use_container_width=True)
if run:
    if not db_files:
        st.error('Nenhuma base `.db` foi encontrada em `data/base/`.')
        st.stop()
    if uploaded_file is None and not manual_text.strip():
        st.error('Envie um arquivo ou cole o texto da peça.')
        st.stop()
    piece_text=read_uploaded_file(uploaded_file) if uploaded_file else manual_text
    file_name=uploaded_file.name if uploaded_file else 'texto_colado.txt'
    st.session_state.last_file_name=file_name
    st.session_state.order_id=make_order_id(file_name)
    refs=extract_references_with_context(piece_text)
    piece_type=classify_piece_type(piece_text)
    blocks=split_into_argument_blocks(piece_text, max_blocks=max_blocks)
    with st.spinner('Auditando citações, compatibilidade e teses...'):
        citation_results=[cached_validate(db_paths, ref, top_k) for ref in refs]
        thesis_results=[]
        for block in blocks[:max_blocks]:
            suggestions=cached_search(db_paths, block['texto'], block['tese_chave'], 'acordao,jurisprudencia,sumula', top_k)
            if suggestions:
                thesis_results.append({'tese':block['tese'],'preview':block['preview'],'fundamentos':block['fundamentos'],'sugestoes':suggestions[:3]})
    st.session_state.analysis={'piece_type':piece_type,'citation_results':citation_results,'thesis_results':thesis_results,'piece_text':piece_text,'rewrite_mode':rewrite_mode}
st.markdown('</div>', unsafe_allow_html=True)

analysis=st.session_state.analysis
if analysis:
    errors=[x for x in analysis['citation_results'] if x['status']!='valida_compatível']
    validas=sum(1 for x in analysis['citation_results'] if x['status']=='valida_compatível')
    ajustes=sum(1 for x in analysis['citation_results'] if x['status']=='valida_pouco_compativel')
    diverg=sum(1 for x in analysis['citation_results'] if x['status']=='divergente')

    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<div class="clean-title">2. Resultado da auditoria</div>', unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric('Tipo de peça', analysis['piece_type']['tipo'])
    b.metric('Referências', len(analysis['citation_results']))
    c.metric('Validadas', validas)
    d.metric('Riscos/Ajustes', ajustes+diverg)

    needs_pay = (not is_premium) and (len(analysis['citation_results'])>1 or analysis['thesis_results'] or ajustes or diverg)
    if needs_pay:
        order=st.session_state.order_id or make_order_id(st.session_state.last_file_name)
        st.session_state.order_id=order
        manual_code=make_unlock_code(order, cfg['unlock_secret'])
        st.markdown(f'''
        <div class="paywall">
          <h3>🔒 Relatório completo bloqueado</h3>
          <p class="small">A amostra grátis aparece abaixo. Para liberar todas as correções, reescrita premium e exportação DOCX/PDF, desbloqueie este pedido.</p>
          <p><b>Pedido:</b> {order} &nbsp; · &nbsp; <b>Valor:</b> R$ {cfg['price']}</p>
        </div>''', unsafe_allow_html=True)
        pay_cols=st.columns([1,1,1])
        with pay_cols[0]:
            if st.button('Gerar pagamento Mercado Pago', use_container_width=True):
                ok, pref = create_mp_preference(cfg, order)
                if ok:
                    st.session_state.mp_preference = pref
                    st.success('Link de pagamento gerado.')
                else:
                    st.error(f'Não foi possível gerar o checkout: {pref.get("error")}')
        pref = st.session_state.get('mp_preference')
        with pay_cols[1]:
            if pref and (pref.get('init_point') or pref.get('sandbox_init_point')):
                st.link_button('Pagar no Mercado Pago', pref.get('init_point') or pref.get('sandbox_init_point'), use_container_width=True)
            elif cfg.get('checkout_url'):
                st.link_button('Pagar agora', cfg['checkout_url'], use_container_width=True)
            else:
                st.button('Pagar agora', disabled=True, use_container_width=True)
        with pay_cols[2]:
            if cfg.get('whatsapp'):
                st.link_button('Enviar comprovante', f'https://wa.me/{cfg["whatsapp"]}?text=Quero%20liberar%20o%20pedido%20{order}', use_container_width=True)
            else:
                st.button('WhatsApp não configurado', disabled=True, use_container_width=True)
        with st.expander('Liberação manual/PIX para venda imediata', expanded=False):
            if cfg.get('pix_key'):
                st.code(f'PIX: {cfg["pix_key"]}\nValor: R$ {cfg["price"]}\nPedido: {order}', language='text')
            st.code(f'Código interno deste pedido: {manual_code}', language='text')
            st.caption('Envie esse código ao cliente após confirmar o pagamento, caso não use confirmação automática do Mercado Pago.')

    shown_results=analysis['citation_results'] if is_premium else analysis['citation_results'][:1]
    for item in shown_results:
        color='#067647' if item['status']=='valida_compatível' else '#b42318' if item['status']=='divergente' else '#b54708'
        st.markdown(f"""
        <div class='result-card' style='border-left-color:{color}'>
          <span class='badge' style='background:{color}'>{item['status_label']}</span>
          <p><b>{item.get('raw')}</b> · linha {item.get('linha')}</p>
          <p class='small'>{item.get('motivo_match')}</p>
        </div>""", unsafe_allow_html=True)
        if item.get('correcao_sugerida'):
            st.write('**Sugestão:**', item['correcao_sugerida'].get('citacao_curta'))
            st.write(item.get('paragrafo_reescrito',''))
    if not is_premium and len(analysis['citation_results'])>1:
        st.markdown('<div class="blur">'+'\n\n'.join([x.get('raw','')+' — '+x.get('status_label','') for x in analysis['citation_results'][1:]])+'</div>', unsafe_allow_html=True)

    if is_premium:
        mode_map={'Correção simples':'simple','Correção contextual':'contextual','Reescrita premium':'premium'}
        revised_text=build_revised_text(analysis['piece_text'], analysis, mode=mode_map.get(rewrite_mode,'premium'))
        marked_text=build_marked_text(analysis['piece_text'], analysis)
        export_rows=build_export_rows(analysis)
        st.markdown('<div class="clean-title">3. Exportação premium</div>', unsafe_allow_html=True)
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
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="clean-title">Busca manual de precedentes</div>', unsafe_allow_html=True)
qcol, bcol = st.columns([3,1])
with qcol:
    manual_query=st.text_input('Digite uma tese ou referência', placeholder='Ex.: falha sanável sem diligência | TCU Acórdão 2622/2013')
with bcol:
    search_btn=st.button('Pesquisar', use_container_width=True)
if search_btn and manual_query.strip():
    parsed=parse_manual_query(manual_query)
    result=cached_manual_search(db_paths, manual_query, 'acordao,jurisprudencia,sumula', 8 if is_premium else 2)
    st.caption(f"Modo: {'referência específica' if result['search_mode']=='referencia_especifica' else 'busca por tese'} · {parsed.get('thesis_label')}")
    for rec in result['matches']:
        st.markdown(f"<div class='result-card'><b>{rec['citacao_curta']}</b><p class='small'>{rec.get('fundamento_curto','')}</p></div>", unsafe_allow_html=True)
    if not is_premium:
        st.warning('A busca completa faz parte do relatório premium.')
st.markdown('</div>', unsafe_allow_html=True)

with st.expander('📌 Secrets para publicar no Streamlit', expanded=False):
    st.code('''# .streamlit/secrets.toml
DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande-e-secreta"
DECIFRA_APP_URL = "https://SEU-APP.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = "" # opcional, precisa ser HTTPS
DECIFRA_CHECKOUT_URL = "" # fallback opcional
''', language='toml')
    st.caption('O Checkout Pro exige Access Token. A confirmação automática funciona quando o Mercado Pago retorna com payment_id/collection_id e o app consulta o status aprovado.')
