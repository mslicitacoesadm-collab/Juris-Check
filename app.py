from __future__ import annotations

import hashlib
import html
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_references_with_context, parse_manual_query, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_marked_text, build_pdf_bytes, build_revised_text
from modules.license_manager import create_token, get_payment_url, log_event, stats as token_stats, validate_token
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import search_candidates, search_manual_precedents, validate_reference

st.set_page_config(page_title="JuriScan", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data" / "base"
LOGO_PATH = BASE_DIR / "assets" / "logo_ms.png"
MAX_UPLOAD_MB = int(os.getenv("JURISCAN_MAX_UPLOAD_MB", "20"))
ADMIN_PASSWORD = os.getenv("JURISCAN_ADMIN_PASSWORD", "")  # não deixe senha fixa no código; configure nos secrets/env.
PRICE_LABEL = "R$ 29,90"

for key, default in {
    "analysis": None,
    "last_file_name": "",
    "unlocked": False,
    "unlock_token": "",
    "admin_ok": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


@st.cache_data(show_spinner=False)
def cached_summary(path: str, signature: tuple):
    return summarize_bases(Path(path))


def _db_signature(base_dir: Path) -> tuple:
    return tuple((p.name, int(p.stat().st_mtime), p.stat().st_size) for p in find_db_files(base_dir))


@st.cache_data(show_spinner=False)
def cached_validate(db_paths: tuple[str, ...], citation: dict, top_k: int):
    return validate_reference([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_key: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(",")) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, kinds=kinds, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_manual_search(db_paths: tuple[str, ...], query_text: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(",")) if kinds_key else None
    return search_manual_precedents([Path(p) for p in db_paths], query_text, kinds=kinds, top_k=top_k)


def confidence_pct(item: dict) -> int:
    score = float(item.get("score_contexto") or 0.0)
    if item.get("status") == "valida_compatível":
        base = max(score, 0.56)
    elif item.get("status") == "valida_pouco_compativel":
        base = max(min(score, 0.75), 0.62)
    elif item.get("correcao_sugerida"):
        sug = item.get("correcao_sugerida") or {}
        base = max(float(sug.get("compat_score") or 0.0), 0.54)
    else:
        base = score
    return max(0, min(99, int(round(base * 100))))


def risk_label(results: list[dict]) -> tuple[str, str]:
    if not results:
        return "SEM CITAÇÕES", "Nenhuma referência explícita foi encontrada."
    problems = sum(1 for x in results if x.get("status") in {"divergente", "nao_localizada", "valida_pouco_compativel"})
    ratio = problems / max(len(results), 1)
    if ratio >= 0.45:
        return "ALTO", "Há volume relevante de citações não confirmadas, divergentes ou com aderência fraca."
    if ratio >= 0.20:
        return "MÉDIO", "Há pontos que devem ser conferidos antes do protocolo."
    return "BAIXO", "As citações encontradas tiveram boa aderência geral, mas ainda exigem revisão profissional."


def status_badge(item: dict) -> tuple[str, str, str]:
    stt = item.get("status")
    if stt == "valida_compatível":
        return "VALIDADA", "#0f5132", "#d1e7dd"
    if stt == "valida_pouco_compativel":
        return "REVISAR TESE", "#7a4d00", "#fff3cd"
    return "CORREÇÃO SUGERIDA", "#842029", "#f8d7da"


def safe(s: object) -> str:
    return html.escape(str(s or "—"))


def analysis_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()[:12]


def run_audit(piece_text: str, file_name: str, top_k: int, max_blocks: int) -> dict:
    refs = extract_references_with_context(piece_text)
    piece_type = classify_piece_type(piece_text)
    blocks = split_into_argument_blocks(piece_text, max_blocks=max_blocks)
    citation_results = [cached_validate(db_paths, ref, top_k) for ref in refs]
    thesis_results = []
    for block in blocks[:max_blocks]:
        suggestions = cached_search(db_paths, block["texto"], block["tese_chave"], "acordao,jurisprudencia,sumula", top_k)
        if suggestions:
            thesis_results.append({"tese": block["tese"], "preview": block["preview"], "fundamentos": block["fundamentos"], "sugestoes": suggestions[:3]})
    return {
        "brand": "JuriScan",
        "file_name": file_name,
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "piece_type": piece_type,
        "citation_results": citation_results,
        "thesis_results": thesis_results,
        "piece_text": piece_text,
        "rewrite_mode": "premium",
        "audit_id": analysis_hash(piece_text + file_name),
    }


def render_result_card(item: dict, idx: int, locked: bool = False):
    label, fg, bg = status_badge(item)
    suggestion = item.get("correcao_sugerida") or {}
    suggested_ref = item.get("substituicao_textual") or suggestion.get("citacao_curta") or "Sem substituição automática"
    fonte = (item.get("matched_record") or suggestion or {}).get("fonte_db") or (item.get("matched_record") or suggestion or {}).get("origem_tabela") or "Base local JuriScan"
    blur_class = " locked" if locked else ""
    st.markdown(
        f"""
        <div class="audit-card{blur_class}">
            <div class="audit-head">
                <div><span class="idx">#{idx}</span> <strong>{safe(item.get('raw'))}</strong></div>
                <span class="badge" style="background:{bg};color:{fg}">{label} · {confidence_pct(item)}%</span>
            </div>
            <div class="compare-grid">
                <div class="compare-box original">
                    <div class="box-title">Citação na peça enviada</div>
                    <div>{safe(item.get('contexto') or item.get('raw'))}</div>
                </div>
                <div class="compare-box suggested">
                    <div class="box-title">Leitura técnica / correção sugerida</div>
                    <div><strong>{safe(suggested_ref)}</strong></div>
                    <div class="muted-mini">{safe(item.get('motivo_match') or item.get('tipo_erro') or 'Conferência automática por referência e tese.')}</div>
                </div>
            </div>
            <div class="meta-line">Fonte: {safe(fonte)} · Colegiado/número/ano conforme base disponível · Alerta: revise antes de protocolar.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
<style>
:root{--bg:#f4f7fb;--ink:#111827;--muted:#667085;--line:#d8e0ee;--card:#fff;--blue:#0b3b66;--cyan:#12b6cb;--green:#14b87a;--danger:#d92d20;--gold:#d39b32}
.stApp{background:radial-gradient(circle at top left,#e9f6ff 0,#f6f8fc 34%,#f4f7fb 100%);color:var(--ink)}
#MainMenu, footer, header{visibility:hidden}.block-container{padding-top:1.2rem;max-width:1220px}
.hero{position:relative;overflow:hidden;border-radius:28px;padding:30px;border:1px solid rgba(255,255,255,.22);background:linear-gradient(135deg,#081f3a 0%,#0b3b66 48%,#0f7491 100%);box-shadow:0 22px 70px rgba(8,31,58,.22);color:#fff;margin-bottom:18px}.hero:after{content:"";position:absolute;width:420px;height:420px;border-radius:50%;right:-170px;top:-180px;background:rgba(18,182,203,.22);filter:blur(4px)}
.brand{display:flex;align-items:center;gap:14px}.brand-mark{width:48px;height:48px;border-radius:16px;background:linear-gradient(135deg,#16e0bd,#48a7ff);display:flex;align-items:center;justify-content:center;font-weight:900;color:#06213b;font-size:24px;box-shadow:0 14px 34px rgba(0,0,0,.18)}
.hero h1{font-size:2.3rem;margin:10px 0 7px;font-weight:850;letter-spacing:-.04em}.hero p{font-size:1.05rem;line-height:1.6;max-width:760px;margin:0;color:#e7f5ff}.hero-steps{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}.step{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.20);border-radius:999px;padding:8px 12px;font-weight:700;font-size:.86rem;color:#fff}
.panel{background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:24px;padding:20px;box-shadow:0 12px 36px rgba(16,24,40,.08);margin-bottom:16px}.mini-title{font-size:1.08rem;font-weight:850;margin-bottom:8px;color:#12233d}.muted{color:var(--muted);line-height:1.55}.muted-mini{color:var(--muted);font-size:.88rem;line-height:1.5;margin-top:6px}.cta-note{border-left:4px solid var(--cyan);padding:12px 14px;background:#eefbff;border-radius:14px;color:#124055;font-weight:650}.risk{border-radius:20px;padding:18px;background:linear-gradient(135deg,#fff,#f7fbff);border:1px solid var(--line)}.risk h2{margin:0;font-size:2rem}.badge{border-radius:999px;padding:7px 11px;font-weight:850;font-size:.78rem;white-space:nowrap}.idx{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:12px;background:#e8f3ff;color:#0b3b66;font-weight:900;margin-right:6px}
.audit-card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:22px;padding:17px;margin-bottom:14px;box-shadow:0 10px 28px rgba(16,24,40,.065)}.audit-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;flex-wrap:wrap}.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.compare-box{border:1px solid #dce4f0;border-radius:18px;padding:13px;min-height:118px;line-height:1.55}.original{background:#fff}.suggested{background:#f4fbff}.box-title{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900;color:#475467;margin-bottom:8px}.meta-line{margin-top:10px;font-size:.82rem;color:#667085;border-top:1px dashed #d7dfeb;padding-top:9px}.locked{filter:blur(5px);pointer-events:none;user-select:none}.paywall{margin-top:-8px;background:linear-gradient(135deg,#071d35,#0b3b66);border:1px solid rgba(255,255,255,.16);border-radius:24px;color:#fff;padding:22px;box-shadow:0 18px 55px rgba(8,31,58,.24)}.paywall h3{margin:0 0 6px;font-size:1.35rem}.paywall p{color:#d9edff;margin:0 0 12px}.price{font-size:2rem;font-weight:950;letter-spacing:-.04em}.legal{font-size:.82rem;color:#667085;line-height:1.55}.free-tag{display:inline-block;background:#ecfdf3;color:#027a48;border-radius:999px;padding:6px 10px;font-weight:900;font-size:.78rem}.warn-tag{display:inline-block;background:#fff3cd;color:#7a4d00;border-radius:999px;padding:6px 10px;font-weight:900;font-size:.78rem}.stButton>button{border-radius:16px!important;font-weight:850!important;min-height:48px}.stDownloadButton>button{border-radius:16px!important;font-weight:850!important;min-height:46px}
@media(max-width:760px){.hero{padding:22px}.hero h1{font-size:1.85rem}.compare-grid{grid-template-columns:1fr}.audit-head{align-items:flex-start}.panel{padding:16px}}
</style>
""",
    unsafe_allow_html=True,
)

db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown(
    """
<div class="hero">
  <div class="brand"><div class="brand-mark">JS</div><div><strong>JuriScan</strong><br><span style="color:#bcecff">Validador de citações e precedentes para peças jurídicas</span></div></div>
  <h1>Audite jurisprudência antes de protocolar.</h1>
  <p>Envie sua impugnação, recurso ou contrarrazão. O JuriScan identifica citações, confere número/ano/colegiado, mede aderência da tese e mostra correções lado a lado.</p>
  <div class="hero-steps"><div class="step">1. Enviar peça</div><div class="step">2. Auditar citações</div><div class="step">3. Ver 1 resultado grátis</div><div class="step">4. Liberar relatório completo</div></div>
</div>
""",
    unsafe_allow_html=True,
)

if not db_files:
    st.error("Nenhuma base `.db` foi encontrada em `data/base/`. Coloque as bases em `data/base/` para a auditoria funcionar.")

col_upload, col_info = st.columns([1.25, .75])
with col_upload:
    st.markdown('<div class="panel"><div class="mini-title">Enviar peça jurídica</div><div class="muted">Upload em PDF, DOCX ou TXT. Limite configurado: {} MB. O texto é processado apenas para gerar a auditoria desta sessão.</div>'.format(MAX_UPLOAD_MB), unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Arquivo da peça", type=["pdf", "docx", "txt"], label_visibility="collapsed")
    manual_text = st.text_area("Ou cole o texto completo da peça", height=170, placeholder="Cole aqui a peça jurídica para auditoria...")
    top_k = st.slider("Profundidade da busca por citação", 2, 6, 4)
    max_blocks = st.slider("Blocos argumentativos para reforço por tese", 3, 12, 6)
    analyze = st.button("🔎 AUDITAR CITAÇÕES", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
with col_info:
    st.markdown(
        f"""
        <div class="panel">
          <div class="mini-title">Modelo comercial inicial</div>
          <div class="free-tag">1 correção grátis</div>
          <p class="muted" style="margin-top:10px">A peça completa e o resumo aparecem, mas as demais inconsistências ficam bloqueadas até a liberação.</p>
          <div class="cta-note"><strong>Relatório completo:</strong><br><span class="price">{PRICE_LABEL}</span><br>sem login e sem cadastro.</div>
        </div>
        <div class="panel">
          <div class="mini-title">Segurança mínima</div>
          <div class="legal">LGPD: não envie dados sensíveis desnecessários. Use HTTPS no deploy. Configure senha/admin e link de pagamento em secrets. A base não é exposta ao usuário final.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if analyze:
    if uploaded_file is None and not manual_text.strip():
        st.error("Envie um arquivo ou cole o texto da peça.")
        st.stop()
    if uploaded_file is not None:
        size_mb = uploaded_file.size / (1024 * 1024)
        if size_mb > MAX_UPLOAD_MB:
            st.error(f"Arquivo acima do limite permitido de {MAX_UPLOAD_MB} MB.")
            st.stop()
        piece_text = read_uploaded_file(uploaded_file)
        file_name = uploaded_file.name
    else:
        piece_text = manual_text
        file_name = "texto_colado.txt"
    if len(piece_text or "") < 30:
        st.error("Não foi possível extrair texto suficiente da peça.")
        st.stop()
    with st.spinner("JuriScan está analisando precedentes, citações e aderência jurídica..."):
        st.session_state.analysis = run_audit(piece_text, file_name, top_k=top_k, max_blocks=max_blocks)
        st.session_state.last_file_name = file_name
        st.session_state.unlocked = False
        st.session_state.unlock_token = ""
        log_event("audit_created", f"{file_name} | {len(piece_text)} chars")

analysis = st.session_state.analysis
if analysis:
    results = analysis.get("citation_results", [])
    validas = sum(1 for x in results if x.get("status") == "valida_compatível")
    revisar = sum(1 for x in results if x.get("status") == "valida_pouco_compativel")
    corrigir = sum(1 for x in results if x.get("status") in {"divergente", "nao_localizada"})
    risco, risco_desc = risk_label(results)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Auditoria concluída")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Peça", analysis.get("piece_type", {}).get("tipo", "Peça jurídica"))
    m2.metric("Citações", len(results))
    m3.metric("Validadas", validas)
    m4.metric("Revisar", revisar)
    m5.metric("Corrigir", corrigir)
    st.markdown(f'<div class="risk"><h2>Risco {risco}</h2><div class="muted">{safe(risco_desc)}</div><div class="legal">ID da auditoria: {safe(analysis.get("audit_id"))} · Gerado em {safe(analysis.get("created_at"))}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    free_limit = 1
    unlocked = bool(st.session_state.unlocked)
    st.markdown("### Comparação lado a lado")
    if not results:
        st.info("Nenhuma citação explícita foi identificada. Use a busca manual abaixo para pesquisar teses e precedentes por assunto.")
    for idx, item in enumerate(results, start=1):
        render_result_card(item, idx, locked=(not unlocked and idx > free_limit))
        if idx == free_limit and not unlocked and len(results) > free_limit:
            payment_url = get_payment_url()
            st.markdown(
                f"""
                <div class="paywall">
                  <h3>Relatório completo bloqueado</h3>
                  <p>Você visualizou 1 resultado grátis. Existem mais {len(results)-free_limit} apontamentos para liberar, com correções, fontes e exportação em DOCX/PDF/CSV.</p>
                  <div class="price">{PRICE_LABEL}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if payment_url:
                st.link_button("💳 Pagar e liberar relatório", payment_url, use_container_width=True)
            else:
                st.warning("Configure `JURISCAN_PAYMENT_URL` nos secrets para ativar o botão de pagamento real do Mercado Pago.")
            with st.expander("Já paguei / tenho código de liberação"):
                token_input = st.text_input("Código de liberação", placeholder="JS-XXXX-XXXX-XXXX")
                if st.button("Liberar relatório", use_container_width=True):
                    check = validate_token(token_input, mark_used=True)
                    if check.get("ok"):
                        st.session_state.unlocked = True
                        st.session_state.unlock_token = check.get("token", "")
                        st.rerun()
                    else:
                        st.error(check.get("reason", "Código inválido."))

    if unlocked or len(results) <= free_limit:
        st.success("Relatório completo liberado nesta sessão.")
        revised_text = build_revised_text(analysis.get("piece_text", ""), analysis, mode="premium")
        marked_text = build_marked_text(analysis.get("piece_text", ""), analysis)
        export_rows = build_export_rows(analysis)
        docx_clean = build_docx_bytes(revised_text, analysis, f"JuriScan - Peça revisada - {analysis.get('file_name','peca')}")
        docx_marked = build_docx_bytes(marked_text, analysis, f"JuriScan - Correções marcadas - {analysis.get('file_name','peca')}", marked=True)
        pdf_clean = build_pdf_bytes(revised_text, analysis, f"Relatório JuriScan - {analysis.get('file_name','peca')}")
        csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig")
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button("DOCX revisado", docx_clean, file_name="juriscan_peca_revisada.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        d2.download_button("DOCX marcado", docx_marked, file_name="juriscan_correcoes_marcadas.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        d3.download_button("PDF relatório", pdf_clean, file_name="juriscan_relatorio.pdf", mime="application/pdf", use_container_width=True)
        d4.download_button("CSV auditoria", csv_bytes, file_name="juriscan_auditoria.csv", mime="text/csv", use_container_width=True)

    with st.expander("Reforços por tese jurídica"):
        if not analysis.get("thesis_results"):
            st.info("Não foram identificados blocos suficientes para reforço por tese.")
        for bloco in analysis.get("thesis_results", []):
            st.markdown(f"**{safe(bloco.get('tese'))}**")
            st.caption(bloco.get("preview") or "")
            for sug in bloco.get("sugestoes", [])[:3]:
                st.write(f"• {sug.get('citacao_curta','Precedente')} — aderência {int(float(sug.get('compat_score') or 0)*100)}%")
                st.caption(sug.get("fundamento_curto") or sug.get("motivo_match") or "")

st.markdown("---")
with st.expander("Busca manual de precedentes"):
    manual_query = st.text_input("Pesquise por número ou tese", placeholder="Ex.: TCU Acórdão 2622/2013 ou falha sanável sem diligência")
    manual_types = st.multiselect("Tipos", ["acordao", "jurisprudencia", "sumula"], default=["acordao", "jurisprudencia", "sumula"])
    if st.button("Pesquisar na base", use_container_width=True):
        if not manual_query.strip():
            st.warning("Digite uma tese ou referência.")
        else:
            parsed = parse_manual_query(manual_query)
            result = cached_manual_search(db_paths, manual_query, ",".join(manual_types), 8)
            st.info(f"Modo: {'referência específica' if result['search_mode']=='referencia_especifica' else 'busca por tese'} · Número={parsed.get('numero') or '—'} · Ano={parsed.get('ano') or '—'}")
            for rec in result.get("matches", []):
                st.markdown(f"**{rec.get('citacao_curta','Precedente')}** · aderência {int(float(rec.get('compat_score') or 0)*100)}%")
                st.caption(rec.get("motivo_match") or rec.get("fundamento_curto") or "")

with st.expander("Administração JuriScan"):
    st.caption("Configure `JURISCAN_ADMIN_PASSWORD` nos secrets/env. Sem isso, o painel permanece protegido por ausência de senha operacional.")
    pwd = st.text_input("Senha administrativa", type="password")
    if st.button("Entrar no admin"):
        if ADMIN_PASSWORD and pwd == ADMIN_PASSWORD:
            st.session_state.admin_ok = True
        else:
            st.error("Senha inválida ou variável `JURISCAN_ADMIN_PASSWORD` não configurada.")
    if st.session_state.admin_ok:
        st.success("Admin liberado.")
        s = token_stats()
        a1, a2, a3 = st.columns(3)
        a1.metric("Tokens gerados", s["total_tokens"])
        a2.metric("Tokens usados", s["used_tokens"])
        a3.metric("Receita estimada", f"R$ {float(s['revenue']):,.2f}".replace(',', 'X').replace('.', ',').replace('X','.'))
        h = st.number_input("Validade do código em horas", 1, 168, 24)
        if st.button("Gerar código de liberação", use_container_width=True):
            token = create_token(hours_valid=int(h), source="admin", amount=29.90, notes="gerado pelo painel")
            st.code(token)
        st.dataframe(pd.DataFrame(s["last_tokens"]), use_container_width=True)

st.markdown(
    """
<div class="legal">
<strong>Aviso jurídico:</strong> O JuriScan é uma ferramenta auxiliar de auditoria. O relatório não substitui a revisão de advogado, consultor ou profissional responsável. Antes de protocolar qualquer peça, confira a fonte oficial, a aderência da tese e a atualização do precedente.
</div>
""",
    unsafe_allow_html=True,
)
