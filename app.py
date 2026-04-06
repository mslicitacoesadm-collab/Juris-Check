from __future__ import annotations

from datetime import datetime
from difflib import HtmlDiff
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, extract_citations_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows, build_markdown_report
from modules.search_engine import build_thesis_paragraph, suggest_mixed_precedents, validate_citation

st.set_page_config(page_title='Atlas de Acórdãos MS V7', page_icon='⚖️', layout='wide')

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
    from pathlib import Path
    return validate_citation([Path(p) for p in db_paths], citation, top_k=top_k)


@st.cache_data(show_spinner=False)
def cached_suggest(db_paths: tuple[str, ...], query_text: str, thesis_key: str, colegiado_hint: str | None, total_limit: int):
    from pathlib import Path
    return suggest_mixed_precedents([Path(p) for p in db_paths], query_text, thesis_key=thesis_key, colegiado_hint=colegiado_hint, total_limit=total_limit)



def badge_html(label: str, tone: str) -> str:
    colors = {
        'good': ('#dcfce7', '#166534'),
        'warn': ('#fef3c7', '#92400e'),
        'bad': ('#fee2e2', '#991b1b'),
        'info': ('#dbeafe', '#1d4ed8'),
    }
    bg, fg = colors[tone]
    return f"<span style='display:inline-block;padding:.2rem .55rem;border-radius:999px;background:{bg};color:{fg};font-size:.8rem;font-weight:700'>{label}</span>"



def risk_style(risk: str) -> tuple[str, str, str]:
    if risk == 'baixo':
        return ('Baixo risco', '#166534', '#dcfce7')
    if risk == 'médio':
        return ('Risco moderado', '#92400e', '#fef3c7')
    return ('Alto risco', '#991b1b', '#fee2e2')



def thesis_quality_label(score: float) -> str:
    if score >= 0.46:
        return 'Aderência forte'
    if score >= 0.30:
        return 'Aderência boa'
    return 'Aderência moderada'



def diff_html(original: str, revised: str) -> str:
    hd = HtmlDiff(wrapcolumn=110)
    return hd.make_table(original.splitlines(), revised.splitlines(), 'Original', 'Corrigida', context=True, numlines=1)



def precedent_type_label(ptype: str) -> str:
    return {'acordao': 'Acórdão', 'jurisprudencia': 'Jurisprudência', 'sumula': 'Súmula'}.get(ptype, ptype.title())


if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))

st.markdown(
    """
    <style>
    .hero{padding:1.25rem 1.3rem;border-radius:28px;background:linear-gradient(135deg,#071527 0%,#12345d 55%,#175b9a 100%);color:white;border:1px solid rgba(255,255,255,.12);margin-bottom:1rem}
    .hero h1{margin:0 0 .35rem 0;font-size:2rem}
    .hero p{margin:.15rem 0;line-height:1.5;opacity:.96}
    .metric-card,.soft-card{padding:1rem 1.05rem;border:1px solid rgba(120,120,120,.16);border-radius:20px;background:rgba(255,255,255,.03);height:100%}
    .soft-card h3{margin:.05rem 0 .4rem 0;font-size:1rem}
    .premium-box{padding:.9rem 1rem;border-radius:18px;background:#f8fafc;border:1px solid #e2e8f0}
    .small{font-size:.92rem;color:#475569;line-height:1.45}
    .scorebar{height:10px;border-radius:999px;background:#e5e7eb;overflow:hidden}
    .scorefill{height:10px;border-radius:999px;background:linear-gradient(90deg,#0ea5e9,#22c55e)}
    .compare-box .diff_header{background:#0f172a;color:white}.compare-box td{font-size:.84rem}.compare-box .diff_add{background:#dcfce7}.compare-box .diff_sub{background:#fee2e2}
    @media (max-width: 768px){.hero h1{font-size:1.55rem}}
    </style>
    """,
    unsafe_allow_html=True,
)

logo_col, hero_col = st.columns([1, 4])
with logo_col:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with hero_col:
    st.markdown(
        """
        <div class='hero'>
            <h1>Atlas de Acórdãos MS · V7 Premium</h1>
            <p><strong>Auditoria, correção e reforço argumentativo</strong> agora com acórdão, jurisprudência e súmula.</p>
            <p>Esta versão valida o número citado, verifica o encaixe da tese no contexto e ainda sugere, quando for melhor para a peça, a inclusão de jurisprudência selecionada, súmula aplicável ou ambos.</p>
            <p><strong>O que ele entrega:</strong> revisão de citação, match por tese, complemento argumentativo multimodal e peça revisada para download.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.header('Painel premium')
    top_k = st.slider('Máximo por citação/tese', 1, 3, 3)
    max_blocks = st.slider('Teses máximas analisadas', 4, 12, 8)
    st.caption('A V7 cruza a peça com a base de acórdãos, jurisprudência e súmulas, sugerindo o melhor encaixe para a tese.')

m1, m2, m3, m4 = st.columns(4)
por_tipo = summary.get('por_tipo', {})
m1.metric('Precedentes ativos', f"{summary['total_registros']:,}".replace(',', '.'))
m2.metric('Acórdãos', f"{por_tipo.get('acordao', 0):,}".replace(',', '.'))
m3.metric('Jurisprudências', f"{por_tipo.get('jurisprudencia', 0):,}".replace(',', '.'))
m4.metric('Súmulas', f"{por_tipo.get('sumula', 0):,}".replace(',', '.'))

st.markdown(
    "<div class='soft-card'><h3>Leitura estratégica da base</h3><div class='small'>O sistema não fica preso ao acórdão. Se a tese ganhar mais força com jurisprudência selecionada ou súmula consolidada, a sugestão sai no formato mais útil para a peça.</div></div>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader('Envie a peça para análise', type=['pdf', 'docx', 'txt'])
manual_text = st.text_area('Ou cole o texto da peça aqui', height=170)
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

    with st.spinner('Auditando a peça premium...'):
        citation_results = [cached_validate(db_paths, cit, top_k) for cit in citations]
        thesis_results = []
        used_keys = set()
        for r in citation_results:
            for cand in [r.get('correcao_sugerida'), r.get('matched_record')]:
                if cand:
                    used_keys.add((cand.get('tipo_precedente'), cand.get('numero_acordao') or cand.get('numero_sumula')))

        for block in thesis_blocks:
            suggestions = cached_suggest(db_paths, block['texto'], block['tese_chave'], None, top_k)
            filtered = []
            for sug in suggestions:
                key = (sug.get('tipo_precedente'), sug.get('numero_acordao') or sug.get('numero_sumula'))
                if key in used_keys:
                    continue
                sug['paragrafo_aplicado'] = build_thesis_paragraph(sug, block['tese'])
                used_keys.add(key)
                filtered.append(sug)
            if filtered:
                best_score = max(float(sug.get('compat_score', 0.0)) for sug in filtered)
                thesis_results.append({
                    'tese': block['tese'],
                    'tese_chave': block['tese_chave'],
                    'trecho_curto': block['preview'],
                    'fundamentos': block.get('fundamentos', ''),
                    'sugestoes': filtered[:top_k],
                    'score_tese': round(best_score, 4),
                })
            if len(thesis_results) >= 3:
                break

    validas = sum(1 for x in citation_results if x['status'] == 'valida_compatível')
    revisao = sum(1 for x in citation_results if x['status'] in {'valida_pouco_compativel', 'divergente', 'nao_localizada'})
    corrected_text = build_revised_text(piece_text, {'piece_type': piece_type, 'citation_results': citation_results, 'thesis_results': thesis_results})
    analysis = {
        'piece_type': piece_type,
        'citation_results': citation_results,
        'thesis_results': thesis_results,
    }

    st.session_state.analysis_history.insert(0, {
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'arquivo': file_name,
        'tipo': piece_type['tipo'],
        'validas': validas,
        'revisao': revisao,
        'teses': len(thesis_results),
    })
    st.session_state.analysis_history = st.session_state.analysis_history[:10]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Tipo da peça', piece_type['tipo'])
    c2.metric('Citações compatíveis', validas)
    c3.metric('Citações para revisão', revisao)
    c4.metric('Teses prontas para uso', len(thesis_results))

    tabs = st.tabs(['Resumo premium', 'Citações auditadas', 'Teses aplicadas', 'Comparação', 'Histórico', 'Downloads'])

    with tabs[0]:
        st.markdown("### Leitura executiva")
        st.markdown(
            f"<div class='premium-box'><div class='small'><strong>Tipo identificado:</strong> {piece_type['tipo']} · confiança <strong>{piece_type['confianca']}</strong>.<br>"
            f"<strong>Base da identificação:</strong> {piece_type['fundamentos']}.<br>"
            f"<strong>Diagnóstico:</strong> {validas} citações ficaram compatíveis; {revisao} exigem revisão; {len(thesis_results)} teses foram convertidas em reforços prontos para uso, com possibilidade de acórdão, jurisprudência e/ou súmula.</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("### Radar de risco")
        if citation_results:
            low = sum(1 for x in citation_results if x.get('risco') == 'baixo')
            med = sum(1 for x in citation_results if x.get('risco') == 'médio')
            high = sum(1 for x in citation_results if x.get('risco') == 'alto')
            a, b, c = st.columns(3)
            a.metric('Baixo risco', low)
            b.metric('Risco moderado', med)
            c.metric('Alto risco', high)
        else:
            st.info('Nenhuma citação automática foi encontrada para compor o radar de risco.')

    with tabs[1]:
        if not citation_results:
            st.info('Nenhuma citação de acórdão ou súmula foi localizada automaticamente.')
        else:
            for item in citation_results:
                title, color, bg = risk_style(item.get('risco', 'alto'))
                tone = 'good' if item['status'] == 'valida_compatível' else 'warn' if item['status'] == 'valida_pouco_compativel' else 'bad'
                with st.container(border=True):
                    st.markdown(badge_html(item['status_label'], tone), unsafe_allow_html=True)
                    st.markdown(f"&nbsp;{badge_html(title, 'info' if item.get('risco') == 'baixo' else 'warn' if item.get('risco') == 'médio' else 'bad')}", unsafe_allow_html=True)
                    st.markdown(f"**Tipo:** {precedent_type_label(item.get('tipo_citacao', 'acordao'))}")
                    st.markdown(f"**Citação localizada na peça:** {item['raw']}")
                    st.caption(f"Linha aproximada: {item.get('linha','-')} · Tese percebida: {item.get('tese','Tese geral')} · Score de contexto: {item.get('score_contexto',0):.2f}")
                    if item.get('matched_record'):
                        rec = item['matched_record']
                        st.write(f"**Correspondência encontrada:** {rec.get('citacao_curta','')}")
                    if item.get('correcao_sugerida'):
                        cor = item['correcao_sugerida']
                        st.write(f"**Correção sugerida:** {cor.get('citacao_curta','')}")
                        st.code(item.get('substituicao_textual',''), language='text')
                    if item.get('alternativas'):
                        st.write('**Alternativas úteis:**')
                        for alt in item['alternativas'][:top_k]:
                            st.write(f"- {alt.get('citacao_curta','')}")

    with tabs[2]:
        if not thesis_results:
            st.info('Nenhuma tese com aderência suficiente foi convertida em reforço útil.')
        else:
            for thesis in thesis_results:
                score_pct = min(100, int(float(thesis.get('score_tese', 0.0)) * 180))
                with st.container(border=True):
                    st.markdown(f"### {thesis['tese']}")
                    st.markdown(f"<div class='small'><strong>Trecho lido:</strong> {thesis['trecho_curto']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='small'><strong>Sinais da tese:</strong> {thesis.get('fundamentos','-')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='small'><strong>Qualidade do match:</strong> {thesis_quality_label(float(thesis.get('score_tese',0.0)))} </div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='scorebar'><div class='scorefill' style='width:{score_pct}%'></div></div>", unsafe_allow_html=True)
                    for sug in thesis['sugestoes'][:top_k]:
                        st.write(f"**{precedent_type_label(sug.get('tipo_precedente','acordao'))} sugerido:** {sug.get('citacao_curta','')}")
                        st.code(sug.get('paragrafo_aplicado',''), language='text')

    with tabs[3]:
        st.markdown("### Comparação entre a peça original e a versão corrigida")
        st.markdown("<div class='small'>Trechos em verde representam acréscimos ou substituições úteis. Trechos em vermelho representam conteúdo substituído na versão revisada.</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='compare-box'>{diff_html(piece_text, corrected_text)}</div>", unsafe_allow_html=True)

    with tabs[4]:
        st.markdown('### Histórico da sessão')
        if st.session_state.analysis_history:
            st.dataframe(pd.DataFrame(st.session_state.analysis_history), use_container_width=True, hide_index=True)
        else:
            st.info('Ainda não há histórico de análises nesta sessão.')

    with tabs[5]:
        rows = build_export_rows(analysis)
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig') if rows else b''
        md_report = build_markdown_report(file_name, analysis).encode('utf-8')
        docx_bytes = build_docx_bytes(corrected_text, analysis, title='Peça revisada premium')
        pdf_bytes = build_pdf_bytes(corrected_text, analysis, title='Peça revisada premium')

        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.download_button('Baixar peça corrigida (.docx)', data=docx_bytes, file_name='peca_corrigida_premium.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
        with d2:
            st.download_button('Baixar peça corrigida (.pdf)', data=pdf_bytes, file_name='peca_corrigida_premium.pdf', mime='application/pdf', use_container_width=True)
        with d3:
            st.download_button('Baixar relatório (.md)', data=md_report, file_name='relatorio_premium.md', mime='text/markdown', use_container_width=True)
        with d4:
            st.download_button('Baixar planilha (.csv)', data=csv_bytes, file_name='relatorio_premium.csv', mime='text/csv', use_container_width=True)

        st.text_area('Prévia da peça corrigida', corrected_text[:5000], height=260)
