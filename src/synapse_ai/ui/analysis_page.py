from __future__ import annotations

from collections import Counter
from datetime import datetime

import streamlit as st

from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.openai_client import create_openai_client
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.services.alert_service import (
    AlertGenerationError,
    PreventiveAlertReport,
    generate_preventive_alert_report,
    preventive_alert_report_to_csv,
    preventive_alert_report_to_markdown,
    preventive_alert_report_to_xlsx,
)
from synapse_ai.services.analysis_repository import (
    AnalysisPersistenceError,
    list_recent_analyses,
    save_action_plan_result,
    save_analysis_result,
    save_document_comparison_result,
    save_historical_pattern_report_result,
    save_intelligence_snapshot_result,
    save_preventive_alert_report_result,
    save_sentiment_report_result,
)
from synapse_ai.services.analysis_service import (
    ActionPlan,
    AnalysisGenerationError,
    SourceSnippet,
    action_plan_to_csv,
    action_plan_to_markdown,
    action_plan_to_xlsx,
    build_source_snippets,
    generate_action_plan,
    generate_rag_answer,
)
from synapse_ai.services.chunk_repository import (
    ChunkPersistenceError,
    list_document_chunk_counts,
    match_document_chunks,
    replace_document_chunks,
)
from synapse_ai.services.chunking_service import split_text_into_chunks
from synapse_ai.services.comparison_service import (
    ComparisonGenerationError,
    DocumentComparisonReport,
    document_comparison_to_csv,
    document_comparison_to_markdown,
    document_comparison_to_xlsx,
    generate_document_comparison,
)
from synapse_ai.services.document_repository import list_user_documents_for_processing
from synapse_ai.services.embedding_service import EmbeddingGenerationError, generate_embeddings
from synapse_ai.services.intelligence_service import (
    IntelligenceGenerationError,
    IntelligenceSnapshot,
    generate_intelligence_snapshot,
    intelligence_snapshot_to_csv,
    intelligence_snapshot_to_markdown,
    intelligence_snapshot_to_xlsx,
)
from synapse_ai.services.pattern_service import (
    HistoricalPatternReport,
    PatternGenerationError,
    generate_historical_pattern_report,
    historical_pattern_report_to_csv,
    historical_pattern_report_to_markdown,
    historical_pattern_report_to_xlsx,
)
from synapse_ai.services.sentiment_service import (
    SentimentGenerationError,
    SentimentReport,
    generate_sentiment_report,
    sentiment_report_to_csv,
    sentiment_report_to_markdown,
    sentiment_report_to_xlsx,
)


def render_analysis_page(config: AppConfig) -> None:
    st.title("Análises inteligentes")
    st.write("Faça perguntas sobre os documentos enviados e receba respostas com fontes.")

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

    openai_client = create_openai_client(config)
    documents = list_user_documents_for_processing(supabase_client, user.id)

    st.subheader("Base documental")
    if "semantic_index_success" in st.session_state:
        st.success(str(st.session_state.pop("semantic_index_success")))
    if not documents:
        st.info("Envie e salve documentos na página de upload antes de rodar análises.")
        return

    document_options = _document_options(documents)
    chunk_counts = list_document_chunk_counts(
        supabase_client,
        user.id,
        _document_ids(documents),
        config.openai.embedding_model,
    )
    selected_labels = st.multiselect(
        "Documentos usados nesta pergunta",
        options=list(document_options.keys()),
        default=list(document_options.keys()),
        help="Selecione um ou mais documentos para definir o escopo da busca semântica.",
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
            "Há documento(s) selecionado(s) ainda sem base semântica para o modelo atual. "
            "Atualize a base antes de perguntar para incluir esses arquivos na busca."
        )
    total_chars = sum(_as_int(document.get("text_char_count")) for document in documents)
    selected_chars = sum(
        _as_int(document.get("text_char_count")) for document in selected_documents
    )
    metric_cols = st.columns(3)
    metric_cols[0].metric("Documentos no escopo", f"{len(selected_documents)} de {len(documents)}")
    metric_cols[1].metric("Caracteres no escopo", str(selected_chars or total_chars))
    metric_cols[2].metric("Modelo", config.openai.embedding_model)

    st.caption(
        "Use esta etapa quando enviar novos documentos ou quiser atualizar a base semântica. "
        "Depois que os embeddings forem gerados, você pode fazer várias perguntas sem preparar "
        "os documentos novamente."
    )
    with st.expander("Documentos disponíveis"):
        for index, document in enumerate(documents, start=1):
            st.write(_format_document_label(document, index))
            st.caption(
                f"Status: {document.get('status', 'indefinido')} | "
                f"Caracteres: {document.get('text_char_count', 0)}"
            )
            _render_ai_status(document, chunk_counts)

    documents_to_index = selected_documents
    if st.button(f"Atualizar base semântica ({len(documents_to_index)} documento(s))"):
        indexed_chunks = _index_documents(
            supabase_client,
            openai_client,
            user.id,
            documents_to_index,
            config,
        )
        if indexed_chunks is not None:
            st.session_state["semantic_index_success"] = (
                f"Base semântica atualizada com {indexed_chunks} trechos. "
                "Agora você pode fazer várias perguntas usando esta mesma preparação."
            )
            st.rerun()

    st.divider()
    st.subheader("Perguntar ao Synapse AI")
    question = st.text_area(
        "Pergunta",
        placeholder="Quais decisões, riscos ou inconsistências aparecem nos documentos?",
        height=110,
    )
    save_to_history = st.checkbox(
        "Salvar esta análise no histórico",
        value=False,
        help="Use quando precisar manter uma trilha auditável da pergunta e da resposta.",
    )

    if st.button("Responder com fontes"):
        _answer_question(
            supabase_client,
            openai_client,
            user.id,
            question,
            config,
            save_to_history,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Inteligência organizacional")
    st.write(
        "Extraia automaticamente decisões, riscos, inconsistências, prazos e recomendações "
        "dos documentos selecionados."
    )
    save_intelligence = st.checkbox(
        "Salvar inteligência no histórico",
        value=False,
        help="Use quando precisar manter a fotografia estruturada para auditoria futura.",
    )
    if st.button("Gerar inteligência organizacional"):
        _generate_intelligence_snapshot(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_intelligence,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Comparação documental")
    st.write(
        "Compare os documentos selecionados para detectar divergências de datas, decisões, "
        "responsáveis, riscos, escopo e evidências."
    )
    save_comparison = st.checkbox(
        "Salvar comparação no histórico",
        value=False,
        help="Use quando precisar manter as divergências encontradas para auditoria futura.",
    )
    if st.button("Comparar documentos selecionados"):
        _generate_document_comparison(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_comparison,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Sentimentos organizacionais")
    st.write(
        "Analise o tom dos documentos selecionados para identificar urgência, tensão, confiança, "
        "conflito, frustração e risco percebido com rastreabilidade."
    )
    save_sentiment = st.checkbox(
        "Salvar sentimentos no histórico",
        value=False,
        help="Use quando precisar manter a leitura de tom organizacional para auditoria futura.",
    )
    if st.button("Analisar sentimentos organizacionais"):
        _generate_sentiment_report(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_sentiment,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Alertas preventivos")
    st.write(
        "Identifique sinais que exigem atenção antes de virarem problema, como prazo crítico, "
        "responsável ausente, risco sem plano, orçamento pendente ou decisão conflitante."
    )
    save_alerts = st.checkbox(
        "Salvar alertas no histórico",
        value=False,
        help="Use quando precisar manter os alertas preventivos para acompanhamento futuro.",
    )
    if st.button("Gerar alertas preventivos"):
        _generate_preventive_alert_report(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_alerts,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Padrões históricos")
    st.write(
        "Compare os sinais atuais com análises salvas anteriormente para reconhecer riscos, "
        "atrasos, pendências, tensões ou inconsistências que já apareceram no histórico."
    )
    save_patterns = st.checkbox(
        "Salvar padrões no histórico",
        value=False,
        help="Use quando precisar manter a leitura de recorrência para auditoria futura.",
    )
    if st.button("Reconhecer padrões históricos"):
        _generate_historical_pattern_report(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_patterns,
            selected_document_ids,
        )

    st.divider()
    st.subheader("Plano de ação")
    st.write("Transforme decisões, riscos e pendências dos documentos em uma lista acompanhável.")
    save_action_plan = st.checkbox(
        "Salvar plano no histórico",
        value=False,
        help="Use quando precisar manter esse plano disponível para consulta futura.",
    )
    if st.button("Gerar plano de ação com fontes"):
        _generate_action_plan(
            supabase_client,
            openai_client,
            user.id,
            config,
            save_action_plan,
            selected_document_ids,
        )

    st.divider()
    _render_analysis_history(supabase_client, user.id)


def _index_documents(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    documents: list[dict[str, object]],
    config: AppConfig,
) -> int | None:
    indexed_chunks = 0
    try:
        with st.spinner("Gerando chunks e embeddings..."):
            for document in documents:
                document_id = str(document.get("id") or "")
                filename = str(document.get("filename") or "Documento sem nome")
                extracted_text = document.get("extracted_text")
                if (
                    not document_id
                    or not isinstance(extracted_text, str)
                    or not extracted_text.strip()
                ):
                    continue

                chunks = split_text_into_chunks(extracted_text)
                embeddings = generate_embeddings(
                    openai_client,
                    [chunk.content for chunk in chunks],
                    config.openai.embedding_model,
                )
                indexed_chunks += replace_document_chunks(
                    supabase_client,
                    user_id,
                    document_id,
                    filename,
                    chunks,
                    embeddings,
                    config.openai.embedding_model,
                )
    except (ChunkPersistenceError, EmbeddingGenerationError) as exc:
        st.error(str(exc))
        return None

    return indexed_chunks


def _answer_question(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    question: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    clean_question = question.strip()
    if not clean_question:
        st.warning("Digite uma pergunta antes de consultar a base.")
        return

    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            clean_question,
            config,
            selected_document_ids,
        )

        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de perguntar sobre este escopo."
            )
            return

        with st.spinner("Gerando resposta com rastreabilidade..."):
            rag_answer = generate_rag_answer(
                openai_client,
                clean_question,
                sources,
                config.openai.generation_model,
            )
    except (AnalysisGenerationError, ChunkPersistenceError, EmbeddingGenerationError) as exc:
        st.error(str(exc))
        return

    st.markdown(rag_answer.answer)
    if save_to_history:
        try:
            save_analysis_result(
                supabase_client,
                user_id,
                clean_question,
                rag_answer,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Análise salva no histórico.")
    else:
        st.info("Análise exibida sem salvar no histórico.")

    with st.expander("Fontes recuperadas"):
        for index, source in enumerate(rag_answer.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _generate_action_plan(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    save_to_history: bool,
    selected_document_ids: list[str],
) -> None:
    action_plan_query = (
        "decisões, responsáveis, prazos, riscos, pendências, ações recomendadas "
        "e critérios de aceite"
    )
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            action_plan_query,
            config,
            selected_document_ids,
            limit=8,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de gerar o plano."
            )
            return

        with st.spinner("Gerando plano de ação com fontes..."):
            action_plan = generate_action_plan(
                openai_client,
                sources,
                config.openai.generation_model,
            )
    except (AnalysisGenerationError, ChunkPersistenceError, EmbeddingGenerationError) as exc:
        st.error(str(exc))
        return

    _render_action_plan(action_plan)
    if save_to_history:
        try:
            save_action_plan_result(
                supabase_client,
                user_id,
                action_plan,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Plano de ação salvo no histórico.")
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
    intelligence_query = (
        "decisões, riscos, inconsistências, pendências, prazos críticos, responsáveis, "
        "dependências e recomendações estratégicas"
    )
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            intelligence_query,
            config,
            selected_document_ids,
            limit=10,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de gerar inteligência organizacional."
            )
            return

        with st.spinner("Extraindo inteligência organizacional..."):
            snapshot = generate_intelligence_snapshot(
                openai_client,
                sources,
                config.openai.generation_model,
            )
    except (
        AnalysisGenerationError,
        ChunkPersistenceError,
        EmbeddingGenerationError,
        IntelligenceGenerationError,
    ) as exc:
        st.error(str(exc))
        return

    _render_intelligence_snapshot(snapshot)
    if save_to_history:
        try:
            save_intelligence_snapshot_result(
                supabase_client,
                user_id,
                snapshot,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Inteligência organizacional salva no histórico.")
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
    if len(set(selected_document_ids)) < 2:
        st.warning("Selecione pelo menos dois documentos para executar a comparação documental.")
        return

    comparison_query = (
        "comparar documentos, datas conflitantes, decisões divergentes, responsáveis diferentes, "
        "riscos omitidos, mudanças de cronograma, escopo inconsistente e evidências conflitantes"
    )
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            comparison_query,
            config,
            selected_document_ids,
            limit=12,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de comparar os documentos."
            )
            return

        with st.spinner("Comparando documentos selecionados..."):
            report = generate_document_comparison(
                openai_client,
                sources,
                config.openai.generation_model,
            )
    except (
        AnalysisGenerationError,
        ChunkPersistenceError,
        ComparisonGenerationError,
        EmbeddingGenerationError,
    ) as exc:
        st.error(str(exc))
        return

    _render_document_comparison(report)
    if save_to_history:
        try:
            save_document_comparison_result(
                supabase_client,
                user_id,
                report,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Comparação documental salva no histórico.")
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
    sentiment_query = (
        "sentimento organizacional, tom comunicacional, urgência, tensão, confiança, conflito, "
        "frustração, alinhamento, risco percebido e sinais emocionais em documentos corporativos"
    )
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            sentiment_query,
            config,
            selected_document_ids,
            limit=10,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de analisar sentimentos."
            )
            return

        with st.spinner("Analisando sentimentos organizacionais..."):
            report = generate_sentiment_report(
                openai_client,
                sources,
                config.openai.generation_model,
            )
    except (
        AnalysisGenerationError,
        ChunkPersistenceError,
        EmbeddingGenerationError,
        SentimentGenerationError,
    ) as exc:
        st.error(str(exc))
        return

    _render_sentiment_report(report)
    if save_to_history:
        try:
            save_sentiment_report_result(
                supabase_client,
                user_id,
                report,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Análise de sentimentos organizacionais salva no histórico.")
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
    alert_query = (
        "alertas preventivos, prazo crítico, risco alto, orçamento pendente, responsável ausente, "
        "decisão conflitante, mudança de cronograma, dependência externa, comunicação crítica "
        "e lacuna de evidência"
    )
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            alert_query,
            config,
            selected_document_ids,
            limit=12,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de gerar alertas preventivos."
            )
            return

        with st.spinner("Gerando alertas preventivos..."):
            report = generate_preventive_alert_report(
                openai_client,
                sources,
                config.openai.generation_model,
            )
    except (
        AlertGenerationError,
        AnalysisGenerationError,
        ChunkPersistenceError,
        EmbeddingGenerationError,
    ) as exc:
        st.error(str(exc))
        return

    _render_preventive_alert_report(report)
    if save_to_history:
        try:
            save_preventive_alert_report_result(
                supabase_client,
                user_id,
                report,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Alertas preventivos salvos no histórico.")
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
    pattern_query = (
        "padrões históricos, recorrência, riscos repetidos, atrasos recorrentes, orçamento "
        "pendente, responsáveis ausentes, tensão comunicacional, inconsistências repetidas "
        "e decisões conflitantes"
    )
    historical_analyses = list_recent_analyses(supabase_client, user_id, limit=30)
    try:
        sources = _retrieve_sources(
            supabase_client,
            openai_client,
            user_id,
            pattern_query,
            config,
            selected_document_ids,
            limit=12,
        )
        if not sources:
            st.info(
                "Nenhum trecho relevante foi encontrado. "
                "Atualize a base semântica antes de reconhecer padrões históricos."
            )
            return

        with st.spinner("Reconhecendo padrões históricos..."):
            report = generate_historical_pattern_report(
                openai_client,
                sources,
                historical_analyses,
                config.openai.generation_model,
            )
    except (
        AnalysisGenerationError,
        ChunkPersistenceError,
        EmbeddingGenerationError,
        PatternGenerationError,
    ) as exc:
        st.error(str(exc))
        return

    _render_historical_pattern_report(report)
    if save_to_history:
        try:
            save_historical_pattern_report_result(
                supabase_client,
                user_id,
                report,
                config.openai.generation_model,
            )
        except AnalysisPersistenceError as exc:
            st.warning(str(exc))
        else:
            st.success("Padrões históricos salvos no histórico.")
    else:
        st.info("Padrões históricos exibidos sem salvar no histórico.")


def _retrieve_sources(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    query: str,
    config: AppConfig,
    selected_document_ids: list[str],
    limit: int = 5,
) -> list[SourceSnippet]:
    with st.spinner("Buscando trechos relevantes..."):
        query_embedding = generate_embeddings(
            openai_client,
            [query],
            config.openai.embedding_model,
        )[0]
        matches = match_document_chunks(
            supabase_client,
            user_id,
            query_embedding,
            document_ids=selected_document_ids,
            limit=limit,
        )
        return build_source_snippets(matches)


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
        "Baixar Excel",
        data=document_comparison_to_xlsx(report),
        file_name="comparacao_documental_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=document_comparison_to_csv(report),
        file_name="comparacao_documental_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
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
        "Baixar Excel",
        data=intelligence_snapshot_to_xlsx(snapshot),
        file_name="inteligencia_organizacional_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=intelligence_snapshot_to_csv(snapshot),
        file_name="inteligencia_organizacional_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
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
        "Baixar Excel",
        data=sentiment_report_to_xlsx(report),
        file_name="sentimentos_organizacionais_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=sentiment_report_to_csv(report),
        file_name="sentimentos_organizacionais_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
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
        "Baixar Excel",
        data=preventive_alert_report_to_xlsx(report),
        file_name="alertas_preventivos_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=preventive_alert_report_to_csv(report),
        file_name="alertas_preventivos_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
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
        "Baixar Excel",
        data=historical_pattern_report_to_xlsx(report),
        file_name="padroes_historicos_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=historical_pattern_report_to_csv(report),
        file_name="padroes_historicos_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
        data=historical_pattern_report_to_markdown(report),
        file_name="padroes_historicos_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes atuais usadas nos padrões"):
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
        "Baixar Excel",
        data=action_plan_to_xlsx(action_plan),
        file_name="plano_de_acao_synapse.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    export_cols[1].download_button(
        "Baixar CSV",
        data=action_plan_to_csv(action_plan),
        file_name="plano_de_acao_synapse.csv",
        mime="text/csv; charset=utf-8",
    )
    export_cols[2].download_button(
        "Baixar Markdown",
        data=action_plan_to_markdown(action_plan),
        file_name="plano_de_acao_synapse.md",
        mime="text/markdown",
    )
    with st.expander("Fontes usadas no plano"):
        for index, source in enumerate(action_plan.sources, start=1):
            st.markdown(f"**Fonte {index}: {source.filename}**")
            st.caption(f"Trecho {source.chunk_index} | similaridade {source.similarity:.3f}")
            st.write(source.content)


def _render_analysis_history(supabase_client: object, user_id: str) -> None:
    st.subheader("Histórico de análises")
    analyses = list_recent_analyses(supabase_client, user_id)
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


def _is_saved_sentiment_report(metadata: object) -> bool:
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "sentiment_report"


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
