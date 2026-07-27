from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.pattern_service import (
    PatternGenerationError,
    build_history_digest,
    generate_historical_pattern_report,
    historical_pattern_report_to_csv,
    historical_pattern_report_to_markdown,
    historical_pattern_report_to_xlsx,
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
            "O orçamento ainda depende de aprovação e pode atrasar o lançamento.",
            0.93,
        )
    ]


def _history() -> list[dict[str, object]]:
    return [
        {
            "title": "Alertas preventivos gerados",
            "created_at": "2026-07-20T10:00:00+00:00",
            "metadata": {
                "artifact_type": "preventive_alert_report",
                "alerts": [
                    {
                        "alert_type": "Orçamento",
                        "title": "Aprovação orçamentária pendente",
                        "severity": "Alta",
                        "trigger": "Orçamento ainda não aprovado.",
                        "recommendation": "Escalar validação financeira.",
                    }
                ],
            },
        }
    ]


def test_build_history_digest_extracts_relevant_saved_artifacts() -> None:
    digest = build_history_digest(_history())

    assert digest[0]["title"] == "Alertas preventivos gerados"
    assert digest[0]["artifact_type"] == "preventive_alert_report"
    assert "Aprovação orçamentária pendente" in str(digest[0]["signals"])


def test_generate_historical_pattern_report_parses_patterns() -> None:
    responses = FakeResponses(
        """
        {
          "executive_summary": "Há recorrência de risco por aprovação orçamentária.",
          "patterns": [
            {
              "pattern_type": "Orçamento",
              "title": "Atraso associado a aprovação financeira",
              "recurrence": "O risco aparece no escopo atual e em alerta salvo anteriormente.",
              "severity": "Alta",
              "current_signal": "Orçamento pendente no documento atual.",
              "historical_evidence": "Alerta anterior indicava aprovação orçamentária pendente.",
              "interpretation": "O mesmo gargalo financeiro voltou a aparecer.",
              "recommendation": "Criar validação financeira antecipada.",
              "source_refs": ["Fonte 1"],
              "related_records": ["Alertas preventivos gerados"]
            }
          ]
        }
        """
    )

    report = generate_historical_pattern_report(
        FakeClient(responses),
        _sources(),
        _history(),
        "gpt-5-mini",
    )

    assert report.executive_summary == "Há recorrência de risco por aprovação orçamentária."
    assert report.historical_record_count == 1
    assert report.patterns[0].pattern_type == "Orçamento"
    assert report.patterns[0].severity == "Alta"
    assert "memória institucional" in str(responses.calls["instructions"])
    assert "Histórico salvo resumido" in str(responses.calls["input"])


def test_generate_historical_pattern_report_requires_history() -> None:
    responses = FakeResponses('{"executive_summary":"Sem padrões.","patterns":[]}')

    with pytest.raises(PatternGenerationError):
        generate_historical_pattern_report(FakeClient(responses), _sources(), [], "gpt-5-mini")


def test_historical_pattern_report_exports_markdown_csv_and_xlsx() -> None:
    report = generate_historical_pattern_report(
        FakeClient(
            FakeResponses(
                '{"executive_summary":"Síntese de padrões.","patterns":[{'
                '"pattern_type":"Risco","title":"Risco recorrente de atraso",'
                '"recurrence":"Aparece em dois registros.",'
                '"severity":"Média","current_signal":"Prazo sensível.",'
                '"historical_evidence":"Alerta anterior citou atraso.",'
                '"interpretation":"Há repetição do mesmo risco.",'
                '"recommendation":"Monitorar aprovação semanalmente.",'
                '"source_refs":["Fonte 1"],'
                '"related_records":["Alertas preventivos gerados"]}]}'
            )
        ),
        _sources(),
        _history(),
        "gpt-5-mini",
    )

    markdown = historical_pattern_report_to_markdown(report)
    csv_text = historical_pattern_report_to_csv(report)
    xlsx_bytes = historical_pattern_report_to_xlsx(report)

    assert "# Padrões históricos - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert csv_text.startswith("\ufeff")
    assert "tipo;título;recorrência" in csv_text
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        worksheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Resumo" in workbook
    assert "Padrões" in workbook
    assert "Resultado" in summary
    assert "Risco recorrente de atraso" in worksheet
    assert "wrapText" in styles
