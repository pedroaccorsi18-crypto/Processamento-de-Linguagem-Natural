from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Any

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.spreadsheet_export import table_to_xlsx

logger = logging.getLogger(__name__)


class IntelligenceGenerationError(RuntimeError):
    """Raised when structured organizational intelligence cannot be generated."""


@dataclass(frozen=True)
class IntelligenceFinding:
    category: str
    title: str
    description: str
    severity: str
    responsible: str
    deadline: str
    evidence: str
    recommendation: str
    source_refs: list[str]


@dataclass(frozen=True)
class IntelligenceSnapshot:
    executive_summary: str
    findings: list[IntelligenceFinding]
    sources: list[SourceSnippet]


def generate_intelligence_snapshot(
    client: Any,
    sources: list[SourceSnippet],
    model: str,
) -> IntelligenceSnapshot:
    if not sources:
        raise IntelligenceGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_intelligence_instructions(),
            input=_build_intelligence_input(sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Structured intelligence generation failed: %s", exc.__class__.__name__)
        raise IntelligenceGenerationError(
            "Não foi possível gerar a inteligência organizacional."
        ) from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    findings = _parse_findings(payload.get("findings"))
    if not findings:
        raise IntelligenceGenerationError(
            "A IA não encontrou decisões, riscos ou inconsistências claras nos documentos."
        )
    return IntelligenceSnapshot(
        executive_summary=_text(
            payload.get("executive_summary"),
            "Síntese estruturada não disponível.",
        ),
        findings=findings,
        sources=sources,
    )


def serialize_intelligence_findings(
    findings: list[IntelligenceFinding],
) -> list[dict[str, object]]:
    return [
        {
            "category": finding.category,
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "responsible": finding.responsible,
            "deadline": finding.deadline,
            "evidence": finding.evidence,
            "recommendation": finding.recommendation,
            "source_refs": finding.source_refs,
        }
        for finding in findings
    ]


def intelligence_snapshot_to_markdown(snapshot: IntelligenceSnapshot) -> str:
    lines = [
        "# Inteligência organizacional - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        snapshot.executive_summary,
        "",
        "## Achados estruturados",
        "",
    ]
    for index, finding in enumerate(snapshot.findings, start=1):
        refs = ", ".join(finding.source_refs) if finding.source_refs else "Fonte não indicada"
        lines.extend(
            [
                f"### {index}. {finding.title}",
                f"- Categoria: {finding.category}",
                f"- Severidade: {finding.severity}",
                f"- Responsável: {finding.responsible}",
                f"- Prazo: {finding.deadline}",
                f"- Evidência: {finding.evidence}",
                f"- Recomendação: {finding.recommendation}",
                f"- Fontes: {refs}",
                "",
                finding.description,
                "",
            ]
        )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "Esta leitura estrutura sinais dos documentos selecionados. Antes de qualquer decisão "
        "operacional, jurídica ou financeira, valide os achados com as áreas responsáveis."
    )
    return "\n".join(lines).strip() + "\n"


def intelligence_snapshot_to_csv(snapshot: IntelligenceSnapshot) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "categoria",
            "título",
            "descrição",
            "severidade",
            "responsável",
            "prazo",
            "evidência",
            "recomendação",
            "fontes",
        ],
    )
    writer.writeheader()
    for finding in snapshot.findings:
        writer.writerow(
            {
                "categoria": finding.category,
                "título": finding.title,
                "descrição": finding.description,
                "severidade": finding.severity,
                "responsável": finding.responsible,
                "prazo": finding.deadline,
                "evidência": finding.evidence,
                "recomendação": finding.recommendation,
                "fontes": ", ".join(finding.source_refs),
            }
        )
    return output.getvalue()


def intelligence_snapshot_to_xlsx(snapshot: IntelligenceSnapshot) -> bytes:
    headers = [
        "Categoria",
        "Título",
        "Descrição",
        "Severidade",
        "Responsável",
        "Prazo",
        "Evidência",
        "Recomendação",
        "Fontes",
    ]
    rows = [
        [
            finding.category,
            finding.title,
            finding.description,
            finding.severity,
            finding.responsible,
            finding.deadline,
            finding.evidence,
            finding.recommendation,
            ", ".join(finding.source_refs),
        ]
        for finding in snapshot.findings
    ]
    return table_to_xlsx(
        headers,
        rows,
        sheet_name="Inteligência",
        column_widths=[18, 34, 58, 14, 26, 18, 58, 58, 20],
    )


def _intelligence_instructions() -> str:
    return (
        "Você é o Synapse AI atuando como uma camada de inteligência organizacional. "
        "Extraia sinais estruturados dos documentos fornecidos. Use apenas as fontes "
        "recuperadas; não invente fatos, datas, responsáveis ou decisões. Classifique cada "
        "achado em uma destas categorias: Decisão, Risco, Inconsistência, Pendência, Prazo, "
        "Responsável ou Recomendação. Use severidade Alta, Média ou Baixa. Quando um campo "
        "não estiver claro, use 'A confirmar'. Responda somente com JSON válido no formato: "
        '{"executive_summary":"...","findings":[{"category":"Decisão|Risco|'
        'Inconsistência|Pendência|Prazo|Responsável|Recomendação","title":"...",'
        '"description":"...","severity":"Alta|Média|Baixa","responsible":"...",'
        '"deadline":"...","evidence":"...","recommendation":"...",'
        '"source_refs":["Fonte 1"]}]}'
    )


def _build_intelligence_input(sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return (
        "Objetivo: gerar uma fotografia estruturada de inteligência organizacional com "
        "decisões, riscos, inconsistências, pendências, prazos, responsáveis e recomendações.\n\n"
        f"Fontes recuperadas:\n{rendered_sources}"
    )


def _parse_findings(value: object) -> list[IntelligenceFinding]:
    if not isinstance(value, list):
        return []
    findings: list[IntelligenceFinding] = []
    for raw_finding in value:
        if not isinstance(raw_finding, dict):
            continue
        title = _text(raw_finding.get("title"), "")
        if not title:
            continue
        findings.append(
            IntelligenceFinding(
                category=_normalize_category(raw_finding.get("category")),
                title=title,
                description=_text(raw_finding.get("description"), "A confirmar"),
                severity=_normalize_severity(raw_finding.get("severity")),
                responsible=_text(raw_finding.get("responsible"), "A confirmar"),
                deadline=_text(raw_finding.get("deadline"), "A confirmar"),
                evidence=_text(raw_finding.get("evidence"), "A confirmar"),
                recommendation=_text(raw_finding.get("recommendation"), "A confirmar"),
                source_refs=_text_list(raw_finding.get("source_refs")),
            )
        )
    return findings


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
        raise IntelligenceGenerationError(
            "A IA retornou a inteligência estruturada em formato inesperado."
        ) from exc
    if not isinstance(value, dict):
        raise IntelligenceGenerationError(
            "A IA retornou a inteligência estruturada em formato inesperado."
        )
    return value


def _normalize_category(value: object) -> str:
    category = _text(value, "Pendência").strip().title()
    valid_categories = {
        "Decisão",
        "Risco",
        "Inconsistência",
        "Pendência",
        "Prazo",
        "Responsável",
        "Recomendação",
    }
    return category if category in valid_categories else "Pendência"


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
