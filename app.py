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

st.set_page_config(page_title='Atlas dos Acórdãos V14', page_icon='⚖️', layout='wide')

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
        return '#0F5132', '#D1E7DD'
    if status == 'valida_pouco_compativel':
        return '#664D03', '#FFF3CD'
    return '#842029', '#F8D7DA'


def confidence_badge(label: str) -> tuple[str, str]:
    if label.startswith('Alta'):
        return '#0F5132', '#D1E7DD'
    if label.startswith('Média'):
        return '#664D03', '#FFF3CD'
    return '#842029', '#F8D7DA'


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown(
    """
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
          <h1>Atlas dos Acórdãos · V14 Realista</h1>
          <p><strong>Auditoria de citações jurídicas geradas por IA</strong>, com validação em base própria, match semântico por tese e reescrita jurídica contextual do parágrafo.</p>
          <p>Esta versão reforça o núcleo do produto: confirmar se o acórdão, a jurisprudência ou a súmula citados na peça existem, corrigir quando houver erro e sugerir fundamento mais aderente com redação mais humana.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.subheader('Ajustes da análise')
    top_k = st.slider('Sugestões por referência', 1, 5, 3)
    max_blocks = st.slider('Blocos de tese para varredura', 3, 12, 6)
    rewrite_mode = st.radio('Nível de intervenção', ['Correção simples', 'Correção contextual', 'Reescrita premium'], index=2)
    st.markdown('**Legenda**')
    st.markdown('<span class="legend" style="background:#D1E7DD;color:#0F5132">Validada</span> <span class="legend" style="background:#FFF3CD;color:#664D03">Ajuste recomendado</span> <span class="legend" style="background:#F8D7DA;color:#842029">Erro relevante</span>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric('Acórdãos', f"{summary['acordao']:,}".replace(',', '.'))
k2.metric('Jurisprudências', f"{summary['jurisprudencia']:,}".replace(',', '.'))
k3.metric('Súmulas', f"{summary['sumula']:,}".replace(',', '.'))
k4.metric('Bases detectadas', summary['total_bases'])

main_tab, manual_tab = st.tabs(['Upload e auditoria', 'Busca manual de precedentes'])

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

        analysis = {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results, 'piece_text': piece_text, 'rewrite_mode': rewrite_mode}
        st.session_state.analysis = analysis

    analysis = st.session_state.analysis
    if analysis:
        piece_text = analysis.get('piece_text', '')
        mode_map = {'Correção simples': 'simple', 'Correção contextual': 'contextual', 'Reescrita premium': 'premium'}
        revised_text = build_revised_text(piece_text, analysis, mode=mode_map[rewrite_mode])
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
                '<div class="block"><div class="small"><strong>Diagnóstico técnico:</strong> a peça foi lida como <strong>{}</strong>, com <strong>{}</strong> referências explícitas e <strong>{}</strong> blocos argumentativos passíveis de reforço. O motor priorizou validação de citação e aderência temática, em vez de mera coincidência por palavra solta.</div></div>'.format(
                    analysis['piece_type']['tipo'], len(analysis['citation_results']), len(analysis['thesis_results'])
                ),
                unsafe_allow_html=True,
            )
            st.text_area('Prévia da peça revisada', revised_text[:12000], height=280)

        with t2:
            if not analysis['citation_results']:
                st.info('Nenhuma citação explícita de acórdão, súmula ou jurisprudência foi identificada na peça.')
            for item in analysis['citation_results']:
                fg, bg = status_tone(item['status'])
                cfg, cbg = confidence_badge(item['grau_confianca'])
                st.markdown(
                    f"<div class='card'><div style='display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.55rem'><span class='legend' style='background:{bg};color:{fg}'>{item['status_label']}</span><span class='legend' style='background:{cbg};color:{cfg}'>{item['grau_confianca']}</span></div><div class='small'><strong>Referência encontrada:</strong> {item['raw']}<br><strong>Linha:</strong> {item.get('linha','-')}<br><strong>Tese do contexto:</strong> {item.get('tese','Tese geral')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption('Contexto lido pelo motor')
                st.write(item.get('contexto') or '—')
                if item.get('matched_record'):
                    st.markdown('**Precedente validado na base**')
                    st.write(f"{item['matched_record']['tipo']} nº {item['matched_record']['numero']}/{item['matched_record']['ano']} - {item['matched_record']['colegiado']}")
                if item.get('motivo_match'):
                    st.markdown('**Motivo técnico do enquadramento**')
                    st.write(item['motivo_match'])
                if item.get('correcao_sugerida'):
                    sug = item['correcao_sugerida']
                    st.markdown('**Melhor correção sugerida**')
                    st.write(f"{sug['citacao_curta']} · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get('fundamento_curto') or '')
                    st.markdown('**Redação sugerida para o parágrafo**')
                    st.write(item.get('paragrafo_reescrito') or '')

        with t3:
            if not analysis['thesis_results']:
                st.info('Não foram identificados blocos suficientes para reforço por tese.')
            for bloco in analysis['thesis_results']:
                st.markdown(f"<div class='card'><div class='section-title'>{bloco['tese']}</div><div class='small'><strong>Fundamentos detectados:</strong> {bloco['fundamentos'] or 'sem indicadores claros'}</div><div class='small' style='margin-top:.5rem'><strong>Trecho lido:</strong> {bloco['preview']}</div></div>", unsafe_allow_html=True)
                for sug in bloco['sugestoes']:
                    st.markdown(f"**{sug['citacao_curta']}** · aderência {int(sug['compat_score']*100)}%")
                    st.write(sug.get('motivo_match') or '')
                    st.write(sug.get('fundamento_curto') or '')

        with t4:
            docx_clean = build_docx_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            docx_marked = build_docx_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}", marked=True)
            pdf_clean = build_pdf_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button('DOCX limpo', docx_clean, file_name='atlas_v14_revisado_limpo.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d2.download_button('DOCX marcado', docx_marked, file_name='atlas_v14_revisado_marcado.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d3.download_button('PDF limpo', pdf_clean, file_name='atlas_v14_revisado_limpo.pdf', mime='application/pdf', use_container_width=True)
            d4.download_button('CSV da auditoria', csv_bytes, file_name='atlas_v14_auditoria.csv', mime='text/csv', use_container_width=True)

with manual_tab:
    st.markdown('<div class="section-title">Busca manual por tese ou referência direta</div>', unsafe_allow_html=True)
    manual_query = st.text_input('Ex.: falha sanável sem diligência | TCU Acórdão 2622/2013 | Súmula 222')
    manual_types = st.multiselect('Tipos a pesquisar', ['acordao', 'jurisprudencia', 'sumula'], default=['acordao', 'jurisprudencia', 'sumula'])
    if st.button('Pesquisar precedentes', use_container_width=True):
        if not db_files:
            st.error('Nenhuma base `.db` foi encontrada em `data/base/`.')
        elif not manual_query.strip():
            st.warning('Digite uma tese ou uma referência direta.')
        else:
            thesis = detect_thesis(manual_query)
            results = cached_search(db_paths, manual_query, thesis['chave'], ','.join(manual_types), 8)
            if not results:
                st.info('Nenhum precedente relevante foi localizado com os filtros atuais.')
            for rec in results:
                st.markdown(f"<div class='card'><div style='display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap'><div><strong>{rec['citacao_curta']}</strong></div><div><span class='legend' style='background:#e8eef8;color:#123b67'>Aderência {int(rec['compat_score']*100)}%</span></div></div><div class='small' style='margin-top:.55rem'><strong>Tema:</strong> {rec.get('tema') or 'Não informado'}<br><strong>Motivo do match:</strong> {rec.get('motivo_match') or 'Sem explicação adicional.'}</div></div>", unsafe_allow_html=True)
                st.write(rec.get('fundamento_curto') or '')
