from __future__ import annotations

from collections import Counter
from datetime import datetime

import streamlit as st

from synapse_ai.application.analysis import (
    ActionPlanCommand,
    AskQuestionCommand,
    DocumentComparisonCommand,
    HistoricalPatternsCommand,
    IntelligenceSnapshotCommand,
    MultiAgentReportCommand,
    PreventiveAlertsCommand,
    SentimentAnalysisCommand,
)
from synapse_ai.application.indexing import PrepareSemanticBaseCommand
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.services.agent_service import (
    MultiAgentReport,
    multi_agent_report_to_csv,
    multi_agent_report_to_markdown,
    multi_agent_report_to_xlsx,
)
from synapse_ai.services.alert_service import (
    PreventiveAlertReport,
    preventive_alert_report_to_csv,
    preventive_alert_report_to_markdown,
    preventive_alert_report_to_xlsx,
)
from synapse_ai.services.analysis_service import (
    ActionPlan,
    action_plan_to_csv,
    action_plan_to_markdown,
    action_plan_to_xlsx,
)
from synapse_ai.services.comparison_service import (
    DocumentComparisonReport,
    document_comparison_to_csv,
    document_comparison_to_markdown,
    document_comparison_to_xlsx,
)
from synapse_ai.services.intelligence_service import (
    IntelligenceSnapshot,
    intelligence_snapshot_to_csv,
    intelligence_snapshot_to_markdown,
    intelligence_snapshot_to_xlsx,
)
from synapse_ai.services.pattern_service import (
    HistoricalPatternReport,
    historical_pattern_report_to_csv,
    historical_pattern_report_to_markdown,
    historical_pattern_report_to_xlsx,
)
from synapse_ai.services.sentiment_service import (
    SentimentReport,
    sentiment_report_to_csv,
    sentiment_report_to_markdown,
    sentiment_report_to_xlsx,
)
from synapse_ai.ui.analysis_use_cases import (
    build_action_plan_use_case,
    build_ask_question_use_case,
    build_document_comparison_use_case,
    build_historical_patterns_use_case,
    build_intelligence_snapshot_use_case,
    build_multi_agent_report_use_case,
    build_prepare_semantic_base_use_case,
    build_preventive_alerts_use_case,
    build_sentiment_analysis_use_case,
)
from synapse_ai.ui.cache import (
    cached_document_chunk_counts,
    cached_recent_analyses,
    cached_user_documents_for_processing,
    get_openai_client,
    invalidate_data_cache,
)
from synapse_ai.ui.state import current_tenant_id, remember_analysis_result
from synapse_ai.ui.theme import render_callout, render_kpi_card, render_page_header


def render_analysis_page(config: AppConfig) -> None:
    render_page_header(
        "Estúdio de IA",
        "Escolha o escopo, faça perguntas com fontes ou gere análises especializadas "
        "em poucos passos.",
        "Inteligência aplicada",
    )
    _render_analysis_focus_hint()

    user = get_current_session_user()
    if user is None:
        st.info("Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar.")
        return

    access_token = get_access_token()
    if access_token is None:
        st.info("Sua autenticação precisa ser renovada para consultar documentos.")
        return

    try:
        connection = create_authenticated_supabase_connection(
            config,
            access_token,
            get_refresh_token(),
        )
    except RuntimeError as exc:
        st.error(str(exc))
        return
    update_auth_tokens(connection.access_token, connection.refresh_token)
    supabase_client = connection.client

    tenant_id = current_tenant_id(user)
    openai_client = get_openai_client(config)
    documents = cached_user_documents_for_processing(supabase_client, tenant_id, user.id)

    st.subheader("Escopo de trabalho")
    render_callout(
        "Antes de perguntar, escolha o contexto",
        "A IA consulta apenas os documentos selecionados abaixo. Isso evita misturar "
        "assuntos diferentes e mantém a resposta mais precisa.",
    )
    if "semantic_index_success" in st.session_state:
        st.success(str(st.session_state.pop("semantic_index_success")))
    if not documents:
        st.info("Envie e salve documentos na página de upload antes de rodar análises.")
        return

    document_options = _document_options(documents)
    chunk_counts = cached_document_chunk_counts(
        supabase_client,
        tenant_id,
        user.id,
        tuple(_document_ids(documents)),
        config.openai.embedding_model,
    )
    document_labels = list(document_options.keys())
    st.caption(
        "A IA usa somente os documentos do escopo abaixo. Documentos preparados continuam na "
        "busca interna, mas não entram na análise se não estiverem selecionados."
    )
    scope_mode = st.radio(
        "Escopo da análise",
        options=(
            "Último documento enviado",
            "Selecionar manualmente",
            "Toda a base documental",
        ),
        horizontal=True,
        help=(
            "Use o último documento para evitar misturar assuntos diferentes. Escolha toda a "
            "base apenas quando quiser analisar o acervo completo."
        ),
    )
    if scope_mode == "Toda a base documental":
        selected_labels = document_labels
        st.info(
            "Toda a base documental está no escopo. Use esta opção quando os documentos fazem "
            "parte do mesmo contexto de análise."
        )
    elif scope_mode == "Selecionar manualmente":
        selected_labels = st.multiselect(
            "Documentos usados nesta análise",
            options=document_labels,
            default=document_labels[:1],
            help="Selecione apenas documentos que pertencem ao mesmo assunto ou decisão.",
            key="analysis-selected-documents",
        )
    else:
        selected_labels = document_labels[:1]
        if selected_labels:
            st.info(
                "Escopo atual: último documento enviado. Para comparar ou juntar documentos, "
                "troque o escopo para seleção manual ou toda a base."
            )
    selected_document_ids = [
        document_options[label]["id"]
        for label in selected_labels
        if isinstance(document_options[label].get("id"), str)
    ]
    selected_documents = [
        document for document in documents if document.get("id") in set(selected_document_ids)
    ]
    if not selected_document_ids:
        st.warning("Selecione pelo menos um documento para definir o escopo da análise.")
        return
    duplicate_filenames = _duplicate_filenames(selected_documents)
    if duplicate_filenames:
        st.warning(
            "Há documentos com o mesmo nome no escopo. Confira a data e o identificador "
            f"antes de perguntar: {', '.join(duplicate_filenames)}."
        )
    unprepared_documents = [
        document
        for document in selected_documents
        if _document_chunk_count(document, chunk_counts) == 0
    ]
    if unprepared_documents:
        st.info(
            "Há documento(s) selecionado(s) ainda não preparado(s) para IA. Prepare o escopo "
            "antes de perguntar para incluir esses arquivos na busca."
        )
    total_chars = sum(_as_int(document.get("text_char_count")) for document in documents)
    selected_chars = sum(
        _as_int(document.get("text_char_count")) for document in selected_documents
    )
    metric_cols = st.columns(3)
    with metric_cols[0]:
        render_kpi_card(
            "Documentos no escopo",
            f"{len(selected_documents)} de {len(documents)}",
            "Arquivos usados nesta análise.",
            tone="blue",
        )
    with metric_cols[1]:
        render_kpi_card(
            "Caracteres no escopo",
            str(selected_chars or total_chars),
            "Volume textual disponível para busca.",
            tone="green",
        )
    with metric_cols[2]:
        render_kpi_card(
            "Preparação",
            "Pendente" if unprepared_documents else "Pronto",
            "Indica se o escopo selecionado já pode responder com fontes.",
            tone="amber" if unprepared_documents else "green",
        )

    st.caption(
        "Prepare documentos quando enviar arquivos novos ou mudar o escopo. Depois disso, "
        "você pode fazer várias perguntas sem repetir esta etapa."
    )
    with st.expander("Ajuda rápida: preparação para IA", expanded=False):
        st.help(_semantic_base_help)
    with st.expander("Documentos disponíveis"):
        for index, document in enumerate(documents, start=1):
            st.write(_format_document_label(document, index))
            st.caption(
                f"Status: {document.get('status', 'indefinido')} | "
                f"Caracteres: {document.get('text_char_count', 0)}"
            )
            _render_ai_status(document, chunk_counts)

    documents_to_index = selected_documents
    if st.button(
        f"Preparar documentos selecionados para IA ({len(documents_to_index)} documento(s))",
        type="primary",
        help=(
            "Cria a estrutura interna de busca apenas para os documentos selecionados. Use "
            "quando subir arquivos novos ou trocar o escopo de análise."
        ),
    ):
        indexed_chunks = _index_documents(
            supabase_client,
            openai_client,
            user.id,
            documents_to_index,
            config,
        )
        if indexed_chunks is not None:
            st.session_state["semantic_index_success"] = (
                f"Documentos preparados para IA com {indexed_chunks} trecho(s). "
                "Agora você pode fazer várias perguntas usando esta mesma preparação."
            )
            st.rerun()

    question_tab, workflow_tab, history_tab = st.tabs(
        ["Perguntar com fontes", "Gerar análises", "Histórico"]
    )
    with question_tab:
        st.subheader("Perguntar ao Synapse AI")
        question = st.text_area(
            "Pergunta",
            placeholder="Quais decisões, riscos ou inconsistências aparecem nos documentos?",
            height=110,
        )
        save_to_history = st.checkbox(
            "Salvar esta análise no histórico",
            value=True,
            help="Use quando precisar manter uma trilha auditável da pergunta e da resposta.",
        )

        if st.button("Responder com fontes", type="primary"):
            _answer_question(
                supabase_client,
                openai_client,
                user.id,
                question,
                config,
                save_to_history,
                selected_document_ids,
            )

    with workflow_tab:
        _render_analysis_workflow_center(
            supabase_client,
            openai_client,
            user.id,
            config,
            selected_document_ids,
        )

    with history_tab:
        _render_analysis_history(supabase_client, tenant_id, user.id)


def _render_analysis_workflow_center(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.subheader("Gerar análises especializadas")
    st.write(
        "Escolha uma capacidade para transformar o escopo atual em evidências, alertas, "
        "comparações ou planos acompanháveis."
    )

    workflow_labels = [
        "Inteligência organizacional",
        "Comparação documental",
        "Sentimentos organizacionais",
        "Alertas preventivos",
        "Padrões históricos",
        "Orquestração multiagente",
        "Plano de ação",
    ]
    default_label = _default_analysis_workflow_label(workflow_labels)
    selected_workflow = st.selectbox(
        "Tipo de análise",
        workflow_labels,
        index=workflow_labels.index(default_label),
        help="Troque o tipo de análise sem precisar percorrer uma tela longa.",
    )
    _render_workflow_guidance(selected_workflow)

    if selected_workflow == "Inteligência organizacional":
        _render_intelligence_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    elif selected_workflow == "Comparação documental":
        _render_comparison_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    elif selected_workflow == "Sentimentos organizacionais":
        _render_sentiment_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    elif selected_workflow == "Alertas preventivos":
        _render_preventive_alerts_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    elif selected_workflow == "Padrões históricos":
        _render_historical_patterns_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    elif selected_workflow == "Orquestração multiagente":
        _render_multi_agent_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )
    else:
        _render_action_plan_workflow(
            supabase_client,
            openai_client,
            user_id,
            config,
            selected_document_ids,
        )


def _default_analysis_workflow_label(workflow_labels: list[str]) -> str:
    focus_to_label = {
        "action_plan": "Plano de ação",
        "historical_patterns": "Padrões históricos",
        "multi_agent": "Orquestração multiagente",
    }
    focused_label = focus_to_label.get(str(st.session_state.get("analysis_focus", "")))
    return focused_label if focused_label in workflow_labels else workflow_labels[0]


def _render_workflow_guidance(selected_workflow: str) -> None:
    guidance = {
        "Inteligência organizacional": (
            "Fotografia executiva",
            "Melhor escolha para entender rapidamente decisões, riscos, prazos e lacunas "
            "presentes nos documentos selecionados.",
        ),
        "Comparação documental": (
            "Comparação entre versões ou fontes",
            "Use quando houver mais de um documento no mesmo contexto e você quiser detectar "
            "divergências, mudanças de prazo ou responsabilidades conflitantes.",
        ),
        "Sentimentos organizacionais": (
            "Leitura de tom e tensão",
            "Útil para transcrições, atas e comunicações internas em que urgência, conflito "
            "ou confiança precisam ser interpretados.",
        ),
        "Alertas preventivos": (
            "Radar de atenção",
            "Transforma evidências em sinais de acompanhamento, como pendências, riscos sem "
            "plano e decisões que exigem validação.",
        ),
        "Padrões históricos": (
            "Recorrências no tempo",
            "Compara o escopo atual com análises salvas para revelar problemas repetidos "
            "ou comportamentos recorrentes.",
        ),
        "Orquestração multiagente": (
            "Parecer por especialistas",
            "Executa perspectivas diferentes sobre o mesmo escopo, como risco, decisão, "
            "governança e consistência documental.",
        ),
        "Plano de ação": (
            "Da análise para execução",
            "Converte achados em tarefas, responsáveis, prazos, critérios de aceite e riscos "
            "a acompanhar.",
        ),
    }
    title, body = guidance.get(
        selected_workflow,
        ("Análise especializada", "Use esta capacidade para aprofundar o escopo selecionado."),
    )
    render_callout(title, body)


def _render_save_toggle(label: str, help_text: str, key: str) -> bool:
    return st.checkbox(
        label,
        value=True,
        help=help_text,
        key=key,
    )


def _render_intelligence_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Extrai decisões, riscos, inconsistências, prazos e recomendações dos documentos "
        "selecionados."
    )
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém a fotografia estruturada para auditoria e relatórios futuros.",
        "save-intelligence-workflow",
    )
    if st.button("Gerar inteligência organizacional", type="primary"):
        _generate_intelligence_snapshot(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_comparison_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Compara documentos para detectar divergências de datas, decisões, responsáveis, "
        "riscos, escopo e evidências."
    )
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém as divergências encontradas para auditoria futura.",
        "save-comparison-workflow",
    )
    if st.button("Comparar documentos selecionados", type="primary"):
        _generate_document_comparison(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_sentiment_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Analisa tom, urgência, tensão, confiança, conflito e risco percebido com "
        "rastreabilidade."
    )
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém a leitura de tom organizacional para auditoria futura.",
        "save-sentiment-workflow",
    )
    if st.button("Analisar sentimentos organizacionais", type="primary"):
        _generate_sentiment_report(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_preventive_alerts_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Identifica sinais que exigem atenção antes de virarem problema, como prazo crítico, "
        "responsável ausente, risco sem plano ou decisão conflitante."
    )
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém os alertas preventivos para acompanhamento futuro.",
        "save-alerts-workflow",
    )
    if st.button("Gerar alertas preventivos", type="primary"):
        _generate_preventive_alert_report(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_historical_patterns_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Compara os sinais atuais com análises já salvas para reconhecer riscos, atrasos, "
        "pendências ou inconsistências recorrentes."
    )
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém a leitura de recorrência para auditoria futura.",
        "save-patterns-workflow",
    )
    if st.button("Reconhecer padrões históricos", type="primary"):
        _generate_historical_pattern_report(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_multi_agent_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write(
        "Executa agentes especializados para avaliar decisões, riscos, consistência "
        "documental, sentimentos e governança antes da consolidação final."
    )
    with st.expander("Ajuda rápida: orquestração multiagente", expanded=False):
        st.help(_multi_agent_help)
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém o parecer multiagente para auditoria futura.",
        "save-multi-agent-workflow",
    )
    if st.button(
        "Executar agentes especializados",
        type="primary",
        help=(
            "Roda perspectivas complementares sobre o mesmo escopo documental. É indicado "
            "quando você precisa comparar riscos, decisões e recomendações."
        ),
    ):
        _generate_multi_agent_report(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_action_plan_workflow(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    selected_document_ids: list[str],
) -> None:
    st.write("Transforma decisões, riscos e pendências em uma lista acompanhável.")
    save_to_history = _render_save_toggle(
        "Salvar no histórico e atualizar Dashboard",
        "Mantém o plano disponível no Dashboard, na Auditoria e nos relatórios.",
        "save-action-plan-workflow",
    )
    if st.button("Gerar plano de ação com fontes", type="primary"):
        _generate_action_plan(
            supabase_client,
            openai_client,
            user_id,
            config,
            save_to_history,
            selected_document_ids,
        )


def _render_analysis_focus_hint() -> None:
    focus = st.session_state.get("analysis_focus")
    hints = {
        "action_plan": (
            "Plano de ação",
            "Selecione os documentos, confirme se eles estão prontos para IA e abra a aba "
            "Gerar análises. O tipo Plano de ação já estará selecionado.",
        ),
        "historical_patterns": (
            "Padrões históricos",
            "Selecione os documentos, confira se há análises anteriores salvas e abra a aba "
            "Gerar análises. O tipo Padrões históricos já estará selecionado.",
        ),
        "multi_agent": (
            "Orquestração multiagente",
            "Selecione os documentos e abra a aba Gerar análises. O tipo Orquestração "
            "multiagente já estará selecionado.",
        ),
    }
    if focus not in hints:
        return

    title, body = hints[focus]
    st.info(f"Você veio do Dashboard para gerar: {title}. {body}")
    if st.button("Limpar orientação", key="clear-analysis-focus"):
        st.session_state.pop("analysis_focus", None)
        st.rerun()


def _semantic_base_help() -> None:
    """Prepara documentos para perguntas com fontes.

    Esta ação organiza o conteúdo em trechos pesquisáveis e cria os vetores internos usados
    pela busca semântica. Ela não gera uma resposta sozinha e não precisa ser repetida a cada
    pergunta. Use quando subir arquivos novos, trocar o escopo ou alterar o modelo técnico de
    preparação.
    """


def _multi_agent_help() -> None:
    """Executa perspectivas especializadas sobre o mesmo escopo.

    A orquestração multiagente compara decisões, riscos, consistência documental,
    sentimentos e governança. Ela é mais poderosa que uma pergunta simples, mas também
    consome mais tempo e chamadas de IA.
    """


def _index_documents(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    documents: list[dict[str, object]],
    config: AppConfig,
) -> int | None:
    prepare_semantic_base_use_case = build_prepare_semantic_base_use_case()
    with st.spinner("Preparando documentos para IA..."):
        result = prepare_semantic_base_use_case.execute(
            PrepareSemanticBaseCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                documents=documents,
                embedding_model=config.openai.embedding_model,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return None

    output = result.value
    if output is None:
        return None
    invalidate_data_cache()
    return output.indexed_chunks


def _answer_question(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    question: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    ask_question_use_case = build_ask_question_use_case()
    result = ask_question_use_case.execute(
        AskQuestionCommand(
            supabase_client=supabase_client,
            openai_client=openai_client,
            user_id=user_id,
            question=question,
            embedding_model=config.openai.embedding_model,
            generation_model=config.openai.generation_model,
            save_to_history=save_to_history,
            selected_document_ids=selected_document_ids,
        )
    )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    st.markdown(output.rag_answer.answer)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Pergunta respondida com fontes")
        st.success("Análise salva no histórico.")
        st.toast("Análise salva no histórico.")
    else:
        st.info("Análise exibida sem salvar no histórico.")

    with st.expander("Fontes recuperadas"):
        for index, source in enumerate(output.rag_answer.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_use_case_message(result: UseCaseResult[object]) -> None:
    if result.severity == ResultSeverity.WARNING:
        st.warning(result.message)
    elif result.severity == ResultSeverity.ERROR:
        st.error(result.message)
    elif result.severity == ResultSeverity.SUCCESS:
        st.success(result.message)
        st.toast(result.message)
    else:
        st.info(result.message)


def _generate_action_plan(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    action_plan_use_case = build_action_plan_use_case()
    with st.spinner("Gerando plano de ação com fontes..."):
        result = action_plan_use_case.execute(
            ActionPlanCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_action_plan(output.action_plan)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Plano de ação")
        st.success("Plano de ação salvo no histórico.")
        st.toast("Plano de ação salvo no histórico.")
    else:
        st.info("Plano exibido sem salvar no histórico.")


def _generate_intelligence_snapshot(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    intelligence_snapshot_use_case = build_intelligence_snapshot_use_case()
    with st.spinner("Extraindo inteligência organizacional..."):
        result = intelligence_snapshot_use_case.execute(
            IntelligenceSnapshotCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_intelligence_snapshot(output.snapshot)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Inteligência organizacional")
        st.success("Inteligência organizacional salva no histórico.")
        st.toast("Inteligência organizacional salva no histórico.")
    else:
        st.info("Inteligência exibida sem salvar no histórico.")


def _generate_document_comparison(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    document_comparison_use_case = build_document_comparison_use_case()
    with st.spinner("Comparando documentos selecionados..."):
        result = document_comparison_use_case.execute(
            DocumentComparisonCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_document_comparison(output.report)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Comparação documental")
        st.success("Comparação documental salva no histórico.")
        st.toast("Comparação documental salva no histórico.")
    else:
        st.info("Comparação exibida sem salvar no histórico.")


def _generate_sentiment_report(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    sentiment_analysis_use_case = build_sentiment_analysis_use_case()
    with st.spinner("Analisando sentimentos organizacionais..."):
        result = sentiment_analysis_use_case.execute(
            SentimentAnalysisCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_sentiment_report(output.report)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Sentimentos organizacionais")
        st.success("Análise de sentimentos organizacionais salva no histórico.")
        st.toast("Análise de sentimentos salva no histórico.")
    else:
        st.info("Análise de sentimentos exibida sem salvar no histórico.")


def _generate_preventive_alert_report(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    preventive_alerts_use_case = build_preventive_alerts_use_case()
    with st.spinner("Gerando alertas preventivos..."):
        result = preventive_alerts_use_case.execute(
            PreventiveAlertsCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_preventive_alert_report(output.report)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Alertas preventivos")
        st.success("Alertas preventivos salvos no histórico.")
        st.toast("Alertas preventivos salvos no histórico.")
    else:
        st.info("Alertas preventivos exibidos sem salvar no histórico.")


def _generate_historical_pattern_report(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    historical_patterns_use_case = build_historical_patterns_use_case()
    with st.spinner("Reconhecendo padrões históricos..."):
        result = historical_patterns_use_case.execute(
            HistoricalPatternsCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_historical_pattern_report(output.report)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Padrões históricos")
        st.success("Padrões históricos salvos no histórico.")
        st.toast("Padrões históricos salvos no histórico.")
    else:
        st.info("Padrões históricos exibidos sem salvar no histórico.")


def _generate_multi_agent_report(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    multi_agent_report_use_case = build_multi_agent_report_use_case()
    with st.spinner("Executando agentes especializados..."):
        result = multi_agent_report_use_case.execute(
            MultiAgentReportCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
                save_to_history=save_to_history,
                selected_document_ids=selected_document_ids,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return

    _render_multi_agent_report(output.report)
    if output.persistence_warning:
        st.warning(output.persistence_warning)
    elif output.saved_to_history:
        invalidate_data_cache()
        remember_analysis_result("Orquestração multiagente")
        st.success("Orquestração multiagente salva no histórico.")
        st.toast("Orquestração multiagente salva no histórico.")
    else:
        st.info("Orquestração multiagente exibida sem salvar no histórico.")


def _render_document_comparison(report: DocumentComparisonReport) -> None:
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    st.markdown("**Inconsistências e divergências**")
    for index, issue in enumerate(report.issues, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {issue.title}**")
            st.caption(
                f"{issue.issue_type} | Severidade: {issue.severity} | "
                f"Documentos: {', '.join(issue.documents) or 'A confirmar'}"
            )
            st.write(issue.description)
            st.markdown(f"**Impacto:** {issue.impact}")
            st.markdown(f"**Evidência:** {issue.evidence}")
            st.markdown(f"**Recomendação:** {issue.recommendation}")
            st.caption(f"Fontes: {', '.join(issue.source_refs) or 'Fonte não indicada'}")
    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=document_comparison_to_xlsx(report),
        file_name="comparacao_documental_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=document_comparison_to_csv(report),
        file_name="comparacao_documental_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=document_comparison_to_markdown(report),
        file_name="comparacao_documental_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas na comparação"):
        for index, source in enumerate(report.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_intelligence_snapshot(snapshot: IntelligenceSnapshot) -> None:
    st.markdown("**Síntese executiva**")
    st.write(snapshot.executive_summary)
    st.markdown("**Achados estruturados**")
    for index, finding in enumerate(snapshot.findings, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {finding.title}**")
            st.caption(
                f"{finding.category} | Severidade: {finding.severity} | "
                f"Prazo: {finding.deadline}"
            )
            st.write(finding.description)
            st.markdown(f"**Responsável:** {finding.responsible}")
            st.markdown(f"**Evidência:** {finding.evidence}")
            st.markdown(f"**Recomendação:** {finding.recommendation}")
            st.caption(f"Fontes: {', '.join(finding.source_refs) or 'Fonte não indicada'}")
    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=intelligence_snapshot_to_xlsx(snapshot),
        file_name="inteligencia_organizacional_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=intelligence_snapshot_to_csv(snapshot),
        file_name="inteligencia_organizacional_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=intelligence_snapshot_to_markdown(snapshot),
        file_name="inteligencia_organizacional_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas na inteligência"):
        for index, source in enumerate(snapshot.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_sentiment_report(report: SentimentReport) -> None:
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Sentimento predominante", report.overall_sentiment)
    metric_cols[1].metric("Risco comunicacional", report.risk_level)
    metric_cols[2].metric("Sinais identificados", len(report.signals))
    if report.dominant_signals:
        st.caption(f"Sinais dominantes: {', '.join(report.dominant_signals)}")

    st.markdown("**Sinais organizacionais**")
    for index, signal in enumerate(report.signals, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {signal.dimension}**")
            st.caption(
                f"Classificação: {signal.label} | Intensidade: {signal.intensity} | "
                f"Polaridade: {signal.polarity:.2f}"
            )
            st.markdown(f"**Evidência:** {signal.evidence}")
            st.markdown(f"**Interpretação:** {signal.interpretation}")
            st.markdown(f"**Recomendação:** {signal.recommendation}")
            st.caption(f"Fontes: {', '.join(signal.source_refs) or 'Fonte não indicada'}")

    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=sentiment_report_to_xlsx(report),
        file_name="sentimentos_organizacionais_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=sentiment_report_to_csv(report),
        file_name="sentimentos_organizacionais_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=sentiment_report_to_markdown(report),
        file_name="sentimentos_organizacionais_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas nos sentimentos"):
        for index, source in enumerate(report.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_preventive_alert_report(report: PreventiveAlertReport) -> None:
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    critical_count = sum(1 for alert in report.alerts if alert.severity == "Crítica")
    high_count = sum(1 for alert in report.alerts if alert.severity == "Alta")
    metric_cols = st.columns(3)
    metric_cols[0].metric("Alertas gerados", len(report.alerts))
    metric_cols[1].metric("Críticos", critical_count)
    metric_cols[2].metric("Alta severidade", high_count)

    st.markdown("**Alertas identificados**")
    for index, alert in enumerate(report.alerts, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {alert.title}**")
            st.caption(
                f"{alert.alert_type} | Severidade: {alert.severity} | "
                f"Status sugerido: {alert.status}"
            )
            st.markdown(f"**Gatilho:** {alert.trigger}")
            st.markdown(f"**Evidência:** {alert.evidence}")
            st.markdown(f"**Impacto provável:** {alert.impact}")
            st.markdown(f"**Recomendação:** {alert.recommendation}")
            st.markdown(f"**Responsável sugerido:** {alert.owner}")
            st.markdown(f"**Prazo sugerido:** {alert.deadline}")
            st.caption(f"Fontes: {', '.join(alert.source_refs) or 'Fonte não indicada'}")

    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=preventive_alert_report_to_xlsx(report),
        file_name="alertas_preventivos_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=preventive_alert_report_to_csv(report),
        file_name="alertas_preventivos_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=preventive_alert_report_to_markdown(report),
        file_name="alertas_preventivos_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas nos alertas"):
        for index, source in enumerate(report.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_historical_pattern_report(report: HistoricalPatternReport) -> None:
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Padrões reconhecidos", len(report.patterns))
    metric_cols[1].metric("Registros históricos", report.historical_record_count)
    metric_cols[2].metric(
        "Alta severidade",
        sum(1 for pattern in report.patterns if pattern.severity == "Alta"),
    )

    st.markdown("**Padrões recorrentes**")
    for index, pattern in enumerate(report.patterns, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {pattern.title}**")
            st.caption(
                f"{pattern.pattern_type} | Severidade: {pattern.severity} | "
                f"Recorrência: {pattern.recurrence}"
            )
            st.markdown(f"**Sinal atual:** {pattern.current_signal}")
            st.markdown(f"**Evidência histórica:** {pattern.historical_evidence}")
            st.markdown(f"**Interpretação:** {pattern.interpretation}")
            st.markdown(f"**Recomendação:** {pattern.recommendation}")
            st.caption(f"Fontes atuais: {', '.join(pattern.source_refs) or 'Fonte não indicada'}")
            st.caption(
                "Registros relacionados: "
                f"{', '.join(pattern.related_records) or 'Registro não indicado'}"
            )

    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=historical_pattern_report_to_xlsx(report),
        file_name="padroes_historicos_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=historical_pattern_report_to_csv(report),
        file_name="padroes_historicos_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=historical_pattern_report_to_markdown(report),
        file_name="padroes_historicos_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes atuais usadas nos padrões"):
        for index, source in enumerate(report.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_multi_agent_report(report: MultiAgentReport) -> None:
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Agentes executados", len(report.agent_outputs))
    metric_cols[1].metric(
        "Achados gerados",
        sum(len(output.findings) for output in report.agent_outputs),
    )
    metric_cols[2].metric("Registros históricos", report.historical_record_count)

    st.markdown("**Consensos**")
    for item in report.consensus or ["A confirmar"]:
        st.write(f"- {item}")

    st.markdown("**Conflitos e lacunas**")
    for item in report.conflicts or ["A confirmar"]:
        st.write(f"- {item}")

    st.markdown("**Recomendações consolidadas**")
    for item in report.recommendations or ["A confirmar"]:
        st.write(f"- {item}")

    st.markdown("**Parecer dos agentes**")
    for output in report.agent_outputs:
        with st.container(border=True):
            st.markdown(f"**{output.agent_name}**")
            st.caption(f"Confiança: {output.confidence} | Missão: {output.mission}")
            st.write(output.summary)
            for index, finding in enumerate(output.findings, start=1):
                st.markdown(f"**{index}. {finding.title}**")
                st.caption(f"{finding.category} | Severidade: {finding.severity}")
                st.markdown(f"**Evidência:** {finding.evidence}")
                st.markdown(f"**Recomendação:** {finding.recommendation}")
                st.caption(f"Fontes: {', '.join(finding.source_refs) or 'Fonte não indicada'}")

    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=multi_agent_report_to_xlsx(report),
        file_name="orquestracao_multiagente_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=multi_agent_report_to_csv(report),
        file_name="orquestracao_multiagente_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=multi_agent_report_to_markdown(report),
        file_name="orquestracao_multiagente_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas pelos agentes"):
        for index, source in enumerate(report.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_action_plan(action_plan: ActionPlan) -> None:
    st.markdown("**Plano estruturado**")
    for index, item in enumerate(action_plan.items, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {item.task}**")
            st.caption(f"Prioridade: {item.priority} | Prazo: {item.deadline}")
            st.markdown(f"**Responsável:** {item.responsible}")
            st.markdown(f"**Risco:** {item.risk}")
            st.markdown(f"**Evidência:** {item.evidence}")
            st.caption(f"Fontes: {', '.join(item.source_refs) or 'Fonte não indicada'}")
    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Exportar Excel",
        data=action_plan_to_xlsx(action_plan),
        file_name="plano_de_acao_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Exportar CSV",
        data=action_plan_to_csv(action_plan),
        file_name="plano_de_acao_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Exportar Markdown",
        data=action_plan_to_markdown(action_plan),
        file_name="plano_de_acao_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas no plano"):
        for index, source in enumerate(action_plan.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_analysis_history(supabase_client: object, tenant_id: str, user_id: str) -> None:
    st.subheader("Histórico de análises")
    analyses = cached_recent_analyses(supabase_client, tenant_id, user_id, 50)
    if not analyses:
        st.info("Nenhuma análise salva ainda.")
        return

    for analysis in analyses:
        title = str(analysis.get("title") or "Análise sem título")
        created_at = str(analysis.get("created_at") or "")
        with st.expander(title):
            document_name = _document_name(analysis)
            if document_name:
                st.caption(f"Documento: {document_name}")
            if created_at:
                st.caption(f"Criada em: {created_at}")
            model = analysis.get("model")
            if isinstance(model, str) and model:
                st.caption(f"Modelo: {model}")
            metadata = analysis.get("metadata")
            if _is_saved_action_plan(metadata):
                _render_saved_action_plan_items(metadata)
            elif _is_saved_document_comparison(metadata):
                _render_saved_document_comparison_issues(metadata)
            elif _is_saved_preventive_alert_report(metadata):
                _render_saved_preventive_alerts(metadata)
            elif _is_saved_historical_pattern_report(metadata):
                _render_saved_historical_patterns(metadata)
            elif _is_saved_multi_agent_report(metadata):
                _render_saved_multi_agent_outputs(metadata)
            elif _is_saved_sentiment_report(metadata):
                _render_saved_sentiment_signals(metadata)
            elif _is_saved_intelligence_snapshot(metadata):
                _render_saved_intelligence_findings(metadata)
            else:
                st.markdown("**Pergunta**")
                st.write(analysis.get("question") or "")
                st.markdown("**Resposta**")
                st.write(analysis.get("answer") or "")
            _render_saved_sources(analysis.get("sources"))


def _render_saved_sources(raw_sources: object) -> None:
    if not isinstance(raw_sources, list) or not raw_sources:
        return
    st.markdown("**Fontes salvas**")
    for index, source in enumerate(raw_sources, start=1):
        if not isinstance(source, dict):
            continue
        filename = source.get("filename") or "Documento sem nome"
        chunk_index = source.get("chunk_index") or 0
        similarity = source.get("similarity") or 0
        st.caption(f"Fonte {index}: {filename} | trecho {chunk_index} | similaridade {similarity}")


def _is_saved_action_plan(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "action_plan"


def _is_saved_intelligence_snapshot(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "intelligence_snapshot"


def _is_saved_document_comparison(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "document_comparison"


def _is_saved_preventive_alert_report(metadata: object) -> bool:
    return (
        isinstance(metadata, dict)
        and metadata.get("artifact_type") == "preventive_alert_report"
    )


def _is_saved_historical_pattern_report(metadata: object) -> bool:
    return (
        isinstance(metadata, dict)
        and metadata.get("artifact_type") == "historical_pattern_report"
    )


def _is_saved_multi_agent_report(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "multi_agent_report"


def _is_saved_sentiment_report(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "sentiment_report"


def _render_saved_multi_agent_outputs(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_outputs = metadata.get("agent_outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        return
    outputs = [output for output in raw_outputs if isinstance(output, dict)]
    if outputs:
        st.markdown("**Orquestração multiagente**")
        st.caption(
            f"Agentes: {metadata.get('agent_count', len(outputs))} | "
            f"Achados: {metadata.get('finding_count', 0)} | "
            f"Registros históricos: {metadata.get('historical_record_count', 0)}"
        )
        if isinstance(metadata.get("consensus"), list):
            st.markdown("**Consensos**")
            for item in _as_text_list(metadata.get("consensus")):
                st.write(f"- {item}")
        if isinstance(metadata.get("conflicts"), list):
            st.markdown("**Conflitos e lacunas**")
            for item in _as_text_list(metadata.get("conflicts")):
                st.write(f"- {item}")
        for output in outputs:
            with st.container(border=True):
                st.markdown(f"**{output.get('agent_name', '')}**")
                st.caption(
                    f"Confiança: {output.get('confidence', '')} | "
                    f"Missão: {output.get('mission', '')}"
                )
                st.write(output.get("summary", ""))
                raw_findings = output.get("findings")
                if not isinstance(raw_findings, list):
                    continue
                for index, finding in enumerate(raw_findings, start=1):
                    if not isinstance(finding, dict):
                        continue
                    st.markdown(f"**{index}. {finding.get('title', '')}**")
                    st.caption(
                        f"{finding.get('category', '')} | "
                        f"Severidade: {finding.get('severity', '')}"
                    )
                    st.markdown(f"**Evidência:** {finding.get('evidence', '')}")
                    st.markdown(f"**Recomendação:** {finding.get('recommendation', '')}")
                    source_refs = ", ".join(_as_text_list(finding.get("source_refs")))
                    st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _render_saved_historical_patterns(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_patterns = metadata.get("patterns")
    if not isinstance(raw_patterns, list) or not raw_patterns:
        return
    patterns = [pattern for pattern in raw_patterns if isinstance(pattern, dict)]
    if patterns:
        st.markdown("**Padrões históricos**")
        st.caption(
            f"Total: {metadata.get('pattern_count', len(patterns))} | "
            f"Registros históricos: {metadata.get('historical_record_count', 0)}"
        )
        for index, pattern in enumerate(patterns, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {pattern.get('title', '')}**")
                st.caption(
                    f"{pattern.get('pattern_type', '')} | "
                    f"Severidade: {pattern.get('severity', '')} | "
                    f"Recorrência: {pattern.get('recurrence', '')}"
                )
                st.markdown(f"**Sinal atual:** {pattern.get('current_signal', '')}")
                st.markdown(
                    f"**Evidência histórica:** {pattern.get('historical_evidence', '')}"
                )
                st.markdown(f"**Interpretação:** {pattern.get('interpretation', '')}")
                st.markdown(f"**Recomendação:** {pattern.get('recommendation', '')}")
                source_refs = ", ".join(_as_text_list(pattern.get("source_refs")))
                related_records = ", ".join(_as_text_list(pattern.get("related_records")))
                st.caption(f"Fontes atuais: {source_refs or 'Fonte não indicada'}")
                st.caption(f"Registros relacionados: {related_records or 'Registro não indicado'}")


def _render_saved_preventive_alerts(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_alerts = metadata.get("alerts")
    if not isinstance(raw_alerts, list) or not raw_alerts:
        return
    alerts = [alert for alert in raw_alerts if isinstance(alert, dict)]
    if alerts:
        st.markdown("**Alertas preventivos**")
        st.caption(
            f"Total: {metadata.get('alert_count', len(alerts))} | "
            f"Críticos: {metadata.get('critical_alert_count', 0)} | "
            f"Alta severidade: {metadata.get('high_alert_count', 0)}"
        )
        for index, alert in enumerate(alerts, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {alert.get('title', '')}**")
                st.caption(
                    f"{alert.get('alert_type', '')} | "
                    f"Severidade: {alert.get('severity', '')} | "
                    f"Status: {alert.get('status', '')}"
                )
                st.markdown(f"**Gatilho:** {alert.get('trigger', '')}")
                st.markdown(f"**Evidência:** {alert.get('evidence', '')}")
                st.markdown(f"**Impacto provável:** {alert.get('impact', '')}")
                st.markdown(f"**Recomendação:** {alert.get('recommendation', '')}")
                st.markdown(f"**Responsável sugerido:** {alert.get('owner', '')}")
                st.markdown(f"**Prazo sugerido:** {alert.get('deadline', '')}")
                source_refs = ", ".join(_as_text_list(alert.get("source_refs")))
                st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _render_saved_sentiment_signals(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_signals = metadata.get("signals")
    if not isinstance(raw_signals, list) or not raw_signals:
        return
    signals = [signal for signal in raw_signals if isinstance(signal, dict)]
    if signals:
        st.markdown("**Sentimentos organizacionais**")
        st.caption(
            f"Sentimento predominante: {metadata.get('overall_sentiment', 'A confirmar')} | "
            f"Risco comunicacional: {metadata.get('risk_level', 'A confirmar')}"
        )
        dominant_signals = ", ".join(_as_text_list(metadata.get("dominant_signals")))
        if dominant_signals:
            st.caption(f"Sinais dominantes: {dominant_signals}")
        for index, signal in enumerate(signals, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {signal.get('dimension', '')}**")
                st.caption(
                    f"Classificação: {signal.get('label', '')} | "
                    f"Intensidade: {signal.get('intensity', '')} | "
                    f"Polaridade: {signal.get('polarity', '')}"
                )
                st.markdown(f"**Evidência:** {signal.get('evidence', '')}")
                st.markdown(f"**Interpretação:** {signal.get('interpretation', '')}")
                st.markdown(f"**Recomendação:** {signal.get('recommendation', '')}")
                source_refs = ", ".join(_as_text_list(signal.get("source_refs")))
                st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _render_saved_document_comparison_issues(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_issues = metadata.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        return
    issues = [issue for issue in raw_issues if isinstance(issue, dict)]
    if issues:
        st.markdown("**Comparação documental**")
        for index, issue in enumerate(issues, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {issue.get('title', '')}**")
                documents = ", ".join(_as_text_list(issue.get("documents")))
                st.caption(
                    f"{issue.get('issue_type', '')} | "
                    f"Severidade: {issue.get('severity', '')} | "
                    f"Documentos: {documents or 'A confirmar'}"
                )
                st.write(issue.get("description", ""))
                st.markdown(f"**Impacto:** {issue.get('impact', '')}")
                st.markdown(f"**Evidência:** {issue.get('evidence', '')}")
                st.markdown(f"**Recomendação:** {issue.get('recommendation', '')}")
                source_refs = ", ".join(_as_text_list(issue.get("source_refs")))
                st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _render_saved_intelligence_findings(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_findings = metadata.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return
    findings: list[dict[str, object]] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            continue
        findings.append(raw_finding)
    if findings:
        st.markdown("**Inteligência organizacional**")
        for index, finding in enumerate(findings, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {finding.get('title', '')}**")
                st.caption(
                    f"{finding.get('category', '')} | "
                    f"Severidade: {finding.get('severity', '')} | "
                    f"Prazo: {finding.get('deadline', '')}"
                )
                st.write(finding.get("description", ""))
                st.markdown(f"**Responsável:** {finding.get('responsible', '')}")
                st.markdown(f"**Evidência:** {finding.get('evidence', '')}")
                st.markdown(f"**Recomendação:** {finding.get('recommendation', '')}")
                source_refs = ", ".join(_as_text_list(finding.get("source_refs")))
                st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _render_saved_action_plan_items(metadata: object) -> None:
    if not isinstance(metadata, dict):
        return
    raw_items = metadata.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return
    items: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        items.append(raw_item)
    if items:
        st.markdown("**Plano de ação**")
        for index, item in enumerate(items, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {item.get('task', '')}**")
                st.caption(
                    f"Prioridade: {item.get('priority', '')} | "
                    f"Prazo: {item.get('deadline', '')}"
                )
                st.markdown(f"**Responsável:** {item.get('responsible', '')}")
                st.markdown(f"**Risco:** {item.get('risk', '')}")
                st.markdown(f"**Evidência:** {item.get('evidence', '')}")
                source_refs = ", ".join(_as_text_list(item.get("source_refs")))
                st.caption(f"Fontes: {source_refs or 'Fonte não indicada'}")


def _document_name(analysis: dict[str, object]) -> str:
    document = analysis.get("documents")
    if isinstance(document, dict):
        filename = document.get("filename")
        return filename if isinstance(filename, str) else ""
    return ""


def _document_options(documents: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    options: dict[str, dict[str, object]] = {}
    for index, document in enumerate(documents, start=1):
        label = _format_document_label(document, index)
        options[label] = document
    return options


def _render_ai_status(document: dict[str, object], chunk_counts: dict[str, int]) -> None:
    chunk_count = _document_chunk_count(document, chunk_counts)
    if chunk_count > 0:
        st.caption(f"IA: preparado ({chunk_count} trechos)")
        return
    st.caption("IA: pendente de preparação")


def _document_chunk_count(document: dict[str, object], chunk_counts: dict[str, int]) -> int:
    document_id = document.get("id")
    return chunk_counts.get(document_id, 0) if isinstance(document_id, str) else 0


def _document_ids(documents: list[dict[str, object]]) -> list[str]:
    return [str(document["id"]) for document in documents if isinstance(document.get("id"), str)]


def _format_document_label(document: dict[str, object], index: int) -> str:
    filename = str(document.get("filename") or f"Documento {index}")
    document_id = str(document.get("id") or "")
    created_at = _format_created_at(document.get("created_at"))
    id_label = document_id[:8] if document_id else "sem id"
    if created_at:
        return f"{index}. {created_at} - {filename} - {id_label}"
    return f"{index}. {filename} - {id_label}"


def _format_created_at(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized_value = value.replace("Z", "+00:00")
    try:
        created_at = datetime.fromisoformat(normalized_value)
    except ValueError:
        return value
    return created_at.strftime("%d/%m %H:%M")


def _duplicate_filenames(documents: list[dict[str, object]]) -> list[str]:
    filenames = [
        str(document.get("filename"))
        for document in documents
        if isinstance(document.get("filename"), str) and document.get("filename")
    ]
    counts = Counter(filenames)
    return sorted(filename for filename, count in counts.items() if count > 1)


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _as_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
