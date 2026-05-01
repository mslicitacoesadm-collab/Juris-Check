from __future__ import annotations

from pathlib import Path
import re
import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_references_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_pdf_bytes, build_revised_text, build_audit_docx_bytes
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_audit_summary, risk_level
from modules.search_engine import search_candidates, search_manual_precedents, validate_reference
from modules.commercial import (
    get_config,
    load_admin_settings,
    save_admin_settings,
    make_order_id,
    make_unlock_code,
    premium_active,
    validate_unlock_code,
    create_mp_preference,
    get_mp_payment_status,
    price_to_float,
)

st.set_page_config(page_title='DECIFRA Licitações', page_icon='⚖️', layout='wide', initial_sidebar_state='collapsed')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'
SETTINGS_FILE = BASE_DIR / '.decifra_admin_config.json'

DEFAULT_STATE = {
    'analysis': None,
    'last_text': '',
    'last_file_name': '',
    'order_id': '',
    'unlock_code': '',
    'premium_unlocked': False,
    'mp_preference': None,
    'admin_ok': False,
}
for key, value in DEFAULT_STATE.items():
    st.session_state.setdefault(key, value)


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


def compact(text: str, limit: int = 420) -> str:
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text[:limit] + ('...' if len(text) > limit else '')


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


def css():
    st.markdown('''
<style>
:root{--ink:#101828;--muted:#667085;--line:#E4E7EC;--navy:#071D35;--navy2:#10375F;--gold:#C9973A;--soft:#F8FAFC;--green:#027A48;--red:#B42318;--amber:#B54708}
.stApp{background:linear-gradient(135deg,#F6F8FB 0%,#EEF3F8 52%,#F7F8FA 100%);color:var(--ink)}
.block-container{max-width:1180px;padding-top:1rem;padding-bottom:3rem}.main .block-container{padding-left:1.1rem;padding-right:1.1rem}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
.hero{background:linear-gradient(135deg,#06182C 0%,#0B2A4A 58%,#123F69 100%);border-radius:30px;padding:30px;color:white;box-shadow:0 30px 90px rgba(16,24,40,.24);border:1px solid rgba(255,255,255,.12);position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-95px;top:-85px;width:280px;height:280px;border-radius:999px;background:rgba(255,255,255,.075)}
.kicker{font-size:.74rem;text-transform:uppercase;letter-spacing:.18em;font-weight:950;color:#F5D99A}.hero h1{font-size:clamp(2.05rem,5vw,4rem);line-height:.98;letter-spacing:-.055em;margin:.45rem 0 .75rem;font-weight:950}.hero p{font-size:1.02rem;line-height:1.62;color:#E8EEF7;max-width:780px;margin:0}
.pill{display:inline-flex;align-items:center;gap:.35rem;margin-top:1rem;margin-right:.45rem;border-radius:999px;padding:.55rem .85rem;font-size:.80rem;font-weight:950;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.12);color:#fff}.pill.gold{background:#fff;color:#071D35;border-color:#fff}.pill.free{background:#ECFDF3;color:#027A48;border-color:#ABEFC6}
.card{background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:24px;padding:21px;box-shadow:0 18px 45px rgba(16,24,40,.075);margin-top:16px}.card.compact{padding:15px}.step{display:inline-flex;background:#EAF2FA;color:#10375F;border:1px solid #D8E6F5;border-radius:999px;padding:.42rem .72rem;font-size:.80rem;font-weight:950;margin-bottom:12px}.muted,.mini{color:var(--muted)}.mini{font-size:.84rem}.section-title{font-size:1.05rem;font-weight:950;margin:12px 0;color:#071D35}.metric{background:#F9FAFB;border:1px solid var(--line);border-radius:18px;padding:15px}.metric b{font-size:1.55rem;display:block;letter-spacing:-.04em}.metric span{color:var(--muted);font-size:.84rem}.result{border:1px solid var(--line);background:#fff;border-radius:18px;padding:15px;margin:12px 0}.badge{display:inline-block;border-radius:999px;padding:.25rem .60rem;font-size:.72rem;font-weight:950;margin-bottom:.45rem}.ok{background:#ECFDF3;color:var(--green);border:1px solid #ABEFC6}.warn{background:#FFFAEB;color:var(--amber);border:1px solid #FEDF89}.danger{background:#FEF3F2;color:var(--red);border:1px solid #FECDCA}.info{background:#EFF8FF;color:#175CD3;border:1px solid #B2DDFF}
.lock{background:linear-gradient(135deg,#FFF9EC,#FFFFFF);border:1px solid #EFD49C;border-radius:22px;padding:22px;text-align:center;margin:16px 0;box-shadow:0 20px 46px rgba(184,135,45,.12)}.lock h3{margin-top:0}.secure{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:12px;justify-content:center}.secure span{background:#F2F4F7;color:#344054;border:1px solid #E4E7EC;border-radius:999px;padding:.38rem .7rem;font-size:.76rem;font-weight:850}
.preview-wrap{position:relative;border:1px solid var(--line);border-radius:20px;background:#fff;overflow:hidden;margin-top:14px}.preview-title{padding:14px 16px;border-bottom:1px solid var(--line);font-weight:950;color:#10375F}.piece-preview{padding:18px;max-height:330px;overflow:hidden;white-space:pre-wrap;font-family:Georgia,'Times New Roman',serif;font-size:.94rem;line-height:1.68;color:#263348}.piece-preview.blurred{filter:blur(4.5px);user-select:none;max-height:280px}.fade-lock{position:absolute;inset:49px 0 0 0;background:linear-gradient(180deg,rgba(255,255,255,.16),rgba(255,255,255,.93) 65%,#fff 100%);display:flex;align-items:center;justify-content:center;text-align:center;padding:22px}.fade-lock>div{background:rgba(255,255,255,.97);border:1px solid #EFD49C;border-radius:18px;padding:16px;box-shadow:0 16px 45px rgba(16,24,40,.12);max-width:560px}.admin-box{border:1px dashed #CBD5E1;border-radius:18px;padding:15px;background:#FBFCFF}.admin-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.footer-note{text-align:center;color:var(--muted);font-size:.82rem;margin-top:20px}.audit-line{padding:.65rem .8rem;border-radius:14px;background:#F8FAFC;border:1px solid #EAECF0;margin:.45rem 0}
.stButton>button,.stDownloadButton>button{border-radius:14px!important;min-height:3rem;font-weight:850!important;border:1px solid #D0D5DD!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#10375F,#071D35)!important;color:#fff!important;border:0!important}.stTextInput input,.stTextArea textarea,.stNumberInput input{border-radius:14px!important;border-color:#D0D5DD!important}.stFileUploader section{border-radius:18px!important;border-color:#D0D5DD!important;background:#FBFCFE!important}a[data-testid="stLinkButton"]{border-radius:14px!important;font-weight:850!important}
@media(max-width:760px){.block-container{padding-left:.82rem!important;padding-right:.82rem!important;padding-top:.7rem}.hero{padding:22px;border-radius:22px}.hero p{font-size:.96rem}.card{padding:16px;border-radius:20px}.metric{padding:12px}.metric b{font-size:1.22rem}.pill{width:100%;justify-content:center;margin-right:0}.piece-preview{font-size:.88rem}.fade-lock{padding:12px}.admin-grid{grid-template-columns:1fr}}
</style>
''', unsafe_allow_html=True)


def status_class(status: str):
    if status == 'valida_compatível':
        return 'ok'
    if status == 'valida_pouco_compativel':
        return 'warn'
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


def render_hero(cfg, settings, summary):
    mode = settings.get('mode', 'pagamento')
    mode_label = 'MODO LIVRE ATIVO' if mode == 'livre' else 'MODO PAGAMENTO ATIVO'
    mode_cls = 'free' if mode == 'livre' else ''
    st.markdown(f'''
<div class="hero">
  <div class="kicker">{cfg.get('brand_name','DECIFRA Licitações')}</div>
  <h1>Auditoria técnica de peças de licitação</h1>
  <p>Valide citações, identifique pontos frágeis e gere um relatório profissional com registro claro do que foi conferido, sugerido e marcado para revisão.</p>
  <div>
    <span class="pill {mode_cls}">{mode_label}</span>
    <span class="pill gold">R$ {settings.get('price', cfg.get('price','19,90'))}</span>
    <span class="pill">{summary.get('total_files',0)} base(s) conectada(s)</span>
  </div>
</div>
''', unsafe_allow_html=True)


def render_admin(cfg, settings):
    with st.expander('Administração da ferramenta', expanded=False):
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        if not st.session_state.admin_ok:
            pwd = st.text_input('Senha administrativa', type='password', placeholder='Digite a senha')
            if st.button('Entrar como administrador', type='primary', use_container_width=True):
                if pwd == cfg.get('admin_password'):
                    st.session_state.admin_ok = True
                    st.rerun()
                else:
                    st.error('Senha administrativa inválida.')
        else:
            st.success('Painel administrativo liberado.')
            c1, c2, c3 = st.columns(3)
            new_mode = c1.radio('Modo público', ['pagamento', 'livre'], index=0 if settings.get('mode') == 'pagamento' else 1, horizontal=True)
            new_price = c2.text_input('Preço do desbloqueio', value=str(settings.get('price', cfg.get('price','19,90'))))
            new_free_limit = c3.number_input('Resultados grátis', min_value=0, max_value=10, value=int(settings.get('free_limit', 1)), step=1)

            c4, c5, c6 = st.columns(3)
            blur_preview = c4.toggle('Prévia com blur', value=bool(settings.get('blur_preview', True)))
            mp_enabled = c5.toggle('Mercado Pago ativo', value=bool(settings.get('mp_enabled', True)))
            pix_enabled = c6.toggle('PIX/WhatsApp fallback', value=bool(settings.get('pix_enabled', True)))

            c7, c8, c9 = st.columns(3)
            manual_code = c7.toggle('Código manual ativo', value=bool(settings.get('manual_code_enabled', True)))
            show_search = c8.toggle('Busca rápida visível', value=bool(settings.get('show_manual_search', True)))
            show_teaser = c9.toggle('Teaser comercial visível', value=bool(settings.get('show_admin_teaser', True)))

            pix_key = st.text_input('Chave PIX exibida no fallback', value=str(settings.get('pix_key') or cfg.get('pix_key','')))
            whatsapp = st.text_input('WhatsApp para comprovante', value=str(settings.get('whatsapp') or cfg.get('whatsapp','')))

            b1, b2, b3 = st.columns(3)
            if b1.button('Salvar configurações', type='primary', use_container_width=True):
                save_admin_settings(SETTINGS_FILE, {
                    'mode': new_mode,
                    'price': new_price,
                    'free_limit': int(new_free_limit),
                    'blur_preview': bool(blur_preview),
                    'mp_enabled': bool(mp_enabled),
                    'pix_enabled': bool(pix_enabled),
                    'manual_code_enabled': bool(manual_code),
                    'show_manual_search': bool(show_search),
                    'show_admin_teaser': bool(show_teaser),
                    'pix_key': pix_key,
                    'whatsapp': whatsapp,
                })
                st.success('Configurações salvas.')
                st.rerun()
            if b2.button('Limpar sessão', use_container_width=True):
                for k, v in DEFAULT_STATE.items():
                    if k != 'admin_ok':
                        st.session_state[k] = v
                st.rerun()
            if b3.button('Sair do admin', use_container_width=True):
                st.session_state.admin_ok = False
                st.rerun()

            st.markdown('##### Controle de liberação manual')
            if st.session_state.get('order_id'):
                st.caption('Use apenas após conferir pagamento/manualmente. Não compartilhe a chave secreta.')
                st.code(f"Pedido: {st.session_state.order_id}")
                st.code(f"Código: {make_unlock_code(st.session_state.order_id, cfg.get('unlock_secret',''))}")
            else:
                st.caption('Depois que uma análise for feita, o pedido e o código de liberação aparecerão aqui.')

            st.markdown('##### Sugestões futuras para o painel')
            st.markdown('- Histórico simples de análises e desbloqueios em CSV local.\n- Campo de cupom por campanha.\n- Limite por IP/sessão para evitar uso abusivo no modo livre.\n- Mensagens comerciais A/B para testar conversão.\n- Dashboard de receita estimada por dia.')
        st.markdown('</div>', unsafe_allow_html=True)


def run_analysis(db_files, db_paths):
    st.markdown('<div class="card"><span class="step">1 · Enviar peça</span>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1], gap='large')
    with c1:
        uploaded = st.file_uploader('Arquivo PDF, DOCX ou TXT', type=['pdf', 'docx', 'txt'])
    with c2:
        manual_text = st.text_area('Ou cole o texto', height=145, placeholder='Cole aqui a impugnação, recurso, contrarrazão ou manifestação...')

    if st.button('Auditar peça agora', type='primary', use_container_width=True):
        if not db_files:
            st.error('Nenhuma base .db encontrada. Envie suas bases para data/base/.')
            st.stop()
        if uploaded is None and not manual_text.strip():
            st.error('Envie um arquivo ou cole o texto da peça.')
            st.stop()
        with st.spinner('Auditando a peça com base local...'):
            if uploaded is not None:
                piece_text = read_uploaded_file(uploaded)
                file_name = uploaded.name
            else:
                piece_text = manual_text.strip()
                file_name = 'texto_colado.txt'
            if len((piece_text or '').strip()) < 40:
                st.error('Não foi possível extrair texto suficiente. Use DOCX/TXT ou cole o conteúdo manualmente.')
                st.stop()

            refs = extract_references_with_context(piece_text)
            piece_type = classify_piece_type(piece_text)
            blocks = split_into_argument_blocks(piece_text, max_blocks=6)
            citation_results = [cached_validate(db_paths, ref, 4) for ref in refs[:60]]
            thesis_results = []
            for block in blocks:
                suggestions = cached_search(db_paths, block.get('texto', ''), block.get('tese_chave', ''), 'acordao,jurisprudencia,sumula', 3)
                if suggestions:
                    thesis_results.append({'tese': block.get('tese', 'Tese'), 'preview': block.get('preview', ''), 'sugestoes': suggestions})

            st.session_state.analysis = {
                'piece_type': piece_type,
                'citation_results': citation_results,
                'thesis_results': thesis_results,
                'piece_text': piece_text,
                'file_name': file_name,
            }
            st.session_state.last_text = piece_text
            st.session_state.last_file_name = file_name
            st.session_state.order_id = make_order_id(file_name)
            st.session_state.premium_unlocked = False
            st.session_state.mp_preference = None
        st.success('Auditoria concluída.')
    st.markdown('</div>', unsafe_allow_html=True)


def render_metrics(analysis, unlocked):
    summary = build_audit_summary(analysis)
    cols = st.columns(4)
    data = [
        (summary['total_referencias'], 'referências'),
        (summary['pontos_revisao'], 'pontos de revisão'),
        (summary['teses_sugeridas'], 'teses sugeridas'),
        (summary['risco'], 'risco técnico'),
    ]
    for col, (num, label) in zip(cols, data):
        col.markdown(f'<div class="metric"><b>{num}</b><span>{label}</span></div>', unsafe_allow_html=True)


def result_item(item):
    sug = item.get('correcao_sugerida') or item.get('matched_record') or {}
    cls = status_class(item.get('status', ''))
    st.markdown('<div class="result">', unsafe_allow_html=True)
    st.markdown(f'<span class="badge {cls}">{item.get("status_label", "Resultado")}</span>', unsafe_allow_html=True)
    st.markdown(f"**{item.get('raw','Referência')}**")
    st.caption(f"Linha aproximada {item.get('linha','-')} · Confiança {item.get('grau_confianca','')} · {item.get('tipo_erro','')}")
    if sug:
        st.markdown(f"**Depois / sugestão segura:** {sug.get('citacao_curta','')}")
        if sug.get('fundamento_curto'):
            st.write(compact(sug.get('fundamento_curto'), 680))
    if item.get('paragrafo_reescrito'):
        with st.expander('Sugestão textual para conferência'):
            st.write(item.get('paragrafo_reescrito'))
    st.markdown('</div>', unsafe_allow_html=True)


def render_piece_preview(analysis, unlocked, settings):
    text = analysis.get('piece_text', '')
    title = analysis.get('file_name', 'peça enviada')
    safe = compact(text, 3200)
    blur = bool(settings.get('blur_preview', True))
    st.markdown('<div class="preview-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="preview-title">Prévia real da peça · {title}</div>', unsafe_allow_html=True)
    if unlocked or not blur:
        st.markdown(f'<div class="piece-preview">{safe}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="piece-preview blurred">{safe}</div>', unsafe_allow_html=True)
        st.markdown('<div class="fade-lock"><div><b>A peça foi lida e auditada.</b><br><span class="mini">O texto real fica parcialmente desfocado para demonstrar valor sem entregar a revisão completa. Desbloqueie para baixar a peça marcada e o relatório técnico.</span></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def payment_box(cfg, settings, analysis):
    price = settings.get('price') or cfg.get('price', '19,90')
    st.markdown('<div class="lock">', unsafe_allow_html=True)
    st.markdown('### Desbloquear entrega completa')
    st.write('Libera todas as referências, o relatório técnico, a peça com marcações e a planilha de auditoria.')
    st.markdown(f"## R$ {price}")

    col1, col2 = st.columns(2, gap='medium')
    with col1:
        if settings.get('mp_enabled', True) and cfg.get('mp_access_token'):
            if st.button('Gerar pagamento Mercado Pago', type='primary', use_container_width=True):
                order_id = st.session_state.get('order_id') or make_order_id(analysis.get('file_name', 'analise'))
                st.session_state.order_id = order_id
                st.session_state.mp_preference = create_mp_preference(cfg, settings, order_id, 'DECIFRA Licitações - Relatório completo', price_to_float(price))
            pref = st.session_state.get('mp_preference') or {}
            if pref.get('init_point'):
                st.link_button('Pagar com Mercado Pago', pref['init_point'], use_container_width=True)
            if pref.get('error'):
                st.error(pref['error'])
        elif settings.get('mp_enabled', True):
            st.info('Configure MERCADO_PAGO_ACCESS_TOKEN para ativar o checkout automático.')
        else:
            st.info('Mercado Pago está desativado no painel admin.')

    with col2:
        if settings.get('manual_code_enabled', True):
            code = st.text_input('Código de liberação', value=st.session_state.get('unlock_code', ''), placeholder='Cole o código recebido')
            if code:
                st.session_state.unlock_code = code.strip().upper()
                if validate_unlock_code(st.session_state.unlock_code, cfg.get('unlock_secret', ''), st.session_state.get('order_id', '')):
                    st.session_state.premium_unlocked = True
                    st.rerun()
        if settings.get('pix_enabled', True):
            pix_key = settings.get('pix_key') or cfg.get('pix_key')
            whatsapp = settings.get('whatsapp') or cfg.get('whatsapp')
            if pix_key:
                st.caption('PIX manual')
                st.code(pix_key)
            if whatsapp:
                msg = f"Olá, quero liberar minha análise DECIFRA. Pedido: {st.session_state.get('order_id','')}"
                url = 'https://wa.me/' + re.sub(r'\D', '', whatsapp) + '?text=' + msg.replace(' ', '%20')
                st.link_button('Enviar comprovante', url, use_container_width=True)

    st.markdown('<div class="secure"><span>Checkout Pro</span><span>PIX fallback</span><span>Liberação manual</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_results(analysis, unlocked, cfg, settings):
    st.markdown('<div class="card"><span class="step">2 · Resultado técnico</span>', unsafe_allow_html=True)
    render_metrics(analysis, unlocked)
    summary = build_audit_summary(analysis)
    risk, reason = risk_level(analysis)
    badge_cls = 'danger' if risk == 'ALTO' else 'warn' if risk in {'MÉDIO', 'INDETERMINADO'} else 'ok'
    st.markdown(f'<div class="audit-line"><span class="badge {badge_cls}">Risco {risk}</span><br><b>Diagnóstico:</b> {reason}</div>', unsafe_allow_html=True)
    render_piece_preview(analysis, unlocked, settings)

    results = analysis.get('citation_results', []) or []
    st.markdown('<div class="section-title">Referências auditadas</div>', unsafe_allow_html=True)
    if not results:
        st.info('Nenhuma citação formal foi detectada. A peça pode ser analisada pela busca rápida de tese abaixo.')
    else:
        limit = len(results) if unlocked else min(int(settings.get('free_limit', 1)), len(results))
        for item in results[:limit]:
            result_item(item)
        if not unlocked and len(results) > limit:
            st.caption(f'{len(results) - limit} resultado(s) protegido(s) no relatório completo.')

    if not unlocked and settings.get('mode') == 'pagamento':
        payment_box(cfg, settings, analysis)

    if unlocked:
        if settings.get('mode') == 'livre':
            st.success('Modo livre ativo: entrega completa liberada para testes.')
        if analysis.get('thesis_results'):
            st.markdown('<div class="section-title">Teses e precedentes de reforço</div>', unsafe_allow_html=True)
            for group in analysis.get('thesis_results', []):
                with st.expander(group.get('tese', 'Tese identificada')):
                    st.write(group.get('preview', ''))
                    for sug in group.get('sugestoes', []):
                        st.markdown(f"**{sug.get('citacao_curta','Precedente')}**")
                        st.caption(compact(sug.get('fundamento_curto',''), 700))

        revised = build_revised_text(st.session_state.last_text, analysis, mode='premium')
        rows = build_export_rows(analysis)
        st.markdown('<div class="section-title">Downloads profissionais</div>', unsafe_allow_html=True)
        st.caption('A peça marcada mostra exatamente os pontos validados, sugeridos ou pendentes de revisão. O relatório é separado para anexar ou conferir internamente.')
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button('Peça marcada DOCX', build_docx_bytes(st.session_state.last_text, analysis, 'DECIFRA - Peça revisada com marcações', marked=True), 'DECIFRA_peca_revisada_marcada.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d2.download_button('Relatório DOCX', build_audit_docx_bytes(analysis), 'DECIFRA_relatorio_auditoria.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d3.download_button('Relatório PDF', build_pdf_bytes(st.session_state.last_text, analysis, 'DECIFRA - Relatório técnico de auditoria'), 'DECIFRA_relatorio_tecnico.pdf', 'application/pdf', use_container_width=True)
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig')
        d4.download_button('Planilha CSV', csv_bytes, 'DECIFRA_auditoria.csv', 'text/csv', use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


def manual_search(db_paths, unlocked, settings):
    if not settings.get('show_manual_search', True):
        return
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
                st.caption(compact(m.get('fundamento_curto',''), 700 if unlocked else 260))
                st.markdown('</div>', unsafe_allow_html=True)
            if not unlocked and settings.get('mode') == 'pagamento':
                st.caption('A busca gratuita é limitada. O relatório completo libera mais resultados.')
    st.markdown('</div>', unsafe_allow_html=True)


def render_teaser(settings):
    if not settings.get('show_admin_teaser', True):
        return
    st.markdown('''
<div class="card compact">
  <b>Entrega ao cliente:</b> diagnóstico na tela, peça com marcações, relatório de auditoria e planilha de conferência. Nada é apresentado como correção absoluta: o sistema informa o que foi localizado, sugerido e o que exige revisão jurídica final.
</div>
''', unsafe_allow_html=True)


def main():
    cfg = get_config(st)
    css()
    check_payment_return(cfg)
    settings = load_admin_settings(SETTINGS_FILE, cfg)
    db_files = find_db_files(DB_DIR)
    db_paths = tuple(str(p) for p in db_files)
    summary = cached_summary(str(DB_DIR), db_signature(DB_DIR)) if db_files else {'total_files': 0, 'acordao': 0, 'total_size_mb': 0}

    render_hero(cfg, settings, summary)
    render_admin(cfg, settings)
    render_teaser(settings)
    run_analysis(db_files, db_paths)

    analysis = st.session_state.get('analysis')
    unlocked = True if settings.get('mode') == 'livre' else premium_active(st, cfg)
    if analysis:
        render_results(analysis, unlocked, cfg, settings)

    manual_search(db_paths, unlocked, settings)
    st.markdown('<div class="footer-note">Ferramenta de apoio técnico. A revisão final deve ser feita por profissional habilitado antes do protocolo.</div>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
