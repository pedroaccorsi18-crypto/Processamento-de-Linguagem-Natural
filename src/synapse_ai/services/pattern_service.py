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


class PatternGenerationError(RuntimeError):
    """Raised when historical patterns cannot be generated."""


@dataclass(frozen=True)
class HistoricalPattern:
    pattern_type: str
    title: str
    recurrence: str
    severity: str
    current_signal: str
    historical_evidence: str
    interpretation: str
    recommendation: str
    source_refs: list[str]
    related_records: list[str]


@dataclass(frozen=True)
class HistoricalPatternReport:
    executive_summary: str
    patterns: list[HistoricalPattern]
    sources: list[SourceSnippet]
    historical_record_count: int


def generate_historical_pattern_report(
    client: Any,
    current_sources: list[SourceSnippet],
    historical_analyses: list[dict[str, object]],
    model: str,
) -> HistoricalPatternReport:
    if not current_sources:
        raise PatternGenerationError("Nenhum trecho relevante foi encontrado.")

    history_digest = build_history_digest(historical_analyses)
    if not history_digest:
        raise PatternGenerationError(
            "Ainda não há histórico suficiente para reconhecer padrões recorrentes."
        )

    try:
        response = client.responses.create(
            model=model,
            instructions=_pattern_instructions(),
            input=_build_pattern_input(current_sources, history_digest),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Historical pattern generation failed: %s", exc.__class__.__name__)
        raise PatternGenerationError("Não foi possível reconhecer padrões históricos.") from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    patterns = _parse_patterns(payload.get("patterns"))
    if not patterns:
        raise PatternGenerationError(
            "A IA não encontrou padrões históricos claros para o escopo selecionado."
        )
    return HistoricalPatternReport(
        executive_summary=_text(payload.get("executive_summary"), "Síntese não disponível."),
        patterns=patterns,
        sources=current_sources,
        historical_record_count=len(history_digest),
    )


def build_history_digest(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    digest: list[dict[str, object]] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        artifact_type = str(metadata.get("artifact_type") or "question_answer")
        if artifact_type == "historical_pattern_report":
            continue
        signals = _metadata_signals(metadata)
        if not signals:
            continue
        digest.append(
            {
                "title": str(analysis.get("title") or "Registro sem título"),
                "created_at": str(analysis.get("created_at") or ""),
                "artifact_type": artifact_type,
                "signals": signals[:8],
            }
        )
    return digest[:20]


def serialize_historical_patterns(patterns: list[HistoricalPattern]) -> list[dict[str, object]]:
    return [
        {
            "pattern_type": pattern.pattern_type,
            "title": pattern.title,
            "recurrence": pattern.recurrence,
            "severity": pattern.severity,
            "current_signal": pattern.current_signal,
            "historical_evidence": pattern.historical_evidence,
            "interpretation": pattern.interpretation,
            "recommendation": pattern.recommendation,
            "source_refs": pattern.source_refs,
            "related_records": pattern.related_records,
        }
        for pattern in patterns
    ]


def historical_pattern_report_to_markdown(report: HistoricalPatternReport) -> str:
    lines = [
        "# Padrões históricos - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        f"Registros históricos considerados: {report.historical_record_count}",
        "",
        "## Padrões reconhecidos",
        "",
    ]
    for index, pattern in enumerate(report.patterns, start=1):
        refs = ", ".join(pattern.source_refs) if pattern.source_refs else "Fonte não indicada"
        records = (
            ", ".join(pattern.related_records)
            if pattern.related_records
            else "Registro não indicado"
        )
        lines.extend(
            [
                f"### {index}. {pattern.title}",
                f"- Tipo: {pattern.pattern_type}",
                f"- Recorrência: {pattern.recurrence}",
                f"- Severidade: {pattern.severity}",
                f"- Sinal atual: {pattern.current_signal}",
                f"- Evidência histórica: {pattern.historical_evidence}",
                f"- Interpretação: {pattern.interpretation}",
                f"- Recomendação: {pattern.recommendation}",
                f"- Fontes atuais: {refs}",
                f"- Registros relacionados: {records}",
                "",
            ]
        )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "O reconhecimento de padrões usa histórico salvo pelo próprio usuário. A recorrência "
        "deve ser interpretada como sinal de apoio à decisão, não como prova causal automática."
    )
    return "\n".join(lines).strip() + "\n"


def historical_pattern_report_to_csv(report: HistoricalPatternReport) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "tipo",
            "título",
            "recorrência",
            "severidade",
            "sinal_atual",
            "evidência_histórica",
            "interpretação",
            "recomendação",
            "fontes_atuais",
            "registros_relacionados",
        ],
    )
    writer.writeheader()
    for pattern in report.patterns:
        writer.writerow(
            {
                "tipo": pattern.pattern_type,
                "título": pattern.title,
                "recorrência": pattern.recurrence,
                "severidade": pattern.severity,
                "sinal_atual": pattern.current_signal,
                "evidência_histórica": pattern.historical_evidence,
                "interpretação": pattern.interpretation,
                "recomendação": pattern.recommendation,
                "fontes_atuais": ", ".join(pattern.source_refs),
                "registros_relacionados": ", ".join(pattern.related_records),
            }
        )
    return output.getvalue()


def historical_pattern_report_to_xlsx(report: HistoricalPatternReport) -> bytes:
    severity_counts = _count_by([pattern.severity for pattern in report.patterns])
    type_counts = _count_by([pattern.pattern_type for pattern in report.patterns])
    pattern_headers = [
        "Tipo",
        "Título",
        "Recorrência",
        "Severidade",
        "Sinal atual",
        "Evidência histórica",
        "Interpretação",
        "Recomendação",
        "Fontes atuais",
        "Registros relacionados",
    ]
    pattern_rows = [
        [
            pattern.pattern_type,
            pattern.title,
            pattern.recurrence,
            pattern.severity,
            pattern.current_signal,
            pattern.historical_evidence,
            pattern.interpretation,
            pattern.recommendation,
            ", ".join(pattern.source_refs),
            ", ".join(pattern.related_records),
        ]
        for pattern in report.patterns
    ]
    return workbook_to_xlsx(
        [
            XlsxSheet(
                name="Resumo",
                headers=["Indicador", "Resultado"],
                rows=[
                    ["Síntese executiva", report.executive_summary],
                    ["Registros históricos considerados", report.historical_record_count],
                    ["Total de padrões", len(report.patterns)],
                    ["Severidade alta", severity_counts.get("Alta", 0)],
                    ["Severidade média", severity_counts.get("Média", 0)],
                    ["Severidade baixa", severity_counts.get("Baixa", 0)],
                    [
                        "Tipos identificados",
                        ", ".join(f"{key}: {value}" for key, value in type_counts.items())
                        or "A confirmar",
                    ],
                ],
                column_widths=[36, 86],
            ),
            XlsxSheet(
                name="Padrões",
                headers=pattern_headers,
                rows=pattern_rows,
                column_widths=[22, 36, 26, 14, 58, 58, 58, 58, 20, 44],
            ),
        ]
    )


def _pattern_instructions() -> str:
    return (
        "Você é o Synapse AI analisando memória institucional. Compare os sinais atuais dos "
        "documentos selecionados com o histórico salvo de análises anteriores. Identifique "
        "padrões recorrentes, como atrasos por aprovação financeira, responsáveis ausentes, "
        "mudanças de cronograma, riscos repetidos, tensão comunicacional recorrente, lacunas de "
        "evidência ou decisões conflitantes já observadas. Use apenas as fontes atuais e o "
        "histórico fornecido; não invente casos anteriores. Se a recorrência for fraca, explique "
        "a limitação. Use severidade Alta, Média ou Baixa. Responda somente com JSON válido no "
        "formato: "
        '{"executive_summary":"...","patterns":[{"pattern_type":"Prazo|Responsável|'
        'Orçamento|Risco|Comunicação|Evidência|Decisão|Outro","title":"...",'
        '"recurrence":"...", "severity":"Alta|Média|Baixa", "current_signal":"...",'
        '"historical_evidence":"...", "interpretation":"...", "recommendation":"...",'
        '"source_refs":["Fonte 1"],"related_records":["..."]}]}'
    )


def _build_pattern_input(
    current_sources: list[SourceSnippet],
    history_digest: list[dict[str, object]],
) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(current_sources, start=1)
    )
    rendered_history = json.dumps(history_digest, ensure_ascii=False, indent=2)
    return (
        "Objetivo: reconhecer padrões históricos comparando sinais atuais com análises salvas.\n\n"
        f"Sinais atuais recuperados:\n{rendered_sources}\n\n"
        f"Histórico salvo resumido:\n{rendered_history}"
    )


def _metadata_signals(metadata: dict[str, object]) -> list[str]:
    signals: list[str] = []
    for item in _dict_items(metadata.get("findings")):
        signals.append(
            _join_parts(
                item.get("category"),
                item.get("title"),
                item.get("severity"),
                item.get("evidence"),
                item.get("recommendation"),
            )
        )
    for item in _dict_items(metadata.get("issues")):
        signals.append(
            _join_parts(
                item.get("issue_type"),
                item.get("title"),
                item.get("severity"),
                item.get("evidence"),
                item.get("recommendation"),
            )
        )
    for item in _dict_items(metadata.get("alerts")):
        signals.append(
            _join_parts(
                item.get("alert_type"),
                item.get("title"),
                item.get("severity"),
                item.get("trigger"),
                item.get("recommendation"),
            )
        )
    for item in _dict_items(metadata.get("signals")):
        signals.append(
            _join_parts(
                item.get("dimension"),
                item.get("label"),
                item.get("intensity"),
                item.get("evidence"),
                item.get("recommendation"),
            )
        )
    for item in _dict_items(metadata.get("items")):
        signals.append(
            _join_parts(
                item.get("task"),
                item.get("priority"),
                item.get("risk"),
                item.get("evidence"),
            )
        )
    return [signal for signal in signals if signal]


def _parse_patterns(value: object) -> list[HistoricalPattern]:
    if not isinstance(value, list):
        return []
    patterns: list[HistoricalPattern] = []
    for raw_pattern in value:
        if not isinstance(raw_pattern, dict):
            continue
        title = _text(raw_pattern.get("title"), "")
        if not title:
            continue
        patterns.append(
            HistoricalPattern(
                pattern_type=_normalize_pattern_type(raw_pattern.get("pattern_type")),
                title=title,
                recurrence=_text(raw_pattern.get("recurrence"), "A confirmar"),
                severity=_normalize_severity(raw_pattern.get("severity")),
                current_signal=_text(raw_pattern.get("current_signal"), "A confirmar"),
                historical_evidence=_text(raw_pattern.get("historical_evidence"), "A confirmar"),
                interpretation=_text(raw_pattern.get("interpretation"), "A confirmar"),
                recommendation=_text(raw_pattern.get("recommendation"), "A confirmar"),
                source_refs=_text_list(raw_pattern.get("source_refs")),
                related_records=_text_list(raw_pattern.get("related_records")),
            )
        )
    return patterns


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
        raise PatternGenerationError("A IA retornou padrões em formato inesperado.") from exc
    if not isinstance(value, dict):
        raise PatternGenerationError("A IA retornou padrões em formato inesperado.")
    return value


def _normalize_pattern_type(value: object) -> str:
    pattern_type = _text(value, "Outro").strip().title()
    valid_types = {
        "Prazo",
        "Responsável",
        "Orçamento",
        "Risco",
        "Comunicação",
        "Evidência",
        "Decisão",
        "Outro",
    }
    return pattern_type if pattern_type in valid_types else "Outro"


def _normalize_severity(value: object) -> str:
    severity = _text(value, "Média").strip().title()
    return severity if severity in {"Alta", "Média", "Baixa"} else "Média"


def _dict_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _join_parts(*values: object) -> str:
    return " | ".join(value.strip() for value in values if isinstance(value, str) and value.strip())


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
