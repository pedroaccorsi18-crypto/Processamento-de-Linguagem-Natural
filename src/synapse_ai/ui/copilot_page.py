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
COPILOT_PENDING_ACTION_KEY = "synapse_copilot_pending_action"

COPILOT_SYSTEM_PROMPT = """
Você é o Copiloto do Synapse AI, uma plataforma B2B de inteligência organizacional.

Atue como um braço de Customer Success dentro do produto. Seu papel é ajudar o usuário
a entender métricas, escolher o próximo passo e usar a plataforma com confiança.

Regras de comportamento:
- Responda em português do Brasil.
- Seja claro, direto e acolhedor.
- Comece pela resposta prática e finalize com o próximo passo recomendado.
- Evite jargões técnicos quando houver uma explicação de produto mais simples.
- Não prometa que executou ações que não foram acionadas pelo sistema.
- Oriente o usuário para as áreas certas: Dashboard, Base documental, Estúdio de IA,
  Insights e Evidências.
- Quando o usuário pedir ajuda sobre uma tela, explique o objetivo daquela área, o que
  observar primeiro e qual ação prática faz sentido em seguida.
- Quando o usuário perguntar o que você faz, apresente capacidades reais do Synapse,
  sem exagero comercial e sem inventar integrações ou ações indisponíveis.
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
    action_label: str | None = None


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

    action_col, clear_col = st.columns([0.78, 0.22])
    with action_col:
        st.caption(
            "Use o Copiloto para decidir o próximo passo, entender indicadores "
            "ou navegar pelo produto."
        )
    with clear_col:
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state.pop(COPILOT_MESSAGES_KEY, None)
            st.session_state.pop(COPILOT_PENDING_ACTION_KEY, None)
            st.toast("Conversa reiniciada.")
            st.rerun()

    messages = _copilot_messages()
    if not messages:
        st.info(COPILOT_WELCOME_MESSAGE)
        _render_quick_actions(config)

    for message in messages:
        with st.chat_message(message.role):
            st.markdown(message.content)

    _render_pending_copilot_action()

    prompt = st.chat_input("Pergunte ao Copiloto ou peça uma ação dentro do Synapse")
    if not prompt:
        return

    _handle_copilot_prompt(config, prompt)
    st.rerun()


def render_copilot_sidebar(config: AppConfig, selected_page: str) -> None:
    st.sidebar.divider()
    with st.sidebar.expander("Copiloto contextual", expanded=False):
        st.caption(
            "Pergunte sem sair da tela atual. O Copiloto usa o contexto da área aberta "
            "para sugerir o próximo passo."
        )
        _render_contextual_quick_actions(config, selected_page)

        recent_messages = _copilot_messages()[-4:]
        if recent_messages:
            st.caption("Conversa recente")
            for message in recent_messages:
                speaker = "Você" if message.role == "user" else "Copiloto"
                st.markdown(f"**{speaker}:** {_compact_text(message.content, 180)}")

        with st.form("sidebar_copilot_form", clear_on_submit=True):
            prompt = st.text_area(
                "Pergunte ao Copiloto",
                placeholder="Ex.: O que eu devo fazer nesta tela?",
                height=92,
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Enviar ao Copiloto", type="primary")
        if submitted and prompt.strip():
            _handle_copilot_prompt(config, prompt.strip())
            st.rerun()

        _render_pending_copilot_action(prefix="sidebar")
        if st.button("Abrir central do Copiloto", use_container_width=True):
            st.session_state["pending_private_page"] = "copilot"
            st.rerun()


def _render_quick_actions(config: AppConfig) -> None:
    st.caption("Atalhos úteis para começar")
    actions = (
        (
            "Priorizar alertas",
            "Estou vendo alertas e evidências salvas. Qual é o melhor próximo passo?",
        ),
        ("Preparar base", "Quando devo preparar a base semântica e por que isso importa?"),
        ("Gerar plano", "Quero gerar um plano de ação a partir dos documentos."),
        ("Montar evidências", "Como eu preparo um pacote de evidências para apresentação?"),
    )
    columns = st.columns(len(actions))
    for index, (label, synthetic_prompt) in enumerate(actions):
        with columns[index]:
            if st.button(label, use_container_width=True, key=f"copilot_quick_action_{index}"):
                _handle_copilot_prompt(config, synthetic_prompt)
                st.rerun()


def _render_contextual_quick_actions(config: AppConfig, selected_page: str) -> None:
    actions_by_page = {
        "dashboard": (
            ("Ler KPIs", "Estou no Dashboard. Como devo interpretar os principais indicadores?"),
            ("Próximo passo", "Estou no Dashboard. Qual é o próximo melhor passo?"),
        ),
        "upload": (
            (
                "Ajuda no upload",
                "Estou na Base documental. O que devo conferir após subir um arquivo?",
            ),
            ("Preparar base", "Quando devo preparar a base semântica?"),
        ),
        "analysis": (
            ("Boa pergunta", "Estou no Estúdio de IA. Como faço uma pergunta forte com fontes?"),
            ("Plano de ação", "Quero transformar esta análise em plano de ação."),
        ),
        "intelligence": (
            ("Priorizar riscos", "Estou em Insights. Como priorizo riscos e alertas?"),
            ("Virar decisão", "Como transformo estes achados em decisão executiva?"),
        ),
        "audit": (
            ("Rastreabilidade", "Estou em Evidências. O que devo exportar para apresentar?"),
            ("Pacote final", "Como monto um pacote de evidências convincente?"),
        ),
        "copilot": (
            ("Capacidades", "O que você é capaz de fazer no Synapse?"),
            ("Roteiro", "Qual roteiro eu devo seguir para usar a plataforma bem?"),
        ),
    }
    actions = actions_by_page.get(selected_page, actions_by_page["copilot"])
    for index, (label, synthetic_prompt) in enumerate(actions):
        if st.button(
            label,
            use_container_width=True,
            key=f"sidebar_copilot_quick_{selected_page}_{index}",
        ):
            _handle_copilot_prompt(config, synthetic_prompt)
            st.rerun()


def _handle_copilot_prompt(config: AppConfig, prompt: str) -> None:
    _append_copilot_message("user", prompt)

    intent = route_copilot_intent(prompt)
    if intent.kind == "navigation":
        assistant_response = (
            intent.response or "Encontrei a área mais adequada para esse próximo passo."
        )
        _store_pending_copilot_action(intent)
    elif intent.response:
        assistant_response = intent.response
    else:
        assistant_response = _generate_copilot_answer(config, _copilot_messages())

    _append_copilot_message("assistant", assistant_response)


def route_copilot_intent(prompt: str) -> CopilotIntent:
    clean_prompt = prompt.casefold()
    if _contains_any(
        clean_prompt,
        (
            "o que você é capaz",
            "o que voce e capaz",
            "o que você faz",
            "o que voce faz",
            "como você pode ajudar",
            "como voce pode ajudar",
            "capacidades",
        ),
    ):
        return CopilotIntent(
            kind="conversation",
            response=(
                "Eu posso ajudar em três camadas do Synapse:\n\n"
                "1. **Orientação de uso:** explico o que cada tela faz, quando preparar "
                "a base semântica e qual fluxo seguir para chegar a uma análise confiável.\n\n"
                "2. **Decisão executiva:** ajudo a priorizar alertas, interpretar riscos, "
                "organizar evidências e escolher se o próximo passo é pergunta com fontes, "
                "plano de ação, padrões históricos, multiagente ou pacote de auditoria.\n\n"
                "3. **Navegação assistida:** quando fizer sentido, sugiro uma ação e mostro "
                "um botão para abrir a área certa sem tirar você do raciocínio.\n\n"
                "Eu ainda não executo operações sensíveis sozinho. A ideia é acelerar sua "
                "análise com rastreabilidade, mantendo decisões críticas sob validação humana."
            ),
        )
    if _contains_any(clean_prompt, ("dashboard", "painel", "visão geral", "visao geral")):
        return CopilotIntent(
            kind="navigation",
            target_page="dashboard",
            response=(
                "O Dashboard é o melhor ponto de partida para uma leitura executiva. "
                "Use-o para enxergar rapidamente volume documental, base preparada, "
                "análises salvas, riscos e alertas que precisam de atenção. Depois, "
                "aprofunde o que parecer crítico em Insights ou gere um plano de ação "
                "no Estúdio de IA.\n\n"
                "Posso abrir o Dashboard para você começar pela visão consolidada."
            ),
            action_label="Abrir Dashboard",
        )
    if _contains_any(clean_prompt, ("perguntar", "responder", "analisar", "estúdio", "estudio")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            response=(
                "O Estúdio de IA é onde a investigação acontece. Primeiro escolha os documentos "
                "que fazem parte do escopo, prepare a base semântica se ela estiver pendente e, "
                "então, faça perguntas com fontes rastreáveis. Para perguntas críticas, valide as "
                "evidências antes de tomar decisão executiva.\n\n"
                "Posso abrir o Estúdio de IA para você seguir por esse fluxo."
            ),
            action_label="Abrir Estúdio de IA",
        )
    if _contains_any(clean_prompt, ("plano de ação", "plano de acao", "tarefas", "responsáveis")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="action_plan",
            response=(
                "Para transformar análise em execução, o melhor caminho é gerar um plano de ação. "
                "Ele organiza tarefas, responsáveis, prazos, evidências e riscos em uma estrutura "
                "mais fácil de acompanhar. Antes de gerar, confirme se os documentos certos estão "
                "no escopo e se a base está preparada.\n\n"
                "Posso abrir o Estúdio de IA já no bloco de plano de ação."
            ),
            action_label="Gerar plano de ação",
        )
    if _contains_any(clean_prompt, ("padrões", "padroes", "recorrência", "recorrencia")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="historical_patterns",
            response=(
                "Padrões históricos ajudam a identificar recorrências: atrasos repetidos, riscos "
                "que aparecem em mais de um documento, responsáveis recorrentes e sinais "
                "de processo. Esse tipo de análise é mais forte quando você seleciona "
                "documentos comparáveis entre si.\n\n"
                "Posso abrir o Estúdio de IA no bloco de padrões históricos."
            ),
            action_label="Analisar padrões históricos",
        )
    if _contains_any(clean_prompt, ("multiagente", "agentes", "especialistas")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            analysis_focus="multi_agent",
            response=(
                "A orquestração multiagente serve para olhar o mesmo conjunto documental "
                "por lentes diferentes, como riscos, decisões, governança, consistência "
                "e recomendações. Use quando você quiser uma leitura mais robusta antes "
                "de consolidar uma decisão.\n\n"
                "Posso abrir o Estúdio de IA no bloco de agentes especializados."
            ),
            action_label="Executar agentes especializados",
        )
    if _contains_any(clean_prompt, ("resumo", "resumir", "síntese", "sintese")):
        return CopilotIntent(
            kind="navigation",
            target_page="analysis",
            response=(
                "Para uma síntese confiável, use o Estúdio de IA com os documentos "
                "corretos no escopo. A melhor pergunta costuma pedir decisões, riscos, "
                "responsáveis, prazos e lacunas de evidência. "
                "Assim a resposta já nasce pronta para discussão executiva.\n\n"
                "Posso abrir o Estúdio de IA para você gerar uma síntese com fontes."
            ),
            action_label="Gerar síntese com fontes",
        )
    if _contains_any(clean_prompt, ("insights", "riscos", "alertas", "achados")):
        return CopilotIntent(
            kind="navigation",
            target_page="intelligence",
            response=(
                "Quando há muitos alertas e evidências, comece por Insights. Priorize "
                "alertas críticos e de alta severidade, confira quais documentos sustentam "
                "cada achado e separe o que exige decisão humana. Depois disso, o próximo "
                "passo natural é gerar um plano de ação no Estúdio de IA e montar um "
                "pacote em Evidências para apresentação.\n\n"
                "Posso abrir Insights para você começar pelo diagnóstico."
            ),
            action_label="Abrir Insights",
        )
    if _contains_any(clean_prompt, ("evidências", "evidencias", "auditoria", "pacote")):
        return CopilotIntent(
            kind="navigation",
            target_page="audit",
            response=(
                "Evidências é a área certa quando você precisa mostrar rastreabilidade: "
                "quais documentos foram analisados, quais fontes sustentaram respostas "
                "e quais registros podem entrar em um pacote auditável. É o melhor "
                "fechamento para apresentação, revisão externa ou validação com "
                "responsáveis.\n\n"
                "Posso abrir Evidências para você revisar e exportar o material."
            ),
            action_label="Abrir Evidências",
        )
    if _contains_any(clean_prompt, ("upload", "subir", "enviar", "documento", "arquivo")):
        return CopilotIntent(
            kind="navigation",
            target_page="upload",
            response=(
                "A Base documental é onde o fluxo começa. Envie arquivos, revise se o "
                "texto foi extraído corretamente e confirme se o documento ficou disponível "
                "para preparação semântica. Depois do upload, vá ao Estúdio de IA para "
                "escolher o escopo e preparar a base.\n\n"
                "Posso abrir a Base documental para você enviar ou revisar arquivos."
            ),
            action_label="Abrir Base documental",
        )
    return CopilotIntent(kind="conversation")


def execute_copilot_intent(intent: CopilotIntent) -> str:
    if intent.target_page:
        st.session_state["pending_private_page"] = intent.target_page
    if intent.analysis_focus:
        st.session_state["analysis_focus"] = intent.analysis_focus
    st.session_state.pop(COPILOT_PENDING_ACTION_KEY, None)
    return intent.response or "Pronto. Direcionei você para a área mais adequada."


def _store_pending_copilot_action(intent: CopilotIntent) -> None:
    if not intent.target_page:
        st.session_state.pop(COPILOT_PENDING_ACTION_KEY, None)
        return

    st.session_state[COPILOT_PENDING_ACTION_KEY] = {
        "target_page": intent.target_page,
        "analysis_focus": intent.analysis_focus or "",
        "label": intent.action_label or "Abrir área sugerida",
    }


def _render_pending_copilot_action(*, prefix: str = "main") -> None:
    pending_action = st.session_state.get(COPILOT_PENDING_ACTION_KEY)
    if not isinstance(pending_action, dict):
        return

    label = pending_action.get("label")
    target_page = pending_action.get("target_page")
    analysis_focus = pending_action.get("analysis_focus")
    if not isinstance(label, str) or not isinstance(target_page, str):
        st.session_state.pop(COPILOT_PENDING_ACTION_KEY, None)
        return

    st.divider()
    st.caption("Próxima ação sugerida")
    if st.button(
        label,
        type="primary",
        use_container_width=True,
        key=f"{prefix}_copilot_pending_action",
    ):
        st.session_state["pending_private_page"] = target_page
        if isinstance(analysis_focus, str) and analysis_focus:
            st.session_state["analysis_focus"] = analysis_focus
        st.session_state.pop(COPILOT_PENDING_ACTION_KEY, None)
        st.rerun()


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
    current_area = _current_product_area()
    return (
        "Mapa do produto:\n"
        "- Dashboard: visão executiva, KPIs, alertas e indicadores consolidados.\n"
        "- Base documental: upload, importação, documentos recentes e disponibilidade "
        "dos arquivos.\n"
        "- Estúdio de IA: perguntas com fontes, plano de ação, padrões históricos e multiagente.\n"
        "- Insights: análise de riscos, alertas preventivos e achados organizacionais.\n"
        "- Evidências: auditoria, fontes salvas, registros e pacotes exportáveis.\n\n"
        f"Área atual do usuário: {current_area}.\n\n"
        "Histórico recente da conversa no Synapse AI:\n"
        f"{transcript}\n\n"
        "Responda à última mensagem do usuário de forma útil e objetiva. "
        "Quando fizer sentido, indique o próximo passo dentro do produto."
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


def _compact_text(value: str, max_length: int) -> str:
    clean_value = " ".join(value.split())
    if len(clean_value) <= max_length:
        return clean_value
    return f"{clean_value[: max_length - 1].rstrip()}..."


def _current_product_area() -> str:
    page = st.session_state.get("private_page") or st.session_state.get("selected_page")
    labels = {
        "dashboard": "Dashboard",
        "upload": "Base documental",
        "analysis": "Estúdio de IA",
        "intelligence": "Insights",
        "audit": "Evidências",
        "copilot": "Copiloto",
    }
    if isinstance(page, str):
        return labels.get(page, page)
    return "não identificada"
