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


st.title('⚖️ Validador de Autoridade Jurídica')
st.caption('Arquitetura otimizada para Streamlit Cloud com bancos SQLite por ano e busca FTS5 sem carregar toda a base na memória.')

with st.sidebar:
    st.header('Configurações')
    top_k = st.slider('Sugestões por bloco', 1, 5, 3)
    max_blocks = st.slider('Máximo de blocos analisados', 5, 60, 20)
    st.info(
        'A forma correta de publicar no GitHub + Streamlit é usar bancos `acordaos_YYYY.db` dentro de `data/base/`. '
        'Evite subir dezenas de JSONs para o app carregar na memória.'
    )

summary = cached_summary(str(DB_DIR))
db_files = find_db_files(DB_DIR)

c1, c2, c3 = st.columns(3)
c1.metric('Bases SQLite', summary['total_bases'])
c2.metric('Registros disponíveis', summary['total_registros'])
c3.metric('Anos encontrados', ', '.join(summary['anos']) if summary['anos'] else 'Nenhum')

with st.expander('Bases detectadas'):
    if summary['detalhes']:
        st.dataframe(pd.DataFrame(summary['detalhes']), use_container_width=True)
    else:
        st.info('Nenhum banco SQLite encontrado ainda em `data/base/`.')

with st.expander('Abordagem recomendada para a base'):
    st.markdown(
        '- **Não** subir vários JSONs para leitura direta no app.\n'
        '- Gerar **um banco SQLite por ano** (`acordaos_2016.db`, `acordaos_2017.db`...).\n'
        '- O app faz consulta sob demanda, sem carregar a base inteira em RAM.\n'
        '- Isso resolve melhor o problema de peso, muitos arquivos e tempo de boot no Streamlit Cloud.'
    )

uploaded_file = st.file_uploader('Envie a peça para análise', type=['pdf', 'docx', 'txt'])
manual_text = st.text_area('Ou cole o texto da peça aqui', height=220)
analyze = st.button('Analisar peça', type='primary', use_container_width=True)

if analyze:
    if not db_files:
        st.error('Nenhuma base SQLite foi encontrada em `data/base/`. Gere os arquivos `.db` antes de publicar.')
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
    with st.spinner('Consultando a base...'):
        for cit in citations:
            exact = exact_lookup(db_files, cit.get('numero_acordao_num', ''), cit.get('ano_acordao') or None)
            if exact:
                validas += 1
                citation_results.append({
                    'raw': cit['raw'],
                    'status': 'valida',
                    'status_label': 'Válida',
                    'matched_record': exact,
                    'suggestions': [],
                })
            else:
                divergentes += 1
                suggestions = search_candidates(db_files, cit['raw'], top_k=top_k)
                citation_results.append({
                    'raw': cit['raw'],
                    'status': 'divergente',
                    'status_label': 'Divergente ou não localizada',
                    'matched_record': None,
                    'suggestions': suggestions,
                })

        block_results = []
        for idx, block in enumerate(blocks, start=1):
            suggestions = search_candidates(db_files, block, top_k=top_k)
            if suggestions:
                block_results.append({'block_index': idx, 'block_text': block, 'suggestions': suggestions})

    summary_md = '\n'.join([
        '### Resumo executivo',
        f'- Foram detectadas **{len(citations)}** citações automáticas.',
        f'- **{validas}** bateram exatamente com a base.',
        f'- **{divergentes}** ficaram como divergentes ou não localizadas.',
        f'- **{len(block_results)}** blocos tiveram sugestão de reforço jurisprudencial.',
        '',
        '**Leitura prática:**',
        '- Válida = número encontrado literalmente na base.',
        '- Divergente = número não localizado ou referência fraca.',
        '- Sugestão por bloco = reforço encontrado via busca textual indexada no SQLite.',
    ])

    analysis = {
        'citation_results': citation_results,
        'block_results': block_results,
        'summary_markdown': summary_md,
        'stats': {
            'citacoes_detectadas': len(citations),
            'citacoes_validas': validas,
            'citacoes_divergentes': divergentes,
            'blocos_com_sugestao': len(block_results),
        },
    }

    st.success('Análise concluída.')
    m1, m2, m3, m4 = st.columns(4)
    m1.metric('Citações detectadas', len(citations))
    m2.metric('Citações válidas', validas)
    m3.metric('Citações divergentes', divergentes)
    m4.metric('Blocos com sugestão', len(block_results))

    tab1, tab2, tab3, tab4 = st.tabs(['Resumo executivo', 'Citações', 'Sugestões por bloco', 'Exportação'])
    with tab1:
        st.markdown(summary_md)
    with tab2:
        if not citation_results:
            st.info('Nenhuma citação automática detectada.')
        else:
            for item in citation_results:
                with st.container(border=True):
                    st.markdown(f"**Trecho citado:** `{item['raw']}`")
                    st.write(f"Status: **{item['status_label']}**")
                    if item.get('matched_record'):
                        rec = item['matched_record']
                        st.write(f"Base encontrada: **{rec['numero_acordao']}** • {rec['colegiado']} • Relator: {rec['relator']}")
                        if rec.get('assunto'):
                            st.caption(rec['assunto'])
                    if item.get('suggestions'):
                        st.write('Sugestões:')
                        for sug in item['suggestions']:
                            score_txt = f"{abs(float(sug.get('score', 0.0))):.3f}"
                            st.markdown(f"- **{sug['numero_acordao']}** | {sug['colegiado']} | score `{score_txt}`")
    with tab3:
        if not block_results:
            st.info('Nenhum bloco teve sugestão de reforço.')
        else:
            for block in block_results:
                with st.container(border=True):
                    st.markdown(f"**Bloco {block['block_index']}**")
                    st.write(block['block_text'])
                    for sug in block['suggestions']:
                        score_txt = f"{abs(float(sug.get('score', 0.0))):.3f}"
                        st.markdown(f"- **{sug['numero_acordao']}** | {sug['colegiado']} | Relator: {sug['relator']} | score `{score_txt}`")
                        if sug.get('sumario'):
                            st.caption(sug['sumario'])
                        st.code(sug['paragrafo_sugerido'])
    with tab4:
        rows = build_export_rows(analysis)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        report_md = build_markdown_report(file_name, analysis)
        st.download_button('Baixar relatório em Markdown', report_md.encode('utf-8'), 'relatorio_analise_jurisprudencia.md', 'text/markdown', use_container_width=True)
        st.download_button('Baixar relatório em CSV', df.to_csv(index=False).encode('utf-8'), 'relatorio_analise_jurisprudencia.csv', 'text/csv', use_container_width=True)

with st.expander('Aviso importante'):
    st.warning('Ferramenta de apoio. Sempre valide a pertinência do precedente e a exatidão da citação antes do protocolo.')
