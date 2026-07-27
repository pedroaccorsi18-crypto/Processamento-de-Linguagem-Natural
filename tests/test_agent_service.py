from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.agent_service import (
    SPECIALIZED_AGENTS,
    AgentOrchestrationError,
    generate_multi_agent_report,
    multi_agent_report_to_csv,
    multi_agent_report_to_markdown,
    multi_agent_report_to_xlsx,
)
from synapse_ai.services.analysis_service import SourceSnippet


class FakeResponses:
    def __init__(self, output_texts: list[str]) -> None:
        self.output_texts = output_texts
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:  # noqa: A002
        self.calls.append({"model": model, "instructions": instructions, "input": input})
        return SimpleNamespace(output_text=self.output_texts.pop(0))


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
            0.94,
        )
    ]


def _history() -> list[dict[str, object]]:
    return [
        {
            "title": "Alertas preventivos gerados",
            "metadata": {
                "artifact_type": "preventive_alert_report",
                "alerts": [
                    {
                        "alert_type": "Orçamento",
                        "title": "Aprovação orçamentária pendente",
                        "severity": "Alta",
                    }
                ],
            },
        }
    ]


def _agent_response(name: str) -> str:
    return (
        '{"summary":"Síntese do '
        + name
        + '.","confidence":"Alta","findings":[{'
        '"category":"Risco","title":"Aprovação pendente",'
        '"severity":"Alta","evidence":"O orçamento depende de aprovação.",'
        '"recommendation":"Escalar validação financeira.",'
        '"source_refs":["Fonte 1"]}]}'
    )


def test_generate_multi_agent_report_runs_agents_and_orchestrator() -> None:
    responses = FakeResponses(
        [
            *[_agent_response(agent.name) for agent in SPECIALIZED_AGENTS],
            '{"executive_summary":"Consenso multiagente sobre risco financeiro.",'
            '"consensus":["Há risco de atraso por aprovação financeira."],'
            '"conflicts":["Nenhum conflito relevante."],'
            '"recommendations":["Priorizar validação financeira."]}',
        ]
    )

    report = generate_multi_agent_report(
        FakeClient(responses),
        _sources(),
        _history(),
        "gpt-5-mini",
    )

    assert len(report.agent_outputs) == len(SPECIALIZED_AGENTS)
    assert len(responses.calls) == len(SPECIALIZED_AGENTS) + 1
    assert report.executive_summary == "Consenso multiagente sobre risco financeiro."
    assert report.consensus == ["Há risco de atraso por aprovação financeira."]
    assert report.agent_outputs[0].agent_name == "Agente de Decisões"
    assert report.agent_outputs[0].findings[0].title == "Aprovação pendente"
    assert "Orquestrador Multiagente" in str(responses.calls[-1]["instructions"])


def test_generate_multi_agent_report_rejects_empty_sources() -> None:
    responses = FakeResponses([])

    with pytest.raises(AgentOrchestrationError):
        generate_multi_agent_report(FakeClient(responses), [], [], "gpt-5-mini")


def test_multi_agent_report_exports_markdown_csv_and_xlsx() -> None:
    responses = FakeResponses(
        [
            *[_agent_response(agent.name) for agent in SPECIALIZED_AGENTS],
            '{"executive_summary":"Síntese consolidada.",'
            '"consensus":["Consenso 1"],"conflicts":["Lacuna 1"],'
            '"recommendations":["Recomendação 1"]}',
        ]
    )
    report = generate_multi_agent_report(
        FakeClient(responses),
        _sources(),
        _history(),
        "gpt-5-mini",
    )

    markdown = multi_agent_report_to_markdown(report)
    csv_text = multi_agent_report_to_csv(report)
    xlsx_bytes = multi_agent_report_to_xlsx(report)

    assert "# Orquestração multiagente - Synapse AI" in markdown
    assert "Agente de Riscos" in markdown
    assert csv_text.startswith("\ufeff")
    assert "agente;missão;confiança" in csv_text
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        findings = archive.read("xl/worksheets/sheet3.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Resumo" in workbook
    assert "Agentes" in workbook
    assert "Achados" in workbook
    assert "Síntese consolidada" in summary
    assert "Aprovação pendente" in findings
    assert "wrapText" in styles
