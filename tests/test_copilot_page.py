from __future__ import annotations

from synapse_ai.ui.copilot_page import resolve_openai_api_key, route_copilot_intent


def test_route_copilot_intent_detects_action_plan_before_document_upload() -> None:
    intent = route_copilot_intent("Quero gerar um plano de ação para este documento")

    assert intent.kind == "navigation"
    assert intent.target_page == "analysis"
    assert intent.analysis_focus == "action_plan"


def test_route_copilot_intent_detects_insights_navigation() -> None:
    intent = route_copilot_intent("Mostre os riscos e alertas")

    assert intent.kind == "navigation"
    assert intent.target_page == "intelligence"


def test_route_copilot_intent_keeps_general_questions_conversational() -> None:
    intent = route_copilot_intent("Como eu interpreto uma resposta com fontes?")

    assert intent.kind == "conversation"
    assert intent.target_page is None


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
