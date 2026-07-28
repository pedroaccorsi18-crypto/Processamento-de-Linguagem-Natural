from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.services.audit_service import (
    AuditRecord,
    audit_records_to_markdown,
    audit_records_to_pdf,
    audit_records_to_premium_pdf,
    build_audit_records,
    build_audit_summary,
    collect_source_references,
)
from synapse_ai.ui.cache import cached_document_chunks_by_references, cached_recent_analyses
from synapse_ai.ui.state import current_tenant_id
from synapse_ai.ui.theme import render_empty_state, render_page_header


def render_audit_page(config: AppConfig) -> None:
    render_page_header(
        "Trilha de evidências",
        "Revise documentos, perguntas, respostas, fontes e pacotes auditáveis gerados "
        "pelo Synapse AI.",
        "Auditoria",
    )

    user = get_current_session_user()
    if user is None:
        st.info("Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar.")
        return

    access_token = get_access_token()
    if access_token is None:
        st.info("Sua autenticação precisa ser renovada para consultar a auditoria.")
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
    client = connection.client

    tenant_id = current_tenant_id(user)
    analyses = cached_recent_analyses(client, tenant_id, user.id, 50)
    references = collect_source_references(analyses)
    chunk_lookup = cached_document_chunks_by_references(
        client,
        tenant_id,
        user.id,
        tuple(references),
    )
    records = build_audit_records(analyses, chunk_lookup)

    if not records:
        render_empty_state(
            "A trilha de auditoria ainda está vazia.",
            "Salve respostas, planos ou relatórios com fontes para montar um pacote de "
            "evidências verificável e pronto para revisão externa.",
            icon="EV",
        )
        return

    filtered_records = _filter_records(records)
    _render_audit_summary(filtered_records)
    download_cols = st.columns(3)
    download_cols[0].download_button(
        "Baixar relatório premium PDF",
        data=audit_records_to_premium_pdf(filtered_records),
        file_name="relatorio_premium_auditoria_synapse.pdf",
        mime="application/pdf",
        type="primary",
    )
    download_cols[1].download_button(
        "Baixar pacote PDF",
        data=audit_records_to_pdf(filtered_records),
        file_name="pacote_de_evidencias_synapse.pdf",
        mime="application/pdf",
    )
    download_cols[2].download_button(
        "Baixar pacote Markdown",
        data=audit_records_to_markdown(filtered_records),
        file_name="pacote_de_evidencias_synapse.md",
        mime="text/markdown",
    )
    _render_audit_records(filtered_records)


def _filter_records(records: list[AuditRecord]) -> list[AuditRecord]:
    artifact_types = ["Todos", *sorted({record.artifact_type for record in records})]
    selected_type = st.selectbox("Tipo de registro", artifact_types)
    if selected_type == "Todos":
        return records
    return [record for record in records if record.artifact_type == selected_type]


def _render_audit_summary(records: list[AuditRecord]) -> None:
    summary = build_audit_summary(records)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Registros", summary.records)
    metric_cols[1].metric("Fontes", summary.sources)
    metric_cols[2].metric("Documentos", summary.documents)
    metric_cols[3].metric("Sem evidência", summary.missing_evidence)
    metric_cols[4].metric("Nomes duplicados", summary.duplicate_filename_records)
    if summary.missing_evidence:
        st.warning("Há fontes salvas cujo trecho não foi encontrado na base semântica atual.")
    if summary.duplicate_filename_records:
        st.info("Há registros com documentos de mesmo nome. Confira identificadores e datas.")


def _render_audit_records(records: list[AuditRecord]) -> None:
    st.subheader("Trilha de evidências")
    for record in records:
        with st.expander(f"{record.artifact_type} - {record.title}"):
            st.caption(f"Criado em: {record.created_at or 'A confirmar'}")
            if record.has_duplicate_filenames:
                st.warning("Este registro usa fontes com nomes de documento repetidos.")
            if record.question:
                st.markdown("**Pergunta/solicitação**")
                st.write(record.question)
            if record.limitations:
                st.markdown("**Lacunas e validações**")
                for limitation in record.limitations:
                    st.write(f"- {limitation}")
            _render_sources(record)
            st.download_button(
                "Baixar PDF deste registro",
                data=audit_records_to_pdf([record]),
                file_name=f"evidencias_{_safe_filename(record.title)}.pdf",
                mime="application/pdf",
                key=f"audit-download-pdf-{record.title}-{record.created_at}",
            )


def _render_sources(record: AuditRecord) -> None:
    if not record.sources:
        st.info("Nenhuma fonte salva para este registro.")
        return
    rows = [
        {
            "Documento": source.filename,
            "Trecho": source.chunk_index,
            "Similaridade": f"{source.similarity:.3f}",
            "Evidência": "Disponível" if source.evidence_available else "Não encontrada",
        }
        for source in record.sources
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    for index, source in enumerate(record.sources, start=1):
        st.markdown(f"**Fonte {index}: {source.filename} | trecho {source.chunk_index}**")
        st.caption(f"Documento: {source.document_id or 'A confirmar'}")
        st.caption(f"Similaridade: {source.similarity:.3f}")
        if source.content:
            st.text_area(
                "Trecho usado como evidência",
                value=source.content,
                height=180,
                disabled=True,
                key=f"audit-source-{record.title}-{record.created_at}-{index}",
            )
        else:
            st.info("Trecho não encontrado na base de chunks atual.")
        st.divider()


def _safe_filename(value: str) -> str:
    clean_value = "".join(char if char.isalnum() else "_" for char in value.lower())
    return clean_value.strip("_")[:60] or "registro"
