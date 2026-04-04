from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import exact_lookup, find_db_files, summarize_bases
from modules.citation_extractor import extract_citations, split_into_blocks
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import search_candidates

st.set_page_config(page_title='Validador de Autoridade Jurídica', page_icon='⚖️', layout='wide')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'


@st.cache_data(show_spinner=False)
def cached_summary(path_str: str):
    return summarize_bases(Path(path_str))


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, top_k: int):
    return search_candidates([Path(p) for p in db_paths], query_text, top_k=top_k)


def metric_card(label: str, value: str, tone: str = 'neutral') -> str:
    return f"<div class='metric-card {tone}'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>"


st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1220px;}
    .hero {background: linear-gradient(135deg,#0f172a 0%,#111827 50%,#1e293b 100%); color:white; padding:1.35rem 1.4rem; border-radius:22px; border:1px solid rgba(255,255,255,0.08); box-shadow:0 12px 28px rgba(15,23,42,0.18); margin-bottom:1rem;}
    .hero h1 {margin:0; font-size:1.55rem;}
    .hero p {margin:.45rem 0 0 0; color:#dbe4f0; font-size:.96rem;}
    .section-title {font-size:1.04rem; font-weight:700; margin:.2rem 0 .7rem 0;}
    .metric-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:.25rem 0 1rem;}
    .metric-card {background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:14px 16px; box-shadow:0 8px 22px rgba(15,23,42,0.05);}
    .metric-card.good {border-color:#bbf7d0; background:#f0fdf4;}
    .metric-card.warn {border-color:#fde68a; background:#fffbeb;}
    .metric-card.bad {border-color:#fecaca; background:#fef2f2;}
    .metric-label {font-size:.84rem; color:#475569; margin-bottom:8px;}
    .metric-value {font-size:1.35rem; font-weight:800; color:#0f172a;}
    .panel {background:#fff; border:1px solid #e5e7eb; border-radius:22px; padding:16px; box-shadow:0 10px 24px rgba(15,23,42,0.05); margin-bottom:1rem;}
    .citation-card, .suggestion-card {background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:14px; margin-bottom:12px;}
    .status-pill {display:inline-block; padding:4px 10px; border-radius:999px; font-size:.78rem; font-weight:700;}
    .pill-good {background:#dcfce7; color:#166534;}
    .pill-bad {background:#fee2e2; color:#991b1b;}
    .mini {font-size:.85rem; color:#475569;}
    .suggestion-title {font-weight:800; color:#111827; margin-bottom:6px;}
    .muted {color:#64748b;}
    @media (max-width: 900px) {.metric-grid {grid-template-columns:1fr 1fr;}}
    @media (max-width: 640px) {.metric-grid {grid-template-columns:1fr;}.hero h1{font-size:1.25rem;}}
    </style>
    """,
    unsafe_allow_html=True,
)

summary = cached_summary(str(DB_DIR))
db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)

st.markdown(
    """
    <div class='hero'>
      <h1>Validador de Autoridade Jurídica</h1>
      <p>Analise recursos, contrarrazões e impugnações com foco em validação de citações e sugestões jurisprudenciais mais aderentes ao tema da peça.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('### Configurações da análise')
    top_k = st.slider('Máximo de sugestões úteis', 1, 4, 2)
    max_blocks = st.slider('Máximo de blocos da peça', 5, 40, 12)
    st.caption('Menos sugestões e menos blocos tendem a deixar a análise mais limpa e aderente.')

left, right = st.columns([1.25, 1])
with left:
    uploaded_file = st.file_uploader('Envie a peça', type=['pdf', 'docx', 'txt'], label_visibility='collapsed')
    manual_text = st.text_area('Ou cole o texto da peça', height=220, placeholder='Cole aqui o texto do recurso, contrarrazão ou impugnação.')
with right:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Base carregada</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='metric-grid'>" +
        metric_card('Bancos detectados', str(summary['total_bases'])) +
        metric_card('Registros', f"{summary['total_registros']:,}".replace(',', '.')) +
        metric_card('Anos', ', '.join(summary['anos']) if summary['anos'] else '—') +
        metric_card('Modo', 'SQLite') +
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption('A base fica no sistema, mas a consulta é feita sob demanda. Isso evita travamentos no Streamlit.')
    st.markdown("</div>", unsafe_allow_html=True)

analyze = st.button('Analisar peça', type='primary', use_container_width=True)

if analyze:
    if not db_files:
        st.error('Nenhuma base SQLite foi encontrada em `data/base/`.')
        st.stop()

    if uploaded_file is None and not manual_text.strip():
        st.error('Envie um arquivo ou cole o texto da peça.')
        st.stop()

    try:
        if uploaded_file is not None:
            piece_text = read_uploaded_file(uploaded_file)
            file_name = uploaded_file.name
        else:
            piece_text = manual_text
            file_name = 'texto_colado.txt'
    except Exception as exc:
        st.error('Falha ao ler a peça enviada.')
        st.exception(exc)
        st.stop()

    if not piece_text.strip():
        st.error('Não foi possível extrair texto útil da peça.')
        st.stop()

    citations = extract_citations(piece_text)
    blocks = split_into_blocks(piece_text, max_blocks=max_blocks)

    citation_results = []
    validas = 0
    divergentes = 0
    blocos_com_sugestao = 0

    with st.spinner('Analisando a peça...'):
        for cit in citations:
            exact = exact_lookup(db_files, cit.get('numero_acordao_num', ''), cit.get('ano_acordao') or None)
            if exact:
                validas += 1
                citation_results.append({
                    'raw': cit['raw'],
                    'status': 'valida',
                    'status_label': 'Citação confirmada',
                    'matched_record': exact,
                    'suggestions': [],
                })
            else:
                divergentes += 1
                suggestions = cached_search(db_paths, cit['raw'], top_k)
                citation_results.append({
                    'raw': cit['raw'],
                    'status': 'divergente',
                    'status_label': 'Não localizada na base',
                    'matched_record': None,
                    'suggestions': suggestions,
                })

        block_results = []
        for idx, block in enumerate(blocks, start=1):
            suggestions = cached_search(db_paths, block, top_k)
            if suggestions:
                blocos_com_sugestao += 1
                block_results.append({'block_index': idx, 'block_text': block, 'suggestions': suggestions})

    summary_md = '\n'.join([
        '### Resumo executivo',
        f'- Citações automáticas detectadas: **{len(citations)}**.',
        f'- Citações confirmadas literalmente na base: **{validas}**.',
        f'- Citações não localizadas: **{divergentes}**.',
        f'- Blocos com sugestão realmente aderente: **{blocos_com_sugestao}**.',
        '',
        'A tela já prioriza apenas resultados mais aderentes. Quando não houver similaridade suficiente, o sistema prefere não sugerir nada.',
    ])

    analysis = {
        'citation_results': citation_results,
        'block_results': block_results,
        'summary_markdown': summary_md,
        'stats': {
            'citacoes_detectadas': len(citations),
            'citacoes_validas': validas,
            'citacoes_divergentes': divergentes,
            'blocos_com_sugestao': blocos_com_sugestao,
        },
    }

    st.markdown(
        "<div class='metric-grid'>" +
        metric_card('Citações detectadas', str(len(citations))) +
        metric_card('Confirmadas', str(validas), 'good') +
        metric_card('Não localizadas', str(divergentes), 'bad' if divergentes else 'warn') +
        metric_card('Sugestões úteis', str(blocos_com_sugestao), 'good' if blocos_com_sugestao else 'warn') +
        "</div>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(['Resumo', 'Citações', 'Sugestões', 'Exportação'])

    with tab1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown(summary_md)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if not citation_results:
            st.info('Nenhuma citação automática foi detectada na peça.')
        else:
            for item in citation_results:
                pill = 'pill-good' if item['status'] == 'valida' else 'pill-bad'
                st.markdown("<div class='citation-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='suggestion-title'>{item['raw']}</div>", unsafe_allow_html=True)
                st.markdown(f"<span class='status-pill {pill}'>{item['status_label']}</span>", unsafe_allow_html=True)
                if item.get('matched_record'):
                    rec = item['matched_record']
                    st.markdown(f"<p class='mini'><strong>{rec['numero_acordao']}</strong> • {rec['colegiado']} • Relator: {rec['relator']}</p>", unsafe_allow_html=True)
                    if rec.get('sumario'):
                        st.caption(rec['sumario'])
                elif item.get('suggestions'):
                    st.markdown("<p class='mini'><strong>Sugestões mais próximas:</strong></p>", unsafe_allow_html=True)
                    for sug in item['suggestions']:
                        st.markdown(f"- **{sug['numero_acordao']}** | {sug['colegiado']} | aderência `{sug['relevance']}`")
                        if sug.get('matched_terms'):
                            st.caption('Aderência por termos: ' + ', '.join(sug['matched_terms']))
                st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        if not block_results:
            st.info('Nenhum bloco da peça atingiu aderência mínima para exibir sugestão.')
        else:
            for block in block_results:
                st.markdown("<div class='suggestion-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='suggestion-title'>Bloco {block['block_index']}</div>", unsafe_allow_html=True)
                st.write(block['block_text'])
                for sug in block['suggestions']:
                    st.markdown(f"**{sug['numero_acordao']}** • {sug['colegiado']} • Relator: {sug['relator']} • aderência `{sug['relevance']}`")
                    if sug.get('matched_terms'):
                        st.caption('Termos coincidentes: ' + ', '.join(sug['matched_terms']))
                    if sug.get('sumario'):
                        st.caption(sug['sumario'])
                    st.code(sug['paragrafo_sugerido'])
                st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        rows = build_export_rows(analysis)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        report_md = build_markdown_report(file_name, analysis)
        st.download_button('Baixar relatório em Markdown', report_md.encode('utf-8'), 'relatorio_analise_jurisprudencia.md', 'text/markdown', use_container_width=True)
        st.download_button('Baixar relatório em CSV', df.to_csv(index=False).encode('utf-8'), 'relatorio_analise_jurisprudencia.csv', 'text/csv', use_container_width=True)

st.caption('Ferramenta de apoio. Sempre valide a pertinência do precedente e a exatidão da citação antes do protocolo.')
