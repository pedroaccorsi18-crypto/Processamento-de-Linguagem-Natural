from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from synapse_ai.services.analysis_service import (
    ActionPlanItem,
    AnalysisGenerationError,
    SourceSnippet,
    action_plan_to_csv,
    action_plan_to_markdown,
    action_plan_to_xlsx,
    analysis_pipeline_available,
    build_source_snippets,
    generate_action_plan,
    generate_rag_answer,
    serialize_action_plan_items,
    serialize_sources,
)


class FakeResponses:
    def __init__(self, output_text: str = "Resposta com [Fonte 1].", fail: bool = False) -> None:
        self.output_text = output_text
        self.fail = fail
        self.calls: dict[str, object] = {}

    def create(self, *, model: str, instructions: str, input: str) -> SimpleNamespace:  # noqa: A002
        if self.fail:
            raise RuntimeError("failed")
        self.calls = {"model": model, "instructions": instructions, "input": input}
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def test_analysis_pipeline_is_available() -> None:
    assert analysis_pipeline_available() is True


def test_build_source_snippets_skips_empty_content() -> None:
    snippets = build_source_snippets(
        [
            {
                "document_id": "doc-1",
                "filename": "ata.txt",
                "chunk_index": 2,
                "content": "Decisao aprovada.",
                "similarity": 0.88,
            },
            {"content": " "},
        ]
    )

    assert snippets == [
        SourceSnippet(
            document_id="doc-1",
            filename="ata.txt",
            chunk_index=2,
            content="Decisao aprovada.",
            similarity=0.88,
        )
    ]


def test_generate_rag_answer_calls_responses_api_with_sources() -> None:
    responses = FakeResponses()
    client = FakeClient(responses)

    result = generate_rag_answer(
        client,
        "Qual foi a decisão?",
        [SourceSnippet("doc-1", "ata.txt", 0, "A diretoria aprovou o projeto.", 0.91)],
        "gpt-5-mini",
    )

    assert result.answer == "Resposta com [Fonte 1]."
    assert responses.calls["model"] == "gpt-5-mini"
    assert "A diretoria aprovou o projeto." in str(responses.calls["input"])


def test_generate_rag_answer_requires_sources() -> None:
    client = FakeClient(FakeResponses())

    with pytest.raises(AnalysisGenerationError):
        generate_rag_answer(client, "Pergunta", [], "gpt-5-mini")


def test_serialize_sources_returns_json_ready_dicts() -> None:
    sources = [SourceSnippet("doc-1", "ata.txt", 1, "Texto fonte", 0.75)]

    assert serialize_sources(sources) == [
        {
            "document_id": "doc-1",
            "filename": "ata.txt",
            "chunk_index": 1,
            "similarity": 0.75,
            "metadata": {},
        }
    ]


def test_generate_action_plan_parses_structured_json() -> None:
    responses = FakeResponses(
        """
        {
          "items": [
            {
              "task": "Validar orçamento final",
              "responsible": "Fernanda Lima",
              "deadline": "30/07/2026",
              "priority": "Alta",
              "risk": "Atraso no lançamento",
              "evidence": "Orçamento depende de aprovação financeira.",
              "source_refs": ["Fonte 1"]
            }
          ]
        }
        """
    )
    client = FakeClient(responses)
    sources = [SourceSnippet("doc-1", "ata.txt", 0, "Orçamento pendente.", 0.91)]

    plan = generate_action_plan(client, sources, "gpt-5-mini")

    assert plan.items == [
        ActionPlanItem(
            task="Validar orçamento final",
            responsible="Fernanda Lima",
            deadline="30/07/2026",
            priority="Alta",
            risk="Atraso no lançamento",
            evidence="Orçamento depende de aprovação financeira.",
            source_refs=["Fonte 1"],
        )
    ]
    assert plan.sources == sources
    assert "JSON válido" in str(responses.calls["instructions"])


def test_generate_action_plan_rejects_unstructured_output() -> None:
    client = FakeClient(FakeResponses("sem json"))

    with pytest.raises(AnalysisGenerationError):
        generate_action_plan(
            client,
            [SourceSnippet("doc-1", "ata.txt", 0, "Texto.", 0.91)],
            "gpt-5-mini",
        )


def test_action_plan_exports_markdown_and_csv() -> None:
    item = ActionPlanItem(
        task="Atualizar comunicação",
        responsible="Ana",
        deadline="22/08/2026",
        priority="Média",
        risk="Chamados de suporte",
        evidence="Comunicação precisa ser revisada.",
        source_refs=["Fonte 1", "Fonte 2"],
    )
    plan = generate_action_plan(
        FakeClient(
            FakeResponses(
                '{"items":[{"task":"Atualizar comunicação","responsible":"Ana",'
                '"deadline":"22/08/2026","priority":"Média",'
                '"risk":"Chamados de suporte","evidence":"Comunicação precisa ser revisada.",'
                '"source_refs":["Fonte 1","Fonte 2"]}]}'
            )
        ),
        [SourceSnippet("doc-1", "ata.txt", 0, "Texto.", 0.91)],
        "gpt-5-mini",
    )

    assert serialize_action_plan_items([item])[0]["task"] == "Atualizar comunicação"
    assert "## 1. Atualizar comunicação" in action_plan_to_markdown(plan)
    csv_text = action_plan_to_csv(plan)

    assert csv_text.startswith("\ufeff")
    assert "tarefa;responsável;prazo" in csv_text

    xlsx_bytes = action_plan_to_xlsx(plan)
    with ZipFile(BytesIO(xlsx_bytes)) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert xlsx_bytes.startswith(b"PK")
    assert "Atualizar comunicação" in worksheet
    assert "wrapText" in styles
