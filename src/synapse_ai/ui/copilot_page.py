from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import streamlit as st
from openai import OpenAI

from synapse_ai.config import AppConfig
from synapse_ai.ui.theme import render_callout, render_page_header

CopilotIntentKind = Literal["conversation", "navigation"]

COPILOT_MESSAGES_KEY = "synapse_copilot_messages"
COPILOT_MODEL_KEY = "synapse_copilot_model"

COPILOT_SYSTEM_PROMPT = """
Você é o Copiloto do Synapse AI, uma plataforma B2B de inteligência organizacional.

Atue como um braço de Customer Success dentro do produto. Seu papel é ajudar o usuário
a entender métricas, escolher o próximo passo e usar a plataforma com confiança.

Regras de comportamento:
- Responda em português do Brasil.
- Seja claro, direto e acolhedor.
- Evite jargões técnicos quando houver uma explicação de produto mais simples.
- Não prometa que executou ações que não foram acionadas pelo sistema.
- Oriente o usuário para as áreas certas: Dashboard, Base documental, Estúdio de IA,
  Insights e Evidências.
- Quando falar de documentos, fontes ou respostas, reforce que o Synapse trabalha com
  rastreabilidade e que decisões críticas devem ser validadas por responsáveis humanos.
- Não invente dados do usuário. Se não houver contexto suficiente, diga como ele pode
  obter a informação dentro da plataforma.
""".strip()

COPILOT_WELCOME_MESSAGE = (
    "Olá! Sou o assistente do Synapse AI. Posso te ajudar a entender suas métricas, "
    "escolher uma análise ou encontrar o próximo passo nos seus documentos. "
    "O que vamos fazer hoje?"
)


@dataclass(frozen=True)
class CopilotMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class CopilotIntent:
    kind: CopilotIntentKind
    target_page: str | None = None
    analysis_focus: str | None = None
    response: str | None = None


def render_copilot(config: AppConfig) -> None:
    render_page_header(
        "Copiloto Synapse",
        "Converse com um assistente de produto para entender métricas, escolher análises "
        "e navegar pela plataforma.",
        "Assistente virtual",
    )
    render_callout(
        "Como usar",
        "Faça perguntas sobre o Synapse ou peça ajuda para ir até uma área do produto. "
        "O Copiloto mantém o histórico desta sessão enquanto você navega.",
    )

    messages = _copilot_messages()
    if not messages:
        st.info(COPILOT_WELCOME_MESSAGE)

    for message in messages:
        with st.chat_message(message.role):
            st.markdown(message.content)

    prompt = st.chat_input("Pergunte ao Copiloto ou peça uma ação dentro do Synapse")
    if not prompt:
        return

    _append_copilot_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    intent = route_copilot_intent(prompt)
    if intent.kind == "navigation":
        assistant_response = execute_copilot_intent(intent)
    else:
        assistant_response = _generate_copilot_answer(config, _copilot_messages())

    _append_copilot_message("assistant", assistant_response)
    with st.chat_message("assistant"):
        st.markdown(assistant_response)

    if intent.kind == "navigation":
        st.rerun()


def route_copilot_intent(prompt: str) -> CopilotIntent:
    clean_prompt = prompt.casefold()
    if _contains_any(clean_prompt, ("dashboard", "painel", "visão geral", "visao geral")):
        return CopilotIntent(
            kind="navigation",
            target_page="dashboard",
            response="Claro. Vou te levar para o Dashboard executivo.",
        )
    if _contains_any(clean_prompt, ("perguntar", "responder", "analisar", "estúdio", "estudio")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            response=(
                "Vamos para o Estúdio de IA. Lá você escolhe o escopo e gera respostas "
                "com fontes."
            ),
        )
    if _contains_any(clean_prompt, ("plano de ação", "plano de acao", "tarefas", "responsáveis")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="action_plan",
            response="Vou abrir o Estúdio de IA já orientado para gerar um plano de ação.",
        )
    if _contains_any(clean_prompt, ("padrões", "padroes", "recorrência", "recorrencia")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="historical_patterns",
            response="Vou abrir o Estúdio de IA com foco em padrões históricos.",
        )
    if _contains_any(clean_prompt, ("multiagente", "agentes", "especialistas")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="multi_agent",
            response="Vou abrir o Estúdio de IA com foco na orquestração multiagente.",
        )
    if _contains_any(clean_prompt, ("resumo", "resumir", "síntese", "sintese")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            response="Vou abrir o Estúdio de IA para você gerar uma síntese com fontes.",
        )
    if _contains_any(clean_prompt, ("insights", "riscos", "alertas", "achados")):
        return CopilotIntent(
            kind="navigation",
            target_page="intelligence",
            response="Vou abrir Insights para você investigar riscos, alertas e achados salvos.",
        )
    if _contains_any(clean_prompt, ("evidências", "evidencias", "auditoria", "pacote")):
        return CopilotIntent(
            kind="navigation",
            target_page="audit",
            response=(
                "Vou abrir Evidências para você revisar fontes, registros e pacotes "
                "auditáveis."
            ),
        )
    if _contains_any(clean_prompt, ("upload", "subir", "enviar", "documento", "arquivo")):
        return CopilotIntent(
            kind="navigation",
            target_page="upload",
            response="Perfeito. Vou abrir a Base documental para você enviar ou revisar arquivos.",
        )
    return CopilotIntent(kind="conversation")


def execute_copilot_intent(intent: CopilotIntent) -> str:
    if intent.target_page:
        st.session_state["pending_private_page"] = intent.target_page
    if intent.analysis_focus:
        st.session_state["analysis_focus"] = intent.analysis_focus
    return intent.response or "Pronto. Direcionei você para a área mais adequada."


def _generate_copilot_answer(config: AppConfig, messages: list[CopilotMessage]) -> str:
    api_key = resolve_openai_api_key(st.secrets, fallback=config.openai.api_key)
    if not api_key:
        return (
            "Não encontrei a chave da OpenAI configurada para o Copiloto. "
            "Configure `OPENAI_API_KEY` nos segredos do Streamlit para ativar as respostas."
        )

    model = str(st.session_state.get(COPILOT_MODEL_KEY) or config.openai.generation_model)
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            instructions=COPILOT_SYSTEM_PROMPT,
            input=_build_copilot_input(messages),
        )
    except Exception:  # noqa: BLE001
        return (
            "Não consegui consultar a IA agora. Tente novamente em instantes ou use o menu "
            "lateral para seguir pelo fluxo principal."
        )

    answer = _extract_response_text(response)
    if not answer:
        return "A IA não retornou uma resposta útil agora. Tente reformular a pergunta."
    return answer


def resolve_openai_api_key(secrets: Mapping[str, Any], *, fallback: str = "") -> str:
    direct_key = secrets.get("OPENAI_API_KEY", "")
    if isinstance(direct_key, str) and direct_key.strip():
        return direct_key.strip()

    openai_section = secrets.get("openai", {})
    if isinstance(openai_section, Mapping):
        section_key = openai_section.get("api_key", "")
        if isinstance(section_key, str) and section_key.strip():
            return section_key.strip()

    return fallback.strip()


def _build_copilot_input(messages: list[CopilotMessage]) -> str:
    recent_messages = messages[-12:]
    transcript = "\n".join(
        f"{'Usuário' if message.role == 'user' else 'Copiloto'}: {message.content}"
        for message in recent_messages
    )
    return (
        "Histórico recente da conversa no Synapse AI:\n"
        f"{transcript}\n\n"
        "Responda à última mensagem do usuário de forma útil e objetiva."
    )


def _copilot_messages() -> list[CopilotMessage]:
    raw_messages = st.session_state.setdefault(COPILOT_MESSAGES_KEY, [])
    if not isinstance(raw_messages, list):
        st.session_state[COPILOT_MESSAGES_KEY] = []
        return []

    messages: list[CopilotMessage] = []
    for raw_message in raw_messages:
        if not isinstance(raw_message, dict):
            continue
        role = raw_message.get("role")
        content = raw_message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            messages.append(CopilotMessage(role=role, content=content))
    return messages


def _append_copilot_message(role: Literal["user", "assistant"], content: str) -> None:
    raw_messages = st.session_state.setdefault(COPILOT_MESSAGES_KEY, [])
    if not isinstance(raw_messages, list):
        raw_messages = []
        st.session_state[COPILOT_MESSAGES_KEY] = raw_messages
    raw_messages.append({"role": role, "content": content})
    del raw_messages[:-20]


def _extract_response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""

    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if not isinstance(content, list):
            continue
        for content_item in content:
            text = getattr(content_item, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)
