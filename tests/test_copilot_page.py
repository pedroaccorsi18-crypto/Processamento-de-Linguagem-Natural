from __future__ import annotations

from synapse_ai.ui.copilot_page import (
    _build_document_excerpt_answer,
    _compact_markdown,
    _is_document_excerpt_request,
    resolve_openai_api_key,
    route_copilot_intent,
)


def test_route_copilot_intent_detects_action_plan_before_document_upload() -> None:
    intent = route_copilot_intent("Quero gerar um plano de ação para este documento")

    assert intent.kind == "navigation"
    assert intent.target_page == "analysis"
    assert intent.analysis_focus == "action_plan"
    assert intent.action_label == "Gerar plano de ação"
    assert intent.response is not None
    assert "responsáveis" in intent.response


def test_route_copilot_intent_detects_insights_navigation() -> None:
    intent = route_copilot_intent("Mostre os riscos e alertas")

    assert intent.kind == "navigation"
    assert intent.target_page == "intelligence"
    assert intent.action_label == "Abrir Insights"
    assert intent.response is not None
    assert "plano de ação" in intent.response
    assert "Evidências" in intent.response


def test_route_copilot_intent_keeps_general_questions_conversational() -> None:
    intent = route_copilot_intent("Como eu interpreto uma resposta com fontes?")

    assert intent.kind == "conversation"
    assert intent.target_page is None


def test_route_copilot_intent_guides_upload_without_immediate_execution() -> None:
    intent = route_copilot_intent("Preciso subir um arquivo novo")

    assert intent.kind == "navigation"
    assert intent.target_page == "upload"
    assert intent.action_label == "Abrir Base documental"
    assert intent.response is not None
    assert "preparação semântica" in intent.response


def test_route_copilot_intent_explains_capabilities_without_navigation() -> None:
    intent = route_copilot_intent("O que você é capaz de fazer?")

    assert intent.kind == "conversation"
    assert intent.target_page is None
    assert intent.response is not None
    assert "Orientação de uso" in intent.response
    assert "Decisão executiva" in intent.response


def test_document_excerpt_request_is_detected_before_generic_chat() -> None:
    assert _is_document_excerpt_request("consegue me elencar os principais trechos do que enviei")


def test_build_document_excerpt_answer_uses_extracted_user_documents() -> None:
    answer = _build_document_excerpt_answer(
        [
            {
                "filename": "ata_orion.pdf",
                "extracted_text": (
                    "Ata de reunião do Projeto Orion. A diretoria aprovou o início "
                    "do projeto com lançamento preliminar em agosto. O orçamento depende "
                    "de validação final do Financeiro.\n"
                    "A equipe de Tecnologia deverá revisar o fluxo de autenticação, "
                    "pois há risco de instabilidade nos horários de pico."
                ),
            }
        ],
        "Quais são os principais trechos sobre risco e orçamento?",
    )

    assert "ata_orion.pdf" in answer
    assert "orçamento" in answer
    assert "risco" in answer
    assert "Estúdio de IA" in answer


def test_build_document_excerpt_answer_guides_when_no_documents_exist() -> None:
    answer = _build_document_excerpt_answer([], "principais trechos do que enviei")

    assert "Não encontrei documentos" in answer
    assert "Base documental" in answer


def test_resolve_openai_api_key_prefers_top_level_secret() -> None:
    api_key = resolve_openai_api_key(
        {
            "OPENAI_API_KEY": "sk-top-level",
            "openai": {"api_key": "sk-section"},
        }
    )

    assert api_key == "sk-top-level"


def test_resolve_openai_api_key_supports_existing_openai_section() -> None:
    api_key = resolve_openai_api_key({"openai": {"api_key": "sk-section"}})

    assert api_key == "sk-section"


def test_compact_markdown_trims_long_contextual_answers() -> None:
    answer = _compact_markdown("palavra " * 120, limit=80)

    assert len(answer) <= 83
    assert answer.endswith("...")
