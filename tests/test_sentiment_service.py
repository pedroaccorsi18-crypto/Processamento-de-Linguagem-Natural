from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.sentiment_service import (
    SentimentGenerationError,
    generate_sentiment_report,
    sentiment_report_to_csv,
    sentiment_report_to_markdown,
    sentiment_report_to_xlsx,
)


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: dict[str, object] = {}

    def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:  # noqa: A002
        self.calls = {"model": model, "instructions": instructions, "input": input}
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def _sources() -> list[SourceSnippet]:
    return [
        SourceSnippet(
            "doc-1",
            "ata.pdf",
            0,
            "A equipe demonstrou preocupação com o prazo e pediu validação urgente.",
            0.92,
        )
    ]


def test_generate_sentiment_report_parses_structured_signals() -> None:
    responses = FakeResponses(
        """
        {
          "overall_sentiment": "Misto",
          "executive_summary": "Há urgência e preocupação moderada no escopo analisado.",
          "risk_level": "Médio",
          "dominant_signals": ["Urgência", "Risco percebido"],
          "signals": [
            {
              "dimension": "Urgência",
              "label": "Negativo",
              "intensity": "Alta",
              "polarity": -0.62,
              "evidence": "Validação urgente solicitada pela equipe.",
              "interpretation": "O prazo é percebido como sensível.",
              "recommendation": "Formalizar responsáveis e data de decisão.",
              "source_refs": ["Fonte 1"]
            }
          ]
        }
        """
    )

    report = generate_sentiment_report(FakeClient(responses), _sources(), "gpt-5-mini")

    assert report.overall_sentiment == "Misto"
    assert report.risk_level == "Médio"
    assert report.dominant_signals == ["Urgência", "Risco percebido"]
    assert report.signals[0].dimension == "Urgência"
    assert report.signals[0].polarity == -0.62
    assert "sentimentos organizacionais" in str(responses.calls["instructions"])
    assert "Fonte 1" in str(responses.calls["input"])


def test_generate_sentiment_report_rejects_empty_signals() -> None:
    responses = FakeResponses(
        '{"overall_sentiment":"Neutro","executive_summary":"Sem sinais.","signals":[]}'
    )

    with pytest.raises(SentimentGenerationError):
        generate_sentiment_report(FakeClient(responses), _sources(), "gpt-5-mini")


def test_sentiment_report_exports_markdown_csv_and_xlsx() -> None:
    report = generate_sentiment_report(
        FakeClient(
            FakeResponses(
                '{"overall_sentiment":"Negativo","executive_summary":"Síntese de tom.",'
                '"risk_level":"Alto","dominant_signals":["Tensão"],"signals":[{'
                '"dimension":"Tensão","label":"Negativo","intensity":"Alta",'
                '"polarity":-0.8,"evidence":"Há preocupação explícita.",'
                '"interpretation":"O texto sinaliza pressão operacional.",'
                '"recommendation":"Alinhar comunicação com as áreas responsáveis.",'
                '"source_refs":["Fonte 1"]}]}'
            )
        ),
        _sources(),
        "gpt-5-mini",
    )

    markdown = sentiment_report_to_markdown(report)
    csv_text = sentiment_report_to_csv(report)
    xlsx_bytes = sentiment_report_to_xlsx(report)

    assert "# Análise de sentimentos organizacionais - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert csv_text.startswith("\ufeff")
    assert "dimensão;classificação;intensidade" in csv_text
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        worksheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Resumo" in workbook
    assert "Sinais" in workbook
    assert "Resultado" in summary
    assert "Tensão" in worksheet
    assert "wrapText" in styles
