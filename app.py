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

st.set_page_config(page_title='Atlas dos Acórdãos V13 Profissional', page_icon='⚖️', layout='wide')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'
LOGO_PATH = BASE_DIR / 'assets' / 'logo_ms.png'

if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'last_file_name' not in st.session_state:
    st.session_state.last_file_name = ''


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
    kinds = set(kinds_key.split(',')) if kinds_key else None
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, kinds=kinds, top_k=top_k)


def status_tone(status: str) -> tuple[str, str]:
    if status == 'valida_compatível':
        return '#0f5132', '#d1e7dd'
    if status == 'valida_pouco_compativel':
        return '#664d03', '#fff3cd'
    return '#842029', '#f8d7da'


def confidence_badge(label: str) -> tuple[str, str]:
    if label.startswith('Alta'):
        return '#0f5132', '#d1e7dd'
    if label.startswith('Média'):
        return '#664d03', '#fff3cd'
    return '#842029', '#f8d7da'


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown(
    """
<style>
.block{padding:1rem 1.1rem;border:1px solid #dbe2ea;border-radius:18px;background:#ffffff}
.hero{padding:1.4rem 1.5rem;border-radius:24px;background:linear-gradient(135deg,#0b1f35 0%,#183b63 55%,#245d8f 100%);color:#fff;border:1px solid rgba(255,255,255,.15)}
.hero h1{margin:0 0 .3rem 0;font-size:2rem}
.hero p{margin:.2rem 0;line-height:1.5}
.legend{display:inline-block;padding:.22rem .6rem;border-radius:999px;font-size:.82rem;font-weight:700}
.card{padding:1rem 1rem;border:1px solid #e2e8f0;border-radius:18px;background:#fff;margin-bottom:.8rem}
.small{font-size:.92rem;color:#334155;line-height:1.5}
.section-title{font-size:1.1rem;font-weight:700;margin:.2rem 0 .8rem 0}
</style>
""",
    unsafe_allow_html=True,
)

c_logo, c_hero = st.columns([1, 5])
with c_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with c_hero:
    st.markdown(
        """
        <div class="hero">
          <h1>Atlas dos Acórdãos · V13 Profissional</h1>
          <p><strong>Auditoria de citações jurídicas geradas por IA</strong>, com validação em base própria, correção orientada por tese e reescrita mais natural do fundamento.</p>
          <p>O foco permanece no núcleo do produto: verificar se o acórdão, a jurisprudência ou a súmula citados na peça existem, encaixam na tese e podem ser corrigidos com segurança.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.subheader('Configuração da análise')
    top_k = st.slider('Sugestões por referência', 1, 5, 3)
    max_blocks = st.slider('Blocos de tese para varredura', 3, 12, 6)
    st.markdown('**Legenda de status**')
    st.markdown('<span class="legend" style="background:#d1e7dd;color:#0f5132">Validada</span> <span class="legend" style="background:#fff3cd;color:#664d03">Ajuste</span> <span class="legend" style="background:#f8d7da;color:#842029">Erro relevante</span>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric('Acórdãos', f"{summary['acordao']:,}".replace(',', '.'))
k2.metric('Jurisprudências', f"{summary['jurisprudencia']:,}".replace(',', '.'))
k3.metric('Súmulas', f"{summary['sumula']:,}".replace(',', '.'))
k4.metric('Bases detectadas', summary['total_bases'])

main_tab, manual_tab = st.tabs(['Upload e auditoria', 'Busca manual'])

with main_tab:
    st.markdown('<div class="section-title">1. Envie a peça ou cole o texto</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader('Arquivo da peça', type=['pdf', 'docx', 'txt'], key='upload_principal')
    manual_text = st.text_area('Ou cole o texto da peça', height=180, key='manual_text_main')
    analyze = st.button('Auditar peça', type='primary', use_container_width=True)

    if analyze:
        if not db_files:
            st.error('Nenhuma base `.db` foi encontrada em `data/base/`.')
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
        st.session_state.last_file_name = file_name

        refs = extract_references_with_context(piece_text)
        piece_type = classify_piece_type(piece_text)
        blocks = split_into_argument_blocks(piece_text, max_blocks=max_blocks)

        with st.spinner('Auditando a peça...'):
            citation_results = [cached_validate(db_paths, ref, top_k) for ref in refs]
            thesis_results = []
            for block in blocks[:max_blocks]:
                suggestions = cached_search(db_paths, block['texto'], block['tese_chave'], 'acordao,jurisprudencia,sumula', top_k)
                if suggestions:
                    thesis_results.append({'tese': block['tese'], 'preview': block['preview'], 'fundamentos': block['fundamentos'], 'sugestoes': suggestions[:3]})

        analysis = {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results, 'piece_text': piece_text}
        st.session_state.analysis = analysis

    analysis = st.session_state.analysis
    if analysis:
        piece_text = analysis.get('piece_text', '')
        revised_text = build_revised_text(piece_text, analysis)
        marked_text = build_marked_text(piece_text, analysis)
        export_rows = build_export_rows(analysis)
        validas = sum(1 for x in analysis['citation_results'] if x['status'] == 'valida_compatível')
        ajustes = sum(1 for x in analysis['citation_results'] if x['status'] == 'valida_pouco_compativel')
        erros = sum(1 for x in analysis['citation_results'] if x['status'] == 'divergente')

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Tipo da peça', analysis['piece_type']['tipo'])
        c2.metric('Validada', validas)
        c3.metric('Ajuste', ajustes)
        c4.metric('Erro relevante', erros)

        t1, t2, t3, t4 = st.tabs(['Diagnóstico', 'Citações auditadas', 'Teses e reforços', 'Exportação'])
        with t1:
            st.markdown(
                '<div class="block"><div class="small"><strong>Diagnóstico técnico:</strong> o sistema leu a peça como <strong>{}</strong>, identificou <strong>{}</strong> referências explícitas e encontrou <strong>{}</strong> blocos argumentativos passíveis de reforço por tese.</div></div>'.format(
                    analysis['piece_type']['tipo'], len(analysis['citation_results']), len(analysis['thesis_results'])
                ),
                unsafe_allow_html=True,
            )
            st.text_area('Prévia da peça revisada', revised_text[:8000], height=260)

        with t2:
            if not analysis['citation_results']:
                st.info('Nenhuma citação explícita de acórdão, súmula ou jurisprudência foi identificada na peça.')
            for item in analysis['citation_results']:
                fg, bg = status_tone(item['status'])
                cfg, cbg = confidence_badge(item['grau_confianca'])
                st.markdown(
                    f"<div class='card'><div style='display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.6rem'><span class='legend' style='background:{bg};color:{fg}'>{item['status_label']}</span><span class='legend' style='background:{cbg};color:{cfg}'>{item['grau_confianca']}</span></div><div class='small'><strong>Referência encontrada:</strong> {item['raw']}<br><strong>Linha:</strong> {item.get('linha','-')}<br><strong>Tese identificada no contexto:</strong> {item.get('tese','Tese geral')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption('Contexto lido pelo motor')
                st.write(item.get('contexto') or '—')
                if item.get('matched_record'):
                    st.markdown('**Precedente validado na base**')
                    st.write(f"{item['matched_record']['tipo']} nº {item['matched_record']['numero']}/{item['matched_record']['ano']} - {item['matched_record']['colegiado']}")
                if item.get('correcao_sugerida'):
                    sug = item['correcao_sugerida']
                    st.markdown('**Melhor correção sugerida**')
                    st.write(f"{sug['citacao_curta']} · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get('fundamento_curto') or '')
                    st.markdown('**Redação jurídica sugerida para o trecho**')
                    st.write(item.get('paragrafo_reescrito') or item.get('substituicao_textual') or '')
                elif item.get('alternativas'):
                    st.markdown('**Alternativas encontradas**')
                    for alt in item['alternativas'][:3]:
                        st.write(f"- {alt['citacao_curta']} · aderência {int(alt['compat_score']*100)}%")
                st.divider()

        with t3:
            if not analysis['thesis_results']:
                st.info('Não houve blocos suficientes para reforço temático automático.')
            for thesis in analysis['thesis_results']:
                st.markdown(
                    f"<div class='card'><div class='section-title'>{thesis['tese']}</div><div class='small'><strong>Trecho-base:</strong> {thesis['preview']}</div></div>",
                    unsafe_allow_html=True,
                )
                for sug in thesis['sugestoes']:
                    st.write(f"**{sug['citacao_curta']}** · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get('fundamento_curto') or '')
                st.divider()

        with t4:
            docx_clean = build_docx_bytes(revised_text, analysis, 'Peça revisada - limpa')
            docx_marked = build_docx_bytes(marked_text, analysis, 'Peça revisada - marcada')
            pdf_clean = build_pdf_bytes(revised_text, analysis, 'Peça revisada - limpa')
            csv_data = pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
            st.download_button('Baixar DOCX limpo', data=docx_clean, file_name='peca_revisada_limpa.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            st.download_button('Baixar DOCX marcado', data=docx_marked, file_name='peca_revisada_marcada.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            st.download_button('Baixar PDF limpo', data=pdf_clean, file_name='peca_revisada_limpa.pdf', mime='application/pdf', use_container_width=True)
            st.download_button('Baixar CSV da auditoria', data=csv_data, file_name='auditoria_citacoes.csv', mime='text/csv', use_container_width=True)

with manual_tab:
    st.markdown('<div class="section-title">Busca manual por tese ou por referência</div>', unsafe_allow_html=True)
    query = st.text_input('Pesquise por tese, tema ou número', placeholder='Ex.: falha sanável sem diligência | Acórdão 2622/2013 | Súmula 222')
    tipo = st.selectbox('Filtrar por tipo', ['Todos', 'Acórdão', 'Jurisprudência', 'Súmula'])
    if st.button('Pesquisar precedentes', use_container_width=True, key='btn_manual'):
        if not db_files:
            st.error('Nenhuma base `.db` foi encontrada em `data/base/`.')
        elif not query.strip():
            st.warning('Digite uma tese, tema ou referência numérica.')
        else:
            thesis = detect_thesis(query)
            kinds = None
            if tipo == 'Acórdão':
                kinds = {'acordao'}
            elif tipo == 'Jurisprudência':
                kinds = {'jurisprudencia'}
            elif tipo == 'Súmula':
                kinds = {'sumula'}
            results = search_candidates([Path(p) for p in db_paths], query, thesis.get('chave'), kinds=kinds, top_k=8)
            if not results:
                st.info('Nenhum precedente relevante foi encontrado para essa consulta.')
            for rec in results:
                st.markdown(
                    f"<div class='card'><div class='section-title'>{rec['citacao_curta']}</div><div class='small'><strong>Tema:</strong> {rec.get('tema') or '—'}<br><strong>Subtema:</strong> {rec.get('subtema') or '—'}<br><strong>Aderência estimada:</strong> {int(rec['compat_score']*100)}%</div></div>",
                    unsafe_allow_html=True,
                )
                st.write(rec.get('fundamento_curto') or '')
                st.divider()
