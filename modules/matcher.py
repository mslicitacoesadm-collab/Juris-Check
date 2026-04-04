import math
import re
from collections import Counter
from typing import Any, Dict, List

TOKEN_RE = re.compile(r"[a-zà-ÿ0-9]{2,}", re.IGNORECASE)
STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "por", "com", "sem", "na", "no", "nas", "nos",
    "ao", "aos", "as", "os", "o", "a", "um", "uma", "que", "se", "ou", "à", "às", "art", "arts", "tcu"
}


def tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or "")]
    return [t for t in tokens if t not in STOPWORDS]



def build_search_index(base_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed: List[Dict[str, Any]] = []
    for rec in base_records:
        text = rec.get("texto_indexacao", "") or "registro vazio"
        tokens = tokenize(text)
        vector = Counter(tokens)
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        indexed.append({
            "record": rec,
            "vector": vector,
            "norm": norm,
        })
    return indexed



def _cosine(query_vec: Counter, query_norm: float, doc_vec: Counter, doc_norm: float) -> float:
    if not query_vec or not doc_vec:
        return 0.0
    common = set(query_vec) & set(doc_vec)
    dot = sum(query_vec[token] * doc_vec[token] for token in common)
    if dot <= 0:
        return 0.0
    return dot / (query_norm * doc_norm)



def _exact_match(citation: Dict[str, str], base_records: List[Dict[str, Any]]):
    numero = (citation.get("numero_acordao_num") or "").strip()
    ano = (citation.get("ano_acordao") or "").strip()
    if not numero:
        return None
    for rec in base_records:
        if rec.get("numero_acordao_num") == numero and (not ano or rec.get("ano_acordao") == ano):
            return rec
        if ano and rec.get("numero_acordao") == f"{numero}/{ano}":
            return rec
    return None



def _semantic_candidates(query_text: str, search_index: List[Dict[str, Any]], top_k: int, min_score: float):
    tokens = tokenize(query_text)
    if not tokens:
        return []
    query_vec = Counter(tokens)
    query_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0

    ranked: List[Dict[str, Any]] = []
    seen = set()
    for item in search_index:
        rec = item["record"]
        if rec.get("id") in seen:
            continue
        score = _cosine(query_vec, query_norm, item["vector"], item["norm"])
        if score < min_score:
            continue
        seen.add(rec.get("id"))
        sug = dict(rec)
        sug["score"] = float(score)
        base_text = (sug.get("sumario") or sug.get("decisao") or sug.get("assunto") or "").strip()
        sug["paragrafo_sugerido"] = (
            f"Conforme entendimento consubstanciado no {sug['numero_acordao']} - {sug['colegiado']}, "
            f"de relatoria de {sug['relator']}, observa-se que "
            f"{base_text or 'há pertinência temática com o argumento desenvolvido na peça'}."
        )
        ranked.append(sug)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]



def analyze_piece(
    piece_text: str,
    blocks: List[str],
    citations: List[Dict[str, str]],
    base_records: List[Dict[str, Any]],
    search_index: List[Dict[str, Any]],
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
            citation_results.append({
                "raw": citation["raw"],
                "status": "valida",
                "status_label": "Válida",
                "matched_record": exact,
                "suggestions": [],
            })
            continue

        suggestions = _semantic_candidates(citation["raw"], search_index, top_k, min_score)
        citacoes_divergentes += 1
        citation_results.append({
            "raw": citation["raw"],
            "status": "divergente",
            "status_label": "Divergente ou não localizada",
            "matched_record": None,
            "suggestions": suggestions,
        })

    block_results = []
    for idx, block in enumerate(blocks, start=1):
        suggestions = _semantic_candidates(block, search_index, top_k, min_score)
        if suggestions:
            block_results.append({
                "block_index": idx,
                "block_text": block,
                "suggestions": suggestions,
            })

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
