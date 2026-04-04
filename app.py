from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import exact_lookup, find_db_files, summarize_bases
from modules.citation_extractor import build_argument_blocks, extract_citations
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import search_candidates
from modules.thesis_analyzer import detect_document_type, THESIS_PROFILES

st.set_page_config(page_title='Atlas de Acórdãos V3', page_icon='⚖️', layout='wide')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'


@st.cache_data(show_spinner=False)
def cached_summary(path_str: str):
    return summarize_bases(Path(path_str))


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_id: str, top_k: int):
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_id=thesis_id, top_k=top_k)


st.markdown(
    """
    <style>
    .main .block-container {max-width: 1180px; padding-top: 1rem; padding-bottom: 2rem;}
    .hero {background: linear-gradient(135deg,#0b1220,#15304f); color:#fff; border-radius:24px; padding:1.4rem; margin-bottom:1rem; box-shadow:0 18px 38px rgba(2,6,23,.18);} 
    .hero h1 {margin:0; font-size:1.65rem;} .hero p {margin:.6rem 0 0 0; color:#dbe7f4; max-width:840px;}
    .grid {display:grid; grid-template-columns:1.35fr .95fr; gap:14px; margin-bottom:1rem;}
    .panel {background:#fff; border:1px solid #e2e8f0; border-radius:22px; padding:16px; box-shadow:0 10px 28px rgba(15,23,42,.05);} 
    .metric {background:#0f172a; color:#fff; border-radius:20px; padding:18px;} .metric .k{color:#cbd5e1; font-size:.86rem;} .metric .v{font-size:1.85rem; font-weight:800; margin-top:8px;} .metric .d{color:#94a3b8; font-size:.84rem; margin-top:8px;}
    .benefits {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px;}
    .benefit {background:#f8fafc; border:1px solid #e2e8f0; border-radius:16px; padding:14px;} .benefit strong{display:block; margin-bottom:6px;} .benefit span{font-size:.9rem; color:#475569;}
    .stats {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:1rem 0;} 
    .card {background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:14px;} .card .v{font-size:1.25rem; font-weight:800;} .card .l{font-size:.82rem; color:#475569;}
    .thesis-card, .citation-card {background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:16px; margin-bottom:12px;}
    .chip {display:inline-block; background:#e2e8f0; color:#0f172a; padding:4px 10px; border-radius:999px; font-size:.78rem; font-weight:700; margin:0 8px 8px 0;}
    .quote {background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:12px 14px; line-height:1.6; margin-top:10px;}
    .muted {color:#64748b; font-size:.84rem;}
    .ok {background:#dcfce7; color:#166534; padding:5px 10px; border-radius:999px; font-size:.78rem; font-weight:700; display:inline-block; margin-bottom:10px;}
    .bad {background:#fee2e2; color:#991b1b; padding:5px 10px; border-radius:999px; font-size:.78rem; font-weight:700; display:inline-block; margin-bottom:10px;}
    .stButton button {height:3rem; border-radius:14px; font-weight:700;}
    @media (max-width: 920px){.grid,.benefits,.stats{grid-template-columns:1fr 1fr;}}
    @media (max-width: 680px){.grid,.benefits,.stats{grid-template-columns:1fr;} .hero h1{font-size:1.3rem;}}
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
      <h1>Atlas de Acórdãos V3 · Leitura por tese jurídica</h1>
      <p>O sistema agora lê a peça por fundamento jurídico, separa os trechos argumentativos mais fortes e sugere apenas citações curtas de acórdãos, em formato mais compatível com recurso, contrarrazão e impugnação.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('### Ajustes da análise')
    top_k = st.slider('Sugestões por tese', 1, 3, 2)
    max_blocks = st.slider('Máximo de trechos argumentativos', 4, 16, 10)
    st.caption('A análise prioriza poucos trechos com alta densidade jurídica para reduzir ruído e evitar sugestões sem aderência.')

left, right = st.columns([1.35, 0.95])
with left:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader('Envie a peça', type=['pdf', 'docx', 'txt'])
    manual_text = st.text_area('Ou cole o texto da peça', height=230, placeholder='Cole aqui o recurso, a contrarrazão ou a impugnação.')
    st.markdown('</div>', unsafe_allow_html=True)
with right:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='metric'><div class='k'>Acórdãos ativos na base</div><div class='v'>{summary['total_registros']:,}</div><div class='d'>A base sustenta validação de citação e sugestão por tese jurídica.</div></div>".replace(',', '.'),
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class='benefits'>
          <div class='benefit'><strong>Leitura por tese</strong><span>O sistema tenta separar fundamentos como formalismo moderado, diligência, inexequibilidade e vinculação ao edital.</span></div>
          <div class='benefit'><strong>Citação curta</strong><span>Entrega sugestão em formato enxuto, com foco no número do acórdão e no trecho realmente aproveitável.</span></div>
          <div class='benefit'><strong>Filtro de aderência</strong><span>Quando não há afinidade temática suficiente, a sugestão é descartada para evitar ruído na peça.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

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

    if not piece_text.strip():
        st.error('Não foi possível extrair texto útil da peça.')
        st.stop()

    doc_type = detect_document_type(piece_text)
    citations = extract_citations(piece_text)
    blocks = build_argument_blocks(piece_text, max_blocks=max_blocks)

    citation_results = []
    citacoes_validas = 0
    citacoes_divergentes = 0
    thesis_results = []

    with st.spinner('Lendo a estrutura da peça e cruzando as teses com a base...'):
        for cit in citations:
            exact = exact_lookup(db_files, cit['numero_acordao_num'], cit.get('ano_acordao') or None)
            if exact:
                citacoes_validas += 1
                citation_results.append({'raw': cit['raw'], 'status': 'valida', 'matched_record': exact, 'suggestions': []})
            else:
                citacoes_divergentes += 1
                citation_results.append({'raw': cit['raw'], 'status': 'divergente', 'matched_record': None, 'suggestions': []})

        seen_theses = set()
        for block in blocks:
            for thesis in block['theses']:
                thesis_id = thesis['id']
                if (block['id'], thesis_id) in seen_theses:
                    continue
                seen_theses.add((block['id'], thesis_id))
                suggestions = cached_search(db_paths, block['texto'], thesis_id, top_k)
                if not suggestions:
                    continue
                thesis_results.append({
                    'thesis_id': thesis_id,
                    'titulo': THESIS_PROFILES[thesis_id].titulo,
                    'descricao': THESIS_PROFILES[thesis_id].descricao,
                    'trecho_base': block['texto'],
                    'trecho_resumo': (block['texto'][:260].rsplit(' ', 1)[0] + '...') if len(block['texto']) > 260 else block['texto'],
                    'secao': block['titulo_secao'],
                    'suggestions': suggestions,
                })

    thesis_results.sort(key=lambda x: len(x['suggestions']), reverse=True)

    st.markdown(
        "<div class='stats'>"
        f"<div class='card'><div class='v'>{len(citations)}</div><div class='l'>Citações detectadas</div></div>"
        f"<div class='card'><div class='v'>{citacoes_validas}</div><div class='l'>Confirmadas</div></div>"
        f"<div class='card'><div class='v'>{citacoes_divergentes}</div><div class='l'>Não localizadas</div></div>"
        f"<div class='card'><div class='v'>{len(thesis_results)}</div><div class='l'>Teses jurídicas úteis</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(['Resumo', 'Teses jurídicas', 'Citações', 'Exportação'])

    with tab1:
        st.markdown(f'**Tipo provável da peça:** {doc_type}')
        st.markdown(
            '- O sistema priorizou apenas trechos argumentativos com aderência temática.\n'
            '- As sugestões foram agrupadas por tese jurídica, para evitar retorno genérico e prolixo.\n'
            '- A citação sugerida já vem em formato curto, mais aproveitável na redação real.'
        )

    with tab2:
        if not thesis_results:
            st.info('Nenhuma tese jurídica com aderência suficiente foi encontrada para sugestão segura.')
        else:
            for thesis in thesis_results:
                st.markdown('<div class="thesis-card">', unsafe_allow_html=True)
                st.markdown(f"### {thesis['titulo']}")
                st.markdown(f"<div class='muted'>{thesis['descricao']}</div>", unsafe_allow_html=True)
                st.markdown(f"<span class='chip'>Seção: {thesis['secao']}</span>", unsafe_allow_html=True)
                st.markdown(f"**Trecho da peça analisado**\n\n> {thesis['trecho_resumo']}")
                for sug in thesis['suggestions']:
                    st.markdown(f"<div class='quote'>{sug['paragrafo_sugerido']}</div>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        if not citation_results:
            st.info('Nenhuma citação de acórdão foi detectada automaticamente.')
        else:
            for item in citation_results:
                st.markdown('<div class="citation-card">', unsafe_allow_html=True)
                badge = 'ok' if item['status'] == 'valida' else 'bad'
                label = 'Citação confirmada' if item['status'] == 'valida' else 'Citação não localizada'
                st.markdown(f"<span class='{badge}'>{label}</span>", unsafe_allow_html=True)
                st.markdown(f"**Trecho detectado:** {item['raw']}")
                if item['matched_record']:
                    record = item['matched_record']
                    st.markdown(f"**Base:** TCU, Acórdão nº {record.get('numero_acordao','')} - {record.get('colegiado','')}")
                st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        analysis = {
            'thesis_results': thesis_results,
            'stats': {
                'citacoes_detectadas': len(citations),
                'citacoes_validas': citacoes_validas,
                'teses_detectadas': len(thesis_results),
            },
        }
        export_rows = build_export_rows(analysis)
        report_md = build_markdown_report(file_name, doc_type, analysis)
        st.download_button('Baixar relatório em Markdown', report_md.encode('utf-8'), file_name='relatorio_teses.md', mime='text/markdown')
        if export_rows:
            df = pd.DataFrame(export_rows)
            st.dataframe(df, use_container_width=True)
            st.download_button('Baixar CSV de sugestões', df.to_csv(index=False).encode('utf-8'), file_name='sugestoes_por_tese.csv', mime='text/csv')
        else:
            st.info('Não houve sugestões exportáveis nesta análise.')
