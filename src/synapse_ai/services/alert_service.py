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


class AlertGenerationError(RuntimeError):
    """Raised when preventive alerts cannot be generated."""


@dataclass(frozen=True)
class PreventiveAlert:
    alert_type: str
    title: str
    severity: str
    status: str
    trigger: str
    evidence: str
    impact: str
    recommendation: str
    owner: str
    deadline: str
    source_refs: list[str]


@dataclass(frozen=True)
class PreventiveAlertReport:
    executive_summary: str
    alerts: list[PreventiveAlert]
    sources: list[SourceSnippet]


def generate_preventive_alert_report(
    client: Any,
    sources: list[SourceSnippet],
    model: str,
) -> PreventiveAlertReport:
    if not sources:
        raise AlertGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_alert_instructions(),
            input=_build_alert_input(sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preventive alert generation failed: %s", exc.__class__.__name__)
        raise AlertGenerationError("Não foi possível gerar alertas preventivos.") from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    alerts = _parse_alerts(payload.get("alerts"))
    if not alerts:
        raise AlertGenerationError(
            "A IA não encontrou alertas preventivos claros nos documentos selecionados."
        )
    return PreventiveAlertReport(
        executive_summary=_text(payload.get("executive_summary"), "Síntese não disponível."),
        alerts=alerts,
        sources=sources,
    )


def serialize_preventive_alerts(alerts: list[PreventiveAlert]) -> list[dict[str, object]]:
    return [
        {
            "alert_type": alert.alert_type,
            "title": alert.title,
            "severity": alert.severity,
            "status": alert.status,
            "trigger": alert.trigger,
            "evidence": alert.evidence,
            "impact": alert.impact,
            "recommendation": alert.recommendation,
            "owner": alert.owner,
            "deadline": alert.deadline,
            "source_refs": alert.source_refs,
        }
        for alert in alerts
    ]


def preventive_alert_report_to_markdown(report: PreventiveAlertReport) -> str:
    lines = [
        "# Alertas preventivos - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        "## Alertas identificados",
        "",
    ]
    for index, alert in enumerate(report.alerts, start=1):
        refs = ", ".join(alert.source_refs) if alert.source_refs else "Fonte não indicada"
        lines.extend(
            [
                f"### {index}. {alert.title}",
                f"- Tipo: {alert.alert_type}",
                f"- Severidade: {alert.severity}",
                f"- Status sugerido: {alert.status}",
                f"- Gatilho: {alert.trigger}",
                f"- Evidência: {alert.evidence}",
                f"- Impacto provável: {alert.impact}",
                f"- Recomendação: {alert.recommendation}",
                f"- Responsável sugerido: {alert.owner}",
                f"- Prazo sugerido: {alert.deadline}",
                f"- Fontes: {refs}",
                "",
            ]
        )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "Os alertas indicam sinais preventivos encontrados nos documentos selecionados. Eles não "
        "executam ações automaticamente e devem ser validados pelas áreas responsáveis antes de "
        "qualquer decisão operacional, jurídica ou financeira."
    )
    return "\n".join(lines).strip() + "\n"


def preventive_alert_report_to_csv(report: PreventiveAlertReport) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "tipo",
            "título",
            "severidade",
            "status",
            "gatilho",
            "evidência",
            "impacto",
            "recomendação",
            "responsável",
            "prazo",
            "fontes",
        ],
    )
    writer.writeheader()
    for alert in report.alerts:
        writer.writerow(
            {
                "tipo": alert.alert_type,
                "título": alert.title,
                "severidade": alert.severity,
                "status": alert.status,
                "gatilho": alert.trigger,
                "evidência": alert.evidence,
                "impacto": alert.impact,
                "recomendação": alert.recommendation,
                "responsável": alert.owner,
                "prazo": alert.deadline,
                "fontes": ", ".join(alert.source_refs),
            }
        )
    return output.getvalue()


def preventive_alert_report_to_xlsx(report: PreventiveAlertReport) -> bytes:
    severity_counts = _count_by([alert.severity for alert in report.alerts])
    type_counts = _count_by([alert.alert_type for alert in report.alerts])
    alert_headers = [
        "Tipo",
        "Título",
        "Severidade",
        "Status",
        "Gatilho",
        "Evidência",
        "Impacto",
        "Recomendação",
        "Responsável",
        "Prazo",
        "Fontes",
    ]
    alert_rows = [
        [
            alert.alert_type,
            alert.title,
            alert.severity,
            alert.status,
            alert.trigger,
            alert.evidence,
            alert.impact,
            alert.recommendation,
            alert.owner,
            alert.deadline,
            ", ".join(alert.source_refs),
        ]
        for alert in report.alerts
    ]
    return workbook_to_xlsx(
        [
            XlsxSheet(
                name="Resumo",
                headers=["Indicador", "Resultado"],
                rows=[
                    ["Síntese executiva", report.executive_summary],
                    ["Total de alertas", len(report.alerts)],
                    ["Severidade crítica", severity_counts.get("Crítica", 0)],
                    ["Severidade alta", severity_counts.get("Alta", 0)],
                    ["Severidade média", severity_counts.get("Média", 0)],
                    ["Severidade baixa", severity_counts.get("Baixa", 0)],
                    [
                        "Tipos identificados",
                        ", ".join(f"{key}: {value}" for key, value in type_counts.items())
                        or "A confirmar",
                    ],
                ],
                column_widths=[34, 86],
            ),
            XlsxSheet(
                name="Alertas",
                headers=alert_headers,
                rows=alert_rows,
                column_widths=[24, 36, 16, 18, 48, 58, 58, 58, 26, 18, 20],
            ),
        ]
    )


def _alert_instructions() -> str:
    return (
        "Você é o Synapse AI atuando como um sistema de alertas preventivos para inteligência "
        "organizacional. Identifique sinais que merecem atenção antes que virem problema, como "
        "prazo crítico, decisão conflitante, responsável ausente, risco alto sem plano, "
        "aprovação pendente, mudança de cronograma, dependência externa, lacuna de evidência, "
        "tensão comunicacional ou documento sem definição operacional. Use apenas as fontes "
        "fornecidas; não invente fatos, datas, responsáveis ou decisões. Escreva em português "
        "do Brasil com ortografia e acentuação corretas. Use severidade Crítica, Alta, Média "
        "ou Baixa. Use status Aberto, Em acompanhamento ou A confirmar. Quando um campo não "
        "estiver claro, use 'A confirmar'. Responda somente com JSON válido no formato: "
        '{"executive_summary":"...","alerts":[{"alert_type":"Prazo|Responsável|'
        'Decisão|Risco|Orçamento|Comunicação|Evidência|Dependência|Outro",'
        '"title":"...","severity":"Crítica|Alta|Média|Baixa","status":"Aberto|'
        'Em acompanhamento|A confirmar","trigger":"...","evidence":"...",'
        '"impact":"...","recommendation":"...","owner":"...","deadline":"...",'
        '"source_refs":["Fonte 1"]}]}'
    )


def _build_alert_input(sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return (
        "Objetivo: gerar alertas preventivos acionáveis a partir de decisões, riscos, prazos, "
        "pendências, responsáveis, orçamento, comunicação e lacunas de evidência.\n\n"
        f"Fontes recuperadas:\n{rendered_sources}"
    )


def _parse_alerts(value: object) -> list[PreventiveAlert]:
    if not isinstance(value, list):
        return []
    alerts: list[PreventiveAlert] = []
    for raw_alert in value:
        if not isinstance(raw_alert, dict):
            continue
        title = _text(raw_alert.get("title"), "")
        if not title:
            continue
        alerts.append(
            PreventiveAlert(
                alert_type=_normalize_alert_type(raw_alert.get("alert_type")),
                title=title,
                severity=_normalize_severity(raw_alert.get("severity")),
                status=_normalize_status(raw_alert.get("status")),
                trigger=_text(raw_alert.get("trigger"), "A confirmar"),
                evidence=_text(raw_alert.get("evidence"), "A confirmar"),
                impact=_text(raw_alert.get("impact"), "A confirmar"),
                recommendation=_text(raw_alert.get("recommendation"), "A confirmar"),
                owner=_text(raw_alert.get("owner"), "A confirmar"),
                deadline=_text(raw_alert.get("deadline"), "A confirmar"),
                source_refs=_text_list(raw_alert.get("source_refs")),
            )
        )
    return alerts


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
        raise AlertGenerationError("A IA retornou alertas em formato inesperado.") from exc
    if not isinstance(value, dict):
        raise AlertGenerationError("A IA retornou alertas em formato inesperado.")
    return value


def _normalize_alert_type(value: object) -> str:
    alert_type = _text(value, "Outro").strip().title()
    valid_types = {
        "Prazo",
        "Responsável",
        "Decisão",
        "Risco",
        "Orçamento",
        "Comunicação",
        "Evidência",
        "Dependência",
        "Outro",
    }
    return alert_type if alert_type in valid_types else "Outro"


def _normalize_severity(value: object) -> str:
    severity = _text(value, "Média").strip().title()
    return severity if severity in {"Crítica", "Alta", "Média", "Baixa"} else "Média"


def _normalize_status(value: object) -> str:
    status = _text(value, "Aberto").strip().casefold()
    if status == "em acompanhamento":
        return "Em acompanhamento"
    if status == "a confirmar":
        return "A confirmar"
    if status == "aberto":
        return "Aberto"
    return "Aberto"


def _count_by(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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
