from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import streamlit as st

try:
    from tools.bootstrap_github_streamlit import ensure_base_ready
except Exception:
    def ensure_base_ready(base_dir: Path | None = None) -> dict:
        root = Path(base_dir or BASE_DIR)
        output_db = root / 'data' / 'base' / 'base_inteligente.db'
        if output_db.exists():
            return {
                'ready': True,
                'message': f'Base já encontrada em {output_db}.',
                'db_path': str(output_db),
                'integrity': 'desconhecida',
            }
        return {
            'ready': False,
            'message': 'Falha ao importar o bootstrap automático. Verifique se a pasta tools/ está presente no projeto.',
            'db_path': str(output_db),
        }

from modules.base_db import find_db_files, summarize_bases
from modules.citation_extractor import classify_piece_type, detect_thesis, extract_references_with_context, split_into_argument_blocks
from modules.document_builder import build_docx_bytes, build_marked_text, build_pdf_bytes, build_revised_text
from modules.piece_reader import read_uploaded_file
from modules.report_builder import build_export_rows
from modules.search_engine import search_candidates, validate_reference
from modules.telemetry import get_summary, log_event

st.set_page_config(page_title='Atlas dos Acórdãos V17', page_icon='⚖️', layout='wide')


DB_DIR = BASE_DIR / 'data' / 'base'
LOGO_PATH = BASE_DIR / 'assets' / 'logo_ms.png'
MAX_UPLOAD_MB = 20
ADMIN_KEY = os.getenv('ATLAS_ADMIN_KEY', 'atlas-admin')


def ensure_runtime_base() -> tuple[bool, str]:
    try:
        result = ensure_base_ready(BASE_DIR)
        return result.get('ready', False), result.get('message', 'Base não encontrada.')
    except Exception as exc:
        return False, f'Falha ao preparar a base automaticamente: {exc}'


base_ready, base_runtime_message = ensure_runtime_base()

if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'last_file_name' not in st.session_state:
    st.session_state.last_file_name = ''
if 'show_admin' not in st.session_state:
    st.session_state.show_admin = False


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


def db_health_message(summary: dict) -> str:
    if summary.get('base_inteligente_detectada'):
        return f"Base inteligente ativa em {summary.get('arquivo_base_inteligente')} com {summary.get('inteligente', 0):,} precedentes.".replace(',', '.')
    if summary.get('total_bases', 0):
        return f"Modo legado ativo com {summary.get('acordao', 0):,} acórdãos, {summary.get('jurisprudencia', 0):,} jurisprudências e {summary.get('sumula', 0):,} súmulas.".replace(',', '.')
    return 'Nenhuma base foi encontrada ainda. Você pode usar o sistema após colocar as bases em data/base/.'


def compatibility_label(score: float) -> str:
    if score >= 0.80:
        return 'Alta aderência'
    if score >= 0.60:
        return 'Aderência moderada'
    if score >= 0.35:
        return 'Referência fraca'
    return 'Referência incompatível'


def risk_label(errors: int, adjustments: int, total: int) -> str:
    if total == 0:
        return 'Sem referências explícitas'
    severity = (errors * 2 + adjustments) / max(total, 1)
    if severity <= 0.4:
        return 'Baixo risco técnico'
    if severity <= 0.9:
        return 'Risco técnico moderado'
    return 'Alto risco técnico'


def mode_help(mode: str) -> str:
    mapping = {
        'Auditoria rápida': 'Valida citações e aponta divergências sem reescrita profunda.',
        'Auditoria contextual': 'Valida contexto, sugere precedentes melhores e reescreve trechos críticos.',
        'Reforço técnico premium': 'Entrega tese dominante, reforço argumentativo e exportação pronta para uso.',
    }
    return mapping[mode]


def base_warning(summary: dict) -> str:
    if summary.get('base_inteligente_detectada'):
        return 'A base inteligente está ativa. O motor prioriza tese central, fundamentos legais, utilidade prática e contexto licitatório.'
    if summary.get('total_bases', 0):
        return 'A base inteligente ainda não foi conectada. O sistema continuará com as bases tradicionais, mantendo a auditoria operacional.'
    return 'Sem base conectada. Coloque suas bases em data/base/ antes de iniciar a auditoria.'


def friendly_read_error(exc: Exception, file_name: str = '') -> str:
    msg = str(exc)
    lower = msg.lower()
    if 'ocr' in lower or 'pdf pesquisável' in lower:
        return 'Não foi possível extrair texto deste PDF. Tente enviar em DOCX ou em PDF pesquisável. O OCR é opcional e pode ser ativado no deploy depois.'
    if 'formato não suportado' in lower:
        return 'Formato não suportado. Envie PDF, DOCX ou TXT.'
    if 'muito grande' in lower:
        return msg
    if file_name.lower().endswith('.pdf'):
        return 'Não foi possível ler este PDF com segurança. Tente reenviar em DOCX ou PDF pesquisável.'
    return f'Não foi possível ler o arquivo enviado. Detalhe técnico: {msg}'


def admin_gate() -> bool:
    if st.session_state.show_admin:
        return True
    with st.expander('Acesso administrativo'):
        key = st.text_input('Chave administrativa', type='password', help='Opcional para liberar o painel administrativo nesta sessão.')
        if st.button('Liberar painel administrativo'):
            if key == ADMIN_KEY:
                st.session_state.show_admin = True
                st.success('Painel administrativo liberado nesta sessão.')
            else:
                st.error('Chave administrativa inválida.')
    return st.session_state.show_admin


db_files = find_db_files(DB_DIR)
db_paths = tuple(str(p) for p in db_files)
summary = cached_summary(str(DB_DIR), _db_signature(DB_DIR))
telemetry = get_summary()

st.markdown(
    """
<style>
:root{--bg:#f5f7fb;--card:#ffffff;--line:#d7dfeb;--ink:#132238;--muted:#4e5d72;--primary:#123b67;--primary2:#194f84;}
.stApp{background:var(--bg);} .hero{padding:1.4rem 1.5rem;border-radius:24px;background:linear-gradient(135deg,#0f2744 0%,#163b62 55%,#245d8f 100%);color:#fff;border:1px solid rgba(255,255,255,.12)}
.hero h1{margin:0 0 .4rem 0;font-size:1.95rem}.hero p{margin:.2rem 0;line-height:1.55}
.card{padding:1rem 1rem;border:1px solid var(--line);border-radius:20px;background:var(--card);margin-bottom:.85rem;box-shadow:0 6px 18px rgba(16,24,40,.04)}
.block{padding:1rem 1.1rem;border:1px solid var(--line);border-radius:20px;background:var(--card)}
.legend{display:inline-block;padding:.24rem .7rem;border-radius:999px;font-size:.82rem;font-weight:700}
.small{font-size:.93rem;color:var(--muted);line-height:1.58}.section-title{font-size:1.08rem;font-weight:700;color:var(--ink);margin:.2rem 0 .8rem 0}
.metric-note{font-size:.85rem;color:#355070;margin-top:.4rem}.warning-box{padding:0.8rem 1rem;border-radius:16px;border:1px solid #d7dfeb;background:#fff}
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
          <h1>Atlas dos Acórdãos · V17 Lançamento</h1>
          <p><strong>Analise sua peça de licitação</strong>, valide citações, identifique incompatibilidades e receba sugestões de reforço técnico-jurídico com suporte à base inteligente.</p>
          <p>Arquivos aceitos: <strong>PDF, DOCX e TXT</strong>. Resultado entregue em blocos claros: diagnóstico, citações auditadas, reforço por tese e exportação.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='warning-box'><strong>Como funciona:</strong> 1) envie a peça ou cole o texto; 2) escolha o modo de auditoria; 3) receba diagnóstico técnico, correções e exportações. <br><strong>Confidencialidade:</strong> o processamento é local ao app. <br><strong>Limite operacional:</strong> este sistema apoia a análise, mas não substitui advogado nem garante êxito.</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader('Configuração da análise')
    analysis_mode = st.radio('Modo de análise', ['Auditoria rápida', 'Auditoria contextual', 'Reforço técnico premium'], index=2)
    st.caption(mode_help(analysis_mode))
    top_k = st.slider('Sugestões por referência', 1, 5, 3)
    max_blocks = st.slider('Blocos de tese para varredura', 3, 12, 6)
    rewrite_mode = {'Auditoria rápida': 'Correção simples', 'Auditoria contextual': 'Correção contextual', 'Reforço técnico premium': 'Reescrita premium'}[analysis_mode]
    st.markdown('**Saúde da base**')
    st.caption(db_health_message(summary))
    st.markdown('**Limites e formatos**')
    st.caption(f'Use PDF, DOCX ou TXT. Tamanho recomendado: até {MAX_UPLOAD_MB} MB por arquivo. PDF escaneado pode exigir OCR opcional no deploy.')
    st.markdown('**Legenda**')
    st.markdown('<span class="legend" style="background:#D1E7DD;color:#0F5132">Validada</span> <span class="legend" style="background:#FFF3CD;color:#664D03">Ajuste recomendado</span> <span class="legend" style="background:#F8D7DA;color:#842029">Erro relevante</span>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
if summary.get('base_inteligente_detectada'):
    k1.metric('Precedentes inteligentes', f"{summary['inteligente']:,}".replace(',', '.'))
    k2.metric('Base inteligente', 'Ativa')
    k3.metric('Arquivo mestre', summary.get('arquivo_base_inteligente') or '-')
    k4.metric('Bases detectadas', summary['total_bases'])
else:
    k1.metric('Acórdãos', f"{summary['acordao']:,}".replace(',', '.'))
    k2.metric('Jurisprudências', f"{summary['jurisprudencia']:,}".replace(',', '.'))
    k3.metric('Súmulas', f"{summary['sumula']:,}".replace(',', '.'))
    k4.metric('Bases detectadas', summary['total_bases'])

if summary.get('total_bases', 0):
    (st.success if summary.get('base_inteligente_detectada') else st.info)(base_warning(summary))
else:
    st.warning(base_warning(summary))

if base_runtime_message:
    if base_ready:
        st.caption('Preparação automática da base: ' + base_runtime_message)
    else:
        st.caption('Preparação automática da base: ' + base_runtime_message)

main_tab, manual_tab, admin_tab = st.tabs(['Upload e auditoria', 'Busca manual de precedentes', 'Painel administrativo'])

with main_tab:
    st.markdown('<div class="section-title">1. Envie a peça ou cole o texto</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader('Arquivo da peça', type=['pdf', 'docx', 'txt'], key='upload_principal', help=f'Tamanho recomendado: até {MAX_UPLOAD_MB} MB por arquivo.')
    manual_text = st.text_area('Ou cole o texto da peça', height=180, key='manual_text_main')
    analyze = st.button('Iniciar auditoria', type='primary', use_container_width=True)

    if analyze:
        if not db_files:
            st.error('A base não foi encontrada. Coloque `base_inteligente.db` ou as bases legadas em `data/base/` e tente novamente.')
            st.stop()
        if uploaded_file is None and not manual_text.strip():
            st.error('Envie um arquivo ou cole o texto da peça antes de iniciar a auditoria.')
            st.stop()
        if uploaded_file is not None:
            size_mb = getattr(uploaded_file, 'size', 0) / (1024 * 1024)
            if size_mb > MAX_UPLOAD_MB:
                st.error(f'Arquivo muito grande para o fluxo recomendado ({size_mb:.1f} MB). Envie um arquivo de até {MAX_UPLOAD_MB} MB ou use DOCX/TXT.')
                st.stop()
        try:
            if uploaded_file is not None:
                piece_text = read_uploaded_file(uploaded_file, max_mb=MAX_UPLOAD_MB)
                file_name = uploaded_file.name
            else:
                piece_text = manual_text
                file_name = 'texto_colado.txt'
        except Exception as exc:
            st.error(friendly_read_error(exc, getattr(uploaded_file, 'name', '')))
            log_event('erro_leitura', {'piece_type': 'desconhecida', 'status': 'erro', 'arquivo': getattr(uploaded_file, 'name', ''), 'mensagem': str(exc)})
            st.stop()

        if not piece_text.strip():
            st.error('A leitura retornou texto vazio. Tente DOCX, TXT ou um PDF pesquisável.')
            st.stop()

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

        dominant_thesis = thesis_results[0]['tese'] if thesis_results else detect_thesis(piece_text).get('label', 'Tese geral')
        analysis = {
            'piece_type': piece_type,
            'citation_results': citation_results,
            'thesis_results': thesis_results,
            'piece_text': piece_text,
            'rewrite_mode': rewrite_mode,
            'analysis_mode': analysis_mode,
            'dominant_thesis': dominant_thesis,
        }
        st.session_state.analysis = analysis

        log_event('analise_peca', {
            'piece_type': piece_type.get('tipo'),
            'thesis': dominant_thesis,
            'citations': len(citation_results),
            'errors': sum(1 for x in citation_results if x['status'] == 'divergente'),
            'adjustments': sum(1 for x in citation_results if x['status'] == 'valida_pouco_compativel'),
            'status': 'concluida',
            'arquivo': file_name,
            'modo': analysis_mode,
        })

    analysis = st.session_state.analysis
    if analysis:
        piece_text = analysis.get('piece_text', '')
        mode_map = {'Correção simples': 'simple', 'Correção contextual': 'contextual', 'Reescrita premium': 'premium'}
        revised_text = build_revised_text(piece_text, analysis, mode=mode_map[analysis['rewrite_mode']])
        marked_text = build_marked_text(piece_text, analysis)
        export_rows = build_export_rows(analysis)
        validas = sum(1 for x in analysis['citation_results'] if x['status'] == 'valida_compatível')
        ajustes = sum(1 for x in analysis['citation_results'] if x['status'] == 'valida_pouco_compativel')
        erros = sum(1 for x in analysis['citation_results'] if x['status'] == 'divergente')
        total_refs = len(analysis['citation_results'])
        risco = risk_label(erros, ajustes, total_refs)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Tipo da peça', analysis['piece_type']['tipo'])
        c2.metric('Tese dominante', analysis.get('dominant_thesis', 'Tese geral'))
        c3.metric('Risco técnico', risco)
        c4.metric('Referências localizadas', total_refs)

        t1, t2, t3, t4 = st.tabs(['Diagnóstico', 'Citações auditadas', 'Teses e reforços', 'Exportação'])
        with t1:
            st.markdown(
                '<div class="block"><div class="small"><strong>Modo escolhido:</strong> {}<br><strong>Resumo executivo:</strong> a peça foi lida como <strong>{}</strong>, com <strong>{}</strong> referências explícitas e <strong>{}</strong> blocos argumentativos passíveis de reforço. <br><strong>Nível de risco:</strong> {}. <br><strong>Observação:</strong> quando não há referência explícita, o sistema reforça a tese pelo contexto textual.</div></div>'.format(
                    analysis['analysis_mode'], analysis['piece_type']['tipo'], total_refs, len(analysis['thesis_results']), risco
                ),
                unsafe_allow_html=True,
            )
            st.markdown('**Leitura recomendada do resultado**')
            st.write('1. Veja o diagnóstico geral. 2. Corrija as referências incompatíveis. 3. Aproveite os precedentes sugeridos nas teses. 4. Exporte a versão final limpa ou marcada.')
            st.text_area('Prévia da peça revisada', revised_text[:12000], height=280)

        with t2:
            if not analysis['citation_results']:
                st.info('Nenhuma citação explícita de acórdão, súmula ou jurisprudência foi identificada. A análise foi feita apenas pelo contexto textual da peça.')
            for item in analysis['citation_results']:
                fg, bg = status_tone(item['status'])
                comercial = compatibility_label(float(item.get('score_contexto') or 0.0))
                st.markdown(
                    f"<div class='card'><div style='display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.55rem'><span class='legend' style='background:{bg};color:{fg}'>{item['status_label']}</span><span class='legend' style='background:#e8eef8;color:#123b67'>{comercial}</span><span class='legend' style='background:#eef3f8;color:#39516b'>{item['grau_confianca']}</span></div><div class='small'><strong>Referência encontrada:</strong> {item['raw']}<br><strong>Linha:</strong> {item.get('linha','-')}<br><strong>Tese do contexto:</strong> {item.get('tese','Tese geral')}</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption('Contexto lido pelo motor')
                st.write(item.get('contexto') or '—')
                if item.get('matched_record'):
                    st.markdown('**Precedente validado na base**')
                    st.write(item['matched_record'].get('citacao_curta') or f"{item['matched_record']['tipo']} nº {item['matched_record']['numero']}/{item['matched_record']['ano']}")
                if item.get('motivo_match'):
                    st.markdown('**Motivo técnico do enquadramento**')
                    st.write(item['motivo_match'])
                if item.get('correcao_sugerida'):
                    sug = item['correcao_sugerida']
                    st.markdown('**Melhor correção sugerida**')
                    st.write(f"{sug['citacao_curta']} · {compatibility_label(float(sug['compat_score']))}")
                    st.write(sug.get('fundamento_curto') or '')
                    st.markdown('**Redação sugerida para o parágrafo**')
                    st.write(item.get('paragrafo_reescrito') or '')

        with t3:
            if not analysis['thesis_results']:
                st.info('Não foram identificados blocos suficientes para reforço por tese. Isso costuma acontecer em peças muito curtas ou pouco estruturadas.')
            for bloco in analysis['thesis_results']:
                st.markdown(f"<div class='card'><div class='section-title'>{bloco['tese']}</div><div class='small'><strong>Fundamentos detectados:</strong> {bloco['fundamentos'] or 'sem indicadores claros'}</div><div class='small' style='margin-top:.5rem'><strong>Trecho lido:</strong> {bloco['preview']}</div></div>", unsafe_allow_html=True)
                for sug in bloco['sugestoes']:
                    st.markdown(f"**{sug['citacao_curta']}** · {compatibility_label(float(sug['compat_score']))}")
                    st.write(sug.get('motivo_match') or '')
                    st.write(sug.get('fundamento_curto') or '')
                    if sug.get('aplicavel_em'):
                        st.caption('Melhor uso: ' + ', '.join(sug['aplicavel_em']))

        with t4:
            docx_clean = build_docx_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            docx_marked = build_docx_bytes(marked_text, analysis, f"Marcado - {st.session_state.last_file_name or 'peca_revisada'}", marked=True)
            pdf_clean = build_pdf_bytes(revised_text, analysis, st.session_state.last_file_name or 'peca_revisada')
            csv_bytes = pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
            st.markdown('**Exportações disponíveis**')
            st.write('Use o DOCX limpo para trabalho final, o DOCX marcado para revisão interna, o PDF para circulação rápida e o CSV para auditoria técnica.')
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button('DOCX limpo', docx_clean, file_name='atlas_v17_revisado_limpo.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d2.download_button('DOCX marcado', docx_marked, file_name='atlas_v17_revisado_marcado.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', use_container_width=True)
            d3.download_button('PDF limpo', pdf_clean, file_name='atlas_v17_revisado_limpo.pdf', mime='application/pdf', use_container_width=True)
            d4.download_button('CSV da auditoria', csv_bytes, file_name='atlas_v17_auditoria.csv', mime='text/csv', use_container_width=True)

with manual_tab:
    st.markdown('<div class="section-title">Busca manual por tese ou referência direta</div>', unsafe_allow_html=True)
    manual_query = st.text_input('Ex.: falha sanável sem diligência | Acórdão 1418/2024 | Súmula 222')
    manual_types = st.multiselect('Tipos a pesquisar', ['acordao', 'jurisprudencia', 'sumula'], default=['acordao', 'jurisprudencia', 'sumula'])
    if st.button('Pesquisar precedentes', use_container_width=True):
        if not db_files:
            st.error('A base não foi encontrada. Conecte `data/base/` antes de pesquisar.')
        elif not manual_query.strip():
            st.warning('Digite uma tese ou uma referência direta para pesquisar.')
        else:
            thesis = detect_thesis(manual_query)
            results = cached_search(db_paths, manual_query, thesis['chave'], ','.join(manual_types), 8)
            log_event('busca_manual', {
                'piece_type': 'busca_manual',
                'thesis': thesis.get('label'),
                'citations': len(results),
                'status': 'executada',
            })
            if not results:
                st.info('Nenhum precedente relevante foi localizado com os filtros atuais. Ajuste a tese, o número ou amplie os tipos pesquisados.')
            for rec in results:
                st.markdown(f"<div class='card'><div style='display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap'><div><strong>{rec['citacao_curta']}</strong></div><div><span class='legend' style='background:#e8eef8;color:#123b67'>{compatibility_label(float(rec['compat_score']))}</span></div></div><div class='small' style='margin-top:.55rem'><strong>Tema:</strong> {rec.get('tema') or 'Não informado'}<br><strong>Motivo do match:</strong> {rec.get('motivo_match') or 'Sem explicação adicional.'}</div></div>", unsafe_allow_html=True)
                st.write(rec.get('fundamento_curto') or '')
                if rec.get('aplicavel_em'):
                    st.caption('Melhor uso: ' + ', '.join(rec['aplicavel_em']))

with admin_tab:
    if admin_gate():
        st.markdown('<div class="section-title">Painel administrativo local</div>', unsafe_allow_html=True)
        a1, a2, a3, a4 = st.columns(4)
        a1.metric('Eventos gravados', telemetry.get('total_eventos', 0))
        a2.metric('Citações processadas', telemetry.get('citacoes_processadas', 0))
        a3.metric('Erros relevantes', telemetry.get('erros_relevantes', 0))
        a4.metric('Ajustes recomendados', telemetry.get('ajustes_recomendados', 0))

        left, right = st.columns(2)
        with left:
            st.markdown('**Teses mais frequentes**')
            st.dataframe(pd.DataFrame(telemetry.get('teses_mais_frequentes', []), columns=['Tese', 'Ocorrências']), use_container_width=True)
        with right:
            st.markdown('**Tipos de peça mais frequentes**')
            st.dataframe(pd.DataFrame(telemetry.get('tipos_peca_mais_frequentes', []), columns=['Tipo', 'Ocorrências']), use_container_width=True)

        st.markdown('**Orientações de deploy GitHub + Streamlit**')
        st.code(
            """python tools/bootstrap_github_streamlit.py
python tools/verify_base.py data/base/base_inteligente.db
streamlit run app.py""",
            language='bash',
        )
        st.caption('Suba este pacote sem a base pesada. Depois reconstrua `data/base/base_inteligente.db` a partir das partes do Atlas_Final.')
    else:
        st.info('O painel administrativo fica separado da experiência do usuário. Informe a chave para liberar esta aba nesta sessão.')
