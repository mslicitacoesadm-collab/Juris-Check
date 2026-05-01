from __future__ import annotations

from pathlib import Path
import json
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
MODE_FILE = BASE_DIR / '.decifra_mode.json'

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


def read_mode(cfg) -> str:
    default = cfg.get('default_mode', 'pagamento')
    if default not in {'pagamento', 'livre'}:
        default = 'pagamento'
    try:
        if MODE_FILE.exists():
            data = json.loads(MODE_FILE.read_text(encoding='utf-8'))
            mode = str(data.get('mode', default)).lower()
            if mode in {'pagamento', 'livre'}:
                return mode
    except Exception:
        pass
    return default


def write_mode(mode: str):
    MODE_FILE.write_text(json.dumps({'mode': mode}, ensure_ascii=False, indent=2), encoding='utf-8')


def css():
    st.markdown('''
<style>
:root{--bg:#f7f8fb;--card:#ffffff;--ink:#101828;--muted:#667085;--line:#e5e7eb;--navy:#071d35;--navy2:#10375f;--accent:#c9973a;--soft:#f9fafb;--danger:#b42318;--warn:#b54708;--ok:#027a48}
.stApp{background:radial-gradient(circle at top left,#eef4fb 0,#f8fafc 35%,#f3f5f8 100%);color:var(--ink)}
.block-container{max-width:1180px;padding-top:1.1rem;padding-bottom:3rem}.main .block-container{padding-left:1.2rem;padding-right:1.2rem}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
.hero{background:linear-gradient(135deg,#071d35 0%,#10375f 60%,#1b4f7d 100%);border-radius:28px;padding:30px;color:white;box-shadow:0 28px 80px rgba(16,24,40,.22);border:1px solid rgba(255,255,255,.12);position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-95px;top:-90px;width:270px;height:270px;border-radius:999px;background:rgba(255,255,255,.08)}.hero:before{content:"";position:absolute;right:70px;bottom:-90px;width:210px;height:210px;border-radius:999px;border:1px solid rgba(255,255,255,.12)}
.brand{font-size:.76rem;text-transform:uppercase;letter-spacing:.16em;font-weight:950;color:#f4d48d}.hero h1{font-size:clamp(2rem,4.8vw,3.9rem);line-height:1;letter-spacing:-.052em;margin:.45rem 0 .7rem;font-weight:950}.hero p{font-size:1.02rem;line-height:1.62;color:#e8eef7;max-width:760px;margin:0}.mode-pill{display:inline-flex;margin-top:1rem;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:#fff;border-radius:999px;padding:.56rem .9rem;font-weight:900}.price-pill{display:inline-flex;margin-top:1rem;margin-left:.45rem;background:#fff;color:#071d35;border-radius:999px;padding:.56rem .9rem;font-weight:950;box-shadow:0 12px 30px rgba(0,0,0,.16)}
.card{background:rgba(255,255,255,.95);border:1px solid var(--line);border-radius:24px;padding:21px;box-shadow:0 18px 45px rgba(16,24,40,.075);margin-top:16px}.card.slim{padding:15px}.step{display:inline-flex;gap:.5rem;align-items:center;background:#eef4fb;color:#10375f;border:1px solid #d8e6f5;border-radius:999px;padding:.42rem .72rem;font-size:.80rem;font-weight:950;margin-bottom:12px}.muted{color:var(--muted)}.mini{font-size:.84rem;color:var(--muted)}
.metric{background:var(--soft);border:1px solid var(--line);border-radius:17px;padding:15px}.metric b{font-size:1.58rem;display:block;letter-spacing:-.04em}.metric span{color:var(--muted);font-size:.84rem}.result{border:1px solid var(--line);background:#fff;border-radius:18px;padding:15px;margin:12px 0}.badge{display:inline-block;border-radius:999px;padding:.25rem .60rem;font-size:.72rem;font-weight:950;margin-bottom:.45rem}.ok{background:#ecfdf3;color:var(--ok);border:1px solid #abefc6}.warn{background:#fffaeb;color:var(--warn);border:1px solid #fedf89}.danger{background:#fef3f2;color:var(--danger);border:1px solid #fecdca}
.lock{background:linear-gradient(135deg,#fff9ec,#ffffff);border:1px solid #efd49c;border-radius:22px;padding:22px;text-align:center;margin:16px 0;box-shadow:0 20px 46px rgba(184,135,45,.12)}.lock h3{margin-top:0}.secure{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:12px;justify-content:center}.secure span{background:#f2f4f7;color:#344054;border:1px solid #e4e7ec;border-radius:999px;padding:.38rem .7rem;font-size:.76rem;font-weight:850}
.preview-wrap{position:relative;border:1px solid var(--line);border-radius:20px;background:#fff;overflow:hidden;margin-top:14px}.preview-title{padding:14px 16px;border-bottom:1px solid var(--line);font-weight:950;color:#10375f}.piece-preview{padding:18px;max-height:280px;overflow:hidden;white-space:pre-wrap;font-family:Georgia,serif;font-size:.93rem;line-height:1.65;color:#263348}.piece-preview.blurred{filter:blur(4px);user-select:none;max-height:260px}.fade-lock{position:absolute;inset:48px 0 0 0;background:linear-gradient(180deg,rgba(255,255,255,.24),rgba(255,255,255,.94) 62%,#fff 100%);display:flex;align-items:center;justify-content:center;text-align:center;padding:22px}.fade-lock>div{background:rgba(255,255,255,.96);border:1px solid #efd49c;border-radius:18px;padding:16px;box-shadow:0 16px 45px rgba(16,24,40,.12);max-width:520px}.admin-box{border:1px dashed #cfd7e3;border-radius:18px;padding:14px;background:#fbfcff}.footer-note{text-align:center;color:var(--muted);font-size:.82rem;margin-top:20px}
.stButton>button,.stDownloadButton>button{border-radius:14px!important;min-height:3rem;font-weight:850!important;border:1px solid #d0d5dd!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#10375f,#071d35)!important;color:#fff!important;border:0!important}.stTextInput input,.stTextArea textarea{border-radius:14px!important;border-color:#d0d5dd!important}.stFileUploader section{border-radius:18px!important;border-color:#d0d5dd!important;background:#fbfcfe!important}a[data-testid="stLinkButton"]{border-radius:14px!important;font-weight:850!important}
@media(max-width:760px){.block-container{padding-left:.82rem!important;padding-right:.82rem!important;padding-top:.7rem}.hero{padding:22px;border-radius:22px}.hero p{font-size:.96rem}.card{padding:16px;border-radius:20px}.metric{padding:12px}.metric b{font-size:1.22rem}.price-pill,.mode-pill{width:100%;justify-content:center;margin-left:0}.piece-preview{font-size:.88rem}.fade-lock{padding:12px}}
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


def render_hero(cfg, summary, mode):
    mode_label = 'MODO LIVRE PARA TESTES' if mode == 'livre' else 'PAGAMENTO ATIVO'
    st.markdown(f'''
<div class="hero">
  <div class="brand">DECIFRA LICITAÇÕES</div>
  <h1>Auditoria jurídica antes do protocolo.</h1>
  <p>Valide precedentes, identifique riscos e gere uma peça revisada com mais segurança. Direto na tela principal, sem fluxo confuso.</p>
  <div class="mode-pill">{mode_label}</div><div class="price-pill">Completo · R$ {cfg['price']}</div>
</div>
<div class="card slim"><b>Base local:</b> {summary.get('total_files',0)} arquivo(s) · {summary.get('acordao',0):,} registros detectados <span class="muted">— envie suas bases .db para <code>data/base/</code>.</span></div>
'''.replace(',', '.'), unsafe_allow_html=True)


def render_admin(cfg, mode):
    with st.expander('Área administrativa'):
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        if not st.session_state.admin_ok:
            pwd = st.text_input('Senha administrativa', type='password', placeholder='Digite a senha para liberar controles')
            if st.button('Entrar como administrador', use_container_width=True):
                if pwd and pwd == cfg.get('admin_password', ''):
                    st.session_state.admin_ok = True
                    st.rerun()
                else:
                    st.error('Senha administrativa inválida.')
        else:
            st.success('Administrador autenticado.')
            selected = st.radio(
                'Modo público do sistema',
                ['pagamento', 'livre'],
                index=0 if mode == 'pagamento' else 1,
                horizontal=True,
                help='Pagamento: libera apenas amostra grátis e exige checkout/código. Livre: libera tudo para testes públicos.'
            )
            if st.button('Salvar modo público', type='primary', use_container_width=True):
                write_mode(selected)
                st.success(f'Modo público alterado para: {selected.upper()}')
                st.rerun()
            c1, c2 = st.columns(2)
            if c1.button('Limpar análise da sessão', use_container_width=True):
                for k in DEFAULT_STATE:
                    if k != 'admin_ok':
                        st.session_state[k] = DEFAULT_STATE[k]
                st.rerun()
            if c2.button('Sair do admin', use_container_width=True):
                st.session_state.admin_ok = False
                st.rerun()
            st.caption('Dica de lançamento: use modo LIVRE para testar com clientes de confiança; depois mude para PAGAMENTO sem alterar código.')
        st.markdown('</div>', unsafe_allow_html=True)


def run_analysis(db_files, db_paths):
    st.markdown('<div class="card"><span class="step">1 · Enviar peça</span>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1], gap='large')
    with c1:
        uploaded = st.file_uploader('Arquivo PDF, DOCX ou TXT', type=['pdf', 'docx', 'txt'])
    with c2:
        manual_text = st.text_area('Ou cole o texto', height=145, placeholder='Cole aqui a impugnação, recurso, contrarrazão ou manifestação...')
    if st.button('Auditar agora', type='primary', use_container_width=True):
        if not db_files:
            st.error('Nenhuma base .db encontrada. Envie suas bases para data/base/.')
            st.stop()
        if uploaded is None and not manual_text.strip():
            st.error('Envie um arquivo ou cole o texto da peça.')
            st.stop()
        with st.spinner('Auditando peça...'):
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
            citation_results = [cached_validate(db_paths, ref, 4) for ref in refs[:50]]
            thesis_results = []
            for block in blocks:
                suggestions = cached_search(db_paths, block.get('texto', ''), block.get('tese_chave', ''), 'acordao,jurisprudencia,sumula', 3)
                if suggestions:
                    thesis_results.append({'tese': block.get('tese', 'Tese'), 'preview': block.get('preview', ''), 'sugestoes': suggestions})

            st.session_state.analysis = {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results, 'piece_text': piece_text, 'file_name': file_name}
            st.session_state.last_text = piece_text
            st.session_state.last_file_name = file_name
            st.session_state.order_id = make_order_id(file_name)
            st.session_state.premium_unlocked = False
            st.session_state.mp_preference = None
        st.success('Auditoria concluída.')
    st.markdown('</div>', unsafe_allow_html=True)


def render_metrics(analysis, unlocked):
    results = analysis.get('citation_results', [])
    total = len(results)
    issues = sum(1 for r in results if r.get('status') != 'valida_compatível')
    teses = len(analysis.get('thesis_results', []))
    liberados = total if unlocked else min(total, 1)
    cols = st.columns(4)
    data = [(total, 'referências'), (issues, 'atenções'), (teses, 'teses'), (liberados, 'liberados')]
    for col, (num, label) in zip(cols, data):
        col.markdown(f'<div class="metric"><b>{num}</b><span>{label}</span></div>', unsafe_allow_html=True)


def result_item(item):
    sug = item.get('correcao_sugerida') or item.get('matched_record') or {}
    cls = status_class(item.get('status', ''))
    st.markdown('<div class="result">', unsafe_allow_html=True)
    st.markdown(f'<span class="badge {cls}">{item.get("status_label", "Resultado")}</span>', unsafe_allow_html=True)
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


def render_piece_preview(analysis, unlocked):
    text = analysis.get('piece_text', '')
    title = analysis.get('file_name', 'peça enviada')
    safe = compact(text, 2500)
    st.markdown('<div class="preview-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="preview-title">Prévia da peça · {title}</div>', unsafe_allow_html=True)
    if unlocked:
        st.markdown(f'<div class="piece-preview">{safe}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="piece-preview blurred">{safe}</div>', unsafe_allow_html=True)
        st.markdown('<div class="fade-lock"><div><b>A peça foi lida e auditada.</b><br><span class="mini">A prévia completa fica protegida até liberar o relatório. Isso mostra valor sem entregar todo o trabalho gratuito.</span></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def payment_box(cfg, analysis):
    st.markdown('<div class="lock">', unsafe_allow_html=True)
    st.markdown('### Desbloquear relatório completo')
    st.write('Libera todas as referências, teses sugeridas, peça revisada e downloads finais.')
    st.markdown(f"## R$ {cfg['price']}")

    col1, col2 = st.columns(2, gap='medium')
    with col1:
        if cfg.get('mp_access_token'):
            if st.button('Gerar pagamento Mercado Pago', type='primary', use_container_width=True):
                order_id = st.session_state.get('order_id') or make_order_id(analysis.get('file_name', 'analise'))
                st.session_state.order_id = order_id
                st.session_state.mp_preference = create_mp_preference(cfg, order_id, 'DECIFRA Licitações - Relatório completo', price_float(cfg['price']))
            pref = st.session_state.get('mp_preference') or {}
            if pref.get('init_point'):
                st.link_button('Pagar agora', pref['init_point'], use_container_width=True)
            if pref.get('error'):
                st.error(pref['error'])
        else:
            st.info('Configure MERCADO_PAGO_ACCESS_TOKEN para ativar checkout automático.')

    with col2:
        code = st.text_input('Código de liberação', value=st.session_state.get('unlock_code', ''), placeholder='Cole o código recebido')
        if code:
            st.session_state.unlock_code = code.strip().upper()
            if validate_unlock_code(st.session_state.unlock_code, cfg.get('unlock_secret', ''), st.session_state.get('order_id', '')):
                st.session_state.premium_unlocked = True
                st.rerun()
        if cfg.get('pix_key'):
            st.caption('PIX manual')
            st.code(cfg.get('pix_key'))
        if cfg.get('whatsapp'):
            msg = f"Olá, quero liberar minha análise DECIFRA. Pedido: {st.session_state.get('order_id','')}"
            url = 'https://wa.me/' + re.sub(r'\D', '', cfg['whatsapp']) + '?text=' + msg.replace(' ', '%20')
            st.link_button('Enviar comprovante', url, use_container_width=True)

    st.markdown('<div class="secure"><span>Mercado Pago</span><span>PIX fallback</span><span>Sem login obrigatório</span></div>', unsafe_allow_html=True)

    if st.session_state.get('admin_ok') and st.session_state.get('order_id'):
        with st.expander('Administrador: liberar pagamento manual'):
            st.caption('Use após conferir o pagamento fora do checkout.')
            st.code(st.session_state.order_id)
            st.code(make_unlock_code(st.session_state.order_id, cfg.get('unlock_secret', '')))
    st.markdown('</div>', unsafe_allow_html=True)


def render_results(analysis, unlocked, cfg, mode):
    st.markdown('<div class="card"><span class="step">2 · Auditoria</span>', unsafe_allow_html=True)
    render_metrics(analysis, unlocked)
    render_piece_preview(analysis, unlocked)

    results = analysis.get('citation_results', [])
    if not results:
        st.info('Nenhuma citação formal foi detectada. Use a busca rápida abaixo para localizar tese ou precedente.')
    else:
        st.markdown('#### Referências auditadas')
        limit = len(results) if unlocked else min(1, len(results))
        for item in results[:limit]:
            result_item(item)
        if not unlocked and len(results) > limit:
            st.caption(f'{len(results) - limit} resultado(s) protegido(s) no relatório completo.')

    if not unlocked and mode == 'pagamento':
        payment_box(cfg, analysis)

    if unlocked:
        if mode == 'livre':
            st.success('Modo livre ativo: relatório completo liberado para testes.')
        if analysis.get('thesis_results'):
            st.markdown('#### Teses sugeridas')
            for group in analysis.get('thesis_results', []):
                with st.expander(group.get('tese', 'Tese identificada')):
                    st.write(group.get('preview', ''))
                    for sug in group.get('sugestoes', []):
                        st.markdown(f"**{sug.get('citacao_curta','Precedente')}**")
                        st.caption(compact(sug.get('fundamento_curto',''), 700))

        revised = build_revised_text(st.session_state.last_text, analysis, mode='premium')
        marked = build_marked_text(st.session_state.last_text, analysis)
        rows = build_export_rows(analysis)
        st.markdown('#### Exportação')
        d1, d2, d3 = st.columns(3)
        d1.download_button('DOCX revisado', build_docx_bytes(marked, analysis, 'DECIFRA - Documento revisado', marked=True), 'decifra_documento_revisado.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d2.download_button('PDF técnico', build_pdf_bytes(revised, analysis, 'DECIFRA - Relatório técnico'), 'decifra_relatorio_tecnico.pdf', 'application/pdf', use_container_width=True)
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig')
        d3.download_button('CSV auditoria', csv_bytes, 'decifra_auditoria.csv', 'text/csv', use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


def manual_search(db_paths, unlocked, mode, cfg):
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
            if not unlocked and mode == 'pagamento':
                st.caption('A busca gratuita é limitada. O relatório completo libera mais resultados.')
    st.markdown('</div>', unsafe_allow_html=True)


def main():
    cfg = get_config(st)
    css()
    check_payment_return(cfg)
    mode = read_mode(cfg)
    db_files = find_db_files(DB_DIR)
    db_paths = tuple(str(p) for p in db_files)
    summary = cached_summary(str(DB_DIR), db_signature(DB_DIR)) if db_files else {'total_files': 0, 'acordao': 0, 'total_size_mb': 0}

    render_hero(cfg, summary, mode)
    render_admin(cfg, mode)

    run_analysis(db_files, db_paths)

    analysis = st.session_state.get('analysis')
    unlocked = True if mode == 'livre' else premium_active(st, cfg)
    if analysis:
        render_results(analysis, unlocked, cfg, mode)

    manual_search(db_paths, unlocked, mode, cfg)
    st.markdown('<div class="footer-note">Ferramenta de apoio técnico. A revisão final deve ser feita por profissional habilitado antes do protocolo.</div>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
