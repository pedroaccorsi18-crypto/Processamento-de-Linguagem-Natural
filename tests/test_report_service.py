from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.report_service import (
    build_executive_report,
    executive_report_to_markdown,
    executive_report_to_pdf,
    generate_intelligent_executive_report,
    intelligent_report_to_markdown,
    intelligent_report_to_pdf,
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


def test_build_executive_report_collects_documents_actions_and_sources() -> None:
    documents = [
        {
            "id": "doc-1",
            "filename": "ata.pdf",
            "text_char_count": 1200,
            "created_at": "2026-07-27T10:00:00+00:00",
        },
        {
            "id": "doc-2",
            "filename": "comunicado.pdf",
            "text_char_count": 800,
            "created_at": "2026-07-27T11:00:00+00:00",
        },
    ]
    analyses = [
        {
            "metadata": {
                "artifact_type": "action_plan",
                "source_filenames": ["ata.pdf"],
                "items": [
                    {
                        "task": "Validar or\u00e7amento",
                        "responsible": "Fernanda",
                        "deadline": "30/07/2026",
                        "priority": "Alta",
                        "risk": "Atraso no lan\u00e7amento",
                        "evidence": "Or\u00e7amento depende de aprova\u00e7\u00e3o.",
                        "source_refs": ["Fonte 1"],
                    }
                ],
            }
        }
    ]

    report = build_executive_report(documents, {"doc-1": 2}, analyses)

    assert report.total_documents == 2
    assert report.prepared_documents == 1
    assert report.pending_documents == 1
    assert report.saved_analyses == 1
    assert report.action_plans == 1
    assert report.action_items[0].task == "Validar or\u00e7amento"
    assert report.source_filenames == ["ata.pdf"]


def test_executive_report_to_markdown_contains_governance_note() -> None:
    report = build_executive_report([], {}, [])

    markdown = executive_report_to_markdown(report)

    assert "# Relatório executivo - Synapse AI" in markdown
    assert "Nota de governança" in markdown
    assert "apoio à decisão" in markdown


def test_executive_report_to_pdf_generates_readable_pdf() -> None:
    report = build_executive_report(
        [{"id": "doc-1", "filename": "ata.pdf", "text_char_count": 1200}],
        {"doc-1": 2},
        [
            {
                "metadata": {
                    "artifact_type": "action_plan",
                    "items": [
                        {
                            "task": "Validar or\u00e7amento",
                            "responsible": "Fernanda",
                            "deadline": "30/07/2026",
                            "priority": "Alta",
                            "risk": "Atraso no lan\u00e7amento",
                            "evidence": "Or\u00e7amento depende de aprova\u00e7\u00e3o.",
                        }
                    ],
                }
            }
        ],
    )

    pdf_bytes = executive_report_to_pdf(report)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert pdf_bytes.startswith(b"%PDF")
    assert "Relatório executivo - Synapse AI" in text
    assert "ata.pdf" in text
    assert "orçamento" in text


def test_generate_intelligent_executive_report_uses_sources_and_history() -> None:
    responses = FakeResponses(
        """
        {
          "title": "Relatório executivo do Projeto Orion",
          "executive_summary": "O projeto tem avanço relevante, mas depende de validações.",
          "key_findings": ["Lançamento depende de aprovação financeira."],
          "risks": ["Atraso se o orçamento não for aprovado."],
          "recommendations": ["Confirmar orçamento antes da comunicação final."],
          "action_items": [
            {
              "task": "Validar orçamento",
              "responsible": "Fernanda",
              "deadline": "30/07/2026",
              "priority": "Alta",
              "risk": "Atraso no lançamento",
              "evidence": "A aprovação financeira está pendente.",
              "source_refs": ["Fonte 1"]
            }
          ],
          "limitations": ["Não há confirmação de assinatura do contrato."]
        }
        """
    )
    client = FakeClient(responses)
    sources = [
        SourceSnippet(
            "doc-1",
            "ata.pdf",
            0,
            "A aprovação financeira está pendente.",
            0.92,
        )
    ]

    report = generate_intelligent_executive_report(
        client,
        sources,
        [{"filename": "ata.pdf", "text_char_count": 1200}],
        [{"question": "Quais riscos?", "answer": "Há risco financeiro."}],
        "gpt-5-mini",
    )

    assert report.title == "Relatório executivo do Projeto Orion"
    assert report.action_items[0].task == "Validar orçamento"
    assert "JSON válido" in str(responses.calls["instructions"])
    assert "A aprovação financeira está pendente." in str(responses.calls["input"])


def test_intelligent_report_exports_markdown_and_pdf() -> None:
    report = generate_intelligent_executive_report(
        FakeClient(
            FakeResponses(
                '{"title":"Relatório executivo","executive_summary":"Síntese crítica.",'
                '"key_findings":["Achado 1"],"risks":["Risco 1"],'
                '"recommendations":["Recomendação 1"],'
                '"action_items":[{"task":"Validar orçamento","responsible":"Fernanda",'
                '"deadline":"30/07/2026","priority":"Alta","risk":"Atraso",'
                '"evidence":"Evidência documental.","source_refs":["Fonte 1"]}],'
                '"limitations":["Lacuna 1"]}'
            )
        ),
        [SourceSnippet("doc-1", "ata.pdf", 0, "Texto fonte", 0.92)],
        [{"filename": "ata.pdf"}],
        [],
        "gpt-5-mini",
    )

    markdown = intelligent_report_to_markdown(report)
    pdf_bytes = intelligent_report_to_pdf(report)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "## Síntese executiva" in markdown
    assert "Validar orçamento" in markdown
    assert pdf_bytes.startswith(b"%PDF")
    assert "Relatório executivo" in text
    assert "Validar orçamento" in text
