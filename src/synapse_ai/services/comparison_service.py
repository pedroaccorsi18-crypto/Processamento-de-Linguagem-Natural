from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Any

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.spreadsheet_export import XlsxSheet, workbook_to_xlsx

logger = logging.getLogger(__name__)


class ComparisonGenerationError(RuntimeError):
    """Raised when a document comparison cannot be generated."""


@dataclass(frozen=True)
class DocumentComparisonIssue:
    issue_type: str
    title: str
    description: str
    severity: str
    documents: list[str]
    impact: str
    evidence: str
    recommendation: str
    source_refs: list[str]


@dataclass(frozen=True)
class DocumentComparisonReport:
    executive_summary: str
    issues: list[DocumentComparisonIssue]
    sources: list[SourceSnippet]


def generate_document_comparison(
    client: Any,
    sources: list[SourceSnippet],
    model: str,
) -> DocumentComparisonReport:
    if not sources:
        raise ComparisonGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_comparison_instructions(),
            input=_build_comparison_input(sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document comparison generation failed: %s", exc.__class__.__name__)
        raise ComparisonGenerationError(
            "Não foi possível comparar os documentos selecionados."
        ) from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    issues = _parse_issues(payload.get("issues"), sources)
    if not issues:
        raise ComparisonGenerationError(
            "A IA não encontrou inconsistências documentais claras neste escopo."
        )
    return DocumentComparisonReport(
        executive_summary=_text(
            payload.get("executive_summary"),
            "Síntese comparativa não disponível.",
        ),
        issues=issues,
        sources=sources,
    )


def serialize_comparison_issues(
    issues: list[DocumentComparisonIssue],
) -> list[dict[str, object]]:
    return [
        {
            "issue_type": issue.issue_type,
            "title": issue.title,
            "description": issue.description,
            "severity": issue.severity,
            "documents": issue.documents,
            "impact": issue.impact,
            "evidence": issue.evidence,
            "recommendation": issue.recommendation,
            "source_refs": issue.source_refs,
        }
        for issue in issues
    ]


def document_comparison_to_markdown(report: DocumentComparisonReport) -> str:
    lines = [
        "# Comparação documental - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        "## Inconsistências e divergências",
        "",
    ]
    for index, issue in enumerate(report.issues, start=1):
        refs = ", ".join(issue.source_refs) if issue.source_refs else "Fonte não indicada"
        documents = ", ".join(issue.documents) if issue.documents else "A confirmar"
        lines.extend(
            [
                f"### {index}. {issue.title}",
                f"- Tipo: {issue.issue_type}",
                f"- Severidade: {issue.severity}",
                f"- Documentos envolvidos: {documents}",
                f"- Impacto: {issue.impact}",
                f"- Evidência: {issue.evidence}",
                f"- Recomendação: {issue.recommendation}",
                f"- Fontes: {refs}",
                "",
                issue.description,
                "",
            ]
        )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "Esta comparação aponta divergências prováveis a partir dos documentos selecionados. "
        "Valide as evidências antes de atualizar cronogramas, responsabilidades ou decisões."
    )
    return "\n".join(lines).strip() + "\n"


def document_comparison_to_csv(report: DocumentComparisonReport) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "tipo",
            "título",
            "descrição",
            "severidade",
            "documentos",
            "impacto",
            "evidência",
            "recomendação",
            "fontes",
        ],
    )
    writer.writeheader()
    for issue in report.issues:
        writer.writerow(
            {
                "tipo": issue.issue_type,
                "título": issue.title,
                "descrição": issue.description,
                "severidade": issue.severity,
                "documentos": ", ".join(issue.documents),
                "impacto": issue.impact,
                "evidência": issue.evidence,
                "recomendação": issue.recommendation,
                "fontes": ", ".join(issue.source_refs),
            }
        )
    return output.getvalue()


def document_comparison_to_xlsx(report: DocumentComparisonReport) -> bytes:
    issue_headers = [
        "Tipo",
        "Título",
        "Descrição",
        "Severidade",
        "Documentos",
        "Impacto",
        "Evidência",
        "Recomendação",
        "Fontes",
    ]
    issue_rows = [
        [
            issue.issue_type,
            issue.title,
            issue.description,
            issue.severity,
            ", ".join(issue.documents),
            issue.impact,
            issue.evidence,
            issue.recommendation,
            ", ".join(issue.source_refs),
        ]
        for issue in report.issues
    ]
    return workbook_to_xlsx(
        [
            XlsxSheet(
                name="Resumo executivo",
                headers=["Indicador", "Resultado"],
                rows=_comparison_summary_rows(report),
                column_widths=[32, 86],
            ),
            XlsxSheet(
                name="Divergências",
                headers=issue_headers,
                rows=issue_rows,
                column_widths=[18, 34, 58, 14, 42, 48, 58, 58, 20],
            ),
        ]
    )


def _comparison_instructions() -> str:
    return (
        "Você é o Synapse AI comparando documentos organizacionais. Procure divergências, "
        "contradições e mudanças relevantes entre documentos, como datas conflitantes, "
        "responsáveis diferentes para a mesma entrega, decisões reprogramadas, riscos citados "
        "em um documento e omitidos em outro, escopos inconsistentes ou evidências insuficientes. "
        "Use apenas as fontes fornecidas; não invente fatos. Preserve a ortografia portuguesa "
        "correta, inclusive acentos, ao redigir títulos, evidências e recomendações. No campo "
        "documents, use nomes reais dos arquivos citados nas fontes, nunca apenas 'Fonte 1' ou "
        "'Fonte 2'. Use severidade Alta, Média ou Baixa. Quando um campo não estiver claro, "
        "use 'A confirmar'. Responda somente com JSON válido no formato: "
        '{"executive_summary":"...","issues":[{"issue_type":"Cronograma|Responsável|'
        'Decisão|Risco|Escopo|Evidência|Outro","title":"...","description":"...",'
        '"severity":"Alta|Média|Baixa","documents":["..."],"impact":"...",'
        '"evidence":"...","recommendation":"...","source_refs":["Fonte 1"]}]}'
    )


def _build_comparison_input(sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return (
        "Objetivo: comparar os documentos selecionados e identificar inconsistências, "
        "divergências, reprogramações, conflitos de responsabilidade, lacunas e impactos.\n\n"
        f"Fontes recuperadas:\n{rendered_sources}"
    )


def _comparison_summary_rows(report: DocumentComparisonReport) -> list[list[object]]:
    severity_counts = _count_by([issue.severity for issue in report.issues])
    issue_type_counts = _count_by([issue.issue_type for issue in report.issues])
    documents = sorted(
        {
            document
            for issue in report.issues
            for document in issue.documents
            if document and not _is_source_reference(document)
        }
    )
    issue_types = ", ".join(f"{key}: {value}" for key, value in issue_type_counts.items())
    return [
        ["Síntese executiva", report.executive_summary],
        ["Total de divergências", len(report.issues)],
        ["Severidade alta", severity_counts.get("Alta", 0)],
        ["Severidade média", severity_counts.get("Média", 0)],
        ["Severidade baixa", severity_counts.get("Baixa", 0)],
        ["Tipos identificados", issue_types or "A confirmar"],
        ["Documentos envolvidos", ", ".join(documents) or "A confirmar"],
    ]


def _parse_issues(
    value: object,
    sources: list[SourceSnippet],
) -> list[DocumentComparisonIssue]:
    if not isinstance(value, list):
        return []
    source_reference_map = _source_reference_map(sources)
    issues: list[DocumentComparisonIssue] = []
    for raw_issue in value:
        if not isinstance(raw_issue, dict):
            continue
        title = _text(raw_issue.get("title"), "")
        if not title:
            continue
        issues.append(
            DocumentComparisonIssue(
                issue_type=_normalize_issue_type(raw_issue.get("issue_type")),
                title=title,
                description=_text(raw_issue.get("description"), "A confirmar"),
                severity=_normalize_severity(raw_issue.get("severity")),
                documents=_normalize_documents(
                    _text_list(raw_issue.get("documents")),
                    _text_list(raw_issue.get("source_refs")),
                    source_reference_map,
                ),
                impact=_text(raw_issue.get("impact"), "A confirmar"),
                evidence=_text(raw_issue.get("evidence"), "A confirmar"),
                recommendation=_text(raw_issue.get("recommendation"), "A confirmar"),
                source_refs=_text_list(raw_issue.get("source_refs")),
            )
        )
    return issues


def _source_reference_map(sources: list[SourceSnippet]) -> dict[str, str]:
    return {
        f"Fonte {index}": source.filename
        for index, source in enumerate(sources, start=1)
        if source.filename
    }


def _normalize_documents(
    documents: list[str],
    source_refs: list[str],
    source_reference_map: dict[str, str],
) -> list[str]:
    mapped_documents = [
        source_reference_map.get(document, document)
        for document in documents
        if document and document != "A confirmar"
    ]
    if not mapped_documents or all(_is_source_reference(document) for document in documents):
        mapped_documents.extend(
            source_reference_map[source_ref]
            for source_ref in source_refs
            if source_ref in source_reference_map
        )
    return _unique_preserving_order(mapped_documents)


def _is_source_reference(value: str) -> bool:
    return value.strip().casefold().startswith("fonte ")


def _count_by(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        content_items = _get_value(item, "content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            text = _get_value(content_item, "text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _load_json_object(response_text: str) -> dict[str, Any]:
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.strip("`")
        if clean_text.lower().startswith("json"):
            clean_text = clean_text[4:].strip()
    try:
        value = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise ComparisonGenerationError(
            "A IA retornou a comparação documental em formato inesperado."
        ) from exc
    if not isinstance(value, dict):
        raise ComparisonGenerationError(
            "A IA retornou a comparação documental em formato inesperado."
        )
    return value


def _normalize_issue_type(value: object) -> str:
    issue_type = _text(value, "Outro").strip().title()
    valid_issue_types = {
        "Cronograma",
        "Responsável",
        "Decisão",
        "Risco",
        "Escopo",
        "Evidência",
        "Outro",
    }
    return issue_type if issue_type in valid_issue_types else "Outro"


def _normalize_severity(value: object) -> str:
    severity = _text(value, "Média").strip().title()
    return severity if severity in {"Alta", "Média", "Baixa"} else "Média"


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
