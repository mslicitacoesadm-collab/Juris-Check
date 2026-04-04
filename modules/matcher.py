from typing import Any, Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity



def build_search_index(base_records: List[Dict[str, Any]]) -> Tuple[TfidfVectorizer, Any]:
    corpus = [r.get("texto_indexacao", "") or "registro vazio" for r in base_records]
    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        lowercase=True,
        ngram_range=(1, 2),
        max_features=30000,
        min_df=1,
    )
    base_matrix = vectorizer.fit_transform(corpus)
    return vectorizer, base_matrix



def _exact_match(citation: Dict[str, str], base_records: List[Dict[str, Any]]):
    numero = citation.get("numero_acordao_num", "").strip()
    ano = citation.get("ano_acordao", "").strip()
    for rec in base_records:
        if rec.get("numero_acordao_num") == numero and (not ano or rec.get("ano_acordao") == ano):
            return rec
        if ano and rec.get("numero_acordao") == f"{numero}/{ano}":
            return rec
    return None



def _semantic_candidates(
    query_text: str,
    vectorizer,
    base_matrix,
    base_records,
    top_k: int,
    min_score: float,
):
    if not query_text.strip():
        return []
    query_vec = vectorizer.transform([query_text])
    sims = cosine_similarity(query_vec, base_matrix).flatten()
    ranked = sims.argsort()[::-1]
    results = []
    seen = set()
    for idx in ranked[: max(top_k * 10, 20)]:
        score = float(sims[idx])
        if score < min_score:
            continue
        rec = dict(base_records[idx])
        if rec.get("id") in seen:
            continue
        seen.add(rec.get("id"))
        rec["score"] = score
        base_text = (rec.get("sumario") or rec.get("decisao") or rec.get("assunto") or "").strip()
        rec["paragrafo_sugerido"] = (
            f"Conforme entendimento consubstanciado no {rec['numero_acordao']} - {rec['colegiado']}, "
            f"de relatoria de {rec['relator']}, observa-se que {base_text or 'há pertinência temática com o argumento desenvolvido na peça'}."
        )
        results.append(rec)
        if len(results) >= top_k:
            break
    return results



def analyze_piece(
    piece_text: str,
    blocks: List[str],
    citations: List[Dict[str, str]],
    base_records: List[Dict[str, Any]],
    vectorizer,
    base_matrix,
    top_k: int = 3,
    min_score: float = 0.12,
) -> Dict[str, Any]:
    citation_results = []
    citacoes_validas = 0
    citacoes_divergentes = 0

    for citation in citations:
        exact = _exact_match(citation, base_records)
        if exact:
            citacoes_validas += 1
            citation_results.append(
                {
                    "raw": citation["raw"],
                    "status": "valida",
                    "status_label": "Válida",
                    "matched_record": exact,
                    "suggestions": [],
                }
            )
            continue

        suggestions = _semantic_candidates(
            query_text=citation["raw"],
            vectorizer=vectorizer,
            base_matrix=base_matrix,
            base_records=base_records,
            top_k=top_k,
            min_score=min_score,
        )
        citacoes_divergentes += 1
        citation_results.append(
            {
                "raw": citation["raw"],
                "status": "divergente",
                "status_label": "Divergente ou não localizada",
                "matched_record": None,
                "suggestions": suggestions,
            }
        )

    block_results = []
    for idx, block in enumerate(blocks, start=1):
        suggestions = _semantic_candidates(
            query_text=block,
            vectorizer=vectorizer,
            base_matrix=base_matrix,
            base_records=base_records,
            top_k=top_k,
            min_score=min_score,
        )
        if suggestions:
            block_results.append(
                {
                    "block_index": idx,
                    "block_text": block,
                    "suggestions": suggestions,
                }
            )

    summary_lines = [
        "### Resumo executivo",
        f"- Foram detectadas **{len(citations)}** citações automáticas de acórdãos.",
        f"- Destas, **{citacoes_validas}** bateram exatamente com a base.",
        f"- **{citacoes_divergentes}** ficaram como divergentes ou não localizadas.",
        f"- O sistema encontrou **{len(block_results)}** blocos com sugestão de reforço jurisprudencial.",
        "",
        "**Leitura prática:**",
        "- Citação válida = número encontrado na base.",
        "- Citação divergente = número não localizado ou sem aderência literal.",
        "- Sugestão por bloco = reforço possível com base semântica no texto da peça.",
    ]

    return {
        "citation_results": citation_results,
        "block_results": block_results,
        "summary_markdown": "\n".join(summary_lines),
        "stats": {
            "citacoes_detectadas": len(citations),
            "citacoes_validas": citacoes_validas,
            "citacoes_divergentes": citacoes_divergentes,
            "blocos_com_sugestao": len(block_results),
        },
    }
