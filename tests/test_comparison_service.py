from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.comparison_service import (
    ComparisonGenerationError,
    document_comparison_to_csv,
    document_comparison_to_markdown,
    document_comparison_to_xlsx,
    generate_document_comparison,
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
        SourceSnippet("doc-1", "ata_inicial.pdf", 0, "Lançamento previsto para 15/08.", 0.91),
        SourceSnippet("doc-2", "ata_final.pdf", 1, "Lançamento reprogramado para 22/08.", 0.89),
    ]


def test_generate_document_comparison_parses_issues() -> None:
    responses = FakeResponses(
        """
        {
          "executive_summary": "Há divergência de cronograma entre documentos.",
          "issues": [
            {
              "issue_type": "Cronograma",
              "title": "Datas de lançamento divergentes",
              "description": "Um documento aponta 15/08 e outro aponta 22/08.",
              "severity": "Alta",
              "documents": ["Fonte 1", "Fonte 2"],
              "impact": "Risco de comunicação inconsistente ao cliente.",
              "evidence": "15/08 versus 22/08.",
              "recommendation": "Confirmar a data oficial e republicar o cronograma.",
              "source_refs": ["Fonte 1", "Fonte 2"]
            }
          ]
        }
        """
    )

    report = generate_document_comparison(FakeClient(responses), _sources(), "gpt-5-mini")

    assert report.executive_summary == "Há divergência de cronograma entre documentos."
    assert report.issues[0].issue_type == "Cronograma"
    assert report.issues[0].severity == "Alta"
    assert report.issues[0].documents == ["ata_inicial.pdf", "ata_final.pdf"]
    assert "comparando documentos" in str(responses.calls["instructions"])
    assert "Fonte 2" in str(responses.calls["input"])


def test_generate_document_comparison_rejects_empty_issues() -> None:
    responses = FakeResponses('{"executive_summary":"Sem divergências.","issues":[]}')

    with pytest.raises(ComparisonGenerationError):
        generate_document_comparison(FakeClient(responses), _sources(), "gpt-5-mini")


def test_document_comparison_exports_markdown_csv_and_xlsx() -> None:
    report = generate_document_comparison(
        FakeClient(
            FakeResponses(
                '{"executive_summary":"Síntese comparativa.","issues":[{'
                '"issue_type":"Responsável","title":"Responsáveis conflitantes",'
                '"description":"Há responsáveis diferentes para a mesma entrega.",'
                '"severity":"Média","documents":["ata.pdf","email.pdf"],'
                '"impact":"Risco de retrabalho.",'
                '"evidence":"Produto versus Tecnologia.",'
                '"recommendation":"Definir responsável único.",'
                '"source_refs":["Fonte 1","Fonte 2"]}]}'
            )
        ),
        _sources(),
        "gpt-5-mini",
    )

    markdown = document_comparison_to_markdown(report)
    csv_text = document_comparison_to_csv(report)
    xlsx_bytes = document_comparison_to_xlsx(report)

    assert "# Comparação documental - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert csv_text.startswith("\ufeff")
    assert "tipo;título;descrição" in csv_text
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        worksheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Resumo executivo" in workbook
    assert "Divergências" in workbook
    assert "Resultado" in summary
    assert "Total de divergências" in summary
    assert "Responsáveis conflitantes" in worksheet
    assert "wrapText" in styles
