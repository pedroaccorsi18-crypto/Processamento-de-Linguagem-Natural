from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import get_current_session_user
from synapse_ai.clients.supabase_client import create_supabase_client
from synapse_ai.config import AppConfig
from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    list_user_documents,
    save_parsed_document,
)
from synapse_ai.services.document_service import (
    DocumentProcessingError,
    describe_supported_document_formats,
    parse_streamlit_upload,
    preview_text,
)


def render_upload_page(config: AppConfig) -> None:
    st.title("Upload de documentos")
    st.write("Envie documentos organizacionais para extração textual e persistência inicial.")

    user = get_current_session_user()
    if user is None:
        st.error("Sessão inválida. Entre novamente para enviar documentos.")
        return

    client = create_supabase_client(config)
    uploaded_file = st.file_uploader(
        "Selecione um documento",
        type=["pdf", "docx", "txt", "md"],
    )
    st.caption("Formatos previstos: " + ", ".join(describe_supported_document_formats()))
    st.caption("Limite nesta fase: 10 MB por arquivo.")

    if uploaded_file is not None:
        try:
            parsed_document = parse_streamlit_upload(uploaded_file)
        except DocumentProcessingError as exc:
            st.error(str(exc))
            return

        st.subheader("Prévia da extração")
        metric_cols = st.columns(3)
        metric_cols[0].metric("Tamanho", f"{parsed_document.size_bytes / 1024:.1f} KB")
        metric_cols[1].metric("Caracteres", str(len(parsed_document.text)))
        metric_cols[2].metric("Palavras", str(parsed_document.metadata["word_count"]))

        with st.expander("Texto extraído"):
            st.text_area(
                "Prévia",
                value=preview_text(parsed_document.text),
                height=240,
                disabled=True,
            )

        if st.button("Salvar documento"):
            try:
                save_parsed_document(client, user.id, parsed_document)
            except DocumentPersistenceError as exc:
                st.error(str(exc))
            else:
                st.success("Documento processado e salvo com sucesso.")
                st.rerun()

    st.subheader("Documentos recentes")
    documents = list_user_documents(client, user.id)
    if not documents:
        st.info("Nenhum documento salvo ainda.")
        return

    for document in documents:
        with st.container(border=True):
            st.write(document.get("filename", "Documento sem nome"))
            st.caption(
                f"Status: {document.get('status', 'indefinido')} | "
                f"Caracteres: {document.get('text_char_count', 0)}"
            )
