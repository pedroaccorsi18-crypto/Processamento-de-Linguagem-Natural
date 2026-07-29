from __future__ import annotations

from synapse_ai.services.ner_service import extract_named_entities


def test_extract_named_entities_returns_structured_business_entities() -> None:
    text = (
        "Ana Ribeiro reuniu a equipe da OpenAI Tecnologia em 03/07/2026 "
        "para aprovar R$ 10.000,00."
    )

    entities = extract_named_entities(text)

    labels = {entity["label"] for entity in entities}
    assert {"PESSOA", "ORGANIZACAO", "DATA", "VALOR"}.issubset(labels)
    required_fields = {"text", "label", "start_char", "end_char", "source"}
    assert all(required_fields <= set(entity) for entity in entities)


def test_extract_named_entities_returns_empty_list_for_blank_text() -> None:
    assert extract_named_entities("   ") == []
