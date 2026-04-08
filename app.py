from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, detect_thesis, extract_references_with_context, split_into_argument_blocks
from modules.document_builder import (
    build_client_report_text,
    build_docx_bytes,
    build_marked_text,
    build_pdf_bytes,
    build_reinforced_text,
    build_revised_text,
)
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import build_argument_snippet, compatibility_label, search_candidates, validate_reference

st.set_page_config(page_title="Atlas dos Acórdãos V18", page_icon="⚖️", layout="wide")

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data" / "base"
LOGO_PATH = BASE_DIR / "assets" / "logo_ms.png"

for key, value in {
    "analysis": None,
    "last_file_name": "",
    "manual_results": [],
    "original_text": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


@st.cache_data(show_spinner=False)
def cached_summary(path: str, signature: tuple):
    return summarize_bases(Path(path))


@st.cache_data(show_spinner=False)
def cached_validate(db_paths: tuple[str, ...], citation: dict, top_k: int):
    return validate_reference([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_key: str, kinds_key: str, top_k: int):
    kinds = set(kinds_key.split(",")) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key or None, kinds=kinds, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_client_report(analysis: dict, file_name: str):
    return build_client_report_text(analysis, file_name)


def _db_signature(base_dir: Path) -> tuple:
    return tuple((p.name, int(p.stat().st_mtime), p.stat().st_size) for p in find_db_files(base_dir))


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
    reforcos = sum(1 for x in analysis.get("thesis_results", []) if x.get("sugestoes"))
    confiabilidade = round((validas + ajustes * 0.5) / total * 100) if total else 100

    if erros == 0 and ajustes <= 1:
        risco = "baixo"
    elif erros <= 2 and (erros + ajustes) <= 4:
        risco = "médio"
    else:
        risco = "alto"

    pronto_protocolo = "sim" if risco == "baixo" and confiabilidade >= 75 else "não"
    recomendacao = {
        "baixo": "Peça com boa base de precedentes. Recomenda-se revisão final de estilo e protocolo.",
        "médio": "Peça utilizável, mas com pontos de citação e aderência que merecem revisão antes do protocolo.",
        "alto": "Peça com risco relevante de fragilidade argumentativa. Recomenda-se revisar as citações, reforçar as teses e consolidar os trechos críticos antes do protocolo.",
    }[risco]
    orientacao_cliente = {
        "baixo": "A peça tende a suportar protocolo após leitura final humana e conferência estratégica do pedido.",
        "médio": "O ideal é ajustar os pontos marcados e utilizar ao menos um reforço automático por tese antes do protocolo.",
        "alto": "Não é prudente protocolar a peça sem revisão técnica mais profunda, substituição de precedentes e reforço argumentativo imediato.",
    }[risco]
    return {
        "total_citacoes": total,
        "validas": validas,
        "ajustes": ajustes,
        "erros": erros,
        "nao_mapeadas": nao_mapeadas,
        "blocos": blocos,
        "blocos_reforcados": reforcos,
        "confiabilidade": confiabilidade,
        "risco": risco,
        "pronto_protocolo": pronto_protocolo,
        "recomendacao": recomendacao,
        "orientacao_cliente": orientacao_cliente,
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
.hero{padding:1.45rem 1.5rem;border-radius:24px;background:linear-gradient(135deg,#0f2744 0%,#163b62 55%,#245d8f 100%);color:#fff;border:1px solid rgba(255,255,255,.12)}
.hero h1{margin:0 0 .4rem 0;font-size:1.95rem}
.hero p{margin:.2rem 0;line-height:1.55}
.card{padding:1rem 1rem;border:1px solid var(--line);border-radius:20px;background:var(--card);margin-bottom:.85rem;box-shadow:0 6px 18px rgba(16,24,40,.04)}
.legend{display:inline-block;padding:.24rem .7rem;border-radius:999px;font-size:.82rem;font-weight:700}
.small{font-size:.93rem;color:var(--muted);line-height:1.58}
.section-title{font-size:1.08rem;font-weight:700;color:var(--ink);margin:.2rem 0 .8rem 0}
.audit-line{padding:.7rem .85rem;border-left:4px solid #123b67;background:#f8fbff;border-radius:10px;margin:.35rem 0}
</style>
"""
st.markdown(css, unsafe_allow_html=True)


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary_bases = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

c_logo, c_hero = st.columns([1, 5])
with c_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with c_hero:
    st.markdown(
        """
        <div class="hero">
          <h1>Atlas dos Acórdãos · V18 Produto Real</h1>
          <p><strong>Auditoria jurídica com foco em correção de acórdãos genéricos, números errados, busca técnica por tese e texto reforçado pronto para implantação.</strong></p>
          <p>Esta versão sobe o nível comercial e técnico: relatório premium para cliente, indicador de protocolo, reforço automático por tese, exportações mais úteis e busca manual mais orientada à aplicação prática.</p>
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

mk1, mk2, mk3, mk4 = st.columns(4)
if summary_bases.get("base_inteligente_detectada"):
    mk1.metric("Precedentes inteligentes", f"{summary_bases['inteligente']:,}".replace(",", "."))
    mk2.metric("Base inteligente", "Ativa")
    mk3.metric("Arquivo mestre", summary_bases.get("arquivo_base_inteligente") or "-")
    mk4.metric("Bases detectadas", summary_bases["total_bases"])
else:
    mk1.metric("Acórdãos", f"{summary_bases['acordao']:,}".replace(",", "."))
    mk2.metric("Jurisprudências", f"{summary_bases['jurisprudencia']:,}".replace(",", "."))
    mk3.metric("Súmulas", f"{summary_bases['sumula']:,}".replace(",", "."))
    mk4.metric("Bases detectadas", summary_bases["total_bases"])

if summary_bases.get("base_inteligente_detectada"):
    st.success(f"Base inteligente ativa: {summary_bases.get('arquivo_base_inteligente')} — o motor prioriza tese central, contexto e utilidade prática.")
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
        st.session_state.original_text = piece_text
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
                        "texto": block["texto"],
                        "tese_secundaria": block.get("tese_secundaria", ""),
                        "score_tese": block.get("score_tese", 0),
                        "fundamentos": block.get("fundamentos", ""),
                        "preview": block["preview"],
                        "sugestoes": suggestions,
                    })
            analysis = {
                "piece_type": piece_type,
                "citation_results": citation_results,
                "thesis_results": thesis_results,
            }
            analysis["summary"] = build_summary(analysis)
            st.session_state.analysis = analysis

    analysis = st.session_state.analysis
    if analysis:
        summary = analysis["summary"]
        critical = [x for x in analysis["citation_results"] if x.get("status") in {"divergente", "valida_pouco_compativel"}]
        mode_key = {"Correção simples": "simple", "Correção contextual": "contextual", "Reescrita premium": "premium"}[rewrite_mode]
        original_text = st.session_state.original_text or manual_text or ""
        revised_text = build_revised_text(original_text, analysis, mode=mode_key)
        marked_text = build_marked_text(revised_text, analysis)
        reinforced_text = build_reinforced_text(revised_text, analysis)
        best_supports = []
        for bloco in analysis.get("thesis_results", []):
            if bloco.get("sugestoes"):
                best_supports.append(bloco["sugestoes"][0])
        export_rows = build_export_rows(analysis)
        report_text = cached_client_report(analysis, st.session_state.last_file_name or "peça")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Citações auditadas", summary["total_citacoes"])
        k2.metric("Confiabilidade", f"{summary['confiabilidade']}%")
        k3.metric("Risco da peça", summary["risco"].upper())
        k4.metric("Blocos reforçados", summary["blocos_reforcados"])
        k5.metric("Pode protocolar", summary["pronto_protocolo"].upper())

        t1, t2, t3, t4, t5, t6 = st.tabs([
            "Visão executiva",
            "Mapa de citações",
            "Reforço por tese",
            "Texto reforçado V18",
            "Relatório premium",
            "Exportações",
        ])

        with t1:
            tone = "success" if summary["risco"] == "baixo" else "warning" if summary["risco"] == "médio" else "danger"
            render_card_html(
                "Diagnóstico da peça",
                f"Tipo identificado: <strong>{analysis['piece_type'].get('tipo','Não identificado')}</strong> | Confiança da classificação: <strong>{analysis['piece_type'].get('confianca','baixa')}</strong> | Pode protocolar agora: <strong>{summary['pronto_protocolo'].upper()}</strong> | Recomendação: {summary['recomendacao']}",
                tone=tone,
            )
            render_card_html("Orientação final ao usuário", summary["orientacao_cliente"], tone="info")
            if critical:
                render_card_html("Trechos que pedem intervenção", f"Foram detectados <strong>{len(critical)}</strong> pontos com erro relevante ou com fundamento fraco para a tese. O ideal é revisar esses trechos antes do protocolo.", tone="warning")
                for item in critical[:6]:
                    st.markdown(f"<div class='audit-line'><strong>Linha {item.get('linha','-')}</strong> · {item.get('raw','')}<br><span class='small'>{item.get('problema_classificado','Sem classificação')}</span></div>", unsafe_allow_html=True)
            else:
                render_card_html("Peça estável", "Não foram detectadas divergências relevantes nas citações identificadas. Ainda assim, recomenda-se leitura final humana.", tone="success")
            st.text_area("Prévia da peça revisada", revised_text[:15000], height=300)

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
                    st.write(f"{rec['citacao_curta']} · aderência {rec.get('compat_label', compatibility_label(rec.get('compat_score', 0.0)))}")
                if item.get("correcao_sugerida"):
                    sug = item["correcao_sugerida"]
                    st.markdown("**Correção principal sugerida**")
                    st.write(f"{sug['citacao_curta']} · aderência {sug.get('compat_label', compatibility_label(sug.get('compat_score', 0.0)))}")
                    st.write(sug.get("fundamento_curto") or "")
                    st.code(sug.get("texto_pronto") or build_argument_snippet(sug, item.get("tese", "Tese geral")), language="text")
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
                for sug in bloco["sugestoes"][:2]:
                    st.markdown(f"**{sug['citacao_curta']}** · {sug.get('compat_label','Boa')} ({int(sug['compat_score']*100)}%)")
                    st.write(sug.get("motivo_match") or "")
                    st.write(sug.get("fundamento_curto") or "")
                    st.code(sug.get("texto_pronto") or "", language="text")

        with t4:
            render_card_html("Inserção automática de reforço", "A V18 passa a gerar uma versão reforçada da peça, mantendo a estrutura original e adicionando blocos de sustentação onde a tese detectada comporta precedente útil.", tone="success")
            if best_supports:
                for idx, rec in enumerate(best_supports[:5], start=1):
                    st.markdown(f"**Sugestão {idx} — {rec.get('citacao_curta')}**")
                    st.code(rec.get("texto_pronto") or "", language="text")
            st.text_area("Versão integral reforçada", reinforced_text[:15000], height=320)
            st.text_area("Versão integral marcada", marked_text[:15000], height=220)

        with t5:
            render_card_html("Relatório premium para cliente", "Essa aba entrega um parecer executivo já formatado para atendimento comercial, explicando risco, confiança, pontos críticos e orientação final.", tone="info")
            st.text_area("Relatório premium", report_text[:15000], height=420)

        with t6:
            docx_clean = build_docx_bytes(revised_text, analysis, st.session_state.last_file_name or "peca_revisada")
            docx_marked = build_docx_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}", marked=True)
            docx_reinforced = build_docx_bytes(reinforced_text, analysis, f"Reforçado - {st.session_state.last_file_name or 'peca_revisada'}")
            docx_report = build_docx_bytes(report_text, analysis, f"Relatório premium - {st.session_state.last_file_name or 'peca_revisada'}")
            pdf_clean = build_pdf_bytes(revised_text, analysis, st.session_state.last_file_name or "peca_revisada")
            pdf_marked = build_pdf_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}")
            pdf_reinforced = build_pdf_bytes(reinforced_text, analysis, f"Reforçado - {st.session_state.last_file_name or 'peca_revisada'}")
            pdf_report = build_pdf_bytes(report_text, analysis, f"Relatório premium - {st.session_state.last_file_name or 'peca_revisada'}")
            csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig")
            txt_revised = revised_text.encode("utf-8")
            txt_reinforced = reinforced_text.encode("utf-8")
            txt_report = report_text.encode("utf-8")
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button("DOCX limpo", docx_clean, file_name="atlas_v18_revisado_limpo.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            d2.download_button("DOCX marcado", docx_marked, file_name="atlas_v18_revisado_marcado.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            d3.download_button("DOCX reforçado", docx_reinforced, file_name="atlas_v18_revisado_reforcado.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            d4.download_button("DOCX relatório", docx_report, file_name="atlas_v18_relatorio_premium.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            e1, e2, e3, e4 = st.columns(4)
            e1.download_button("PDF limpo", pdf_clean, file_name="atlas_v18_revisado_limpo.pdf", mime="application/pdf", use_container_width=True)
            e2.download_button("PDF marcado", pdf_marked, file_name="atlas_v18_revisado_marcado.pdf", mime="application/pdf", use_container_width=True)
            e3.download_button("PDF reforçado", pdf_reinforced, file_name="atlas_v18_revisado_reforcado.pdf", mime="application/pdf", use_container_width=True)
            e4.download_button("PDF relatório", pdf_report, file_name="atlas_v18_relatorio_premium.pdf", mime="application/pdf", use_container_width=True)
            f1, f2, f3, f4 = st.columns(4)
            f1.download_button("CSV da auditoria", csv_bytes, file_name="atlas_v18_auditoria.csv", mime="text/csv", use_container_width=True)
            f2.download_button("TXT revisado", txt_revised, file_name="atlas_v18_texto_revisado.txt", mime="text/plain", use_container_width=True)
            f3.download_button("TXT reforçado", txt_reinforced, file_name="atlas_v18_texto_reforcado.txt", mime="text/plain", use_container_width=True)
            f4.download_button("TXT relatório", txt_report, file_name="atlas_v18_relatorio_premium.txt", mime="text/plain", use_container_width=True)
            st.caption("A V18 amplia a entrega com relatório premium, texto reforçado e indicador objetivo de protocolo, sem perder a revisão marcada e a auditoria em CSV.")

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
    fy1, fy2 = st.columns(2)
    with fy1:
        year_filter = st.text_input("Filtrar por ano", placeholder="Ex.: 2023")
    with fy2:
        colegiado_filter = st.text_input("Filtrar por colegiado", placeholder="Ex.: Plenário")

    if st.button("Pesquisar precedentes", use_container_width=True):
        if not db_files:
            st.error("Nenhuma base `.db` foi encontrada em `data/base/`.")
        elif not manual_query.strip():
            st.warning("Digite uma tese ou uma referência direta.")
        else:
            thesis = detect_thesis(manual_query)
            thesis_key = thesis["chave"]
            if search_mode == "Número":
                thesis_key = None
            elif search_mode == "Tese" and thesis_key == "geral":
                thesis_key = None
            results = cached_search(db_paths, manual_query, thesis_key or "", ",".join(manual_types), limit * 3)
            filtered = []
            for rec in results:
                if year_filter.strip() and str(rec.get("ano") or "") != year_filter.strip():
                    continue
                if colegiado_filter.strip() and colegiado_filter.strip().lower() not in str(rec.get("colegiado") or "").lower():
                    continue
                filtered.append(rec)
            st.session_state.manual_results = filtered[:limit]

    if st.session_state.manual_results:
        render_card_html("Busca manual fortalecida", "A V18 mantém a busca por número/tese e passa a destacar aplicação prática, aderência e texto pronto para inserção imediata na peça.", tone="info")
        for rec in st.session_state.manual_results:
            st.markdown(
                f"<div class='card'><div style='display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap'><div><strong>{rec['citacao_curta']}</strong></div><div><span class='legend' style='background:#e8eef8;color:#123b67'>{rec.get('compat_label','Boa')} · {int(rec['compat_score']*100)}%</span></div></div><div class='small' style='margin-top:.55rem'><strong>Tema:</strong> {rec.get('tema') or rec.get('tese_central') or 'Não informado'}<br><strong>Colegiado:</strong> {rec.get('colegiado') or 'Não informado'}<br><strong>Motivo do match:</strong> {rec.get('motivo_match') or 'Sem explicação adicional.'}</div></div>",
                unsafe_allow_html=True,
            )
            st.write(rec.get("fundamento_curto") or "")
            st.code(rec.get("citacao_curta") or "", language="text")
            st.code(rec.get("texto_pronto") or "", language="text")
