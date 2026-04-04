from typing import Any, Dict, List


def build_export_rows(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for item in analysis.get("citation_results", []):
        if item.get("matched_record"):
            rec = item["matched_record"]
            rows.append({
                "tipo": "citacao",
                "status": item["status_label"],
                "trecho": item["raw"],
                "numero_acordao_sugerido": rec["numero_acordao"],
                "colegiado": rec["colegiado"],
                "relator": rec["relator"],
                "score": 1.0,
            })
        elif item.get("suggestions"):
            for sug in item["suggestions"]:
                rows.append({
                    "tipo": "citacao",
                    "status": item["status_label"],
                    "trecho": item["raw"],
                    "numero_acordao_sugerido": sug["numero_acordao"],
                    "colegiado": sug["colegiado"],
                    "relator": sug["relator"],
                    "score": sug["score"],
                })
        else:
            rows.append({
                "tipo": "citacao",
                "status": item["status_label"],
                "trecho": item["raw"],
                "numero_acordao_sugerido": "",
                "colegiado": "",
                "relator": "",
                "score": "",
            })

    for block in analysis.get("block_results", []):
        for sug in block.get("suggestions", []):
            rows.append({
                "tipo": f"bloco_{block['block_index']}",
                "status": "Sugestão semântica",
                "trecho": block["block_text"][:500],
                "numero_acordao_sugerido": sug["numero_acordao"],
                "colegiado": sug["colegiado"],
                "relator": sug["relator"],
                "score": sug["score"],
            })

    return rows



def build_markdown_report(file_name: str, analysis: Dict[str, Any]) -> str:
    lines = [
        f"# Relatório de análise - {file_name}",
        "",
        analysis.get("summary_markdown", ""),
        "",
        "## Citações detectadas",
    ]

    if not analysis.get("citation_results"):
        lines.append("- Nenhuma citação automática detectada.")
    else:
        for item in analysis["citation_results"]:
            lines.append(f"- **{item['raw']}** -> {item['status_label']}")
            if item.get("matched_record"):
                rec = item["matched_record"]
                lines.append(f"  - Correspondência: {rec['numero_acordao']} | {rec['colegiado']} | {rec['relator']}")
            for sug in item.get("suggestions", []):
                lines.append(
                    f"  - Sugestão: {sug['numero_acordao']} | {sug['colegiado']} | {sug['relator']} | score {sug['score']:.3f}"
                )

    lines.append("")
    lines.append("## Sugestões por bloco")
    if not analysis.get("block_results"):
        lines.append("- Nenhuma sugestão acima do score mínimo.")
    else:
        for block in analysis["block_results"]:
            lines.append(f"### Bloco {block['block_index']}")
            lines.append(block["block_text"])
            lines.append("")
            for sug in block["suggestions"]:
                lines.append(
                    f"- {sug['numero_acordao']} | {sug['colegiado']} | {sug['relator']} | score {sug['score']:.3f}"
                )
                lines.append(f"  - Parágrafo sugerido: {sug['paragrafo_sugerido']}")

    return "\n".join(lines)
