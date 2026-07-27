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
from synapse_ai.services.chunk_repository import list_document_chunk_counts
from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    list_user_documents,
    save_parsed_document,
    update_document_storage_location,
)
from synapse_ai.services.document_service import (
    DocumentProcessingError,
    UploadedDocument,
    describe_supported_document_formats,
    parse_uploaded_document,
    preview_text,
)
from synapse_ai.services.document_storage import (
    DocumentStorageError,
    download_original_document,
    upload_original_document,
)


def render_upload_page(config: AppConfig) -> None:
    st.title("Upload de documentos")
    st.write("Envie documentos organizacionais para extração textual e persistência inicial.")

    user = get_current_session_user()
    if user is None:
        st.info("Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar.")
        return

    access_token = get_access_token()
    if access_token is None:
        st.info("Sua autenticação precisa ser renovada para enviar documentos.")
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
    documents = list_user_documents(client, user.id)
    chunk_counts = list_document_chunk_counts(
        client,
        user.id,
        _document_ids(documents),
        config.openai.embedding_model,
    )
    uploaded_file = st.file_uploader(
        "Selecione um documento",
        type=["pdf", "docx", "txt", "md"],
    )
    st.caption("Formatos previstos: " + ", ".join(describe_supported_document_formats()))
    st.caption("Limite nesta fase: 10 MB por arquivo.")
    st.caption("O arquivo original fica guardado em storage privado para download futuro.")

    if uploaded_file is not None:
        uploaded_document = UploadedDocument(
            filename=uploaded_file.name,
            content_type=uploaded_file.type or "application/octet-stream",
            content=uploaded_file.getvalue(),
        )
        try:
            parsed_document = parse_uploaded_document(uploaded_document)
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

        duplicate_document = _find_duplicate_document(parsed_document.metadata, documents)
        allow_duplicate_save = True
        button_label = "Salvar documento"
        if duplicate_document is not None:
            st.warning(
                "Este arquivo parece já ter sido enviado. Encontramos outro documento "
                f"com o mesmo conteúdo: {duplicate_document.get('filename', 'documento')}."
            )
            allow_duplicate_save = st.checkbox(
                "Salvar mesmo assim como nova versão",
                value=False,
                help=(
                    "Use esta opção quando o arquivo for uma nova versão intencional. "
                    "Caso contrário, utilize o documento já salvo abaixo."
                ),
            )
            button_label = "Salvar nova versão"

        if st.button(button_label, disabled=not allow_duplicate_save):
            try:
                saved_document = save_parsed_document(client, user.id, parsed_document)
            except DocumentPersistenceError as exc:
                st.error(str(exc))
            else:
                document_id = saved_document.get("id")
                original_file_saved = False
                if isinstance(document_id, str) and document_id:
                    original_file_saved = _store_original_file(
                        client,
                        user.id,
                        document_id,
                        uploaded_document,
                    )
                if original_file_saved:
                    st.success("Documento processado, salvo e disponível para download.")
                    st.rerun()
                else:
                    st.success("Documento processado e salvo com sucesso.")

    st.subheader("Documentos recentes")
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
            _render_ai_status(document, chunk_counts)
            _render_download_button(client, document)


def _store_original_file(
    client: object,
    user_id: str,
    document_id: str,
    uploaded_document: UploadedDocument,
) -> bool:
    try:
        stored_file = upload_original_document(client, user_id, document_id, uploaded_document)
        update_document_storage_location(
            client,
            user_id,
            document_id,
            stored_file.bucket,
            stored_file.path,
        )
    except (DocumentPersistenceError, DocumentStorageError) as exc:
        st.warning(str(exc))
        return False
    return True


def _render_ai_status(document: dict[str, object], chunk_counts: dict[str, int]) -> None:
    document_id = document.get("id")
    chunk_count = chunk_counts.get(document_id, 0) if isinstance(document_id, str) else 0
    if chunk_count > 0:
        st.caption(f"IA: preparado ({chunk_count} trechos)")
        return
    st.caption("IA: pendente de preparação")


def _render_download_button(client: object, document: dict[str, object]) -> None:
    storage_bucket = document.get("storage_bucket")
    storage_path = document.get("storage_path")
    filename = str(document.get("filename") or "documento")
    content_type = str(document.get("content_type") or "application/octet-stream")
    if not isinstance(storage_bucket, str) or not isinstance(storage_path, str):
        st.caption("Arquivo original ainda não está disponível para download.")
        return

    try:
        file_content = download_original_document(client, storage_bucket, storage_path)
    except DocumentStorageError:
        st.caption("Não foi possível carregar o arquivo original para download.")
        return

    st.download_button(
        "Baixar arquivo original",
        data=file_content,
        file_name=filename,
        mime=content_type,
        key=f"download-{document.get('id', filename)}",
    )


def _document_ids(documents: list[dict[str, object]]) -> list[str]:
    return [str(document["id"]) for document in documents if isinstance(document.get("id"), str)]


def _find_duplicate_document(
    parsed_metadata: dict[str, object],
    documents: list[dict[str, object]],
) -> dict[str, object] | None:
    checksum = parsed_metadata.get("checksum_sha256")
    if not isinstance(checksum, str) or not checksum:
        return None

    for document in documents:
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if metadata.get("checksum_sha256") == checksum:
            return document
    return None
