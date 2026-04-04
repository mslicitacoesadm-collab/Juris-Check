import json
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_loader import load_acordaos, summarize_base
from modules.citation_extractor import extract_citations, split_into_blocks
from modules.matcher import analyze_piece, build_search_index
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report

st.set_page_config(page_title="Validador de Autoridade Jurídica", page_icon="⚖️", layout="wide")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "acordaos"


@st.cache_data(show_spinner=False)
def cached_load_acordaos(data_dir_str: str):
    return load_acordaos(Path(data_dir_str))


@st.cache_resource(show_spinner=False)
def cached_build_index(records_json: str):
    records = json.loads(records_json)
    return build_search_index(records)


st.title("⚖️ Validador de Autoridade Jurídica")
st.caption(
    "Sistema de apoio para validar citações, localizar divergências de numeração e sugerir acórdãos aderentes."
)

with st.sidebar:
    st.header("Configurações")
    top_k = st.slider("Sugestões por bloco", 1, 5, 3)
    min_score = st.slider("Score mínimo de similaridade", 0.0, 1.0, 0.12, 0.01)
    max_blocks = st.slider("Máximo de blocos analisados", 5, 80, 25)
    st.info(
        "Coloque seus arquivos JSON ou JSONL em `data/acordaos/`.\n\n"
        "O app funciona mesmo sem base carregada, mas a análise só é liberada quando a pasta tiver registros."
    )

base_records = cached_load_acordaos(str(DATA_DIR))
base_summary = summarize_base(DATA_DIR, base_records)

col1, col2, col3 = st.columns(3)
col1.metric("Registros carregados", base_summary["total_registros"])
col2.metric("Arquivos da base", base_summary["total_arquivos"])
col3.metric("Anos encontrados", ", ".join(base_summary["anos"]) if base_summary["anos"] else "Nenhum")

search_index = None
if base_records:
    try:
        search_index = cached_build_index(json.dumps(base_records, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        st.error("A base foi encontrada, mas houve falha ao montar o índice de busca.")
        st.exception(exc)
        st.stop()
else:
    st.warning("Nenhuma base foi carregada ainda. O app abriu normalmente, mas você precisa colocar os JSONs em `data/acordaos/`.")

with st.expander("Schema esperado da base JSON"):
    st.code(
        json.dumps(
            {
                "id": "ACORDAO-COMPLETO-2230911",
                "tipo": "ACÓRDÃO",
                "titulo": "ACÓRDÃO 3215/2016 ATA 40/2016 - PLENÁRIO",
                "numero_acordao": "3215/2016",
                "numero_acordao_num": "3215",
                "ano_acordao": "2016",
                "colegiado": "PLENÁRIO",
                "data_sessao": "07/12/2016",
                "relator": "MINISTRO XXXXX",
                "processo": "XXXXX/2016-0",
                "assunto": "Representação sobre irregularidades em licitação",
                "sumario": "Trecho resumido da tese jurídica",
                "ementa_match": "licitação, diligência, inexequibilidade, saneamento",
                "decisao": "texto resumido da decisão",
                "url_oficial": "",
                "status": "ativo",
                "tags": ["licitação", "inexequibilidade", "diligência", "saneamento"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        language="json",
    )

uploaded_file = st.file_uploader("Envie a peça para análise", type=["pdf", "docx", "txt"])
manual_text = st.text_area("Ou cole o texto da peça aqui", height=220)
analyze = st.button("Analisar peça", type="primary", use_container_width=True)

if analyze:
    if not base_records or search_index is None:
        st.error("Nenhuma base carregada. Adicione os arquivos em `data/acordaos/` antes de analisar.")
        st.stop()

    if uploaded_file is None and not manual_text.strip():
        st.error("Envie um arquivo ou cole o texto da peça.")
        st.stop()

    try:
        if uploaded_file is not None:
            piece_text = read_uploaded_file(uploaded_file)
            file_name = uploaded_file.name
        else:
            piece_text = manual_text
            file_name = "texto_colado.txt"
    except Exception as exc:
        st.error("Falha ao ler o arquivo enviado.")
        st.exception(exc)
        st.stop()

    if not piece_text.strip():
        st.error("Não foi possível extrair texto útil da peça.")
        st.stop()

    blocks = split_into_blocks(piece_text, max_blocks=max_blocks)
    citations = extract_citations(piece_text)

    with st.spinner("Analisando peça e cruzando com a base..."):
        analysis = analyze_piece(
            piece_text=piece_text,
            blocks=blocks,
            citations=citations,
            base_records=base_records,
            search_index=search_index,
            top_k=top_k,
            min_score=min_score,
        )

    st.success("Análise concluída.")

    stats = analysis["stats"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Citações detectadas", stats["citacoes_detectadas"])
    c2.metric("Citações válidas", stats["citacoes_validas"])
    c3.metric("Citações divergentes", stats["citacoes_divergentes"])
    c4.metric("Blocos com sugestão", stats["blocos_com_sugestao"])

    tab1, tab2, tab3, tab4 = st.tabs(["Resumo executivo", "Citações", "Sugestões por bloco", "Exportação"])

    with tab1:
        st.markdown(analysis["summary_markdown"])

    with tab2:
        if not analysis["citation_results"]:
            st.info("Nenhuma citação de acórdão detectada automaticamente.")
        else:
            for item in analysis["citation_results"]:
                with st.container(border=True):
                    st.markdown(f"**Trecho citado:** `{item['raw']}`")
                    st.write(f"Status: **{item['status_label']}**")
                    if item.get("matched_record"):
                        rec = item["matched_record"]
                        st.write(f"Base encontrada: **{rec['numero_acordao']}** • {rec['colegiado']} • Relator: {rec['relator']}")
                        if rec.get("assunto"):
                            st.caption(rec["assunto"])
                    if item.get("suggestions"):
                        st.write("Sugestões:")
                        for sug in item["suggestions"]:
                            st.markdown(f"- **{sug['numero_acordao']}** | {sug['colegiado']} | score `{sug['score']:.3f}`")

    with tab3:
        if not analysis["block_results"]:
            st.info("Nenhum bloco com sugestão acima do score mínimo.")
        else:
            for block in analysis["block_results"]:
                with st.container(border=True):
                    st.markdown(f"**Bloco {block['block_index']}**")
                    st.write(block["block_text"])
                    st.write("Melhores sugestões:")
                    for sug in block["suggestions"]:
                        st.markdown(
                            f"- **{sug['numero_acordao']}** | {sug['colegiado']} | Relator: {sug['relator']} | score `{sug['score']:.3f}`"
                        )
                        if sug.get("sumario"):
                            st.caption(sug["sumario"])
                        st.code(sug["paragrafo_sugerido"], language="markdown")

    with tab4:
        export_rows = build_export_rows(analysis)
        df = pd.DataFrame(export_rows) if export_rows else pd.DataFrame()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Não houve linhas para exportação nesta análise.")

        report_md = build_markdown_report(file_name=file_name, analysis=analysis)
        st.download_button(
            "Baixar relatório em Markdown",
            data=report_md.encode("utf-8"),
            file_name="relatorio_analise_jurisprudencia.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.download_button(
            "Baixar relatório em CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="relatorio_analise_jurisprudencia.csv",
            mime="text/csv",
            use_container_width=True,
        )

with st.expander("Aviso importante"):
    st.warning("Este sistema é ferramenta de apoio. Sempre valide a citação, o contexto e a pertinência antes do protocolo da peça.")
