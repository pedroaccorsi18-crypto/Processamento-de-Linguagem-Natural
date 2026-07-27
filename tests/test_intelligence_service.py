from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.intelligence_service import (
    IntelligenceGenerationError,
    generate_intelligence_snapshot,
    intelligence_snapshot_to_csv,
    intelligence_snapshot_to_markdown,
    intelligence_snapshot_to_xlsx,
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
            "O lançamento foi reprogramado para 22 de agosto por pendência financeira.",
            0.93,
        )
    ]


def test_generate_intelligence_snapshot_parses_structured_findings() -> None:
    responses = FakeResponses(
        """
        {
          "executive_summary": "Há risco de atraso por pendência financeira.",
          "findings": [
            {
              "category": "Risco",
              "title": "Atraso por aprovação financeira",
              "description": "O lançamento depende da conclusão financeira.",
              "severity": "Alta",
              "responsible": "Financeiro",
              "deadline": "22/08/2026",
              "evidence": "Lançamento reprogramado por pendência financeira.",
              "recommendation": "Antecipar validação orçamentária.",
              "source_refs": ["Fonte 1"]
            }
          ]
        }
        """
    )

    snapshot = generate_intelligence_snapshot(FakeClient(responses), _sources(), "gpt-5-mini")

    assert snapshot.executive_summary == "Há risco de atraso por pendência financeira."
    assert snapshot.findings[0].category == "Risco"
    assert snapshot.findings[0].severity == "Alta"
    assert snapshot.findings[0].source_refs == ["Fonte 1"]
    assert "inteligência organizacional" in str(responses.calls["instructions"])
    assert "Fonte 1" in str(responses.calls["input"])


def test_generate_intelligence_snapshot_rejects_empty_findings() -> None:
    responses = FakeResponses('{"executive_summary":"Sem achados.","findings":[]}')

    with pytest.raises(IntelligenceGenerationError):
        generate_intelligence_snapshot(FakeClient(responses), _sources(), "gpt-5-mini")


def test_intelligence_snapshot_exports_markdown_and_csv_with_correct_portuguese() -> None:
    snapshot = generate_intelligence_snapshot(
        FakeClient(
            FakeResponses(
                '{"executive_summary":"Síntese executiva.","findings":[{'
                '"category":"Decisão","title":"Nova data de lançamento",'
                '"description":"A data foi reprogramada.",'
                '"severity":"Média","responsible":"Produto","deadline":"22/08/2026",'
                '"evidence":"Documento informa nova data.",'
                '"recommendation":"Comunicar as áreas envolvidas.",'
                '"source_refs":["Fonte 1"]}]}'
            )
        ),
        _sources(),
        "gpt-5-mini",
    )

    markdown = intelligence_snapshot_to_markdown(snapshot)
    csv_text = intelligence_snapshot_to_csv(snapshot)

    assert "# Inteligência organizacional - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert csv_text.startswith("\ufeff")
    assert "categoria;título;descrição" in csv_text
    assert "responsável" in csv_text
    assert "evidência" in csv_text


def test_intelligence_snapshot_exports_formatted_xlsx() -> None:
    snapshot = generate_intelligence_snapshot(
        FakeClient(
            FakeResponses(
                '{"executive_summary":"Síntese executiva.","findings":[{'
                '"category":"Risco","title":"Aprovação orçamentária pendente",'
                '"description":"O orçamento ainda não foi aprovado.",'
                '"severity":"Alta","responsible":"Financeiro","deadline":"30/07/2026",'
                '"evidence":"Evidência documental.",'
                '"recommendation":"Validar orçamento com urgência.",'
                '"source_refs":["Fonte 1"]}]}'
            )
        ),
        _sources(),
        "gpt-5-mini",
    )

    xlsx_bytes = intelligence_snapshot_to_xlsx(snapshot)

    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Aprovação orçamentária pendente" in worksheet
    assert "wrapText" in styles
