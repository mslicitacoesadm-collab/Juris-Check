from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import (
    classify_piece_type,
    detect_thesis,
    extract_citations_with_context,
    split_into_argument_blocks,
)
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import search_candidates, validate_citation

st.set_page_config(page_title='Atlas de Acórdãos', page_icon='⚖️', layout='wide')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'


@st.cache_data(show_spinner=False)
def cached_summary(path_str: str):
    return summarize_bases(Path(path_str))


@st.cache_data(show_spinner=False)
def cached_validate(db_paths: tuple[str, ...], citation: dict, top_k: int):
    return validate_citation([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_key: str, top_k: int):
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, top_k=top_k)


summary = cached_summary(str(DB_DIR))
db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)

st.markdown(
    """
    <style>
    .hero {padding: 1.2rem 1.4rem; border: 1px solid rgba(120,120,120,.22); border-radius: 20px; background: linear-gradient(135deg, rgba(26,51,86,.95), rgba(17,25,40,.95)); color: white; margin-bottom: 1rem;}
    .subcard {padding: 1rem 1.1rem; border: 1px solid rgba(120,120,120,.18); border-radius: 18px; background: rgba(255,255,255,.02);}
    .tiny {font-size: .92rem; opacity: .9;}
    .tag {display:inline-block; padding: .18rem .6rem; border-radius: 999px; background:#eef3ff; color:#1e3a8a; margin-right:.4rem; font-size:.8rem;}
    .good {border-left: 5px solid #16a34a; padding-left: .8rem;}
    .warn {border-left: 5px solid #d97706; padding-left: .8rem;}
    .bad {border-left: 5px solid #dc2626; padding-left: .8rem;}
    .soft {color:#475569; font-size:.94rem;}
    @media (max-width: 768px){ .hero{padding:1rem;} }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class='hero'>
        <h1 style='margin:0 0 .25rem 0;'>Atlas de Acórdãos</h1>
        <div class='tiny'>Validação de acórdãos citados, correção de referência e reforço por tese jurídica para recurso, contrarrazão e impugnação.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header('Configurações')
    top_k = st.slider('Sugestões por tese', 1, 3, 2)
    max_blocks = st.slider('Teses máximas analisadas', 4, 18, 10)
    st.caption('O sistema prioriza validação de citação existente e sugere no máximo poucos reforços por tese, para uso real na peça.')

m1, m2, m3 = st.columns([1,1,2])
m1.metric('Acórdãos ativos na base', f"{summary['total_registros']:,}".replace(',', '.'))
m2.metric('Anos cobertos', len(summary['anos']))
m3.markdown(
    "<div class='subcard'><strong>O que este sistema resolve</strong><div class='soft'>Evita citação fantasma, reduz erro de número, melhora a aderência temática do acórdão usado e devolve fundamento curto, pronto para aproveitamento.</div></div>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader('Envie a peça para análise', type=['pdf', 'docx', 'txt'])
manual_text = st.text_area('Ou cole o texto da peça aqui', height=200)
analyze = st.button('Analisar peça', type='primary', use_container_width=True)

if analyze:
    if not db_files:
        st.error('Nenhuma base SQLite foi encontrada em `data/base/`.')
        st.stop()
    if uploaded_file is None and not manual_text.strip():
        st.error('Envie um arquivo ou cole o texto da peça.')
        st.stop()

    if uploaded_file is not None:
        piece_text = read_uploaded_file(uploaded_file)
        file_name = uploaded_file.name
    else:
        piece_text = manual_text
        file_name = 'texto_colado.txt'

    piece_type = classify_piece_type(piece_text)
    citations = extract_citations_with_context(piece_text)
    thesis_blocks = split_into_argument_blocks(piece_text, max_blocks=max_blocks)

    with st.spinner('Lendo a peça e confrontando com a base...'):
        citation_results = [cached_validate(db_paths, cit, top_k) for cit in citations]
        thesis_results = []
        for block in thesis_blocks:
            suggestions = cached_search(db_paths, block['texto'], block['tese_chave'], top_k)
            if suggestions:
                thesis_results.append({
                    'tese': block['tese'],
                    'tese_chave': block['tese_chave'],
                    'trecho_curto': block['preview'],
                    'sugestoes': suggestions,
                })

    validas = sum(1 for x in citation_results if x['status'] == 'valida_compatível')
    fracas = sum(1 for x in citation_results if x['status'] == 'valida_pouco_compativel')
    divergentes = sum(1 for x in citation_results if x['status'] in {'divergente', 'nao_localizada'})

    analysis = {
        'piece_type': piece_type,
        'citation_results': citation_results,
        'thesis_results': thesis_results,
    }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Tipo da peça', piece_type['tipo'])
    c2.metric('Citações compatíveis', validas)
    c3.metric('Citações fracas/divergentes', fracas + divergentes)
    c4.metric('Teses com reforço', len(thesis_results))

    st.markdown(
        f"<div class='subcard'><strong>Leitura estrutural</strong><div class='soft'>Confiança da classificação: <strong>{piece_type['confianca']}</strong>. Base da identificação: {piece_type['fundamentos']}.</div></div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(['Resumo', 'Citações encontradas', 'Sugestões por tese', 'Exportação'])

    with tabs[0]:
        st.markdown('### Diagnóstico objetivo')
        st.markdown(
            f"- A peça foi classificada como **{piece_type['tipo']}**.\n"
            f"- Foram detectadas **{len(citation_results)}** citações de acórdão.\n"
            f"- **{validas}** citações ficaram compatíveis com o contexto.\n"
            f"- **{fracas + divergentes}** exigem revisão ou substituição.\n"
            f"- O sistema identificou **{len(thesis_results)}** teses com potencial de reforço jurisprudencial."
        )
        st.info('A lógica agora prioriza primeiro a auditoria do acórdão já citado. Só depois sugere reforço curto por tese jurídica.')

    with tabs[1]:
        if not citation_results:
            st.info('Nenhuma citação de acórdão foi localizada automaticamente.')
        else:
            for item in citation_results:
                css = 'good' if item['status'] == 'valida_compatível' else 'warn' if item['status'] == 'valida_pouco_compativel' else 'bad'
                with st.container(border=True):
                    st.markdown(f"<div class='{css}'><strong>{item['raw']}</strong></div>", unsafe_allow_html=True)
                    st.caption(f"Linha aproximada: {item.get('linha','-')}")
                    st.write(f"**Status:** {item['status_label']}")
                    if item.get('matched_record'):
                        rec = item['matched_record']
                        st.markdown(f"<span class='tag'>{rec['numero_acordao']}</span><span class='tag'>{rec['colegiado']}</span>", unsafe_allow_html=True)
                        st.write(rec['citacao_curta'])
                    if item.get('correcao_sugerida'):
                        cor = item['correcao_sugerida']
                        st.write('**Correção sugerida:**')
                        st.success(cor['citacao_curta'])
                    elif item.get('alternativas'):
                        st.write('**Alternativas compatíveis:**')
                        for alt in item['alternativas'][:2]:
                            st.markdown(f"- {alt['citacao_curta']}")
                    ctx = item.get('contexto','')
                    if ctx:
                        st.caption(ctx[:300] + ('...' if len(ctx) > 300 else ''))

    with tabs[2]:
        if not thesis_results:
            st.info('Nenhuma tese relevante recebeu sugestão segura.')
        else:
            for item in thesis_results:
                with st.container(border=True):
                    st.markdown(f"### {item['tese']}")
                    st.write(item['trecho_curto'])
                    st.write('**Sugestões curtas para aproveitamento:**')
                    for sug in item['sugestoes']:
                        st.success(sug['citacao_curta'])

    with tabs[3]:
        rows = build_export_rows(analysis)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        report_md = build_markdown_report(file_name, analysis)
        st.download_button('Baixar relatório em Markdown', report_md.encode('utf-8'), 'relatorio_atlas_acordaos.md', 'text/markdown', use_container_width=True)
        st.download_button('Baixar relatório em CSV', df.to_csv(index=False).encode('utf-8'), 'relatorio_atlas_acordaos.csv', 'text/csv', use_container_width=True)

    st.warning('Ferramenta de apoio. Sempre confirme a adequação final do precedente antes do protocolo.')
