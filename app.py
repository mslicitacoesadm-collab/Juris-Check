from __future__ import annotations

from pathlib import Path
import re
import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_references_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_marked_text, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import search_candidates, search_manual_precedents, validate_reference
from modules.commercial import get_config, make_order_id, make_unlock_code, premium_active, validate_unlock_code, create_mp_preference, get_mp_payment_status

st.set_page_config(page_title='DECIFRA Licitações', page_icon='⚖️', layout='wide', initial_sidebar_state='collapsed')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'
LOGO_PATH = BASE_DIR / 'assets' / 'logo_ms.png'

DEFAULT_STATE = {
    'analysis': None, 'last_text': '', 'last_file_name': '', 'order_id': '',
    'unlock_code': '', 'premium_unlocked': False, 'mp_preference': None,
}
for k, v in DEFAULT_STATE.items():
    st.session_state.setdefault(k, v)


@st.cache_data(show_spinner=False)
def cached_summary(path: str, signature):
    return summarize_bases(Path(path))


def db_signature(base_dir: Path):
    files = find_db_files(base_dir)
    return tuple((p.name, int(p.stat().st_mtime), p.stat().st_size) for p in files)


@st.cache_data(show_spinner=False)
def cached_validate(db_paths, citation, top_k: int):
    return validate_reference([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_search(db_paths, query_text: str, thesis_key: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(',')) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, kinds=kinds, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_manual_search(db_paths, query_text: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(',')) if kinds_key else None
    return search_manual_precedents([Path(p) for p in db_paths], query_text, kinds=kinds, top_k=top_k)


def price_float(price_text: str) -> float:
    try:
        return float(str(price_text).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except Exception:
        return 19.90


def query_params():
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}


def get_first_param(params, *names):
    for name in names:
        value = params.get(name)
        if isinstance(value, list):
            value = value[0] if value else ''
        if value:
            return str(value)
    return ''


def compact(text: str, limit: int = 420) -> str:
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text[:limit] + ('...' if len(text) > limit else '')


def css():
    st.markdown('''
<style>
:root{--bg:#f6f8fb;--card:#ffffff;--ink:#121826;--muted:#667085;--line:#e4e7ec;--blue:#163b66;--blue2:#0b2745;--gold:#b8872d;--soft:#f9fafb;--danger:#b42318;--warn:#b54708;--ok:#027a48}
.stApp{background:linear-gradient(180deg,#f8fafc 0%,#eef3f8 100%);color:var(--ink)}
.block-container{max-width:1160px;padding-top:1.2rem;padding-bottom:3rem}.main .block-container{padding-left:1.3rem;padding-right:1.3rem}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
.hero{background:linear-gradient(135deg,#0b2745 0%,#163b66 52%,#235789 100%);border-radius:30px;padding:30px;color:white;box-shadow:0 26px 70px rgba(16,24,40,.20);border:1px solid rgba(255,255,255,.14);position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-80px;top:-80px;width:240px;height:240px;border-radius:999px;background:rgba(255,255,255,.09)}
.brand{font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#f4d28b}.hero h1{font-size:clamp(2.2rem,5vw,4.2rem);line-height:.98;letter-spacing:-.05em;margin:.45rem 0 .6rem;font-weight:950}.hero p{font-size:1.04rem;line-height:1.65;color:#e7eef8;max-width:760px;margin:0}.price-pill{display:inline-flex;margin-top:1.1rem;background:#fff;color:#0b2745;border-radius:999px;padding:.62rem 1rem;font-weight:900;box-shadow:0 12px 30px rgba(0,0,0,.16)}
.card{background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:24px;padding:22px;box-shadow:0 18px 45px rgba(16,24,40,.08);margin-top:16px}.card.slim{padding:16px}.step{display:inline-flex;gap:.5rem;align-items:center;background:#eff6ff;color:#16416f;border:1px solid #d7e8fb;border-radius:999px;padding:.42rem .75rem;font-size:.82rem;font-weight:900;margin-bottom:12px}.muted{color:var(--muted)}
.metric{background:var(--soft);border:1px solid var(--line);border-radius:18px;padding:16px}.metric b{font-size:1.7rem;display:block;letter-spacing:-.04em}.metric span{color:var(--muted);font-size:.86rem}.result{border:1px solid var(--line);background:#fff;border-radius:18px;padding:16px;margin:12px 0}.badge{display:inline-block;border-radius:999px;padding:.26rem .62rem;font-size:.74rem;font-weight:900;margin-bottom:.48rem}.ok{background:#ecfdf3;color:var(--ok);border:1px solid #abefc6}.warn{background:#fffaeb;color:var(--warn);border:1px solid #fedf89}.danger{background:#fef3f2;color:var(--danger);border:1px solid #fecdca}.lock{background:linear-gradient(135deg,#fff8eb,#ffffff);border:1px solid #f0d49a;border-radius:22px;padding:22px;text-align:center;margin:16px 0;box-shadow:0 20px 46px rgba(184,135,45,.12)}.lock h3{margin-top:0}.secure{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:12px}.secure span{background:#f2f4f7;color:#344054;border:1px solid #e4e7ec;border-radius:999px;padding:.38rem .7rem;font-size:.78rem;font-weight:800}
.stButton>button,.stDownloadButton>button{border-radius:14px!important;min-height:3rem;font-weight:850!important;border:1px solid #d0d5dd!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#163b66,#0b2745)!important;color:#fff!important;border:0!important}.stTextInput input,.stTextArea textarea{border-radius:14px!important;border-color:#d0d5dd!important}.stFileUploader section{border-radius:18px!important;border-color:#d0d5dd!important;background:#fbfcfe!important}a[data-testid="stLinkButton"]{border-radius:14px!important;font-weight:850!important}.divider{height:1px;background:var(--line);margin:16px 0}.footer-note{text-align:center;color:var(--muted);font-size:.82rem;margin-top:20px}
@media(max-width:760px){.block-container{padding-left:.85rem!important;padding-right:.85rem!important;padding-top:.7rem}.hero{padding:22px;border-radius:22px}.card{padding:17px;border-radius:20px}.metric{padding:13px}.metric b{font-size:1.25rem}.hero p{font-size:.98rem}.price-pill{width:100%;justify-content:center}.secure{justify-content:center}}
</style>
''', unsafe_allow_html=True)


def status_class(status: str):
    if status == 'valida_compatível': return 'ok'
    if status == 'valida_pouco_compativel': return 'warn'
    return 'danger'


def check_payment_return(cfg):
    params = query_params()
    payment_id = get_first_param(params, 'payment_id', 'collection_id')
    status_param = get_first_param(params, 'status', 'collection_status')
    if not payment_id:
        return
    payment = get_mp_payment_status(cfg, payment_id)
    if payment.get('status') == 'approved' or status_param == 'approved':
        st.session_state.premium_unlocked = True
        st.success('Pagamento aprovado. Relatório completo liberado.')
    elif payment.get('error'):
        st.warning(payment['error'])
    else:
        st.warning(f"Pagamento com status: {payment.get('status','pendente')}.")


def render_hero(cfg, summary):
    st.markdown(f'''
<div class="hero">
  <div class="brand">DECIFRA LICITAÇÕES</div>
  <h1>Auditoria de precedentes antes do protocolo.</h1>
  <p>Envie a peça, valide as citações e libere um relatório técnico com correções sugeridas. Tudo em uma tela, direto e pronto para uso.</p>
  <div class="price-pill">Análise completa · R$ {cfg['price']}</div>
</div>
<div class="card slim"><b>Base local:</b> {summary.get('total_files',0)} arquivo(s) · {summary.get('acordao',0):,} registros detectados <span class="muted">— coloque suas bases .db em <code>data/base/</code>.</span></div>
'''.replace(',', '.'), unsafe_allow_html=True)


def run_analysis(db_files, db_paths):
    st.markdown('<div class="card"><span class="step">1 · Enviar peça</span>', unsafe_allow_html=True)
    c1, c2 = st.columns([1,1], gap='large')
    with c1:
        uploaded = st.file_uploader('Arquivo PDF, DOCX ou TXT', type=['pdf','docx','txt'])
    with c2:
        manual_text = st.text_area('Ou cole o texto', height=145, placeholder='Cole aqui o recurso, impugnação, contrarrazão ou trecho jurídico...')
    if st.button('Auditar agora', type='primary', use_container_width=True):
        if not db_files:
            st.error('Nenhuma base .db encontrada. Envie suas bases para a pasta data/base/.')
            st.stop()
        if uploaded is None and not manual_text.strip():
            st.error('Envie um arquivo ou cole o texto da peça.')
            st.stop()
        with st.spinner('Lendo peça e cruzando com a base local...'):
            if uploaded is not None:
                piece_text = read_uploaded_file(uploaded)
                file_name = uploaded.name
            else:
                piece_text = manual_text.strip()
                file_name = 'texto_colado.txt'
            if len((piece_text or '').strip()) < 40:
                st.error('Não foi possível extrair texto suficiente. Tente DOCX/TXT ou cole o conteúdo manualmente.')
                st.stop()
            refs = extract_references_with_context(piece_text)
            piece_type = classify_piece_type(piece_text)
            blocks = split_into_argument_blocks(piece_text, max_blocks=6)
            citation_results = [cached_validate(db_paths, ref, 4) for ref in refs[:50]]
            thesis_results = []
            for block in blocks:
                suggestions = cached_search(db_paths, block.get('texto',''), block.get('tese_chave',''), 'acordao,jurisprudencia,sumula', 3)
                if suggestions:
                    thesis_results.append({'tese': block.get('tese','Tese'), 'preview': block.get('preview',''), 'sugestoes': suggestions})
            st.session_state.analysis = {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results, 'piece_text': piece_text, 'file_name': file_name}
            st.session_state.last_text = piece_text
            st.session_state.last_file_name = file_name
            st.session_state.order_id = make_order_id(file_name)
            st.session_state.premium_unlocked = False
            st.session_state.mp_preference = None
        st.success('Auditoria concluída. A amostra gratuita foi liberada abaixo.')
    st.markdown('</div>', unsafe_allow_html=True)


def render_metrics(analysis, unlocked):
    results = analysis.get('citation_results', [])
    total = len(results)
    issues = sum(1 for r in results if r.get('status') != 'valida_compatível')
    teses = len(analysis.get('thesis_results', []))
    liberados = total if unlocked else min(total, 1)
    cols = st.columns(4)
    data = [(total,'referências'),(issues,'pontos de atenção'),(teses,'teses'),(liberados,'liberados')]
    for col, (num, label) in zip(cols, data):
        col.markdown(f'<div class="metric"><b>{num}</b><span>{label}</span></div>', unsafe_allow_html=True)


def result_item(item):
    sug = item.get('correcao_sugerida') or item.get('matched_record') or {}
    cls = status_class(item.get('status',''))
    st.markdown('<div class="result">', unsafe_allow_html=True)
    st.markdown(f'<span class="badge {cls}">{item.get("status_label","Resultado")}</span>', unsafe_allow_html=True)
    st.markdown(f"**{item.get('raw','Referência')}**")
    st.caption(f"Linha {item.get('linha','-')} · {item.get('grau_confianca','')} · {item.get('tipo_erro','')}")
    if sug:
        st.markdown(f"**Sugestão:** {sug.get('citacao_curta','')}")
        if sug.get('fundamento_curto'):
            st.write(compact(sug.get('fundamento_curto'), 650))
    if item.get('paragrafo_reescrito'):
        with st.expander('Texto sugerido'):
            st.write(item.get('paragrafo_reescrito'))
    st.markdown('</div>', unsafe_allow_html=True)


def payment_box(cfg, analysis):
    st.markdown('<div class="lock">', unsafe_allow_html=True)
    st.markdown('### Liberar análise completa')
    st.write('Desbloqueie todas as referências, teses sugeridas e downloads finais.')
    st.markdown(f"## R$ {cfg['price']}")
    col1, col2 = st.columns(2, gap='medium')
    with col1:
        if cfg.get('mp_access_token'):
            if st.button('Gerar checkout Mercado Pago', type='primary', use_container_width=True):
                order_id = st.session_state.get('order_id') or make_order_id(analysis.get('file_name','analise'))
                st.session_state.order_id = order_id
                st.session_state.mp_preference = create_mp_preference(cfg, order_id, 'DECIFRA Licitações - Análise completa', price_float(cfg['price']))
            pref = st.session_state.get('mp_preference') or {}
            if pref.get('init_point'):
                st.link_button('Pagar com Mercado Pago', pref['init_point'], use_container_width=True)
            if pref.get('error'):
                st.error(pref['error'])
        else:
            st.info('Configure MERCADO_PAGO_ACCESS_TOKEN nos Secrets para ativar o checkout.')
    with col2:
        code = st.text_input('Código de liberação', value=st.session_state.get('unlock_code',''), placeholder='Cole o código após pagamento manual')
        if code:
            st.session_state.unlock_code = code.strip().upper()
            if validate_unlock_code(st.session_state.unlock_code, cfg.get('unlock_secret',''), st.session_state.get('order_id','')):
                st.session_state.premium_unlocked = True
                st.rerun()
        if cfg.get('pix_key'):
            st.caption('PIX manual')
            st.code(cfg.get('pix_key'))
        if cfg.get('whatsapp'):
            msg = f"Olá, quero liberar minha análise DECIFRA. Pedido: {st.session_state.get('order_id','')}"
            url = 'https://wa.me/' + re.sub(r'\D','',cfg['whatsapp']) + '?text=' + msg.replace(' ', '%20')
            st.link_button('Enviar comprovante', url, use_container_width=True)
    st.markdown('<div class="secure"><span>Checkout seguro</span><span>Base local</span><span>Sem login obrigatório</span></div>', unsafe_allow_html=True)
    if st.session_state.get('order_id'):
        with st.expander('Operador: gerar código manual'):
            st.caption('Use apenas quando confirmar pagamento manualmente.')
            st.code(st.session_state.order_id)
            st.code(make_unlock_code(st.session_state.order_id, cfg.get('unlock_secret','')))
    st.markdown('</div>', unsafe_allow_html=True)


def render_results(analysis, unlocked, cfg):
    st.markdown('<div class="card"><span class="step">2 · Resultado</span>', unsafe_allow_html=True)
    render_metrics(analysis, unlocked)
    results = analysis.get('citation_results', [])
    if not results:
        st.info('Nenhuma citação formal foi detectada. Use a busca por tese no final da página.')
    else:
        st.markdown('#### Referências auditadas')
        limit = len(results) if unlocked else min(1, len(results))
        for item in results[:limit]:
            result_item(item)
        if not unlocked and len(results) > limit:
            payment_box(cfg, analysis)
    if unlocked:
        if analysis.get('thesis_results'):
            st.markdown('#### Teses sugeridas')
            for group in analysis.get('thesis_results', []):
                with st.expander(group.get('tese','Tese identificada')):
                    st.write(group.get('preview',''))
                    for sug in group.get('sugestoes', []):
                        st.markdown(f"**{sug.get('citacao_curta','Precedente')}**")
                        st.caption(compact(sug.get('fundamento_curto',''), 700))
        revised = build_revised_text(st.session_state.last_text, analysis, mode='premium')
        marked = build_marked_text(st.session_state.last_text, analysis)
        rows = build_export_rows(analysis)
        st.markdown('#### Downloads')
        d1, d2, d3 = st.columns(3)
        d1.download_button('DOCX revisado', build_docx_bytes(marked, analysis, 'DECIFRA - Documento revisado', marked=True), 'decifra_documento_revisado.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d2.download_button('PDF técnico', build_pdf_bytes(revised, analysis, 'DECIFRA - Relatório técnico'), 'decifra_relatorio_tecnico.pdf', 'application/pdf', use_container_width=True)
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig')
        d3.download_button('CSV auditoria', csv_bytes, 'decifra_auditoria.csv', 'text/csv', use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


def manual_search(db_paths, unlocked):
    st.markdown('<div class="card"><span class="step">3 · Busca rápida</span>', unsafe_allow_html=True)
    q = st.text_input('Buscar precedente por tese ou número', placeholder='Ex.: inexequibilidade, diligência, Acórdão 1211/2021')
    if st.button('Buscar na base', use_container_width=True):
        if not q.strip():
            st.warning('Digite uma tese ou referência.')
        else:
            data = cached_manual_search(db_paths, q.strip(), 'acordao,sumula,jurisprudencia', 8 if unlocked else 2)
            matches = data.get('matches', [])
            if not matches:
                st.info('Nenhum resultado seguro encontrado na base local.')
            for m in matches:
                st.markdown('<div class="result">', unsafe_allow_html=True)
                st.markdown(f"**{m.get('citacao_curta','Resultado')}**")
                st.caption(compact(m.get('fundamento_curto',''), 700))
                st.markdown('</div>', unsafe_allow_html=True)
            if not unlocked:
                st.caption('A busca gratuita mostra resultados limitados.')
    st.markdown('</div>', unsafe_allow_html=True)


def main():
    cfg = get_config(st)
    css()
    check_payment_return(cfg)
    db_files = find_db_files(DB_DIR)
    db_paths = tuple(str(p) for p in db_files)
    summary = cached_summary(str(DB_DIR), db_signature(DB_DIR)) if db_files else {'total_files':0,'acordao':0,'total_size_mb':0}
    render_hero(cfg, summary)
    run_analysis(db_files, db_paths)
    unlocked = premium_active(st, cfg)
    analysis = st.session_state.get('analysis')
    if analysis:
        render_results(analysis, unlocked, cfg)
    manual_search(db_paths, unlocked)
    st.markdown('<div class="footer-note">Ferramenta de apoio técnico. A revisão final deve ser feita por profissional habilitado antes do protocolo.</div>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
