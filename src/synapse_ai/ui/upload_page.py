from __future__ import annotations

import hashlib

import streamlit as st

from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    set_auth_session,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.models.user import AuthenticatedUser
from synapse_ai.services.audio_transcription_service import (
    AudioTranscriptionError,
    transcribe_audio,
)
from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    save_parsed_document,
    update_document_storage_location,
)
from synapse_ai.services.document_service import (
    DocumentProcessingError,
    ParsedDocument,
    UploadedDocument,
    describe_supported_document_formats,
    is_audio_document,
    parse_transcribed_audio_document,
    parse_uploaded_document,
    preview_text,
)
from synapse_ai.services.document_storage import (
    DocumentStorageError,
    download_original_document,
    upload_original_document,
)
from synapse_ai.services.google_drive_service import (
    GoogleDriveConnectorError,
    GoogleDriveCredentials,
    GoogleDriveFile,
    download_google_drive_file,
    extract_google_drive_folder_id,
    list_google_drive_folder_files,
)
from synapse_ai.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthTokens,
    build_google_oauth_authorization_url,
    build_pkce_code_challenge,
    consume_google_oauth_pending_authorization,
    exchange_google_oauth_code,
    generate_oauth_state,
    generate_pkce_code_verifier,
    store_google_oauth_pending_authorization,
)
from synapse_ai.ui.cache import (
    cached_document_chunk_counts,
    cached_user_documents,
    get_openai_client,
    invalidate_data_cache,
)
from synapse_ai.ui.state import (
    current_tenant_id,
    remember_document_status,
    remember_processed_document,
)
from synapse_ai.ui.theme import (
    render_document_card,
    render_empty_state,
    render_page_header,
    render_status_badge,
)

UPLOAD_PARSE_CACHE_KEY = "synapse_upload_parse_cache"


def render_upload_page(config: AppConfig) -> None:
    render_page_header(
        "Ingestão documental",
        "Envie documentos locais ou conecte fontes corporativas para preparar sua inteligência.",
        "Upload",
    )

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
    tenant_id = current_tenant_id(user)
    documents = cached_user_documents(client, tenant_id, user.id, 50)
    chunk_counts = cached_document_chunk_counts(
        client,
        tenant_id,
        user.id,
        tuple(_document_ids(documents)),
        config.openai.embedding_model,
    )
    upload_tab, drive_tab, documents_tab = st.tabs(
        ["Enviar arquivo", "Google Drive", "Documentos recentes"]
    )

    uploaded_file = None
    with upload_tab:
        st.subheader("Enviar arquivo")
        uploaded_file = st.file_uploader(
            "Selecione um documento",
            type=[
                "pdf",
                "docx",
                "pptx",
                "xlsx",
                "txt",
                "md",
                "csv",
                "json",
                "vtt",
                "eml",
                "mp3",
                "mp4",
                "mpeg",
                "mpga",
                "m4a",
                "wav",
                "webm",
                "ogg",
            ],
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
                with st.spinner("Extraindo texto e metadados do documento..."):
                    parsed_document = _parse_document_for_upload_cached(
                        config,
                        uploaded_document,
                    )
            except (AudioTranscriptionError, DocumentProcessingError, RuntimeError) as exc:
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

            duplicate_document = _find_duplicate_document(
                parsed_document.metadata,
                documents,
                user.id,
            )
            button_label = "Salvar documento"
            if duplicate_document is not None:
                st.warning(
                    "Este arquivo parece já existir na sua conta. O Synapse encontrou "
                    "outro documento com o mesmo conteúdo: "
                    f"{duplicate_document.get('filename', 'documento')}.\n\n"
                    "Isso não bloqueia o envio. Se você quiser manter uma nova cópia "
                    "para teste, comparação ou versão atualizada, salve como nova versão."
                )
                button_label = "Salvar nova versão"

            if st.button(button_label, type="primary"):
                try:
                    with st.spinner("Salvando documento e preparando trilha de auditoria..."):
                        saved_document = save_parsed_document(client, user.id, parsed_document)
                        invalidate_data_cache()
                except DocumentPersistenceError as exc:
                    st.error(str(exc))
                else:
                    document_id = saved_document.get("id")
                    original_file_saved = False
                    if isinstance(document_id, str) and document_id:
                        remember_processed_document(
                            document_id,
                            str(saved_document.get("filename") or parsed_document.filename),
                        )
                        remember_document_status(document_id, "extracted")
                        original_file_saved = _store_original_file(
                            client,
                            user.id,
                            document_id,
                            uploaded_document,
                        )
                    if original_file_saved:
                        st.success("Documento processado, salvo e disponível para download.")
                        st.toast("Documento salvo com sucesso.")
                        st.rerun()
                    else:
                        st.warning(
                            "Documento processado e salvo para análise, mas o arquivo original "
                            "não ficou disponível para download."
                        )

    with drive_tab:
        st.subheader("Importar de fonte corporativa")
        _render_google_drive_import(config, client, user.id, documents)

    with documents_tab:
        st.subheader("Documentos recentes")
        if not documents:
            render_empty_state(
                "Nenhum documento salvo ainda.",
                "Envie um arquivo local ou conecte o Google Drive para iniciar sua base "
                "documental.",
                icon="DOC",
            )
            return

        for document in documents:
            with st.container():
                document_status, status_label = _document_ai_status(document, chunk_counts)
                render_document_card(
                    str(document.get("filename") or "Documento sem nome"),
                    [
                        f"Status: {document.get('status', 'indefinido')}",
                        f"Caracteres: {document.get('text_char_count', 0)}",
                    ],
                    status=document_status,
                    status_label=status_label,
                )
                _render_download_button(client, document)


def has_google_drive_oauth_return() -> bool:
    return bool(_query_param("code") and _query_param("state"))


def render_google_drive_oauth_return_without_session(config: AppConfig) -> None:
    render_page_header(
        "Conexão com Google Drive",
        "Conclua a autorização usando o mesmo endereço público configurado no Synapse AI.",
        "Integração",
    )
    st.warning(
        "O Google autorizou o retorno, mas a sessão do Synapse não está mais ativa "
        "nesta aba."
    )
    st.write(
        "Isso acontece quando a autorização volta por um endereço diferente daquele "
        "em que você estava usando a plataforma. Para manter a sessão, abra o Synapse "
        "pelo mesmo endereço configurado para o Google Drive."
    )
    st.link_button(
        "Abrir Synapse no endereço correto",
        config.google_drive.redirect_uri,
        type="primary",
    )
    if st.button("Limpar retorno do Google e entrar novamente"):
        st.query_params.clear()
        st.rerun()


def restore_google_drive_oauth_synapse_session() -> bool:
    state = _query_param("state")
    if not state:
        return False

    pending_authorization = consume_google_oauth_pending_authorization(state)
    if pending_authorization is None:
        return False
    if not (
        pending_authorization.user_id
        and pending_authorization.user_email
        and pending_authorization.access_token
    ):
        return False

    set_auth_session(
        AuthenticatedUser(
            id=pending_authorization.user_id,
            email=pending_authorization.user_email,
        ),
        pending_authorization.access_token,
        pending_authorization.refresh_token or None,
    )
    st.session_state["google_drive_oauth_state"] = pending_authorization.state
    st.session_state["google_drive_pkce_code_verifier"] = pending_authorization.code_verifier
    return True


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


def _parse_document_for_upload(
    config: AppConfig,
    uploaded_document: UploadedDocument,
) -> ParsedDocument:
    if not is_audio_document(uploaded_document.filename):
        return parse_uploaded_document(uploaded_document)

    openai_client = get_openai_client(config)
    with st.spinner("Transcrevendo áudio para análise textual..."):
        transcription_text = transcribe_audio(
            openai_client,
            uploaded_document,
            config.openai.transcription_model,
        )
    return parse_transcribed_audio_document(
        uploaded_document,
        transcription_text,
        config.openai.transcription_model,
    )


def _parse_document_for_upload_cached(
    config: AppConfig,
    uploaded_document: UploadedDocument,
) -> ParsedDocument:
    cache_key = _uploaded_document_cache_key(config, uploaded_document)
    cached_entry = st.session_state.get(UPLOAD_PARSE_CACHE_KEY)
    if isinstance(cached_entry, dict) and cached_entry.get("key") == cache_key:
        parsed_document = cached_entry.get("parsed_document")
        if isinstance(parsed_document, ParsedDocument):
            return parsed_document

    parsed_document = _parse_document_for_upload(config, uploaded_document)
    st.session_state[UPLOAD_PARSE_CACHE_KEY] = {
        "key": cache_key,
        "parsed_document": parsed_document,
    }
    return parsed_document


def _uploaded_document_cache_key(
    config: AppConfig,
    uploaded_document: UploadedDocument,
) -> str:
    checksum = hashlib.sha256(uploaded_document.content).hexdigest()
    return "|".join(
        (
            uploaded_document.filename,
            uploaded_document.content_type,
            checksum,
            config.openai.transcription_model,
        )
    )


def _render_google_drive_import(
    config: AppConfig,
    client: object,
    user_id: str,
    documents: list[dict[str, object]],
) -> None:
    with st.expander("Configurar conexão e buscar arquivos", expanded=True):
        _complete_google_drive_oauth_if_needed(config)
        credentials = _google_drive_credentials(config)

        if not _has_google_drive_oauth_config(config) and not credentials.api_key:
            if config.google_drive.client_id and not config.google_drive.client_secret:
                st.warning(
                    "A credencial OAuth do Google Drive ainda não está completa. "
                    "Configure `google_drive.client_secret` para habilitar a conexão "
                    "com contas Google."
                )
                return
            st.info(
                "Configure `google_drive.client_id`, `google_drive.client_secret` e "
                "`google_drive.redirect_uri` nos segredos para conectar o Google Drive."
            )
            return

        if _has_google_drive_oauth_config(config):
            _render_google_drive_oauth_controls(config)
            credentials = _google_drive_credentials(config)

        if not credentials.access_token and not credentials.api_key:
            st.info("Conecte uma conta Google Drive para importar arquivos.")
            return

        folder_reference = st.text_input(
            "Link ou ID da pasta compartilhada",
            key="google-drive-folder-reference",
        )
        max_files = st.number_input(
            "Limite de arquivos para buscar",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="google-drive-max-files",
        )
        if st.button("Buscar arquivos no Google Drive", type="primary"):
            try:
                folder_id = extract_google_drive_folder_id(folder_reference)
                with st.spinner("Buscando arquivos no Google Drive..."):
                    st.session_state["google_drive_files"] = list_google_drive_folder_files(
                        credentials,
                        folder_id,
                        page_size=int(max_files),
                    )
            except GoogleDriveConnectorError as exc:
                st.error(str(exc))
                return

        drive_files = st.session_state.get("google_drive_files", [])
        if not isinstance(drive_files, list) or not drive_files:
            return

        labels = [_google_drive_file_label(file) for file in drive_files]
        selected_labels = st.multiselect(
            "Arquivos encontrados",
            options=labels,
            key="google-drive-selected-files",
        )
        selected_files = [
            file
            for file, label in zip(drive_files, labels, strict=False)
            if label in selected_labels
        ]
        if st.button("Importar selecionados", disabled=not selected_files, type="primary"):
            _import_google_drive_files(
                config,
                client,
                user_id,
                credentials,
                selected_files,
                documents,
            )


def _import_google_drive_files(
    config: AppConfig,
    client: object,
    user_id: str,
    credentials: GoogleDriveCredentials,
    drive_files: list[GoogleDriveFile],
    documents: list[dict[str, object]],
) -> None:
    imported_count = 0
    for drive_file in drive_files:
        try:
            downloaded_file = download_google_drive_file(credentials, drive_file)
            uploaded_document = UploadedDocument(
                filename=downloaded_file.filename,
                content_type=downloaded_file.content_type,
                content=downloaded_file.content,
            )
            parsed_document = _parse_document_for_upload(config, uploaded_document)
            if (
                _find_duplicate_document(parsed_document.metadata, documents, user_id)
                is not None
            ):
                st.warning(
                    f"{downloaded_file.filename} já existe na sua conta e foi ignorado."
                )
                continue
            saved_document = save_parsed_document(client, user_id, parsed_document)
            invalidate_data_cache()
            document_id = saved_document.get("id")
            if isinstance(document_id, str) and document_id:
                remember_processed_document(
                    document_id,
                    str(saved_document.get("filename") or parsed_document.filename),
                )
                remember_document_status(document_id, "extracted")
                _store_original_file(client, user_id, document_id, uploaded_document)
        except (
            AudioTranscriptionError,
            DocumentPersistenceError,
            DocumentProcessingError,
            GoogleDriveConnectorError,
            RuntimeError,
        ) as exc:
            st.warning(str(exc))
            continue
        imported_count += 1

    if imported_count:
        st.success(f"{imported_count} arquivo(s) importado(s) do Google Drive.")
        st.toast("Importação concluída.")
        st.rerun()
    else:
        st.info("Nenhum arquivo novo foi importado do Google Drive.")


def _google_drive_file_label(file: GoogleDriveFile) -> str:
    size = f" | {file.size_bytes / 1024:.1f} KB" if file.size_bytes else ""
    return f"{file.name} | {file.mime_type}{size}"


def _has_google_drive_oauth_config(config: AppConfig) -> bool:
    return bool(
        config.google_drive.client_id
        and config.google_drive.client_secret
        and config.google_drive.redirect_uri
    )


def _render_google_drive_oauth_controls(config: AppConfig) -> None:
    tokens = _google_drive_tokens()
    if tokens is not None:
        st.success("Google Drive conectado nesta sessão.")
        if st.button("Desconectar Google Drive"):
            st.session_state.pop("google_drive_oauth_tokens", None)
            st.session_state.pop("google_drive_files", None)
            st.rerun()
        return

    state = st.session_state.get("google_drive_oauth_state")
    if not isinstance(state, str) or not state:
        state = generate_oauth_state()
        st.session_state["google_drive_oauth_state"] = state
    code_verifier = st.session_state.get("google_drive_pkce_code_verifier")
    if not isinstance(code_verifier, str) or not code_verifier:
        code_verifier = generate_pkce_code_verifier()
        st.session_state["google_drive_pkce_code_verifier"] = code_verifier

    try:
        user = get_current_session_user()
        access_token = get_access_token() or ""
        store_google_oauth_pending_authorization(
            state,
            code_verifier,
            user_id=user.id if user is not None else "",
            user_email=user.email if user is not None else "",
            access_token=access_token,
            refresh_token=get_refresh_token() or "",
        )
        authorization_url = build_google_oauth_authorization_url(
            config.google_drive.client_id,
            config.google_drive.redirect_uri,
            state,
            code_challenge=build_pkce_code_challenge(code_verifier),
        )
    except GoogleOAuthError as exc:
        if code_verifier:
            store_google_oauth_pending_authorization(state, code_verifier)
        st.warning(str(exc))
        return

    st.link_button("Conectar Google Drive", authorization_url, type="primary")


def _complete_google_drive_oauth_if_needed(config: AppConfig) -> None:
    code = _query_param("code")
    state = _query_param("state")
    if not code and not state:
        return

    expected_state = st.session_state.get("google_drive_oauth_state")
    pending_authorization = consume_google_oauth_pending_authorization(state)
    state_matches_session = isinstance(expected_state, str) and state == expected_state
    if pending_authorization is None and not state_matches_session:
        st.warning("Não foi possível validar o retorno do Google Drive. Tente conectar novamente.")
        return
    code_verifier = st.session_state.get("google_drive_pkce_code_verifier")
    if pending_authorization is not None:
        code_verifier = pending_authorization.code_verifier
    elif not isinstance(code_verifier, str):
        code_verifier = ""

    try:
        tokens = exchange_google_oauth_code(
            config.google_drive.client_id,
            config.google_drive.client_secret,
            config.google_drive.redirect_uri,
            code,
            code_verifier=code_verifier,
        )
    except GoogleOAuthError as exc:
        st.warning(str(exc))
        return

    st.session_state["google_drive_oauth_tokens"] = tokens
    st.session_state.pop("google_drive_oauth_state", None)
    st.session_state.pop("google_drive_pkce_code_verifier", None)
    st.query_params.clear()
    st.success("Google Drive conectado com sucesso.")


def _google_drive_credentials(config: AppConfig) -> GoogleDriveCredentials:
    tokens = _google_drive_tokens()
    if tokens is not None:
        return GoogleDriveCredentials(access_token=tokens.access_token)
    return GoogleDriveCredentials(api_key=config.google_drive.api_key)


def _google_drive_tokens() -> GoogleOAuthTokens | None:
    tokens = st.session_state.get("google_drive_oauth_tokens")
    return tokens if isinstance(tokens, GoogleOAuthTokens) else None


def _query_param(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0] if value else "")
    return str(value or "")


def _render_ai_status(document: dict[str, object], chunk_counts: dict[str, int]) -> None:
    status, label = _document_ai_status(document, chunk_counts)
    render_status_badge(status, label=label)


def _document_ai_status(
    document: dict[str, object],
    chunk_counts: dict[str, int],
) -> tuple[str, str]:
    document_id = document.get("id")
    chunk_count = chunk_counts.get(document_id, 0) if isinstance(document_id, str) else 0
    if chunk_count > 0:
        return "concluído", f"IA concluída ({chunk_count} trechos)"
    return "pendente", "IA pendente"


def _render_download_button(client: object, document: dict[str, object]) -> None:
    storage_bucket = document.get("storage_bucket")
    storage_path = document.get("storage_path")
    filename = str(document.get("filename") or "documento")
    content_type = str(document.get("content_type") or "application/octet-stream")
    if not isinstance(storage_bucket, str) or not isinstance(storage_path, str):
        st.caption(
            "Arquivo original não está disponível para download. O texto extraído continua "
            "disponível para análises."
        )
        return

    try:
        file_content = download_original_document(client, storage_bucket, storage_path)
    except DocumentStorageError:
        st.caption("Não foi possível carregar o arquivo original para download.")
        return

    st.download_button(
        "Baixar original",
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
    current_user_id: str,
) -> dict[str, object] | None:
    checksum = parsed_metadata.get("checksum_sha256")
    if not isinstance(checksum, str) or not checksum:
        return None

    for document in documents:
        document_user_id = document.get("user_id")
        if not isinstance(document_user_id, str) or document_user_id != current_user_id:
            continue
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if metadata.get("checksum_sha256") == checksum:
            return document
    return None
