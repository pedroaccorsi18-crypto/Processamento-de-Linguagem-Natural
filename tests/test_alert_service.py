from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.alert_service import (
    AlertGenerationError,
    generate_preventive_alert_report,
    preventive_alert_report_to_csv,
    preventive_alert_report_to_markdown,
    preventive_alert_report_to_xlsx,
)
from synapse_ai.services.analysis_service import SourceSnippet


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
            "O orçamento ainda depende de aprovação até 30/07/2026.",
            0.94,
        )
    ]


def test_generate_preventive_alert_report_parses_alerts() -> None:
    responses = FakeResponses(
        """
        {
          "executive_summary": "Há alerta preventivo por aprovação orçamentária pendente.",
          "alerts": [
            {
              "alert_type": "Orçamento",
              "title": "Aprovação orçamentária próxima do limite",
              "severity": "Alta",
              "status": "Em acompanhamento",
              "trigger": "A aprovação precisa ocorrer até 30/07/2026.",
              "evidence": "O orçamento ainda depende de aprovação.",
              "impact": "Risco de atraso no lançamento.",
              "recommendation": "Confirmar aprovação financeira antes da data limite.",
              "owner": "Financeiro",
              "deadline": "30/07/2026",
              "source_refs": ["Fonte 1"]
            }
          ]
        }
        """
    )

    report = generate_preventive_alert_report(FakeClient(responses), _sources(), "gpt-5-mini")

    assert report.executive_summary == "Há alerta preventivo por aprovação orçamentária pendente."
    assert report.alerts[0].alert_type == "Orçamento"
    assert report.alerts[0].severity == "Alta"
    assert report.alerts[0].status == "Em acompanhamento"
    assert report.alerts[0].source_refs == ["Fonte 1"]
    assert "alertas preventivos" in str(responses.calls["instructions"])
    assert "Fonte 1" in str(responses.calls["input"])


def test_generate_preventive_alert_report_rejects_empty_alerts() -> None:
    responses = FakeResponses('{"executive_summary":"Sem alertas.","alerts":[]}')

    with pytest.raises(AlertGenerationError):
        generate_preventive_alert_report(FakeClient(responses), _sources(), "gpt-5-mini")


def test_preventive_alert_report_exports_markdown_csv_and_xlsx() -> None:
    report = generate_preventive_alert_report(
        FakeClient(
            FakeResponses(
                '{"executive_summary":"Síntese dos alertas.","alerts":[{'
                '"alert_type":"Prazo","title":"Prazo crítico para aprovação",'
                '"severity":"Crítica","status":"Aberto",'
                '"trigger":"Prazo final próximo.",'
                '"evidence":"Aprovação exigida até 30/07/2026.",'
                '"impact":"Risco de atraso.",'
                '"recommendation":"Escalar validação com Financeiro.",'
                '"owner":"Financeiro","deadline":"30/07/2026",'
                '"source_refs":["Fonte 1"]}]}'
            )
        ),
        _sources(),
        "gpt-5-mini",
    )

    markdown = preventive_alert_report_to_markdown(report)
    csv_text = preventive_alert_report_to_csv(report)
    xlsx_bytes = preventive_alert_report_to_xlsx(report)

    assert "# Alertas preventivos - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert csv_text.startswith("\ufeff")
    assert "tipo;título;severidade" in csv_text
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        worksheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Resumo" in workbook
    assert "Alertas" in workbook
    assert "Resultado" in summary
    assert "Prazo crítico para aprovação" in worksheet
    assert "wrapText" in styles
