from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, detect_thesis, extract_references_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_marked_text, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import search_candidates, validate_reference

st.set_page_config(page_title="Atlas dos Acórdãos V16", page_icon="⚖️", layout="wide")

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data" / "base"
LOGO_PATH = BASE_DIR / "assets" / "logo_ms.png"

DEFAULT_EMPTY_ANALYSIS = {
    "piece_type": {"tipo": "Não identificado", "chave": "peca", "confianca": "baixa", "score": 0},
    "citation_results": [],
    "thesis_results": [],
    "piece_text": "",
    "rewrite_mode": "Reescrita premium",
    "summary": {},
}

for key, value in {
    "analysis": None,
    "last_file_name": "",
    "manual_results": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


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


def status_tone(status: str) -> tuple[str, str]:
    if status == "valida_compatível":
        return "#0F5132", "#D1E7DD"
    if status == "valida_pouco_compativel":
        return "#664D03", "#FFF3CD"
    return "#842029", "#F8D7DA"


def confidence_badge(label: str) -> tuple[str, str]:
    if label.startswith("Alta"):
        return "#0F5132", "#D1E7DD"
    if label.startswith("Média"):
        return "#664D03", "#FFF3CD"
    return "#842029", "#F8D7DA"


def build_summary(analysis: dict) -> dict:
    citation_results = analysis.get("citation_results", [])
    total = len(citation_results)
    validas = sum(1 for x in citation_results if x.get("status") == "valida_compatível")
    ajustes = sum(1 for x in citation_results if x.get("status") == "valida_pouco_compativel")
    erros = sum(1 for x in citation_results if x.get("status") == "divergente")
    nao_mapeadas = sum(1 for x in citation_results if x.get("status") == "nao_localizada")
    blocos = len(analysis.get("thesis_results", []))
    confiabilidade = round((validas + ajustes * 0.5) / total * 100) if total else 100
    risco = "baixo" if erros == 0 and ajustes <= 1 else "médio" if erros <= 2 else "alto"
    recomendacao = {
        "baixo": "Peça com boa base de precedentes. Recomenda-se apenas revisão final de estilo e protocolo.",
        "médio": "Peça utilizável, mas com pontos de citação e aderência que merecem revisão antes do protocolo.",
        "alto": "Peça com risco relevante de fragilidade argumentativa. Recomenda-se revisar as citações e reestruturar os trechos críticos.",
    }[risco]
    return {
        "total_citacoes": total,
        "validas": validas,
        "ajustes": ajustes,
        "erros": erros,
        "nao_mapeadas": nao_mapeadas,
        "blocos": blocos,
        "confiabilidade": confiabilidade,
        "risco": risco,
        "recomendacao": recomendacao,
    }


def render_card_html(title: str, body: str, tone: str = "default"):
    tone_map = {
        "default": ("#ffffff", "#d7dfeb", "#132238"),
        "success": ("#eef9f1", "#b7dfbf", "#0f5132"),
        "warning": ("#fff8e6", "#f0d482", "#664d03"),
        "danger": ("#fff2f1", "#efb8b3", "#842029"),
        "info": ("#eff5ff", "#bfd2ec", "#123b67"),
    }
    bg, border, ink = tone_map[tone]
    st.markdown(
        f"<div style='background:{bg};border:1px solid {border};padding:1rem 1.1rem;border-radius:18px;margin-bottom:.85rem'><div style='font-weight:700;color:{ink};margin-bottom:.35rem'>{title}</div><div style='color:#334155;line-height:1.58'>{body}</div></div>",
        unsafe_allow_html=True,
    )


css = """
<style>
:root{--bg:#f5f7fb;--card:#ffffff;--line:#d7dfeb;--ink:#132238;--muted:#4e5d72;--primary:#123b67;--primary2:#194f84;}
.stApp{background:var(--bg);}
.hero{padding:1.4rem 1.5rem;border-radius:24px;background:linear-gradient(135deg,#0f2744 0%,#163b62 55%,#245d8f 100%);color:#fff;border:1px solid rgba(255,255,255,.12)}
.hero h1{margin:0 0 .4rem 0;font-size:1.95rem}
.hero p{margin:.2rem 0;line-height:1.55}
.card{padding:1rem 1rem;border:1px solid var(--line);border-radius:20px;background:var(--card);margin-bottom:.85rem;box-shadow:0 6px 18px rgba(16,24,40,.04)}
.block{padding:1rem 1.1rem;border:1px solid var(--line);border-radius:20px;background:var(--card)}
.legend{display:inline-block;padding:.24rem .7rem;border-radius:999px;font-size:.82rem;font-weight:700}
.small{font-size:.93rem;color:var(--muted);line-height:1.58}
.section-title{font-size:1.08rem;font-weight:700;color:var(--ink);margin:.2rem 0 .8rem 0}
.audit-line{padding:.7rem .85rem;border-left:4px solid #123b67;background:#f8fbff;border-radius:10px;margin:.35rem 0}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

c_logo, c_hero = st.columns([1, 5])
with c_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with c_hero:
    st.markdown(
        """
        <div class="hero">
          <h1>Atlas dos Acórdãos · V16 Profissional</h1>
          <p><strong>Auditoria de citações jurídicas geradas por IA</strong>, com validação em base própria, busca por número ou tese, classificação de risco da peça e exportação marcada com lógica de revisão técnica.</p>
          <p>O foco continua sendo o que mais importa ao usuário: localizar precedentes reais, apontar números errados, sugerir substituições mais aderentes e entregar um arquivo revisado com marcação útil para trabalho profissional.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.subheader("Ajustes da análise")
    top_k = st.slider("Sugestões por referência", 1, 6, 3)
    max_blocks = st.slider("Blocos de tese para varredura", 3, 12, 6)
    rewrite_mode = st.radio("Nível de intervenção", ["Correção simples", "Correção contextual", "Reescrita premium"], index=2)
    st.markdown("**Legenda**")
    st.markdown('<span class="legend" style="background:#D1E7DD;color:#0F5132">Validada</span> <span class="legend" style="background:#FFF3CD;color:#664D03">Ajuste recomendado</span> <span class="legend" style="background:#F8D7DA;color:#842029">Erro relevante</span>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
if summary.get("base_inteligente_detectada"):
    k1.metric("Precedentes inteligentes", f"{summary['inteligente']:,}".replace(",", "."))
    k2.metric("Base inteligente", "Ativa")
    k3.metric("Arquivo mestre", summary.get("arquivo_base_inteligente") or "-")
    k4.metric("Bases detectadas", summary["total_bases"])
else:
    k1.metric("Acórdãos", f"{summary['acordao']:,}".replace(",", "."))
    k2.metric("Jurisprudências", f"{summary['jurisprudencia']:,}".replace(",", "."))
    k3.metric("Súmulas", f"{summary['sumula']:,}".replace(",", "."))
    k4.metric("Bases detectadas", summary["total_bases"])

if summary.get("base_inteligente_detectada"):
    st.success(f"Base inteligente ativa: {summary.get('arquivo_base_inteligente')} — o motor prioriza tese central, utilidade prática e contexto licitatório.")
else:
    st.info("Base inteligente ainda não instalada. O app segue operando com as bases brutas atuais.")

main_tab, manual_tab = st.tabs(["Upload e auditoria", "Busca manual de precedentes"])

with main_tab:
    st.markdown('<div class="section-title">1. Envie a peça ou cole o texto</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Arquivo da peça", type=["pdf", "docx", "txt"], key="upload_principal")
    manual_text = st.text_area("Ou cole o texto da peça", height=180, key="manual_text_main")
    analyze = st.button("Auditar peça", type="primary", use_container_width=True)

    if analyze:
        if not db_files:
            st.error("Nenhuma base `.db` foi encontrada em `data/base/`.")
            st.stop()
        if uploaded_file is None and not manual_text.strip():
            st.error("Envie um arquivo ou cole o texto da peça.")
            st.stop()

        if uploaded_file is not None:
            piece_text = read_uploaded_file(uploaded_file)
            file_name = uploaded_file.name
        else:
            piece_text = manual_text
            file_name = "texto_colado.txt"

        st.session_state.last_file_name = file_name
        refs = extract_references_with_context(piece_text)
        piece_type = classify_piece_type(piece_text)
        blocks = split_into_argument_blocks(piece_text, max_blocks=max_blocks)

        with st.spinner("Auditando a peça..."):
            citation_results = [cached_validate(db_paths, ref, top_k) for ref in refs]
            thesis_results = []
            for block in blocks[:max_blocks]:
                suggestions = cached_search(db_paths, block["texto"], block["tese_chave"], "acordao,jurisprudencia,sumula", top_k)
                if suggestions:
                    thesis_results.append({
                        "tese": block["tese"],
                        "tese_secundaria": block.get("tese_secundaria", ""),
                        "preview": block["preview"],
                        "fundamentos": block["fundamentos"],
                        "score_tese": block.get("score_tese", 0),
                        "sugestoes": suggestions[:4],
                    })

        analysis = {
            "piece_type": piece_type,
            "citation_results": citation_results,
            "thesis_results": thesis_results,
            "piece_text": piece_text,
            "rewrite_mode": rewrite_mode,
        }
        analysis["summary"] = build_summary(analysis)
        st.session_state.analysis = analysis

    analysis = st.session_state.analysis or DEFAULT_EMPTY_ANALYSIS
    if analysis and (analysis.get("piece_text") or analysis.get("citation_results") or analysis.get("thesis_results")):
        piece_text = analysis.get("piece_text", "")
        mode_map = {"Correção simples": "simple", "Correção contextual": "contextual", "Reescrita premium": "premium"}
        active_mode = analysis.get("rewrite_mode") or rewrite_mode
        revised_text = build_revised_text(piece_text, analysis, mode=mode_map.get(active_mode, "premium"))
        marked_text = build_marked_text(piece_text, analysis)
        export_rows = build_export_rows(analysis)
        summary_box = analysis.get("summary") or build_summary(analysis)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Tipo da peça", analysis["piece_type"].get("tipo", "Não identificado"))
        c2.metric("Confiabilidade", f"{summary_box['confiabilidade']}%")
        c3.metric("Cit. validadas", summary_box["validas"])
        c4.metric("Ajustes", summary_box["ajustes"])
        c5.metric("Risco da peça", summary_box["risco"].capitalize())

        t1, t2, t3, t4 = st.tabs(["Diagnóstico executivo", "Citações auditadas", "Teses e reforços", "Exportação"])
        with t1:
            render_card_html(
                "Resumo executivo",
                f"A peça foi identificada como <strong>{analysis['piece_type'].get('tipo','Não identificado')}</strong> com confiança <strong>{analysis['piece_type'].get('confianca','baixa')}</strong>. Foram localizadas <strong>{summary_box['total_citacoes']}</strong> referências explícitas, sendo <strong>{summary_box['validas']}</strong> validadas, <strong>{summary_box['ajustes']}</strong> com aderência fraca e <strong>{summary_box['erros']}</strong> com divergência relevante. O sistema encontrou <strong>{summary_box['blocos']}</strong> blocos com potencial de reforço por tese.",
                "info",
            )
            render_card_html("Recomendação final", summary_box["recomendacao"], {"baixo": "success", "médio": "warning", "alto": "danger"}[summary_box["risco"]])
            if analysis.get("citation_results"):
                st.markdown("**Mapa rápido das ocorrências**")
                for item in analysis["citation_results"]:
                    tone = "success" if item.get("status") == "valida_compatível" else "warning" if item.get("status") == "valida_pouco_compativel" else "danger"
                    explanation = item.get("problema_classificado") or item.get("status_label")
                    st.markdown(f"<div class='audit-line'><strong>Linha {item.get('linha','-')}</strong> · {item.get('raw','')}<br><span class='small'>{explanation}</span></div>", unsafe_allow_html=True)
            st.text_area("Prévia da peça revisada", revised_text[:15000], height=320)

        with t2:
            if not analysis["citation_results"]:
                st.info("Nenhuma citação explícita de acórdão, súmula ou jurisprudência foi identificada na peça.")
            for item in analysis["citation_results"]:
                fg, bg = status_tone(item["status"])
                cfg, cbg = confidence_badge(item["grau_confianca"])
                st.markdown(
                    f"<div class='card'><div style='display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.55rem'><span class='legend' style='background:{bg};color:{fg}'>{item['status_label']}</span><span class='legend' style='background:{cbg};color:{cfg}'>{item['grau_confianca']}</span></div><div class='small'><strong>Referência encontrada:</strong> {item['raw']}<br><strong>Linha:</strong> {item.get('linha','-')}<br><strong>Tese do contexto:</strong> {item.get('tese','Tese geral')}<br><strong>Classificação técnica:</strong> {item.get('problema_classificado','Sem classificação adicional')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption("Contexto lido pelo motor")
                st.write(item.get("contexto") or "—")
                if item.get("matched_record"):
                    rec = item["matched_record"]
                    st.markdown("**Precedente localizado na base**")
                    st.write(f"{rec['tipo']} nº {rec['numero']}/{rec['ano']} - {rec['colegiado']}")
                if item.get("motivo_match"):
                    st.markdown("**Motivo técnico do enquadramento**")
                    st.write(item["motivo_match"])
                if item.get("correcao_sugerida"):
                    sug = item["correcao_sugerida"]
                    st.markdown("**Correção principal sugerida**")
                    st.write(f"{sug['citacao_curta']} · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get("fundamento_curto") or "")
                if item.get("nota_auditoria"):
                    st.markdown("**Nota de auditoria**")
                    st.write(item["nota_auditoria"])
                if item.get("paragrafo_reescrito"):
                    st.markdown("**Redação sugerida para o parágrafo**")
                    st.write(item.get("paragrafo_reescrito") or "")

        with t3:
            if not analysis["thesis_results"]:
                st.info("Não foram identificados blocos suficientes para reforço por tese.")
            for bloco in analysis["thesis_results"]:
                secondary = f" · tese secundária: {bloco['tese_secundaria']}" if bloco.get("tese_secundaria") else ""
                st.markdown(
                    f"<div class='card'><div class='section-title'>{bloco['tese']}{secondary}</div><div class='small'><strong>Fundamentos detectados:</strong> {bloco['fundamentos'] or 'sem indicadores claros'}<br><strong>Força do bloco:</strong> {bloco.get('score_tese',0)}</div><div class='small' style='margin-top:.5rem'><strong>Trecho lido:</strong> {bloco['preview']}</div></div>",
                    unsafe_allow_html=True,
                )
                for sug in bloco["sugestoes"]:
                    st.markdown(f"**{sug['citacao_curta']}** · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get("motivo_match") or "")
                    st.write(sug.get("fundamento_curto") or "")

        with t4:
            docx_clean = build_docx_bytes(revised_text, analysis, st.session_state.last_file_name or "peca_revisada")
            docx_marked = build_docx_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}", marked=True)
            pdf_clean = build_pdf_bytes(revised_text, analysis, st.session_state.last_file_name or "peca_revisada")
            pdf_marked = build_pdf_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}")
            csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.download_button("DOCX limpo", docx_clean, file_name="atlas_v16_revisado_limpo.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            d2.download_button("DOCX marcado", docx_marked, file_name="atlas_v16_revisado_marcado.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            d3.download_button("PDF limpo", pdf_clean, file_name="atlas_v16_revisado_limpo.pdf", mime="application/pdf", use_container_width=True)
            d4.download_button("PDF marcado", pdf_marked, file_name="atlas_v16_revisado_marcado.pdf", mime="application/pdf", use_container_width=True)
            d5.download_button("CSV da auditoria", csv_bytes, file_name="atlas_v16_auditoria.csv", mime="text/csv", use_container_width=True)
            st.caption("O DOCX/PDF marcado agora sai com bloco de auditoria, indicação do problema, correção aplicada, nível de confiança e referência sugerida.")

with manual_tab:
    st.markdown('<div class="section-title">Busca manual por número, tese ou fundamento</div>', unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns([2, 1, 1])
    with mc1:
        manual_query = st.text_input("Ex.: Acórdão 2622/2013 | Súmula 222 | formalismo moderado sem diligência")
    with mc2:
        search_mode = st.selectbox("Modo", ["Automático", "Número", "Tese"])
    with mc3:
        limit = st.selectbox("Resultados", [5, 8, 10, 12], index=1)
    manual_types = st.multiselect("Tipos a pesquisar", ["acordao", "jurisprudencia", "sumula"], default=["acordao", "jurisprudencia", "sumula"])
    if st.button("Pesquisar precedentes", use_container_width=True):
        if not db_files:
            st.error("Nenhuma base `.db` foi encontrada em `data/base/`.")
        elif not manual_query.strip():
            st.warning("Digite uma tese ou uma referência direta.")
        else:
            query_for_search = manual_query
            thesis = detect_thesis(manual_query)
            thesis_key = thesis["chave"]
            if search_mode == "Número":
                thesis_key = None
            elif search_mode == "Tese" and thesis_key == "geral":
                thesis_key = None
            st.session_state.manual_results = cached_search(db_paths, query_for_search, thesis_key or "", ",".join(manual_types), limit)

    if st.session_state.manual_results:
        for rec in st.session_state.manual_results:
            st.markdown(
                f"<div class='card'><div style='display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap'><div><strong>{rec['citacao_curta']}</strong></div><div><span class='legend' style='background:#e8eef8;color:#123b67'>Aderência {int(rec['compat_score']*100)}%</span></div></div><div class='small' style='margin-top:.55rem'><strong>Tema:</strong> {rec.get('tema') or rec.get('tese_central') or 'Não informado'}<br><strong>Motivo do match:</strong> {rec.get('motivo_match') or 'Sem explicação adicional.'}</div></div>",
                unsafe_allow_html=True,
            )
            st.write(rec.get("fundamento_curto") or "")
            st.code(rec.get("citacao_curta") or "", language="text")
