from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class NamedEntity:
    text: str
    label: str
    start_char: int
    end_char: int
    source: str


SPACY_MODEL_CANDIDATES = ("pt_core_news_sm", "xx_ent_wiki_sm")
MAX_ENTITIES_PER_CHUNK = 40

_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+de\s+[A-Za-zÀ-ÿ]+(?:\s+de\s+\d{4})?)\b",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"\b(?:R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?"
    r"|\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:reais|milhões|mil|BRL))\b",
    re.IGNORECASE,
)
_ORG_RE = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ&.-]*(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ&.-]*)*\s+"
    r"(?:S\.A\.|SA|Ltda\.?|LTDA|Inc\.?|Corp\.?|Banco|Financeira|Tecnologia)\b"
)
_PERSON_RE = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-zà-ÿ]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-zà-ÿ]+){1,3}\b"
)

_LABEL_MAP = {
    "PER": "PESSOA",
    "PERSON": "PESSOA",
    "ORG": "ORGANIZACAO",
    "LOC": "LOCAL",
    "GPE": "LOCAL",
    "DATE": "DATA",
    "TIME": "DATA",
    "MONEY": "VALOR",
    "CARDINAL": "VALOR",
    "QUANTITY": "VALOR",
}


def extract_named_entities(text: str) -> list[dict[str, Any]]:
    """Extract explicit NLP entities with spaCy, plus deterministic business fallbacks."""
    clean_text = text.strip()
    if not clean_text:
        return []

    entities: list[NamedEntity] = []
    nlp = _load_spacy_pipeline()
    if nlp is not None:
        doc = nlp(clean_text)
        for ent in doc.ents:
            label = _LABEL_MAP.get(ent.label_, ent.label_)
            if label in {"PESSOA", "ORGANIZACAO", "DATA", "VALOR", "LOCAL"}:
                entities.append(
                    NamedEntity(
                        text=ent.text.strip(),
                        label=label,
                        start_char=ent.start_char,
                        end_char=ent.end_char,
                        source="spacy",
                    )
                )

    entities.extend(_fallback_entities(clean_text))
    return [
        _entity_to_dict(entity)
        for entity in _dedupe_entities(entities)[:MAX_ENTITIES_PER_CHUNK]
    ]


@lru_cache(maxsize=1)
def _load_spacy_pipeline() -> Any | None:
    try:
        import spacy  # type: ignore[import-not-found]
    except ImportError:
        return None

    for model in SPACY_MODEL_CANDIDATES:
        try:
            return spacy.load(model)
        except OSError:
            continue
    try:
        return spacy.blank("pt")
    except (OSError, ValueError):
        return None


def _fallback_entities(text: str) -> list[NamedEntity]:
    entities: list[NamedEntity] = []
    entities.extend(_regex_entities(text, _DATE_RE, "DATA"))
    entities.extend(_regex_entities(text, _MONEY_RE, "VALOR"))
    entities.extend(_regex_entities(text, _ORG_RE, "ORGANIZACAO"))
    entities.extend(_regex_entities(text, _PERSON_RE, "PESSOA"))
    return entities


def _regex_entities(text: str, pattern: re.Pattern[str], label: str) -> list[NamedEntity]:
    return [
        NamedEntity(
            text=match.group(0).strip(),
            label=label,
            start_char=match.start(),
            end_char=match.end(),
            source="rule",
        )
        for match in pattern.finditer(text)
        if match.group(0).strip()
    ]


def _dedupe_entities(entities: list[NamedEntity]) -> list[NamedEntity]:
    seen: set[tuple[str, str]] = set()
    deduped: list[NamedEntity] = []
    for entity in entities:
        key = (entity.text.casefold(), entity.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    return deduped


def _entity_to_dict(entity: NamedEntity) -> dict[str, Any]:
    return {
        "text": entity.text,
        "label": entity.label,
        "start_char": entity.start_char,
        "end_char": entity.end_char,
        "source": entity.source,
    }
