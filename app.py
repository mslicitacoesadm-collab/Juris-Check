from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_piece_structure
from modules.document_builder import build_docx_bytes, build_pdf_bytes, build_revised_text
from modules.piece_reader import inspect_extraction, read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import build_thesis_paragraph, search_candidates, validate_citation

st.set_page_config(page_title='Atlas de Precedentes MS V10', page_icon='⚖️', layout='wide')

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
def cached_search(db_paths: tuple[str, ...], query_text: str, thesis_key: str, top_k: int, tipo: str | None = None):
    return search_candidates([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, top_k=top_k, tipo=tipo)


if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'last_analysis' not in st.session_state:
    st.session_state.last_analysis = None
if 'last_file_name' not in st.session_state:
    st.session_state.last_file_name = None
if 'last_text' not in st.session_state:
    st.session_state.last_text = ''


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown("""
<style>
.hero{padding:1.25rem 1.3rem;border-radius:28px;background:linear-gradient(135deg,#071527 0%,#12345d 55%,#175b9a 100%);color:white;border:1px solid rgba(255,255,255,.12);margin-bottom:1rem}
.hero h1{margin:0 0 .35rem 0;font-size:2rem}.hero p{margin:.15rem 0;line-height:1.5;opacity:.96}
.soft-card,.metric-card{padding:1rem 1.05rem;border:1px solid rgba(120,120,120,.16);border-radius:20px;background:rgba(255,255,255,.03);height:100%}
.result-card{padding:.9rem 1rem;border-radius:18px;background:#f8fafc;border:1px solid #e2e8f0;margin-bottom:.8rem}
.small{font-size:.92rem;color:#475569;line-height:1.45}
.good{color:#166534}.warn{color:#92400e}.bad{color:#991b1b}
</style>
""", unsafe_allow_html=True)

logo_col, hero_col = st.columns([1, 4])
with logo_col:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with hero_col:
    st.markdown("""
    <div class='hero'>
        <h1>Atlas de Precedentes MS · Validação Profissional</h1>
        <p><strong>Foco principal da ferramenta:</strong> validar citações de acórdão, jurisprudência e súmula inseridas na peça, conferir se batem com a base e apontar a correção mais aderente quando houver erro.</p>
        <p><strong>Evolução aplicada:</strong> leitura mais precisa da tese, motor de match refinado e busca manual mantida como apoio, sem desviar do núcleo da plataforma.</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header('Configuração da análise')
    top_k = st.slider('Máximo de precedentes por tese', 1, 5, 3)
    max_blocks = st.slider('Blocos argumentativos analisados', 3, 12, 6)
    force_piece = st.selectbox('Foco da análise', ['Automático', 'Recurso administrativo', 'Contrarrazão', 'Impugnação'])
    st.caption('A prioridade do sistema é validar, corrigir e reforçar precedentes citados na peça. A busca manual entra como apoio complementar.')

c1, c2, c3, c4 = st.columns(4)
c1.metric('Precedentes totais', f"{summary['total_registros']:,}".replace(',', '.'))
c2.metric('Acórdãos', f"{summary['por_tipo']['acordao']:,}".replace(',', '.'))
c3.metric('Jurisprudências', f"{summary['por_tipo']['jurisprudencia']:,}".replace(',', '.'))
c4.metric('Súmulas', f"{summary['por_tipo']['sumula']:,}".replace(',', '.'))

main_tabs = st.tabs(['1. Upload e validação', '2. Resultado técnico', '3. Busca manual de precedentes', '4. Histórico'])

with main_tabs[0]:
    uploaded_file = st.file_uploader('Envie a peça para validação técnica', type=['pdf', 'docx', 'txt'])
    manual_text = st.text_area('Ou cole o texto da peça aqui', height=180)
    analyze = st.button('Validar peça agora', type='primary', use_container_width=True)

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
        if force_piece != 'Automático':
            piece_type['tipo'] = force_piece
        extraction = inspect_extraction(piece_text)
        structure = extract_piece_structure(piece_text)
        thesis_blocks = structure['blocos_argumentativos'][:max_blocks]
        citations = structure['citacoes']

        citation_results = [cached_validate(db_paths, cit, top_k) for cit in citations]
        thesis_results = []
        used_ids = set()
        for res in citation_results:
            for key in ['matched_record', 'correcao_sugerida']:
                rec = res.get(key) or {}
                ident = (rec.get('tipo'), rec.get('numero_identificador'))
                if all(ident):
                    used_ids.add(ident)
        for block in thesis_blocks:
            suggestions = cached_search(db_paths, block['texto'], block['tese_chave'], top_k)
            refined = []
            for sug in suggestions:
                ident = (sug.get('tipo'), sug.get('numero_identificador'))
                if ident in used_ids:
                    continue
                sug['paragrafo_aplicado'] = build_thesis_paragraph(sug, block['tese'])
                refined.append(sug)
                used_ids.add(ident)
                if len(refined) >= top_k:
                    break
            if refined:
                thesis_results.append({'tese': block['tese'], 'tese_chave': block['tese_chave'], 'trecho_curto': block['preview'], 'fundamentos': block.get('fundamentos', ''), 'sugestoes': refined, 'score_tese': block['score_tese']})

        corrected_text = build_revised_text(piece_text, {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results})
        analysis = {'piece_type': piece_type, 'piece_structure': structure, 'extraction': extraction, 'citation_results': citation_results, 'thesis_results': thesis_results, 'corrected_text': corrected_text}
        st.session_state.last_analysis = analysis
        st.session_state.last_file_name = file_name
        st.session_state.last_text = piece_text
        st.session_state.analysis_history.insert(0, {'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M'), 'arquivo': file_name, 'tipo': piece_type['tipo'], 'citacoes': len(citation_results), 'teses': len(thesis_results), 'qualidade': extraction['qualidade']})
        st.session_state.analysis_history = st.session_state.analysis_history[:15]

        st.success('Validação concluída. Veja a aba “Resultado técnico”.')
        d1, d2, d3, d4 = st.columns(4)
        d1.metric('Citações localizadas', len(citation_results))
        d2.metric('Citações validadas', sum(1 for x in citation_results if x['status'] == 'valida_compatível'))
        d3.metric('Citações com correção', sum(1 for x in citation_results if x.get('correcao_sugerida')))
        d4.metric('Teses com reforço', len(thesis_results))
        if extraction['alertas']:
            for alert in extraction['alertas']:
                st.warning(alert)
        st.markdown('### Prévia do conteúdo lido')
        st.text_area('Texto extraído', piece_text[:6000], height=280)

with main_tabs[1]:
    analysis = st.session_state.last_analysis
    if not analysis:
        st.info('Faça primeiro a análise da peça na aba anterior.')
    else:
        piece_type = analysis['piece_type']
        structure = analysis['piece_structure']
        extraction = analysis['extraction']
        citation_results = analysis['citation_results']
        thesis_results = analysis['thesis_results']
        corrected_text = analysis['corrected_text']

        r1, r2, r3, r4 = st.columns(4)
        r1.metric('Tipo da peça', piece_type['tipo'])
        r2.metric('Tese principal', structure.get('tese_principal', '-'))
        r3.metric('Validadas', sum(1 for x in citation_results if x['status'] == 'valida_compatível'))
        r4.metric('Para revisar', sum(1 for x in citation_results if x['status'] != 'valida_compatível'))

        st.markdown('### Diagnóstico técnico')
        st.markdown(f"- **Qualidade da leitura:** {extraction['qualidade']}  ")
        st.markdown(f"- **Tese principal detectada:** {structure.get('tese_principal', '-')}  ")
        st.markdown(f"- **Resumo objetivo:** {structure.get('resumo_inicial', '-')}")

        st.markdown('### Validação e correção de citações')
        if not citation_results:
            st.info('Nenhuma citação explícita de acórdão ou súmula foi localizada na peça.')
        for item in citation_results:
            st.markdown(f"<div class='result-card'><strong>{item.get('raw')}</strong><br><span class='small'>Status: {item.get('status_label')} · tese relacionada: {item.get('tese')} · risco: {item.get('risco')}</span><br><span class='small'>Contexto: {item.get('contexto')}</span></div>", unsafe_allow_html=True)
            if item.get('matched_record'):
                st.caption(f"Base localizada: {item['matched_record'].get('citacao_curta')}")
            if item.get('correcao_sugerida'):
                st.caption(f"Correção sugerida: {item['correcao_sugerida'].get('citacao_curta')}")

        st.markdown('### Reforços sugeridos por tese')
        for block in thesis_results:
            st.markdown(f"#### {block['tese']}")
            st.caption(block['trecho_curto'])
            for sug in block['sugestoes']:
                st.markdown(f"<div class='result-card'><strong>{sug.get('citacao_curta')}</strong><br><span class='small'>Aderência: {round(float(sug.get('compat_score',0))*100)}% · tipo: {sug.get('tipo')}</span><br><span class='small'>{sug.get('paragrafo_aplicado')}</span></div>", unsafe_allow_html=True)

        export_rows = build_export_rows(analysis)
        report_md = build_markdown_report(st.session_state.last_file_name or 'arquivo', analysis)
        export_title = f"Peça revisada - {st.session_state.last_file_name or 'arquivo'}"
        docx_bytes = build_docx_bytes(corrected_text, export_title, analysis)
        pdf_bytes = build_pdf_bytes(corrected_text, export_title, analysis)
        csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')

        st.markdown('### Downloads')
        cdl1, cdl2, cdl3, cdl4 = st.columns(4)
        cdl1.download_button('Baixar peça revisada (.docx)', data=docx_bytes, file_name='peca_revisada.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        cdl2.download_button('Baixar peça revisada (.pdf)', data=pdf_bytes, file_name='peca_revisada.pdf', mime='application/pdf', use_container_width=True)
        cdl3.download_button('Baixar relatório (.md)', data=report_md.encode('utf-8'), file_name='relatorio_precedentes.md', mime='text/markdown', use_container_width=True)
        cdl4.download_button('Baixar auditoria (.csv)', data=csv_bytes, file_name='auditoria_precedentes.csv', mime='text/csv', use_container_width=True)

with main_tabs[2]:
    st.markdown('### Busca manual de precedentes')
    q = st.text_input('Pesquise por tese, tema ou referência direta', placeholder='Ex.: falha sanável sem diligência | TCU Acórdão 2622/2013 | Súmula 222')
    tipo = st.selectbox('Filtrar tipo', ['todos', 'acordao', 'jurisprudencia', 'sumula'])
    if st.button('Pesquisar precedentes', use_container_width=True):
        if not q.strip():
            st.warning('Digite uma tese, tema ou referência.')
        else:
            thesis_key = 'geral'
            if st.session_state.last_analysis and st.session_state.last_analysis.get('piece_structure', {}).get('blocos_argumentativos'):
                thesis_key = st.session_state.last_analysis['piece_structure']['blocos_argumentativos'][0].get('tese_chave', 'geral')
            results = cached_search(db_paths, q, thesis_key, top_k=max(top_k, 5), tipo=None if tipo == 'todos' else tipo)
            if not results:
                st.info('Nenhum precedente aderente foi localizado.')
            for res in results:
                st.markdown(f"<div class='result-card'><strong>{res.get('citacao_curta')}</strong><br><span class='small'>Tipo: {res.get('tipo')} · aderência: {round(float(res.get('compat_score',0))*100)}% · colegiado: {res.get('colegiado')}</span><br><span class='small'>Assunto: {res.get('assunto')}</span></div>", unsafe_allow_html=True)
                st.code(build_thesis_paragraph(res, 'tese pesquisada'), language='text')

with main_tabs[3]:
    if not st.session_state.analysis_history:
        st.info('Ainda não há histórico de análise nesta sessão.')
    else:
        st.dataframe(pd.DataFrame(st.session_state.analysis_history), use_container_width=True, hide_index=True)
