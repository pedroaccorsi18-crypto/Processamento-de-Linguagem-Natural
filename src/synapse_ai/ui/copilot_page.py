from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import streamlit as st
from openai import OpenAI

from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.ui.cache import (
    cached_recent_analyses,
    cached_user_documents_for_processing,
)
from synapse_ai.ui.state import current_tenant_id
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


def render_copilot_context_panel(config: AppConfig, selected_page: str) -> None:
    context = _page_context(selected_page)
    with st.container(border=True):
        st.caption("Copiloto contextual")
        header_col, action_col = st.columns([0.72, 0.28])
        with header_col:
            st.markdown(f"**Assistente ativo em {context['label']}**")
            st.caption(context["description"])
        with action_col:
            if st.button("Abrir central", use_container_width=True, key="context_open_copilot"):
                st.session_state["pending_private_page"] = "copilot"
                st.rerun()

        latest_answer = _latest_assistant_message()
        if latest_answer:
            with st.expander("Última orientação do Copiloto", expanded=True):
                st.markdown(latest_answer)
        else:
            st.info(context["empty_state"])

        _render_contextual_quick_actions(
            config,
            selected_page,
            prefix="context",
            layout="columns",
        )

        with st.form(f"context_copilot_form_{selected_page}", clear_on_submit=True):
            prompt = st.text_input(
                "Pergunte ao Copiloto sem sair desta tela",
                placeholder=context["placeholder"],
            )
            submitted = st.form_submit_button("Perguntar ao Copiloto", type="primary")
        if submitted and prompt.strip():
            _handle_copilot_prompt(config, prompt.strip())
            st.rerun()

        _render_pending_copilot_action(prefix="context")


def render_copilot_sidebar(config: AppConfig, selected_page: str) -> None:
    st.sidebar.divider()
    with st.sidebar.expander("Copiloto contextual", expanded=False):
        st.caption(
            "Pergunte sem sair da tela atual. O Copiloto usa o contexto da área aberta "
            "para sugerir o próximo passo."
        )
        _render_contextual_quick_actions(config, selected_page, prefix="sidebar")

        latest_answer = _latest_assistant_message()
        if latest_answer:
            st.caption("Resposta mais recente")
            st.markdown(latest_answer)

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


def _render_contextual_quick_actions(
    config: AppConfig,
    selected_page: str,
    *,
    prefix: str,
    layout: Literal["stack", "columns"] = "stack",
) -> None:
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
    if layout == "columns":
        columns = st.columns(len(actions))
        for index, (label, synthetic_prompt) in enumerate(actions):
            with columns[index]:
                _render_contextual_quick_action(
                    config,
                    selected_page,
                    index,
                    label,
                    synthetic_prompt,
                    prefix=prefix,
                )
        return

    for index, (label, synthetic_prompt) in enumerate(actions):
        _render_contextual_quick_action(
            config,
            selected_page,
            index,
            label,
            synthetic_prompt,
            prefix=prefix,
        )


def _render_contextual_quick_action(
    config: AppConfig,
    selected_page: str,
    index: int,
    label: str,
    synthetic_prompt: str,
    *,
    prefix: str,
) -> None:
    if st.button(
        label,
        use_container_width=True,
        key=f"{prefix}_copilot_quick_{selected_page}_{index}",
    ):
        _handle_copilot_prompt(config, synthetic_prompt)
        st.rerun()


def _handle_copilot_prompt(config: AppConfig, prompt: str) -> None:
    _append_copilot_message("user", prompt)

    if _is_document_excerpt_request(prompt):
        assistant_response = _answer_document_excerpt_request(config, prompt)
    elif (intent := route_copilot_intent(prompt)).kind == "navigation":
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
    context_snapshot = _load_copilot_context_snapshot(config)
    current_area = _current_product_area()
    system_content = (
        f"{COPILOT_SYSTEM_PROMPT}\n\n"
        "Mapa do produto:\n"
        "- Dashboard: visão executiva, KPIs, alertas e indicadores consolidados.\n"
        "- Base documental: upload, importação, documentos recentes e disponibilidade "
        "dos arquivos.\n"
        "- Estúdio de IA: perguntas com fontes, plano de ação, padrões históricos e multiagente.\n"
        "- Insights: análise de riscos, alertas preventivos e achados organizacionais.\n"
        "- Evidências: auditoria, fontes salvas, registros e pacotes exportáveis.\n\n"
        f"Área atual do usuário: {current_area}.\n\n"
        "Contexto disponível do usuário:\n"
        f"{context_snapshot or 'Nenhum contexto documental adicional foi carregado.'}"
    )
    chat_messages = [
        {"role": "system", "content": system_content},
        *[
            {"role": message.role, "content": message.content}
            for message in messages[-12:]
        ],
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=chat_messages,
        )
    except Exception:  # noqa: BLE001
        return (
            "Não consegui consultar a IA agora. Tente novamente em instantes ou use o menu "
            "lateral para seguir pelo fluxo principal."
        )

    answer = response.choices[0].message.content if response.choices else ""
    if not answer:
        return "A IA não retornou uma resposta útil agora. Tente reformular a pergunta."
    return answer.strip()


def _answer_document_excerpt_request(config: AppConfig, prompt: str) -> str:
    documents = _load_user_processable_documents(config)
    return _build_document_excerpt_answer(documents, prompt)


def _load_user_processable_documents(config: AppConfig) -> list[dict[str, object]]:
    user = get_current_session_user()
    access_token = get_access_token()
    if user is None or access_token is None:
        return []

    try:
        connection = create_authenticated_supabase_connection(
            config,
            access_token,
            get_refresh_token(),
        )
        update_auth_tokens(connection.access_token, connection.refresh_token)
        tenant_id = current_tenant_id(user)
        return cached_user_documents_for_processing(connection.client, tenant_id, user.id)
    except Exception:  # noqa: BLE001
        return []


def _load_copilot_context_snapshot(config: AppConfig) -> str:
    documents = _load_user_processable_documents(config)
    user = get_current_session_user()
    access_token = get_access_token()
    analyses: list[dict[str, object]] = []
    if user is not None and access_token is not None:
        try:
            connection = create_authenticated_supabase_connection(
                config,
                access_token,
                get_refresh_token(),
            )
            update_auth_tokens(connection.access_token, connection.refresh_token)
            tenant_id = current_tenant_id(user)
            analyses = cached_recent_analyses(connection.client, tenant_id, user.id, 8)
        except Exception:  # noqa: BLE001
            analyses = []
    return _build_context_snapshot(documents, analyses)


def _build_context_snapshot(
    documents: list[dict[str, object]],
    analyses: list[dict[str, object]],
) -> str:
    sections: list[str] = []
    if documents:
        document_lines = []
        for document in documents[:5]:
            filename = str(document.get("filename") or "Documento sem nome")
            char_count = document.get("text_char_count") or 0
            document_lines.append(f"- {filename} ({char_count} caracteres extraídos)")
        sections.append("Documentos recentes:\n" + "\n".join(document_lines))
    else:
        sections.append("Documentos recentes: nenhum documento extraído encontrado.")

    if analyses:
        analysis_lines = []
        for analysis in analyses[:5]:
            title = str(
                analysis.get("title")
                or analysis.get("question")
                or "Análise salva sem título"
            )
            analysis_lines.append(f"- {title}")
        sections.append("Análises recentes:\n" + "\n".join(analysis_lines))
    else:
        sections.append("Análises recentes: nenhuma análise salva encontrada.")
    return "\n\n".join(sections)


def _build_document_excerpt_answer(
    documents: list[dict[str, object]],
    prompt: str,
) -> str:
    if not documents:
        return (
            "Não encontrei documentos com texto extraído na sua conta agora. Se você acabou "
            "de enviar um arquivo, confira na Base documental se ele aparece como extraído. "
            "Para análises com fonte, o próximo passo é preparar a base semântica no Estúdio de IA."
        )

    excerpts = _select_document_excerpts(documents, prompt, max_excerpts=5)
    if not excerpts:
        return (
            "Encontrei documentos enviados, mas não localizei texto suficiente para elencar "
            "trechos úteis. Confira se a extração do arquivo foi concluída na Base documental."
        )

    lines = [
        "Separei os principais trechos disponíveis nos documentos extraídos da sua conta:",
        "",
    ]
    for index, excerpt in enumerate(excerpts, start=1):
        lines.extend(
            [
                f"**{index}. {excerpt['filename']}**",
                f"> {excerpt['text']}",
                "",
            ]
        )
    lines.append(
        "Para uma resposta analítica com citações e fontes, use o Estúdio de IA com esses "
        "documentos no escopo. O Copiloto aqui ajuda a orientar e antecipar os pontos principais."
    )
    return "\n".join(lines).strip()


def _select_document_excerpts(
    documents: list[dict[str, object]],
    prompt: str,
    *,
    max_excerpts: int,
) -> list[dict[str, str]]:
    query_terms = _significant_terms(prompt)
    candidates: list[tuple[int, int, dict[str, str]]] = []
    for document_order, document in enumerate(documents):
        filename = str(document.get("filename") or "Documento sem nome")
        text = document.get("extracted_text")
        if not isinstance(text, str) or not text.strip():
            continue
        for paragraph_order, paragraph in enumerate(_candidate_paragraphs(text)):
            score = _excerpt_score(paragraph, query_terms)
            if score <= 0 and query_terms:
                continue
            candidates.append(
                (
                    score,
                    -(document_order * 1000 + paragraph_order),
                    {
                        "filename": filename,
                        "text": _trim_excerpt(paragraph),
                    },
                )
            )

    if not candidates and not query_terms:
        for document in documents:
            filename = str(document.get("filename") or "Documento sem nome")
            text = document.get("extracted_text")
            if isinstance(text, str) and text.strip():
                return [{"filename": filename, "text": _trim_excerpt(text)}]

    ranked = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)
    excerpts: list[dict[str, str]] = []
    seen_texts: set[str] = set()
    for _, _, excerpt in ranked:
        fingerprint = excerpt["text"][:120].casefold()
        if fingerprint in seen_texts:
            continue
        seen_texts.add(fingerprint)
        excerpts.append(excerpt)
        if len(excerpts) >= max_excerpts:
            break
    return excerpts


def _candidate_paragraphs(text: str) -> list[str]:
    normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not normalized_lines:
        return []
    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in normalized_lines:
        buffer.append(line)
        if len(" ".join(buffer)) >= 260:
            paragraphs.append(" ".join(buffer))
            buffer = []
    if buffer:
        paragraphs.append(" ".join(buffer))
    return [paragraph for paragraph in paragraphs if len(paragraph) >= 80]


def _significant_terms(prompt: str) -> set[str]:
    stopwords = {
        "consegue",
        "principais",
        "trechos",
        "parte",
        "partes",
        "documento",
        "documentos",
        "enviei",
        "enviado",
        "arquivo",
        "arquivos",
        "sobre",
        "para",
        "com",
        "que",
        "uma",
        "dos",
        "das",
        "me",
        "o",
        "a",
    }
    terms = {
        term.strip(".,;:!?()[]{}\"'").casefold()
        for term in prompt.split()
        if len(term.strip(".,;:!?()[]{}\"'")) >= 4
    }
    return {term for term in terms if term and term not in stopwords}


def _excerpt_score(paragraph: str, query_terms: set[str]) -> int:
    clean_paragraph = paragraph.casefold()
    score = sum(3 for term in query_terms if term in clean_paragraph)
    if any(marker in clean_paragraph for marker in ("decidiu", "risco", "prazo", "responsável")):
        score += 2
    if len(paragraph) >= 180:
        score += 1
    return score


def _trim_excerpt(text: str, limit: int = 520) -> str:
    clean_text = " ".join(text.split())
    if len(clean_text) <= limit:
        return clean_text
    return f"{clean_text[: limit - 1].rstrip()}..."


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


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _is_document_excerpt_request(prompt: str) -> bool:
    clean_prompt = prompt.casefold()
    return _contains_any(
        clean_prompt,
        (
            "principais trechos",
            "trechos do que enviei",
            "trechos que enviei",
            "o que enviei",
            "o arquivo que enviei",
            "documento que enviei",
            "principais pontos do documento",
            "principais partes",
            "resuma o que enviei",
        ),
    )


def _latest_assistant_message() -> str:
    for message in reversed(_copilot_messages()):
        if message.role == "assistant":
            return message.content
    return ""


def _page_context(selected_page: str) -> dict[str, str]:
    contexts = {
        "dashboard": {
            "label": "Dashboard",
            "description": (
                "Ajuda a interpretar KPIs, riscos consolidados e próximos passos executivos."
            ),
            "empty_state": (
                "Pergunte como ler os indicadores ou peça uma recomendação de próximo passo."
            ),
            "placeholder": "Ex.: O que merece minha atenção primeiro neste painel?",
        },
        "upload": {
            "label": "Base documental",
            "description": (
                "Ajuda a conferir upload, tipos de arquivo, duplicidade e preparação semântica."
            ),
            "empty_state": (
                "Pergunte o que validar após enviar um arquivo ou quando preparar a base para IA."
            ),
            "placeholder": "Ex.: O que devo conferir depois de subir este documento?",
        },
        "analysis": {
            "label": "Estúdio de IA",
            "description": (
                "Ajuda a escolher perguntas, escopo documental, planos de ação e agentes."
            ),
            "empty_state": (
                "Peça ajuda para formular uma pergunta forte ou decidir qual análise executar."
            ),
            "placeholder": "Ex.: Qual pergunta eu devo fazer para extrair decisões e riscos?",
        },
        "intelligence": {
            "label": "Insights",
            "description": (
                "Ajuda a priorizar alertas, riscos, padrões e achados salvos."
            ),
            "empty_state": (
                "Pergunte como transformar alertas e evidências em decisão executiva."
            ),
            "placeholder": "Ex.: Como priorizo estes riscos para uma reunião executiva?",
        },
        "audit": {
            "label": "Evidências",
            "description": (
                "Ajuda a preparar rastreabilidade, auditoria e pacotes para apresentação."
            ),
            "empty_state": (
                "Pergunte o que exportar para provar as fontes e decisões do Synapse."
            ),
            "placeholder": "Ex.: Como monto um pacote de evidências convincente?",
        },
        "copilot": {
            "label": "Copiloto",
            "description": "Ajuda a navegar pelo Synapse e escolher o melhor fluxo.",
            "empty_state": COPILOT_WELCOME_MESSAGE,
            "placeholder": "Ex.: Qual roteiro devo seguir para usar a plataforma?",
        },
    }
    return contexts.get(selected_page, contexts["copilot"])


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
