from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Any

from synapse_ai.services.spreadsheet_export import table_to_xlsx

logger = logging.getLogger(__name__)


class AnalysisGenerationError(RuntimeError):
    """Raised when a RAG answer cannot be generated."""


@dataclass(frozen=True)
class SourceSnippet:
    document_id: str
    filename: str
    chunk_index: int
    content: str
    similarity: float


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    sources: list[SourceSnippet]


@dataclass(frozen=True)
class ActionPlanItem:
    task: str
    responsible: str
    deadline: str
    priority: str
    risk: str
    evidence: str
    source_refs: list[str]


@dataclass(frozen=True)
class ActionPlan:
    items: list[ActionPlanItem]
    sources: list[SourceSnippet]


def serialize_sources(sources: list[SourceSnippet]) -> list[dict[str, object]]:
    return [
        {
            "document_id": source.document_id,
            "filename": source.filename,
            "chunk_index": source.chunk_index,
            "similarity": source.similarity,
        }
        for source in sources
    ]


def serialize_action_plan_items(items: list[ActionPlanItem]) -> list[dict[str, object]]:
    return [
        {
            "task": item.task,
            "responsible": item.responsible,
            "deadline": item.deadline,
            "priority": item.priority,
            "risk": item.risk,
            "evidence": item.evidence,
            "source_refs": item.source_refs,
        }
        for item in items
    ]


def describe_planned_analysis_capabilities() -> list[str]:
    return [
        "Busca semântica em documentos organizacionais",
        "Perguntas em linguagem natural com rastreabilidade",
        "Sínteses executivas",
        "Identificação de decisões, responsáveis, riscos e inconsistências",
        "Análise de sentimentos organizacionais com evidências",
        "Alertas preventivos para riscos, prazos e lacunas de responsabilidade",
        "Reconhecimento de padrões históricos a partir de análises salvas",
        "Agentes especializados reais com orquestração de consensos e conflitos",
    ]


def analysis_pipeline_available() -> bool:
    return True


def build_source_snippets(matches: list[dict[str, Any]]) -> list[SourceSnippet]:
    snippets: list[SourceSnippet] = []
    for match in matches:
        content = match.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        snippets.append(
            SourceSnippet(
                document_id=str(match.get("document_id", "")),
                filename=str(match.get("filename") or "Documento sem nome"),
                chunk_index=_as_int(match.get("chunk_index")),
                content=content.strip(),
                similarity=_as_float(match.get("similarity")),
            )
        )
    return snippets


def generate_rag_answer(
    client: Any,
    question: str,
    sources: list[SourceSnippet],
    model: str,
) -> RAGAnswer:
    clean_question = question.strip()
    if not clean_question:
        raise AnalysisGenerationError("Informe uma pergunta para a análise.")
    if not sources:
        raise AnalysisGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_analysis_instructions(),
            input=_build_rag_input(clean_question, sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG answer generation failed: %s", exc.__class__.__name__)
        raise AnalysisGenerationError("Não foi possível gerar a resposta com IA.") from exc

    answer = _extract_response_text(response)
    if not answer:
        raise AnalysisGenerationError("A resposta da IA veio vazia.")
    return RAGAnswer(answer=answer, sources=sources)


def generate_action_plan(
    client: Any,
    sources: list[SourceSnippet],
    model: str,
) -> ActionPlan:
    if not sources:
        raise AnalysisGenerationError("Nenhum trecho relevante foi encontrado.")

    try:
        response = client.responses.create(
            model=model,
            instructions=_action_plan_instructions(),
            input=_build_action_plan_input(sources),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Action plan generation failed: %s", exc.__class__.__name__)
        raise AnalysisGenerationError("Não foi possível gerar o plano de ação.") from exc

    response_text = _extract_response_text(response)
    items = _parse_action_plan_items(response_text)
    if not items:
        raise AnalysisGenerationError("A IA não encontrou ações claras nos documentos.")
    return ActionPlan(items=items, sources=sources)


def action_plan_to_markdown(plan: ActionPlan) -> str:
    lines = ["# Plano de ação", ""]
    for index, item in enumerate(plan.items, start=1):
        refs = ", ".join(item.source_refs) if item.source_refs else "Fonte não indicada"
        lines.extend(
            [
                f"## {index}. {item.task}",
                f"- Responsável: {item.responsible}",
                f"- Prazo: {item.deadline}",
                f"- Prioridade: {item.priority}",
                f"- Risco: {item.risk}",
                f"- Evidência: {item.evidence}",
                f"- Fontes: {refs}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def action_plan_to_csv(plan: ActionPlan) -> str:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(
        output,
        delimiter=";",
        fieldnames=[
            "tarefa",
            "responsável",
            "prazo",
            "prioridade",
            "risco",
            "evidência",
            "fontes",
        ],
    )
    writer.writeheader()
    for item in plan.items:
        writer.writerow(
            {
                "tarefa": item.task,
                "responsável": item.responsible,
                "prazo": item.deadline,
                "prioridade": item.priority,
                "risco": item.risk,
                "evidência": item.evidence,
                "fontes": ", ".join(item.source_refs),
            }
        )
    return output.getvalue()


def action_plan_to_xlsx(plan: ActionPlan) -> bytes:
    headers = [
        "Tarefa",
        "Responsável",
        "Prazo",
        "Prioridade",
        "Risco",
        "Evidência",
        "Fontes",
    ]
    rows = [
        [
            item.task,
            item.responsible,
            item.deadline,
            item.priority,
            item.risk,
            item.evidence,
            ", ".join(item.source_refs),
        ]
        for item in plan.items
    ]
    return table_to_xlsx(
        headers,
        rows,
        sheet_name="Plano de ação",
        column_widths=[44, 26, 18, 14, 42, 58, 20],
    )


def _analysis_instructions() -> str:
    return (
        "Você é o Synapse AI, uma plataforma acadêmica de PLN e inteligência "
        "organizacional. Responda em português do Brasil. Use apenas os trechos "
        "fornecidos como contexto. Quando a evidência for insuficiente, diga isso. "
        "Estruture a resposta em síntese executiva, evidências, riscos ou próximas "
        "ações quando fizer sentido. Cite as fontes usando [Fonte 1], [Fonte 2]."
    )


def _build_rag_input(question: str, sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return f"Pergunta do usuário:\n{question}\n\nContexto recuperado:\n{rendered_sources}"


def _action_plan_instructions() -> str:
    return (
        "Você é o Synapse AI gerando um plano de ação para inteligência organizacional. "
        "Use apenas as fontes fornecidas. Não invente responsáveis, datas ou decisões. "
        "Quando algum campo não estiver claro, use 'A confirmar'. Responda somente com "
        "JSON válido no formato: "
        '{"items":[{"task":"...","responsible":"...","deadline":"...",'
        '"priority":"Alta|Média|Baixa","risk":"...","evidence":"...",'
        '"source_refs":["Fonte 1"]}]}.'
    )


def _build_action_plan_input(sources: list[SourceSnippet]) -> str:
    rendered_sources = "\n\n".join(
        (
            f"[Fonte {index}] Documento: {source.filename}\n"
            f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}\n"
            f"{source.content}"
        )
        for index, source in enumerate(sources, start=1)
    )
    return (
        "Gere um plano de ação estruturado a partir das decisões, prazos, riscos, "
        f"responsáveis e pendências presentes nestas fontes:\n\n{rendered_sources}"
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        content_items = _get_value(item, "content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            text = _get_value(content_item, "text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _parse_action_plan_items(response_text: str) -> list[ActionPlanItem]:
    raw_plan = _load_json_object(response_text)
    raw_items = raw_plan.get("items")
    if not isinstance(raw_items, list):
        return []

    items: list[ActionPlanItem] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        task = _clean_text(raw_item.get("task"))
        if not task:
            continue
        items.append(
            ActionPlanItem(
                task=task,
                responsible=_clean_text(raw_item.get("responsible")) or "A confirmar",
                deadline=_clean_text(raw_item.get("deadline")) or "A confirmar",
                priority=_normalize_priority(raw_item.get("priority")),
                risk=_clean_text(raw_item.get("risk")) or "A confirmar",
                evidence=_clean_text(raw_item.get("evidence")) or "A confirmar",
                source_refs=_clean_source_refs(raw_item.get("source_refs")),
            )
        )
    return items


def _load_json_object(response_text: str) -> dict[str, Any]:
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.strip("`")
        if clean_text.lower().startswith("json"):
            clean_text = clean_text[4:].strip()
    try:
        value = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise AnalysisGenerationError("A IA retornou um plano em formato inesperado.") from exc
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_priority(value: Any) -> str:
    priority = _clean_text(value).title()
    return priority if priority in {"Alta", "Média", "Baixa"} else "Média"


def _clean_source_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            refs.append(item.strip())
    return refs


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _as_float(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
