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
from modules.commercial import (
    get_config,
    make_order_id,
    make_unlock_code,
    premium_active,
    validate_unlock_code,
    create_mp_preference,
    get_mp_payment_status,
)

st.set_page_config(page_title="DECIFRA Licitações", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data" / "base"

DEFAULT_STATE = {
    "analysis": None,
    "last_text": "",
    "last_file_name": "",
    "order_id": "",
    "unlock_code": "",
    "premium_unlocked": False,
    "mp_preference": None,
    "payment_checked": False,
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
    kinds = set(kinds_key.split(",")) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, kinds=kinds, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_manual_search(db_paths, query_text: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(",")) if kinds_key else None
    return search_manual_precedents([Path(p) for p in db_paths], query_text, kinds=kinds, top_k=top_k)


def price_float(price_text: str) -> float:
    clean = str(price_text or "19,90").replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(clean)
    except Exception:
        return 19.90


def safe_query_params():
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}


def first_param(params: dict, *names: str) -> str:
    for name in names:
        value = params.get(name)
        if isinstance(value, list):
            value = value[0] if value else ""
        if value:
            return str(value)
    return ""


def status_badge(status: str) -> str:
    if status == "valida_compatível":
        return "ok"
    if status == "valida_pouco_compativel":
        return "warn"
    return "danger"


def small_text(text: str, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def render_css():
    st.markdown("""
<style>
:root{--bg:#070A12;--panel:#0D1220;--line:rgba(255,255,255,.10);--text:#F8FAFC;--muted:#A3AEC2;--gold:#D9B45F;}
.stApp{background:radial-gradient(circle at 15% 0%,rgba(217,180,95,.18),transparent 28%),radial-gradient(circle at 85% 10%,rgba(125,211,252,.10),transparent 26%),linear-gradient(180deg,#070A12 0%,#090D16 48%,#070A12 100%);color:var(--text);}
.block-container{max-width:1180px;padding-top:1.6rem;padding-bottom:3rem;}
[data-testid="stSidebar"]{background:#070A12;}
.hero{border:1px solid var(--line);border-radius:30px;padding:30px;background:linear-gradient(135deg,rgba(255,255,255,.08),rgba(255,255,255,.03));box-shadow:0 28px 90px rgba(0,0,0,.35);position:relative;overflow:hidden}
.kicker{color:var(--gold);font-weight:800;letter-spacing:.11em;font-size:.76rem;text-transform:uppercase}
.hero h1{font-size:clamp(2.15rem,5vw,4.7rem);line-height:.96;margin:.35rem 0 .75rem;font-weight:900;letter-spacing:-.055em}
.hero p{font-size:1.06rem;color:var(--muted);max-width:760px;margin:0}
.card{border:1px solid var(--line);background:rgba(13,18,32,.83);border-radius:24px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.22);backdrop-filter:blur(10px);margin-top:14px}
.step{display:inline-flex;align-items:center;gap:.55rem;background:rgba(217,180,95,.10);color:#F5D78D;border:1px solid rgba(217,180,95,.25);border-radius:999px;padding:.42rem .78rem;font-weight:800;font-size:.82rem}
.metric{border:1px solid var(--line);border-radius:20px;padding:18px;background:rgba(255,255,255,.045)}
.metric b{display:block;font-size:1.8rem;letter-spacing:-.04em}.metric span{color:var(--muted);font-size:.88rem}
.lock{border:1px solid rgba(217,180,95,.34);border-radius:24px;padding:24px;background:linear-gradient(135deg,rgba(217,180,95,.16),rgba(255,255,255,.035));text-align:center;margin-top:14px}
.result{border:1px solid var(--line);border-radius:20px;padding:18px;background:rgba(255,255,255,.04);margin-bottom:12px}
.badge{display:inline-block;border-radius:999px;padding:.24rem .62rem;font-size:.74rem;font-weight:900;margin-bottom:.4rem}
.badge.ok{background:rgba(25,195,125,.13);color:#8EF3C5;border:1px solid rgba(25,195,125,.28)}
.badge.warn{background:rgba(245,196,81,.13);color:#FFE09A;border:1px solid rgba(245,196,81,.28)}
.badge.danger{background:rgba(255,92,122,.13);color:#FFB4C1;border:1px solid rgba(255,92,122,.28)}
.muted{color:var(--muted)}.gold{color:var(--gold)}
.stButton>button,.stDownloadButton>button{border-radius:16px!important;font-weight:850!important;min-height:3rem}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#D9B45F,#FFE4A3)!important;color:#111827!important;border:0!important}
a[data-testid="stLinkButton"]{border-radius:16px!important;font-weight:850!important}
.stTextInput input,.stTextArea textarea{border-radius:16px!important}
@media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem;padding-top:.9rem}.hero{padding:22px;border-radius:24px}.card{padding:18px;border-radius:20px}.metric b{font-size:1.35rem}}
</style>
""", unsafe_allow_html=True)


def render_hero(cfg):
    st.markdown(f"""
<div class="hero">
  <div class="kicker">Auditoria jurídica automatizada</div>
  <h1>DECIFRA<br/>Licitações</h1>
  <p>Valide acórdãos, súmulas e precedentes antes do protocolo. Gere uma amostra grátis e desbloqueie a análise completa por <b class="gold">R$ {cfg['price']}</b>.</p>
</div>
""", unsafe_allow_html=True)


def render_upload_area(db_files, db_paths):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step">1 · Envie a peça</span>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        uploaded_file = st.file_uploader("Arquivo PDF, DOCX ou TXT", type=["pdf", "docx", "txt"], label_visibility="collapsed")
    with col2:
        manual_text = st.text_area("Ou cole o texto", height=132, placeholder="Cole aqui o trecho do recurso, impugnação ou contrarrazão...", label_visibility="collapsed")

    if st.button("Auditar agora", type="primary", use_container_width=True):
        if not db_files:
            st.error("Nenhuma base `.db` foi encontrada em `data/base/`.")
            st.stop()
        if uploaded_file is None and not manual_text.strip():
            st.error("Envie um arquivo ou cole o texto da peça.")
            st.stop()

        with st.spinner("Auditando referências e cruzando com a base local..."):
            if uploaded_file is not None:
                piece_text = read_uploaded_file(uploaded_file)
                file_name = uploaded_file.name
            else:
                piece_text = manual_text.strip()
                file_name = "texto_colado.txt"

            if not piece_text or len(piece_text.strip()) < 40:
                st.error("Não foi possível extrair texto suficiente. Tente DOCX/TXT ou cole o conteúdo manualmente.")
                st.stop()

            refs = extract_references_with_context(piece_text)
            piece_type = classify_piece_type(piece_text)
            blocks = split_into_argument_blocks(piece_text)[:6]

            results = [cached_validate(db_paths, ref, 4) for ref in refs[:40]]

            thesis_suggestions = []
            for block in blocks:
                q = block.get("text", "")[:1600]
                if q.strip():
                    found = cached_search(db_paths, q, block.get("title", ""), "acordao,sumula,jurisprudencia", 3)
                    if found:
                        thesis_suggestions.append({"title": block.get("title", "Tese identificada"), "matches": found})

            st.session_state.analysis = {
                "piece_type": piece_type,
                "citation_results": results,
                "thesis_suggestions": thesis_suggestions,
                "refs_count": len(refs),
                "file_name": file_name,
            }
            st.session_state.last_text = piece_text
            st.session_state.last_file_name = file_name
            st.session_state.order_id = make_order_id(file_name)
            st.session_state.premium_unlocked = False
            st.session_state.mp_preference = None
            st.session_state.payment_checked = False
            st.success("Auditoria concluída.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_metrics(analysis, unlocked: bool):
    results = analysis.get("citation_results", [])
    total = len(results)
    issues = sum(1 for r in results if r.get("status") != "valida_compatível")
    thesis = len(analysis.get("thesis_suggestions", []))
    shown = total if unlocked else min(total, 1)
    a, b, c, d = st.columns(4)
    with a:
        st.markdown(f'<div class="metric"><b>{total}</b><span>referências detectadas</span></div>', unsafe_allow_html=True)
    with b:
        st.markdown(f'<div class="metric"><b>{issues}</b><span>pontos de atenção</span></div>', unsafe_allow_html=True)
    with c:
        st.markdown(f'<div class="metric"><b>{thesis}</b><span>teses sugeridas</span></div>', unsafe_allow_html=True)
    with d:
        st.markdown(f'<div class="metric"><b>{shown}</b><span>itens liberados</span></div>', unsafe_allow_html=True)


def render_result_item(item):
    badge = status_badge(item.get("status", ""))
    st.markdown('<div class="result">', unsafe_allow_html=True)
    st.markdown(f'<span class="badge {badge}">{item.get("status_label", "Resultado")}</span>', unsafe_allow_html=True)
    st.markdown(f"**Referência:** {item.get('raw', '—')}")
    st.caption(f"{item.get('tipo_erro', '')} · {item.get('grau_confianca', '')}")
    suggested = item.get("correcao_sugerida") or item.get("matched_record") or {}
    if suggested:
        st.markdown(f"**Sugestão:** {suggested.get('citacao_curta', '—')}")
        st.markdown(f'<div class="muted">{small_text(suggested.get("fundamento_curto", ""), 520)}</div>', unsafe_allow_html=True)
    paragraph = item.get("paragrafo_reescrito")
    if paragraph:
        with st.expander("Texto sugerido para aproveitamento"):
            st.write(paragraph)
    st.markdown("</div>", unsafe_allow_html=True)


def render_payment_box(cfg, analysis):
    st.markdown('<div class="lock">', unsafe_allow_html=True)
    st.markdown("### 🔒 Análise completa bloqueada")
    st.write("A amostra gratuita foi liberada. Desbloqueie o relatório completo, teses sugeridas e arquivos finais para download.")
    st.markdown(f"## R$ {cfg['price']}")

    pay_col, pix_col = st.columns([1, 1], gap="medium")
    with pay_col:
        if cfg.get("mp_access_token"):
            if st.button("Gerar pagamento Mercado Pago", type="primary", use_container_width=True):
                order_id = st.session_state.get("order_id") or make_order_id(analysis.get("file_name", "analise"))
                st.session_state.order_id = order_id
                preference = create_mp_preference(
                    cfg=cfg,
                    order_id=order_id,
                    title="DECIFRA Licitações - Análise completa",
                    amount=price_float(cfg["price"]),
                )
                st.session_state.mp_preference = preference

            preference = st.session_state.get("mp_preference") or {}
            if preference.get("init_point"):
                st.link_button("Pagar com Mercado Pago", preference["init_point"], use_container_width=True)
                st.caption("Após o pagamento aprovado, volte para esta página para liberação automática.")
            elif preference.get("error"):
                st.error(preference["error"])
        else:
            st.info("Mercado Pago ainda não configurado. Cadastre o Access Token nos Secrets.")

    with pix_col:
        if cfg.get("pix_key"):
            st.markdown("**PIX manual**")
            st.code(cfg["pix_key"])
        if cfg.get("whatsapp"):
            msg = f"Olá, quero liberar minha análise DECIFRA. Pedido: {st.session_state.get('order_id','')}"
            url = "https://wa.me/" + re.sub(r"\D", "", cfg["whatsapp"]) + "?text=" + msg.replace(" ", "%20")
            st.link_button("Enviar comprovante no WhatsApp", url, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_outputs(analysis, unlocked: bool, cfg):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step">2 · Resultado</span>', unsafe_allow_html=True)
    render_metrics(analysis, unlocked)

    results = analysis.get("citation_results", [])
    if not results:
        st.info("Nenhuma citação formal foi detectada. Use a busca por tese abaixo para localizar precedentes úteis.")
    else:
        limit = len(results) if unlocked else min(1, len(results))
        st.markdown("#### Referências auditadas")
        for item in results[:limit]:
            render_result_item(item)
        if not unlocked and len(results) > limit:
            render_payment_box(cfg, analysis)

    if unlocked:
        thesis = analysis.get("thesis_suggestions", [])
        if thesis:
            st.markdown("#### Teses e precedentes sugeridos")
            for group in thesis:
                with st.expander(group.get("title", "Tese identificada"), expanded=False):
                    for match in group.get("matches", []):
                        st.markdown(f"**{match.get('citacao_curta', 'Precedente')}**")
                        st.caption(small_text(match.get("fundamento_curto", ""), 700))

        st.markdown("#### Exportar")
        revised = build_revised_text(st.session_state.last_text, analysis, mode="premium")
        marked = build_marked_text(st.session_state.last_text, analysis)
        rows = build_export_rows(analysis)
        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("Baixar DOCX revisado", data=build_docx_bytes(marked, analysis, title="DECIFRA - Documento revisado", marked=True), file_name="decifra_documento_revisado.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        with c2:
            st.download_button("Baixar PDF técnico", data=build_pdf_bytes(revised, analysis, title="DECIFRA - Relatório técnico"), file_name="decifra_relatorio_tecnico.pdf", mime="application/pdf", use_container_width=True)
        with c3:
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Baixar planilha CSV", data=csv_bytes, file_name="decifra_auditoria.csv", mime="text/csv", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_manual_search(db_paths, unlocked: bool):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="step">3 · Busca rápida por tese</span>', unsafe_allow_html=True)
    q = st.text_input("Digite uma tese, tema ou número de acórdão", placeholder="Ex.: diligência, inexequibilidade, falha sanável, Acórdão 1211/2021", label_visibility="collapsed")
    if st.button("Buscar precedentes", use_container_width=True):
        if not q.strip():
            st.warning("Digite uma tese ou referência.")
        else:
            data = cached_manual_search(db_paths, q.strip(), "acordao,sumula,jurisprudencia", 8 if unlocked else 2)
            matches = data.get("matches", [])
            if not matches:
                st.info("Nenhum resultado seguro encontrado na base local.")
            else:
                for match in matches:
                    st.markdown('<div class="result">', unsafe_allow_html=True)
                    st.markdown(f"**{match.get('citacao_curta', 'Resultado')}**")
                    st.caption(small_text(match.get("fundamento_curto", ""), 600))
                    st.markdown("</div>", unsafe_allow_html=True)
                if not unlocked:
                    st.caption("A busca gratuita mostra resultados limitados. Desbloqueie para ampliar a pesquisa.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_admin(cfg):
    with st.sidebar:
        st.markdown("### Operador")
        code = st.text_input("Código de liberação", value=st.session_state.get("unlock_code", ""))
        if code:
            st.session_state.unlock_code = code.strip().upper()
            if validate_unlock_code(st.session_state.unlock_code, cfg["unlock_secret"]):
                st.session_state.premium_unlocked = True
                st.success("Código validado.")

        if st.session_state.get("order_id"):
            st.caption("Pedido atual")
            st.code(st.session_state.order_id)
            st.caption("Código interno")
            st.code(make_unlock_code(st.session_state.order_id, cfg["unlock_secret"]))

        with st.expander("Configuração"):
            st.write("Use `.streamlit/secrets.toml` para preço, PIX, WhatsApp e Mercado Pago.")
            st.code("""DECIFRA_PRICE = "19,90"
DECIFRA_PIX_KEY = "sua-chave-pix"
DECIFRA_WHATSAPP = "5571999999999"
DECIFRA_UNLOCK_SECRET = "troque-por-uma-chave-grande"
DECIFRA_APP_URL = "https://seu-app.streamlit.app"
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
DECIFRA_NOTIFICATION_URL = """"", language="toml")


def check_payment_return(cfg):
    params = safe_query_params()
    payment_id = first_param(params, "payment_id", "collection_id")
    status_param = first_param(params, "status", "collection_status")
    if not payment_id:
        return

    st.session_state.payment_checked = True
    payment = get_mp_payment_status(cfg, payment_id)
    if payment.get("status") == "approved":
        st.session_state.premium_unlocked = True
        st.success("Pagamento aprovado. A análise completa foi liberada automaticamente.")
    elif payment.get("error"):
        if status_param == "approved":
            st.warning("O retorno indicou aprovação, mas a consulta automática não confirmou. Confira o Access Token ou libere manualmente.")
        else:
            st.warning(payment["error"])
    else:
        st.warning(f"Pagamento localizado com status: {payment.get('status', 'não aprovado')}.")


def main():
    cfg = get_config(st)
    render_css()
    check_payment_return(cfg)

    db_files = find_db_files(DB_DIR)
    db_paths = tuple(str(p) for p in db_files)
    summary = cached_summary(str(DB_DIR), db_signature(DB_DIR)) if db_files else {"total_files": 0, "total_size_mb": 0}

    render_hero(cfg)
    render_admin(cfg)

    st.markdown(f"""
<div class="card">
  <b>Base local:</b> {summary.get('total_files', 0)} arquivo(s) · {summary.get('total_size_mb', 0)} MB
  <span class="muted"> — validação executada sem expor a peça para serviços externos.</span>
</div>
""", unsafe_allow_html=True)

    render_upload_area(db_files, db_paths)

    unlocked = premium_active(st, cfg)
    analysis = st.session_state.get("analysis")
    if analysis:
        render_outputs(analysis, unlocked, cfg)

    render_manual_search(db_paths, unlocked)
    st.caption("DECIFRA é ferramenta de apoio técnico. A revisão final deve ser feita por profissional habilitado antes do protocolo.")


if __name__ == "__main__":
    main()
