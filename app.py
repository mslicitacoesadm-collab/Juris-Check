from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_piece_structure
from modules.document_builder import build_docx_bytes, build_pdf_bytes, build_revised_versions
from modules.piece_reader import inspect_extraction, read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import build_thesis_paragraph, search_candidates, validate_citation

st.set_page_config(page_title='Atlas de Precedentes MS V12', page_icon='⚖️', layout='wide')

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


def _status_meta(item: dict) -> tuple[str, str, str]:
    status = item.get('status')
    if status == 'valida_compatível':
        return 'status-ok', 'Validada', 'Citação localizada na base e coerente com a tese identificada.'
    if item.get('correcao_sugerida'):
        return 'status-med', 'Corrigir', 'A base sugere precedente mais aderente ou correção do número citado.'
    return 'status-bad', 'Revisar', 'A citação não foi localizada com segurança ou o contexto está fraco.'


def _quality_meta(extraction: dict) -> tuple[str, str]:
    q = (extraction or {}).get('qualidade', '').lower()
    if 'alta' in q:
        return 'status-ok', 'Extração forte'
    if 'média' in q or 'media' in q:
        return 'status-med', 'Extração intermediária'
    return 'status-bad', 'Extração sensível'


for key, default in {
    'analysis_history': [],
    'last_analysis': None,
    'last_file_name': None,
    'last_text': '',
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown("""
<style>
:root {
  --bg-0:#f4f7fb;
  --bg-1:#ffffff;
  --text:#0f172a;
  --muted:#475569;
  --line:#dbe3ee;
  --brand:#0f3d73;
  --brand-2:#155e95;
  --brand-soft:#e9f2ff;
  --ok:#166534;
  --ok-bg:#ecfdf3;
  --med:#9a6700;
  --med-bg:#fff8e6;
  --bad:#b42318;
  --bad-bg:#fff1f0;
}
html, body, [class*="css"] { color:var(--text); }
.stApp { background:linear-gradient(180deg, #f7f9fc 0%, #eef4fb 100%); }
.block-container { padding-top:1.2rem; }
.hero{padding:1.35rem 1.4rem;border-radius:26px;background:linear-gradient(135deg,var(--brand) 0%, #0c2f58 48%, var(--brand-2) 100%);color:white;margin-bottom:1rem;box-shadow:0 12px 28px rgba(15,61,115,.18)}
.hero p{margin:.35rem 0 0 0;line-height:1.5}
.panel{padding:1rem 1rem;border:1px solid var(--line);border-radius:20px;background:var(--bg-1);box-shadow:0 6px 18px rgba(15,23,42,.05);margin-bottom:.85rem}
.section-title{font-size:1.06rem;font-weight:700;margin:0 0 .55rem 0;color:var(--brand)}
.soft{font-size:.95rem;color:var(--muted);line-height:1.5}
.kicker{display:inline-block;padding:.34rem .65rem;border-radius:999px;background:var(--brand-soft);color:var(--brand);font-size:.82rem;font-weight:700;margin-bottom:.55rem}
.legend{display:flex;gap:.55rem;flex-wrap:wrap;margin:.15rem 0 .2rem 0}
.badge{display:inline-flex;align-items:center;gap:.4rem;padding:.38rem .72rem;border-radius:999px;border:1px solid var(--line);font-size:.84rem;font-weight:700;background:#fff}
.status-ok{color:var(--ok);background:var(--ok-bg);border-color:#b7ebc6}
.status-med{color:var(--med);background:var(--med-bg);border-color:#f0d48a}
.status-bad{color:var(--bad);background:var(--bad-bg);border-color:#f4b5ae}
.audit-card{padding:1rem;border:1px solid var(--line);border-left:6px solid var(--brand);border-radius:18px;background:var(--bg-1);margin:.85rem 0}
.audit-card.status-ok{border-left-color:var(--ok)}
.audit-card.status-med{border-left-color:var(--med)}
.audit-card.status-bad{border-left-color:var(--bad)}
.audit-head{display:flex;justify-content:space-between;gap:.8rem;align-items:flex-start;flex-wrap:wrap}
.audit-title{font-weight:800;font-size:1rem}
.audit-meta{font-size:.92rem;color:var(--muted);margin-top:.3rem;line-height:1.45}
.mini{font-size:.84rem;color:var(--muted)}
textarea, input, .stTextArea textarea, .stTextInput input { border-radius:14px !important; }
[data-baseweb="tab-list"] { gap:.4rem; }
[data-baseweb="tab"] { background:#eef4fb; border-radius:14px 14px 0 0; padding:.65rem 1rem; }
[data-baseweb="tab-highlight"] { background:var(--brand); }
div[data-testid="metric-container"] { background:var(--bg-1); border:1px solid var(--line); padding:1rem; border-radius:18px; box-shadow:0 4px 12px rgba(15,23,42,.04); }
.stDownloadButton button, .stButton button { border-radius:14px !important; font-weight:700 !important; }
</style>
""", unsafe_allow_html=True)

left, right = st.columns([1, 4])
with left:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with right:
    st.markdown("""
    <div class='hero'>
        <div class='kicker'>Auditoria inteligente de precedentes</div>
        <h1 style='margin:0 0 .3rem 0'>Atlas de Precedentes MS</h1>
        <p>Ferramenta voltada ao núcleo do produto: <strong>validar citações geradas por IA</strong>, localizar o precedente correto na base e <strong>corrigir automaticamente</strong> acórdão, jurisprudência e súmula com saída pronta para uso.</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Configuração da auditoria</div>", unsafe_allow_html=True)
    top_k = st.slider('Sugestões por tese', 1, 5, 3)
    max_blocks = st.slider('Blocos argumentativos prioritários', 3, 10, 5)
    force_piece = st.selectbox('Tipo da peça', ['Automático', 'Recurso administrativo', 'Contrarrazão', 'Impugnação'])
    st.caption('A busca manual fica como apoio. O foco principal permanece na conferência e correção de citações usadas na peça.')
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='panel'><div class='section-title'>Legenda visual</div><div class='legend'><span class='badge status-ok'>● Validada</span><span class='badge status-med'>● Corrigir</span><span class='badge status-bad'>● Revisar</span></div><div class='mini'>Cores com alto contraste e leitura simplificada para análise rápida.</div></div>", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric('Total na base', f"{summary['total_registros']:,}".replace(',', '.'))
m2.metric('Acórdãos', f"{summary['por_tipo']['acordao']:,}".replace(',', '.'))
m3.metric('Jurisprudências', f"{summary['por_tipo']['jurisprudencia']:,}".replace(',', '.'))
m4.metric('Súmulas', f"{summary['por_tipo']['sumula']:,}".replace(',', '.'))

st.markdown("<div class='panel'><div class='section-title'>Leitura do sistema</div><div class='legend'><span class='badge'>1. Upload da peça</span><span class='badge'>2. Auditoria das citações</span><span class='badge'>3. Correção automática</span><span class='badge'>4. Reforço por tese</span><span class='badge'>5. Busca manual complementar</span></div></div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(['1. Upload e auditoria', '2. Resultado e correção', '3. Busca manual'])

with tab1:
    st.markdown("<div class='panel'><div class='section-title'>Entrada principal</div><div class='soft'>Envie a peça ou cole o texto. O sistema identifica citações, confere com a base e prepara a versão revisada com foco no uso prático.</div></div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader('Envie a peça', type=['pdf', 'docx', 'txt'])
    manual_text = st.text_area('Ou cole o texto da peça', height=180)
    analyze = st.button('Auditar precedentes da peça', type='primary', use_container_width=True)

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

        versions = build_revised_versions(piece_text, {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results})
        analysis = {
            'piece_type': piece_type,
            'piece_structure': structure,
            'extraction': extraction,
            'citation_results': citation_results,
            'thesis_results': thesis_results,
            'corrected_text': versions['clean_text'],
            'marked_text': versions['marked_text'],
            'replacement_log': versions['replacement_log'],
        }
        st.session_state.last_analysis = analysis
        st.session_state.last_file_name = file_name
        st.session_state.last_text = piece_text
        st.session_state.analysis_history.insert(0, {
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'arquivo': file_name,
            'tipo': piece_type['tipo'],
            'citacoes': len(citation_results),
            'corrigidas': len(versions['replacement_log']),
            'qualidade': extraction['qualidade'],
        })
        st.session_state.analysis_history = st.session_state.analysis_history[:15]

        q_class, q_label = _quality_meta(extraction)
        st.success('Auditoria concluída. A versão revisada já está pronta na aba “Resultado e correção”.')
        a1, a2, a3, a4 = st.columns(4)
        a1.metric('Citações detectadas', len(citation_results))
        a2.metric('Validadas', sum(1 for x in citation_results if x['status'] == 'valida_compatível'))
        a3.metric('Com correção', len(versions['replacement_log']))
        a4.metric('Teses reforçadas', len(thesis_results))
        st.markdown(f"<div class='legend'><span class='badge {q_class}'>● {q_label}</span><span class='badge'>Tipo identificado: {piece_type['tipo']}</span><span class='badge'>Tese principal: {structure.get('tese_principal','-')}</span></div>", unsafe_allow_html=True)
        if extraction['alertas']:
            for alert in extraction['alertas']:
                st.warning(alert)
        st.text_area('Prévia do texto lido', piece_text[:6000], height=260)

with tab2:
    analysis = st.session_state.last_analysis
    if not analysis:
        st.info('Faça primeiro a auditoria da peça.')
    else:
        citation_results = analysis['citation_results']
        replacement_log = analysis.get('replacement_log', [])
        thesis_results = analysis['thesis_results']

        s1, s2, s3, s4 = st.columns(4)
        s1.metric('Tipo da peça', analysis['piece_type']['tipo'])
        s2.metric('Tese principal', analysis['piece_structure'].get('tese_principal', '-'))
        s3.metric('Validadas', sum(1 for x in citation_results if x['status'] == 'valida_compatível'))
        s4.metric('Corrigidas', len(replacement_log))

        st.markdown("<div class='panel'><div class='section-title'>Legenda da auditoria</div><div class='legend'><span class='badge status-ok'>● Validada</span><span class='badge status-med'>● Corrigir</span><span class='badge status-bad'>● Revisar</span></div><div class='mini'>A legenda também aparece em cada cartão para facilitar leitura com acessibilidade e contraste.</div></div>", unsafe_allow_html=True)
        st.markdown('### Auditoria principal')
        if not citation_results:
            st.info('Nenhuma referência explícita foi localizada na peça.')
        for item in citation_results:
            css, label, explain = _status_meta(item)
            matched = item.get('matched_record', {}) or {}
            corrected = item.get('correcao_sugerida', {}) or {}
            reason_parts = [f"Status: {item.get('status_label')}", f"Tese: {item.get('tese')}", f"Risco: {item.get('risco')}"]
            if item.get('score_contexto'):
                reason_parts.append(f"Aderência: {round(float(item.get('score_contexto', 0))*100)}%")
            st.markdown(
                f"<div class='audit-card {css}'>"
                f"<div class='audit-head'><div><div class='audit-title'>{item.get('raw')}</div>"
                f"<div class='audit-meta'>{' · '.join(reason_parts)}</div></div>"
                f"<span class='badge {css}'>{label}</span></div>"
                f"<div class='audit-meta'><strong>Contexto:</strong> {item.get('contexto')}</div>"
                f"<div class='audit-meta'><strong>Leitura do sistema:</strong> {explain}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if matched:
                st.caption(f"Validado na base: {matched.get('citacao_curta')}")
            if corrected:
                st.caption(f"Correção aplicada: {corrected.get('citacao_curta')}")
            if item.get('redacao_sugerida'):
                st.code(item['redacao_sugerida'], language='text')

        st.markdown('### Substituições automáticas aplicadas')
        if not replacement_log:
            st.info('Nenhuma troca textual foi necessária.')
        else:
            for rep in replacement_log:
                css = 'status-med' if rep.get('modo') == 'substituicao_simples' else 'status-ok'
                mode = 'Troca direta' if rep.get('modo') == 'substituicao_simples' else 'Reescrita contextual'
                st.markdown(f"<div class='audit-card {css}'><div class='audit-title'>{mode}</div><div class='audit-meta'><strong>Original:</strong> {rep['original']}</div><div class='audit-meta'><strong>Aplicado:</strong> {rep['substituicao']}</div></div>", unsafe_allow_html=True)

        if thesis_results:
            st.markdown('### Reforços úteis para a tese')
            for block in thesis_results:
                with st.expander(block['tese']):
                    st.caption(block['trecho_curto'])
                    for sug in block['sugestoes']:
                        st.markdown(f"**{sug.get('citacao_curta')}**")
                        st.caption(sug.get('paragrafo_aplicado'))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown('### Texto revisado com marcação')
            st.text_area('Peça com correções destacadas', analysis['marked_text'], height=340)
        with col_b:
            st.markdown('### Texto revisado limpo')
            st.text_area('Peça pronta', analysis['corrected_text'], height=340)

        export_rows = build_export_rows(analysis)
        report_md = build_markdown_report(st.session_state.last_file_name or 'arquivo', analysis)
        export_title = f"Peça revisada - {st.session_state.last_file_name or 'arquivo'}"
        docx_marked = build_docx_bytes(analysis['marked_text'], export_title + ' (marcada)', analysis, marked=True)
        docx_clean = build_docx_bytes(analysis['corrected_text'], export_title, analysis, marked=False)
        pdf_clean = build_pdf_bytes(analysis['corrected_text'], export_title, analysis)
        csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')

        st.markdown("<div class='panel'><div class='section-title'>Exportação</div><div class='soft'>Baixe a peça revisada, com ou sem marcação, além da trilha de auditoria para conferência técnica.</div></div>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button('DOCX com marcação', data=docx_marked, file_name='peca_revisada_marcada.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d2.download_button('DOCX limpo', data=docx_clean, file_name='peca_revisada_limpa.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        d3.download_button('PDF limpo', data=pdf_clean, file_name='peca_revisada.pdf', mime='application/pdf', use_container_width=True)
        d4.download_button('Auditoria CSV', data=csv_bytes, file_name='auditoria_precedentes.csv', mime='text/csv', use_container_width=True)
        st.download_button('Relatório técnico (.md)', data=report_md.encode('utf-8'), file_name='relatorio_precedentes.md', mime='text/markdown', use_container_width=True)

with tab3:
    st.markdown("<div class='panel'><div class='section-title'>Busca manual complementar</div><div class='soft'>Use esta aba quando já tiver uma tese ou um número em mente. Ela não substitui a auditoria da peça: serve como apoio para reforço e conferência fina.</div></div>", unsafe_allow_html=True)
    q = st.text_input('Pesquise por tese ou referência direta', placeholder='Ex.: falha sanável sem diligência | Acórdão 2622/2013 | Súmula 222 | Jurisprudência 145/2024')
    tipo = st.selectbox('Tipo', ['todos', 'acordao', 'jurisprudencia', 'sumula'])
    if st.button('Pesquisar', use_container_width=True):
        if not q.strip():
            st.warning('Digite uma tese ou referência.')
        else:
            thesis_key = 'geral'
            if st.session_state.last_analysis and st.session_state.last_analysis.get('piece_structure', {}).get('blocos_argumentativos'):
                thesis_key = st.session_state.last_analysis['piece_structure']['blocos_argumentativos'][0].get('tese_chave', 'geral')
            results = cached_search(db_paths, q, thesis_key, top_k=max(top_k, 5), tipo=None if tipo == 'todos' else tipo)
            if not results:
                st.info('Nenhum precedente aderente foi localizado.')
            for res in results:
                css = 'status-ok' if float(res.get('compat_score', 0)) >= 0.5 else 'status-med' if float(res.get('compat_score', 0)) >= 0.3 else 'status-bad'
                st.markdown(
                    f"<div class='audit-card {css}'><div class='audit-head'><div><div class='audit-title'>{res.get('citacao_curta')}</div>"
                    f"<div class='audit-meta'>Tipo: {res.get('tipo')} · aderência: {round(float(res.get('compat_score',0))*100)}% · colegiado: {res.get('colegiado')}</div></div>"
                    f"<span class='badge {css}'>{res.get('risco').capitalize()}</span></div>"
                    f"<div class='audit-meta'><strong>Assunto:</strong> {res.get('assunto')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.code(build_thesis_paragraph(res, 'tese pesquisada'), language='text')
