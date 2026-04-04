from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ThesisProfile:
    id: str
    titulo: str
    descricao: str
    keywords: tuple[str, ...]
    negatives: tuple[str, ...] = ()


THESIS_PROFILES: Dict[str, ThesisProfile] = {
    'formalismo_moderado': ThesisProfile(
        id='formalismo_moderado',
        titulo='Formalismo moderado e erro sanável',
        descricao='Desclassificação indevida por falha formal, baixa materialidade ou vício sanável.',
        keywords=('formalismo moderado', 'erro formal', 'vício sanável', 'vicio sanavel', 'falha formal', 'baixa materialidade', 'saneamento', 'desclassificação', 'desclassificacao'),
    ),
    'diligencia': ThesisProfile(
        id='diligencia',
        titulo='Necessidade de diligência',
        descricao='Dever de oportunizar esclarecimento, saneamento ou comprovação antes de afastar a proposta.',
        keywords=('diligência', 'diligencia', 'saneamento', 'esclarecimento', 'oportunidade', 'comprovação', 'comprovacao', 'demonstração', 'demonstracao'),
    ),
    'inexequibilidade': ThesisProfile(
        id='inexequibilidade',
        titulo='Inexequibilidade e defesa da proposta',
        descricao='Presunção relativa e oportunidade de demonstrar exequibilidade.',
        keywords=('inexequibilidade', 'exequibilidade', 'planilha', 'custos', 'preço', 'preco', 'proposta inexequível', 'proposta inexequivel'),
    ),
    'vinculacao_edital': ThesisProfile(
        id='vinculacao_edital',
        titulo='Vinculação ao edital',
        descricao='Ilegalidade de exigência não prevista ou interpretação ampliativa do edital.',
        keywords=('edital', 'vinculação ao edital', 'vinculacao ao edital', 'exigência não prevista', 'exigencia nao prevista', 'instrumento convocatório', 'instrumento convocatorio', 'critério não previsto', 'criterio nao previsto'),
    ),
    'competitividade': ThesisProfile(
        id='competitividade',
        titulo='Competitividade e proposta mais vantajosa',
        descricao='Restrição indevida à disputa, perda de vantajosidade e prejuízo ao interesse público.',
        keywords=('competitividade', 'proposta mais vantajosa', 'interesse público', 'interesse publico', 'restrição à competição', 'restricao a competicao', 'certame', 'isonomia'),
    ),
    'habilitacao': ThesisProfile(
        id='habilitacao',
        titulo='Habilitação e capacidade técnica',
        descricao='Excesso formal em documentos de habilitação, atestados e comprovação técnica.',
        keywords=('habilitação', 'habilitacao', 'atestado', 'capacidade técnica', 'capacidade tecnica', 'qualificação técnica', 'qualificacao tecnica', 'documento de habilitação', 'documento de habilitacao'),
    ),
    'julgamento_objetivo': ThesisProfile(
        id='julgamento_objetivo',
        titulo='Julgamento objetivo',
        descricao='Critérios subjetivos ou interpretação extensiva no julgamento da proposta.',
        keywords=('julgamento objetivo', 'subjetivo', 'critério objetivo', 'criterio objetivo', 'interpretação extensiva', 'interpretacao extensiva', 'razoabilidade', 'proporcionalidade'),
    ),
}

DOC_TYPE_KEYWORDS = {
    'recurso': ('recurso administrativo', 'recorrente', 'ato recorrido', 'reforma da decisão', 'provimento do recurso'),
    'contrarrazao': ('contrarrazões', 'contrarrazoes', 'recorrido', 'improvimento do recurso', 'manutenção da decisão', 'manutencao da decisao'),
    'impugnacao': ('impugnação', 'impugnacao', 'edital', 'retificação do edital', 'retificacao do edital', 'suspensão do certame', 'suspensao do certame'),
}


def detect_document_type(text: str) -> str:
    txt = (text or '').lower()
    scores = {}
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        scores[doc_type] = sum(2 if kw in txt else 0 for kw in keywords)
    best = max(scores, key=scores.get) if scores else 'peça'
    if scores.get(best, 0) == 0:
        return 'peça jurídica'
    return {'recurso': 'recurso administrativo', 'contrarrazao': 'contrarrazões', 'impugnacao': 'impugnação'}[best]


def score_thesis(text: str, profile: ThesisProfile) -> int:
    txt = (text or '').lower()
    score = 0
    for kw in profile.keywords:
        if kw in txt:
            score += 3 if ' ' in kw else 2
    for neg in profile.negatives:
        if neg in txt:
            score -= 2
    return score


def infer_theses_for_block(text: str) -> List[dict]:
    candidates = []
    for thesis_id, profile in THESIS_PROFILES.items():
        sc = score_thesis(text, profile)
        if sc >= 3:
            candidates.append({'id': thesis_id, 'score': sc, 'titulo': profile.titulo, 'descricao': profile.descricao})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:2]
