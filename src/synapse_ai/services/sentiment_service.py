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


class SentimentGenerationError(RuntimeError):
    """Raised when organizational sentiment cannot be generated."""


@dataclass(frozen=True)
class SentimentSignal:
    dimension: str
    label: str
    intensity: str
    polarity: float
    evidence: str
    interpretation: str
    recommendation: str
    source_refs: list[str]


@dataclass(frozen=True)
class SentimentReport:
    overall_sentiment: str
    executive_summary: str
    risk_level: str
    dominant_signals: list[str]
    signals: list[SentimentSignal]
    sources: list[SourceSnippet]


def generate_sentiment_report(
    client: Any,
    sources: list[SourceSnippet],
    model: str,
) -> SentimentReport:
    if not sources:
        raise SentimentGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_sentiment_instructions(),
            input=_build_sentiment_input(sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Organizational sentiment generation failed: %s", exc.__class__.__name__)
        raise SentimentGenerationError(
            "Não foi possível gerar a análise de sentimentos organizacionais."
        ) from exc

    response_text = _extract_response_text(response)
    payload = _load_json_object(response_text)
    signals = _parse_signals(payload.get("signals"))
    if not signals:
        raise SentimentGenerationError(
            "A IA não encontrou sinais de sentimento organizacional claros neste escopo."
        )
    return SentimentReport(
        overall_sentiment=_normalize_overall_sentiment(payload.get("overall_sentiment")),
        executive_summary=_text(payload.get("executive_summary"), "Síntese não disponível."),
        risk_level=_normalize_risk_level(payload.get("risk_level")),
        dominant_signals=_text_list(payload.get("dominant_signals")),
        signals=signals,
        sources=sources,
    )


def serialize_sentiment_signals(signals: list[SentimentSignal]) -> list[dict[str, object]]:
    return [
        {
            "dimension": signal.dimension,
            "label": signal.label,
            "intensity": signal.intensity,
            "polarity": signal.polarity,
            "evidence": signal.evidence,
            "interpretation": signal.interpretation,
            "recommendation": signal.recommendation,
            "source_refs": signal.source_refs,
        }
        for signal in signals
    ]


def sentiment_report_to_markdown(report: SentimentReport) -> str:
    dominant_signals = (
        ", ".join(report.dominant_signals) if report.dominant_signals else "A confirmar"
    )
    lines = [
        "# Análise de sentimentos organizacionais - Synapse AI",
        "",
        "## Síntese executiva",
        "",
        report.executive_summary,
        "",
        "## Indicadores gerais",
        "",
        f"- Sentimento predominante: {report.overall_sentiment}",
        f"- Nível de risco comunicacional: {report.risk_level}",
        f"- Sinais dominantes: {dominant_signals}",
        "",
        "## Sinais identificados",
        "",
    ]
    for index, signal in enumerate(report.signals, start=1):
        refs = ", ".join(signal.source_refs) if signal.source_refs else "Fonte não indicada"
        lines.extend(
            [
                f"### {index}. {signal.dimension}",
                f"- Classificação: {signal.label}",
                f"- Intensidade: {signal.intensity}",
                f"- Polaridade: {signal.polarity:.2f}",
                f"- Evidência: {signal.evidence}",
                f"- Interpretação: {signal.interpretation}",
                f"- Recomendação: {signal.recommendation}",
                f"- Fontes: {refs}",
                "",
            ]
        )
    lines.extend(["## Nota de governança", ""])
    lines.append(
        "Esta análise interpreta sinais textuais dos documentos selecionados. Ela não avalia "
        "pessoas individualmente e deve ser usada como apoio à leitura organizacional, sempre "
        "com validação humana."
    )
    return "\n".join(lines).strip() + "\n"


def sentiment_report_to_csv(report: SentimentReport) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "dimensão",
            "classificação",
            "intensidade",
            "polaridade",
            "evidência",
            "interpretação",
            "recomendação",
            "fontes",
        ],
    )
    writer.writeheader()
    for signal in report.signals:
        writer.writerow(
            {
                "dimensão": signal.dimension,
                "classificação": signal.label,
                "intensidade": signal.intensity,
                "polaridade": f"{signal.polarity:.2f}",
                "evidência": signal.evidence,
                "interpretação": signal.interpretation,
                "recomendação": signal.recommendation,
                "fontes": ", ".join(signal.source_refs),
            }
        )
    return output.getvalue()


def sentiment_report_to_xlsx(report: SentimentReport) -> bytes:
    dominant_signals = (
        ", ".join(report.dominant_signals) if report.dominant_signals else "A confirmar"
    )
    signal_headers = [
        "Dimensão",
        "Classificação",
        "Intensidade",
        "Polaridade",
        "Evidência",
        "Interpretação",
        "Recomendação",
        "Fontes",
    ]
    signal_rows = [
        [
            signal.dimension,
            signal.label,
            signal.intensity,
            f"{signal.polarity:.2f}",
            signal.evidence,
            signal.interpretation,
            signal.recommendation,
            ", ".join(signal.source_refs),
        ]
        for signal in report.signals
    ]
    return workbook_to_xlsx(
        [
            XlsxSheet(
                name="Resumo",
                headers=["Indicador", "Resultado"],
                rows=[
                    ["Síntese executiva", report.executive_summary],
                    ["Sentimento predominante", report.overall_sentiment],
                    ["Nível de risco comunicacional", report.risk_level],
                    ["Sinais dominantes", dominant_signals],
                    ["Total de sinais", len(report.signals)],
                ],
                column_widths=[34, 86],
            ),
            XlsxSheet(
                name="Sinais",
                headers=signal_headers,
                rows=signal_rows,
                column_widths=[24, 18, 16, 14, 58, 58, 58, 20],
            ),
        ]
    )


def _sentiment_instructions() -> str:
    return (
        "Você é o Synapse AI atuando como analista de PLN e sentimentos organizacionais. "
        "Analise o tom textual dos documentos selecionados, procurando sinais de urgência, "
        "tensão, confiança, alinhamento, conflito, frustração, risco percebido e abertura para "
        "colaboração. Use apenas as fontes fornecidas; não invente fatos e não faça julgamento "
        "psicológico de pessoas. Responda em português do Brasil com ortografia e acentuação "
        "corretas. Use overall_sentiment como Positivo, Neutro, Negativo ou Misto. Use "
        "risk_level como Baixo, Médio ou Alto. Para cada sinal, use label como Positivo, "
        "Neutro, Negativo ou Misto; intensity como Baixa, Média ou Alta; polarity como número "
        "entre -1.0 e 1.0. Quando um campo não estiver claro, use 'A confirmar'. Responda "
        "somente com JSON válido no formato: "
        '{"overall_sentiment":"Positivo|Neutro|Negativo|Misto",'
        '"executive_summary":"...","risk_level":"Baixo|Médio|Alto",'
        '"dominant_signals":["..."],"signals":[{"dimension":"Urgência|Tensão|'
        'Confiança|Alinhamento|Conflito|Frustração|Risco percebido|Outro",'
        '"label":"Positivo|Neutro|Negativo|Misto","intensity":"Baixa|Média|Alta",'
        '"polarity":0.0,"evidence":"...","interpretation":"...",'
        '"recommendation":"...","source_refs":["Fonte 1"]}]}'
    )


def _build_sentiment_input(sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return (
        "Objetivo: identificar sinais de sentimento organizacional, tom comunicacional, "
        "urgência, tensão, confiança, conflito, frustração e risco percebido nos documentos.\n\n"
        f"Fontes recuperadas:\n{rendered_sources}"
    )


def _parse_signals(value: object) -> list[SentimentSignal]:
    if not isinstance(value, list):
        return []
    signals: list[SentimentSignal] = []
    for raw_signal in value:
        if not isinstance(raw_signal, dict):
            continue
        dimension = _normalize_dimension(raw_signal.get("dimension"))
        if not dimension:
            continue
        signals.append(
            SentimentSignal(
                dimension=dimension,
                label=_normalize_sentiment_label(raw_signal.get("label")),
                intensity=_normalize_intensity(raw_signal.get("intensity")),
                polarity=_normalize_polarity(raw_signal.get("polarity")),
                evidence=_text(raw_signal.get("evidence"), "A confirmar"),
                interpretation=_text(raw_signal.get("interpretation"), "A confirmar"),
                recommendation=_text(raw_signal.get("recommendation"), "A confirmar"),
                source_refs=_text_list(raw_signal.get("source_refs")),
            )
        )
    return signals


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
        raise SentimentGenerationError(
            "A IA retornou a análise de sentimentos em formato inesperado."
        ) from exc
    if not isinstance(value, dict):
        raise SentimentGenerationError(
            "A IA retornou a análise de sentimentos em formato inesperado."
        )
    return value


def _normalize_dimension(value: object) -> str:
    dimension = _text(value, "Outro").strip().title()
    valid_dimensions = {
        "Urgência",
        "Tensão",
        "Confiança",
        "Alinhamento",
        "Conflito",
        "Frustração",
        "Risco Percebido",
        "Outro",
    }
    return dimension if dimension in valid_dimensions else "Outro"


def _normalize_overall_sentiment(value: object) -> str:
    sentiment = _text(value, "Misto").strip().title()
    return sentiment if sentiment in {"Positivo", "Neutro", "Negativo", "Misto"} else "Misto"


def _normalize_sentiment_label(value: object) -> str:
    return _normalize_overall_sentiment(value)


def _normalize_risk_level(value: object) -> str:
    risk_level = _text(value, "Médio").strip().title()
    return risk_level if risk_level in {"Baixo", "Médio", "Alto"} else "Médio"


def _normalize_intensity(value: object) -> str:
    intensity = _text(value, "Média").strip().title()
    return intensity if intensity in {"Baixa", "Média", "Alta"} else "Média"


def _normalize_polarity(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.0
    return max(min(float(value), 1.0), -1.0)


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
