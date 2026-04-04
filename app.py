from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_citations_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import build_thesis_paragraph, search_candidates, validate_citation

st.set_page_config(page_title='Atlas de Acórdãos MS', page_icon='⚖️', layout='wide')

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / 'data' / 'base'
LOGO_PATH = BASE_DIR / 'assets' / 'logo_ms.png'


def _db_signature(base_dir: Path) -> tuple:
    files = find_db_files(base_dir)
    return tuple((p.name, int(p.stat().st_mtime), p.stat().st_size) for p in files)


@st.cache_data(show_spinner=False)
def cached_summary(path_str: str, signature: tuple):
    return summarize_bases(Path(path_str))


@st.cache_data(show_spinner=False)
def cached_validate(db_paths: tuple[str, ...], citation: dict, top_k: int):
    return validate_citation([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_key: str, top_k: int):
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, top_k=top_k)


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown(
    """
    <style>
    .hero {padding: 1.2rem 1.3rem; border: 1px solid rgba(120,120,120,.16); border-radius: 24px; background: linear-gradient(135deg, #081528 0%, #14325c 55%, #1d4d85 100%); color: white; margin-bottom: 1rem;}
    .hero p {margin: .2rem 0 0 0; opacity: .95; line-height: 1.45;}
    .card {padding: 1rem 1.05rem; border: 1px solid rgba(120,120,120,.15); border-radius: 20px; background: rgba(255,255,255,.03); height: 100%;}
    .soft {color:#475569; font-size:.95rem; line-height:1.5;}
    .tiny {font-size:.88rem; color:#64748b;}
    .tag {display:inline-block; padding: .22rem .62rem; border-radius: 999px; background:#eef3ff; color:#1e3a8a; margin-right:.4rem; margin-bottom:.35rem; font-size:.8rem;}
    .badge-good,.badge-warn,.badge-bad {display:inline-block; padding:.18rem .55rem; border-radius:999px; font-size:.78rem; font-weight:600;}
    .badge-good {background:#dcfce7; color:#166534;}
    .badge-warn {background:#fef3c7; color:#92400e;}
    .badge-bad {background:#fee2e2; color:#991b1b;}
    .panel-title {margin:.1rem 0 .5rem 0; font-size:1.02rem; font-weight:700;}
    @media (max-width: 768px){ .hero{padding:1rem;} }
    </style>
    """,
    unsafe_allow_html=True,
)

col_logo, col_text = st.columns([1, 4])
with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with col_text:
    st.markdown(
        """
        <div class='hero'>
            <h1 style='margin:0;'>Atlas de Acórdãos MS</h1>
            <p>Auditoria de citações, correção inteligente de acórdãos e reforço por tese jurídica para recurso, contrarrazão e impugnação.</p>
            <p><strong>Por que você merece este sistema?</strong> Porque uma peça bem escrita perde força quando a referência está errada, desalinhada com o tema ou artificialmente inflada. Aqui, a validação vem antes da sugestão.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.header('Configurações da análise')
    top_k = st.slider('Máximo de acórdãos por tese', 1, 2, 2)
    max_blocks = st.slider('Teses máximas lidas na peça', 4, 14, 8)
    st.caption('A V5 prioriza auditoria da citação existente e devolve no máximo duas teses úteis, curtas e aplicáveis.')

m1, m2, m3 = st.columns([1, 1, 2.2])
m1.metric('Acórdãos ativos na base', f"{summary['total_registros']:,}".replace(',', '.'))
m2.metric('Bases SQLite detectadas', summary['total_bases'])
m3.markdown(
    "<div class='card'><div class='panel-title'>Lacunas que o sistema preenche</div><div class='soft'>Corrige referência incompatível, evita citação fantasma, reduz excesso de texto e devolve reforço jurisprudencial em formato mais aproveitável para peça administrativa.</div></div>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader('Envie a peça para análise', type=['pdf', 'docx', 'txt'])
manual_text = st.text_area('Ou cole o texto da peça aqui', height=180)
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

    with st.spinner('Auditando a peça, conferindo citações e refinando teses...'):
        citation_results = [cached_validate(db_paths, cit, top_k) for cit in citations]
        thesis_results = []
        used_numbers = {r['correcao_sugerida']['numero_acordao'] for r in citation_results if r.get('correcao_sugerida')}
        used_numbers |= {(r.get('matched_record') or {}).get('numero_acordao') for r in citation_results if r.get('matched_record')}
        used_numbers.discard(None)

        for block in thesis_blocks:
            suggestions = cached_search(db_paths, block['texto'], block['tese_chave'], top_k)
            suggestions = [s for s in suggestions if s.get('numero_acordao') not in used_numbers][:top_k]
            if suggestions:
                for sug in suggestions:
                    sug['paragrafo_aplicado'] = build_thesis_paragraph(sug, block['tese'])
                    used_numbers.add(sug.get('numero_acordao'))
                thesis_results.append({
                    'tese': block['tese'],
                    'tese_chave': block['tese_chave'],
                    'trecho_curto': block['preview'],
                    'fundamentos': block.get('fundamentos', ''),
                    'sugestoes': suggestions[:2],
                })
            if len(thesis_results) >= 2:
                break

    validas = sum(1 for x in citation_results if x['status'] == 'valida_compatível')
    revisao = sum(1 for x in citation_results if x['status'] in {'valida_pouco_compativel', 'divergente', 'nao_localizada'})
    corrected_text = build_revised_text(piece_text, {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results})

    analysis = {
        'piece_type': piece_type,
        'citation_results': citation_results,
        'thesis_results': thesis_results,
    }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Tipo da peça', piece_type['tipo'])
    c2.metric('Citações compatíveis', validas)
    c3.metric('Citações para revisão', revisao)
    c4.metric('Teses prontas para uso', len(thesis_results))

    st.markdown(
        f"<div class='card'><div class='panel-title'>Leitura estrutural da peça</div><div class='soft'>Classificação com confiança <strong>{piece_type['confianca']}</strong>. O sistema identificou a peça por sinais estruturais como: {piece_type['fundamentos']}.</div></div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(['Resumo executivo', 'Citações encontradas', 'Teses aplicadas', 'Download da peça corrigida'])

    with tabs[0]:
        st.markdown('### Diagnóstico objetivo')
        st.markdown(
            f"- A peça foi classificada como **{piece_type['tipo']}**.\n"
            f"- Foram encontradas **{len(citation_results)}** citações de acórdão.\n"
            f"- **{validas}** citações ficaram compatíveis com o contexto.\n"
            f"- **{revisao}** citações exigem revisão, correção ou nova validação.\n"
            f"- O sistema preparou **{len(thesis_results)}** teses curtas para reforço argumentativo."
        )
        st.info('O fluxo desta versão prioriza primeiro a auditoria da citação já usada na peça. Depois, acrescenta teses curtas e aplicáveis para reforço.')

    with tabs[1]:
        if not citation_results:
            st.info('Nenhuma citação de acórdão foi localizada automaticamente.')
        else:
            for item in citation_results:
                badge = 'badge-good' if item['status'] == 'valida_compatível' else 'badge-warn' if item['status'] == 'valida_pouco_compativel' else 'badge-bad'
                with st.container(border=True):
                    st.markdown(f"<span class='{badge}'>{item['status_label']}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Citação localizada na peça:** {item['raw']}")
                    st.caption(f"Linha aproximada: {item.get('linha','-')} · Tese percebida: {item.get('tese','Tese geral')}")
                    if item.get('matched_record'):
                        rec = item['matched_record']
                        st.markdown(f"<span class='tag'>{rec['numero_acordao']}</span><span class='tag'>{rec['colegiado']}</span>", unsafe_allow_html=True)
                        st.write(rec['citacao_curta'])
                    if item.get('correcao_sugerida'):
                        cor = item['correcao_sugerida']
                        st.markdown('**Correção automática sugerida pelo sistema**')
                        st.success(f"TCU, Acórdão nº {cor.get('numero_acordao')} - {cor.get('colegiado')}")
                        st.caption(cor.get('citacao_curta', ''))
                    elif item.get('alternativas'):
                        st.markdown('**Alternativas compatíveis**')
                        for alt in item['alternativas'][:2]:
                            st.markdown(f"- {alt['citacao_curta']}")
                    ctx = item.get('contexto','')
                    if ctx:
                        st.caption('Trecho auditado: ' + ctx[:360] + ('...' if len(ctx) > 360 else ''))

    with tabs[2]:
        if not thesis_results:
            st.info('Nenhuma tese relevante recebeu sugestão segura.')
        else:
            for item in thesis_results:
                with st.container(border=True):
                    st.markdown(f"### {item['tese']}")
                    st.caption(f"Fundamentos detectados: {item.get('fundamentos','tese jurídica principal')}")
                    st.write(item['trecho_curto'])
                    for idx, sug in enumerate(item['sugestoes'][:2], start=1):
                        st.markdown(f"**Tese aplicada {idx}**")
                        st.success(sug['paragrafo_aplicado'])
                        st.caption(sug['citacao_curta'])

    with tabs[3]:
        rows = build_export_rows(analysis)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        report_md = build_markdown_report(file_name, analysis)
        docx_bytes = build_docx_bytes(corrected_text, analysis, title='Peça corrigida pelo Atlas de Acórdãos MS')
        pdf_bytes = build_pdf_bytes(corrected_text, analysis, title='Peça corrigida pelo Atlas de Acórdãos MS')
        st.download_button('Baixar peça corrigida em DOCX', docx_bytes, 'peca_corrigida_atlas_ms.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        st.download_button('Baixar peça corrigida em PDF', pdf_bytes, 'peca_corrigida_atlas_ms.pdf', 'application/pdf', use_container_width=True)
        st.download_button('Baixar relatório em Markdown', report_md.encode('utf-8'), 'relatorio_atlas_acordaos.md', 'text/markdown', use_container_width=True)
        st.download_button('Baixar relatório em CSV', df.to_csv(index=False).encode('utf-8'), 'relatorio_atlas_acordaos.csv', 'text/csv', use_container_width=True)

    st.warning('Ferramenta de apoio técnico-jurídico. Antes do protocolo, confirme a aderência final do precedente e a fidelidade do trecho aproveitado.')
