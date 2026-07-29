"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useSynapseSession } from "@/components/auth-gate";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import {
  beginMicrosoftAuthorization,
  beginGoogleDriveAuthorization,
  beginSlackAuthorization,
  completeMicrosoftAuthorization,
  completeGoogleDriveAuthorization,
  completeSlackAuthorization,
  disconnectMicrosoft,
  disconnectGoogleDrive,
  disconnectSlack,
  downloadDocument,
  importMicrosoftTeamChannels,
  importGoogleDriveFiles,
  importSharePointFiles,
  importSlackConversations,
  listMicrosoftTeamChannels,
  listMicrosoftTeams,
  listSharePointDrives,
  listSharePointFiles,
  listSharePointSites,
  listSlackConversations,
  listDocuments,
  listGoogleDriveFiles,
  listIntegrations,
  type ConnectorImportResponse,
  uploadDocument,
  type GoogleDriveFile,
  type IntegrationStatus,
  type MicrosoftChannel,
  type MicrosoftTeam,
  type SharePointDrive,
  type SharePointFile,
  type SharePointSite,
  type SlackConversation,
  type SynapseDocument,
} from "@/services/api";

const acceptedFormats = ".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.json,.vtt,.eml,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg";
const maxUploadSizeBytes = 10 * 1024 * 1024;
const oauthProviderKey = "synapse.integration.oauth-provider";
const oauthStateKey = "synapse.integration.oauth-state";
const googleVerifierKey = "synapse.google-drive.pkce-verifier";
type CorporateProvider = "google_drive" | "slack" | "microsoft";

export default function UploadPage() {
  const { session } = useSynapseSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const oauthReturnHandledRef = useRef(false);
  const [documents, setDocuments] = useState<SynapseDocument[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [driveFolderReference, setDriveFolderReference] = useState("");
  const [driveFiles, setDriveFiles] = useState<GoogleDriveFile[]>([]);
  const [selectedDriveFileIds, setSelectedDriveFileIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isConnectingDrive, setIsConnectingDrive] = useState(false);
  const [isConnectingSlack, setIsConnectingSlack] = useState(false);
  const [isConnectingMicrosoft, setIsConnectingMicrosoft] = useState(false);
  const [isListingDriveFiles, setIsListingDriveFiles] = useState(false);
  const [isImportingDriveFiles, setIsImportingDriveFiles] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    const nextDocuments = await listDocuments(session.access_token);
    setDocuments(nextDocuments);
  }, [session.access_token]);

  const loadIntegrations = useCallback(async () => {
    const nextIntegrations = await listIntegrations(session.access_token);
    setIntegrations(nextIntegrations);
  }, [session.access_token]);

  useEffect(() => {
    let isActive = true;
    void Promise.all([loadDocuments(), loadIntegrations()])
      .then(() => {
        if (isActive) {
          setError(null);
        }
      })
      .catch((nextError) => {
        if (isActive) {
          setError(nextError instanceof Error ? nextError.message : "Não foi possível carregar a base documental.");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });
    return () => {
      isActive = false;
    };
  }, [loadDocuments, loadIntegrations]);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code || !state || oauthReturnHandledRef.current) {
      return;
    }

    oauthReturnHandledRef.current = true;
    const provider = window.sessionStorage.getItem(oauthProviderKey) as CorporateProvider | null;
    const expectedState = window.sessionStorage.getItem(oauthStateKey);
    const codeVerifier = window.sessionStorage.getItem(googleVerifierKey);
    if (!provider || expectedState !== state || (provider === "google_drive" && !codeVerifier)) {
      setError("Não foi possível validar o retorno da fonte corporativa. Inicie a conexão novamente.");
      router.replace("/upload");
      return;
    }

    setIsConnectingDrive(provider === "google_drive");
    setIsConnectingSlack(provider === "slack");
    setIsConnectingMicrosoft(provider === "microsoft");
    const completeAuthorization = provider === "google_drive"
      ? completeGoogleDriveAuthorization({
        accessToken: session.access_token,
        code,
        state,
        codeVerifier: codeVerifier ?? "",
      })
      : provider === "slack"
        ? completeSlackAuthorization({ accessToken: session.access_token, code, state })
        : completeMicrosoftAuthorization({ accessToken: session.access_token, code, state });

    void completeAuthorization
      .then((integrationStatus) => {
        setIntegrations((current) => (
          provider === "microsoft"
            ? replaceMicrosoftStatus(current, integrationStatus)
            : replaceIntegrationStatus(current, integrationStatus)
        ));
        setMessage(
          provider === "google_drive"
            ? "Google Drive conectado com sucesso. Escolha uma pasta para importar arquivos."
            : provider === "slack"
              ? "Slack conectado com sucesso. Adicione o app Synapse AI aos canais desejados e escolha-os para importar."
              : "Microsoft 365 conectado com sucesso. Escolha conteúdo do Teams ou SharePoint.",
        );
        setError(null);
      })
      .catch((nextError) => {
        setError(
          nextError instanceof Error
            ? nextError.message
            : "Não foi possível concluir a conexão corporativa.",
        );
      })
      .finally(() => {
        window.sessionStorage.removeItem(oauthProviderKey);
        window.sessionStorage.removeItem(oauthStateKey);
        window.sessionStorage.removeItem(googleVerifierKey);
        setIsConnectingDrive(false);
        setIsConnectingSlack(false);
        setIsConnectingMicrosoft(false);
        router.replace("/upload");
      });
  }, [router, searchParams, session.access_token]);

  const googleDrive = integrations.find((integration) => integration.provider === "google_drive");
  const slack = integrations.find((integration) => integration.provider === "slack");
  const microsoftTeams = integrations.find(
    (integration) => integration.provider === "microsoft_teams",
  );
  const sharePoint = integrations.find((integration) => integration.provider === "sharepoint");

  async function handleUpload() {
    if (selectedFile === null || isUploading) {
      return;
    }

    setIsUploading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await uploadDocument(session.access_token, selectedFile);
      setDocuments((current) => [result.document, ...current]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setMessage(result.message);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível processar o arquivo.");
    } finally {
      setIsUploading(false);
    }
  }

  function handleFileSelection(file: File | null) {
    setMessage(null);
    if (file !== null && file.size > maxUploadSizeBytes) {
      setSelectedFile(null);
      setError("O arquivo excede o limite de 10 MB desta fase.");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setError(null);
    setSelectedFile(file);
  }

  async function handleGoogleDriveConnection() {
    if (isConnectingDrive) {
      return;
    }

    setIsConnectingDrive(true);
    setError(null);
    try {
      const authorization = await beginGoogleDriveAuthorization(session.access_token);
      window.sessionStorage.setItem(oauthProviderKey, "google_drive");
      window.sessionStorage.setItem(oauthStateKey, authorization.state);
      window.sessionStorage.setItem(googleVerifierKey, authorization.code_verifier);
      window.location.assign(authorization.authorization_url);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível iniciar o Google Drive.");
      setIsConnectingDrive(false);
    }
  }

  async function handleGoogleDriveDisconnect() {
    if (isConnectingDrive) {
      return;
    }

    setIsConnectingDrive(true);
    setError(null);
    try {
      await disconnectGoogleDrive(session.access_token);
      setIntegrations((current) => current.map((integration) => (
        integration.provider === "google_drive"
          ? { ...integration, connected: false, connected_at: null }
          : integration
      )));
      setDriveFiles([]);
      setSelectedDriveFileIds([]);
      setMessage("Google Drive desconectado. Os documentos já importados permanecem na sua base privada.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível desconectar o Google Drive.");
    } finally {
      setIsConnectingDrive(false);
    }
  }

  async function handleSlackConnection() {
    if (isConnectingSlack) {
      return;
    }
    setIsConnectingSlack(true);
    setError(null);
    try {
      const authorization = await beginSlackAuthorization(session.access_token);
      window.sessionStorage.setItem(oauthProviderKey, "slack");
      window.sessionStorage.setItem(oauthStateKey, authorization.state);
      window.location.assign(authorization.authorization_url);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível iniciar o Slack.");
      setIsConnectingSlack(false);
    }
  }

  async function handleSlackDisconnect() {
    if (isConnectingSlack) {
      return;
    }
    setIsConnectingSlack(true);
    setError(null);
    try {
      await disconnectSlack(session.access_token);
      setIntegrations((current) => current.map((integration) => (
        integration.provider === "slack"
          ? { ...integration, connected: false, connected_at: null }
          : integration
      )));
      setMessage("Slack desconectado. Os conteúdos já importados permanecem na sua base privada.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível desconectar o Slack.");
    } finally {
      setIsConnectingSlack(false);
    }
  }

  async function handleMicrosoftConnection() {
    if (isConnectingMicrosoft) {
      return;
    }
    setIsConnectingMicrosoft(true);
    setError(null);
    try {
      const authorization = await beginMicrosoftAuthorization(session.access_token);
      window.sessionStorage.setItem(oauthProviderKey, "microsoft");
      window.sessionStorage.setItem(oauthStateKey, authorization.state);
      window.location.assign(authorization.authorization_url);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Não foi possível iniciar a conexão Microsoft 365.",
      );
      setIsConnectingMicrosoft(false);
    }
  }

  async function handleMicrosoftDisconnect() {
    if (isConnectingMicrosoft) {
      return;
    }
    setIsConnectingMicrosoft(true);
    setError(null);
    try {
      await disconnectMicrosoft(session.access_token);
      setIntegrations((current) => current.map((integration) => (
        integration.provider === "microsoft_teams" || integration.provider === "sharepoint"
          ? { ...integration, connected: false, connected_at: null }
          : integration
      )));
      setMessage("Microsoft 365 desconectado. Os conteúdos já importados permanecem na sua base privada.");
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Não foi possível desconectar o Microsoft 365.",
      );
    } finally {
      setIsConnectingMicrosoft(false);
    }
  }

  async function handleGoogleDriveFiles() {
    if (!driveFolderReference.trim() || isListingDriveFiles) {
      return;
    }

    setIsListingDriveFiles(true);
    setError(null);
    setMessage(null);
    try {
      const files = await listGoogleDriveFiles({
        accessToken: session.access_token,
        folderReference: driveFolderReference,
      });
      setDriveFiles(files);
      setSelectedDriveFileIds([]);
      setMessage(files.length ? "Selecione os arquivos que deseja adicionar à base." : "Nenhum arquivo foi encontrado nesta pasta.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível listar a pasta do Google Drive.");
    } finally {
      setIsListingDriveFiles(false);
    }
  }

  async function handleGoogleDriveImport() {
    if (!driveFolderReference.trim() || selectedDriveFileIds.length === 0 || isImportingDriveFiles) {
      return;
    }

    setIsImportingDriveFiles(true);
    setError(null);
    try {
      const result = await importGoogleDriveFiles({
        accessToken: session.access_token,
        folderReference: driveFolderReference,
        fileIds: selectedDriveFileIds,
      });
      setDocuments((current) => [...result.imported_documents, ...current]);
      setDriveFiles([]);
      setSelectedDriveFileIds([]);
      setMessage(result.message);
      if (result.failures.length) {
        setError(result.failures.map((failure) => `${failure.filename}: ${failure.detail}`).join(" "));
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível importar os arquivos do Google Drive.");
    } finally {
      setIsImportingDriveFiles(false);
    }
  }

  async function handleDownload(document: SynapseDocument) {
    try {
      setError(null);
      await downloadDocument(session.access_token, document);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Não foi possível baixar o arquivo.");
    }
  }

  function handleConnectorImportResult(result: ConnectorImportResponse) {
    setDocuments((current) => [...result.imported_documents, ...current]);
    setMessage(result.message);
    setError(
      result.failures.length
        ? result.failures.map((failure) => `${failure.filename}: ${failure.detail}`).join(" ")
        : null,
    );
  }

  function toggleGoogleDriveFile(fileId: string) {
    setSelectedDriveFileIds((current) => (
      current.includes(fileId) ? current.filter((id) => id !== fileId) : [...current, fileId]
    ));
  }

  return (
    <>
      <PageHeader
        eyebrow="Base documental"
        title="Ingestão documental"
        description="Envie arquivos da sua conta ou conecte uma fonte corporativa para extrair texto e preparar a próxima análise."
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <SectionCard
          title="Enviar arquivo"
          description="O Synapse extrai o conteúdo, isola o documento por conta e preserva o original para download."
        >
          <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center">
            <p className="text-lg font-bold text-ink">Selecione um documento</p>
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              PDF, DOCX, PPTX, XLSX, TXT, CSV, JSON, EML e arquivos de áudio até 10 MB.
            </p>
            <input
              accept={acceptedFormats}
              className="mt-6 block w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-sm file:font-bold file:text-blue-700"
              onChange={(event) => handleFileSelection(event.target.files?.[0] ?? null)}
              ref={fileInputRef}
              type="file"
            />
            {selectedFile ? (
              <p className="mt-4 text-sm font-semibold text-ink">
                Pronto para processar: {selectedFile.name} ({formatBytes(selectedFile.size)})
              </p>
            ) : null}
            <button
              className="mt-6 rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={selectedFile === null || isUploading}
              onClick={() => void handleUpload()}
              type="button"
            >
              {isUploading ? "Extraindo e salvando..." : "Processar documento"}
            </button>
          </div>
        </SectionCard>

        <SectionCard
          title="Fontes corporativas"
          description="Conexões separadas por conta, com acesso somente leitura e credenciais protegidas no servidor."
        >
          <GoogleDriveConnection
            drive={googleDrive}
            isConnecting={isConnectingDrive}
            onConnect={() => void handleGoogleDriveConnection()}
            onDisconnect={() => void handleGoogleDriveDisconnect()}
          />
          <div className="mt-5 space-y-3 border-t border-slate-100 pt-5">
            <CorporateConnection
              integration={slack}
              isConnecting={isConnectingSlack}
              onConnect={() => void handleSlackConnection()}
              onDisconnect={() => void handleSlackDisconnect()}
              title="Slack"
            />
            <CorporateConnection
              integration={microsoftTeams}
              isConnecting={isConnectingMicrosoft}
              onConnect={() => void handleMicrosoftConnection()}
              onDisconnect={() => void handleMicrosoftDisconnect()}
              title="Microsoft 365"
            />
          </div>
        </SectionCard>
      </div>

      {googleDrive?.connected ? (
        <SectionCard
          title="Importar do Google Drive"
          description="Informe o link ou ID de uma pasta compartilhada. O Synapse busca somente os arquivos autorizados pela conta conectada."
        >
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              className="min-w-0 flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              onChange={(event) => setDriveFolderReference(event.target.value)}
              placeholder="Link ou ID da pasta do Google Drive"
              value={driveFolderReference}
            />
            <button
              className="rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!driveFolderReference.trim() || isListingDriveFiles}
              onClick={() => void handleGoogleDriveFiles()}
              type="button"
            >
              {isListingDriveFiles ? "Buscando arquivos..." : "Buscar arquivos"}
            </button>
          </div>

          {driveFiles.length ? (
            <div className="mt-5 space-y-3">
              {driveFiles.map((file) => (
                <label
                  className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4 transition hover:border-synapse-blue hover:bg-blue-50"
                  key={file.id}
                >
                  <input
                    checked={selectedDriveFileIds.includes(file.id)}
                    className="mt-1 h-4 w-4 accent-synapse-blue"
                    onChange={() => toggleGoogleDriveFile(file.id)}
                    type="checkbox"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block break-words font-bold text-ink">{file.name}</span>
                    <span className="mt-1 block text-sm text-ink-soft">
                      {file.mime_type}{file.size_bytes ? ` · ${formatBytes(file.size_bytes)}` : ""}
                    </span>
                  </span>
                </label>
              ))}
              <button
                className="rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={selectedDriveFileIds.length === 0 || isImportingDriveFiles}
                onClick={() => void handleGoogleDriveImport()}
                type="button"
              >
                {isImportingDriveFiles
                  ? "Importando e extraindo..."
                  : `Importar ${selectedDriveFileIds.length || ""} arquivo(s)`}
              </button>
            </div>
          ) : null}
        </SectionCard>
      ) : null}

      {slack?.connected ? (
        <SlackImportPanel
          accessToken={session.access_token}
          onImported={handleConnectorImportResult}
          onError={setError}
        />
      ) : null}

      {microsoftTeams?.connected || sharePoint?.connected ? (
        <MicrosoftImportPanel
          accessToken={session.access_token}
          onImported={handleConnectorImportResult}
          onError={setError}
        />
      ) : null}

      {message ? <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">{message}</p> : null}
      {error ? <p className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm font-semibold text-red-800">{error}</p> : null}

      <SectionCard
        title="Documentos recentes"
        description="Arquivos visíveis apenas para a conta autenticada nesta sessão."
      >
        {isLoading ? <p className="text-sm text-ink-soft">Carregando documentos...</p> : null}
        {!isLoading && documents.length === 0 ? (
          <EmptyState
            title="Sua base documental está vazia."
            description="Envie o primeiro arquivo ou importe uma pasta autorizada para criar uma base privada de conhecimento."
          />
        ) : null}
        {!isLoading && documents.length > 0 ? (
          <div className="space-y-3">
            {documents.map((document) => (
              <article
                className="flex flex-col gap-4 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between"
                key={document.id}
              >
                <div>
                  <p className="font-bold text-ink">{document.filename}</p>
                  <p className="mt-1 text-sm text-ink-soft">
                    {document.text_char_count.toLocaleString("pt-BR")} caracteres extraídos · {document.status}
                  </p>
                </div>
                {document.original_file_available ? (
                  <button
                    className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink transition hover:border-synapse-blue hover:bg-blue-50"
                    onClick={() => void handleDownload(document)}
                    type="button"
                  >
                    Baixar original
                  </button>
                ) : (
                  <span className="text-sm font-semibold text-amber-700">Original indisponível</span>
                )}
              </article>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </>
  );
}

function GoogleDriveConnection({
  drive,
  isConnecting,
  onConnect,
  onDisconnect,
}: {
  drive: IntegrationStatus | undefined;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  const isAvailable = drive?.availability === "available";
  return (
    <article className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-ink">Google Drive</p>
          <p className="mt-1 text-sm leading-6 text-ink-soft">{drive?.detail ?? "Verificando disponibilidade da conexão..."}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${drive?.connected ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
          {drive?.connected ? "Conectado" : isAvailable ? "Disponível" : "Configuração pendente"}
        </span>
      </div>
      {drive?.connected ? (
        <button
          className="mt-4 rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isConnecting}
          onClick={onDisconnect}
          type="button"
        >
          {isConnecting ? "Aguarde..." : "Desconectar"}
        </button>
      ) : (
        <button
          className="mt-4 rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!isAvailable || isConnecting}
          onClick={onConnect}
          type="button"
        >
          {isConnecting ? "Abrindo Google..." : "Conectar Google Drive"}
        </button>
      )}
    </article>
  );
}

function CorporateConnection({
  integration,
  isConnecting,
  onConnect,
  onDisconnect,
  title,
}: {
  integration: IntegrationStatus | undefined;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  title: string;
}) {
  const isAvailable = integration?.availability === "available";
  return (
    <article className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-bold text-ink">{title}</p>
          <p className="mt-1 text-sm leading-6 text-ink-soft">
            {integration?.detail ?? "Verificando disponibilidade da conexão..."}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${integration?.connected ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
          {integration?.connected ? "Conectado" : isAvailable ? "Disponível" : "Configuração pendente"}
        </span>
      </div>
      {integration?.connected ? (
        <button
          className="mt-4 rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isConnecting}
          onClick={onDisconnect}
          type="button"
        >
          {isConnecting ? "Aguarde..." : "Desconectar"}
        </button>
      ) : (
        <button
          className="mt-4 rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!isAvailable || isConnecting}
          onClick={onConnect}
          type="button"
        >
          {isConnecting ? "Abrindo autorização..." : `Conectar ${title}`}
        </button>
      )}
    </article>
  );
}

function SlackImportPanel({
  accessToken,
  onImported,
  onError,
}: {
  accessToken: string;
  onImported: (result: ConnectorImportResponse) => void;
  onError: (error: string | null) => void;
}) {
  const [conversations, setConversations] = useState<SlackConversation[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  async function loadConversations() {
    setIsLoading(true);
    onError(null);
    try {
      const nextConversations = await listSlackConversations(accessToken);
      setConversations(nextConversations);
      setSelectedIds([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar os canais do Slack.");
    } finally {
      setIsLoading(false);
    }
  }

  async function importSelected() {
    if (!selectedIds.length || isImporting) {
      return;
    }
    setIsImporting(true);
    onError(null);
    try {
      const result = await importSlackConversations({ accessToken, conversationIds: selectedIds });
      onImported(result);
      setSelectedIds([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível importar os canais do Slack.");
    } finally {
      setIsImporting(false);
    }
  }

  function toggleConversation(id: string) {
    setSelectedIds((current) => (
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    ));
  }

  return (
    <SectionCard
      title="Importar do Slack"
      description="Seleciona canais aos quais o app Synapse AI já foi adicionado. O Synapse cria um registro privado por canal, sem publicar ou alterar mensagens."
    >
      <button
        className="rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isLoading}
        onClick={() => void loadConversations()}
        type="button"
      >
        {isLoading ? "Carregando canais..." : "Buscar canais disponíveis"}
      </button>
      {conversations.length ? (
        <div className="mt-5 space-y-3">
          {conversations.map((conversation) => (
            <label className="flex cursor-pointer gap-3 rounded-xl border border-slate-200 p-4 transition hover:border-synapse-blue hover:bg-blue-50" key={conversation.id}>
              <input
                checked={selectedIds.includes(conversation.id)}
                className="mt-1 h-4 w-4 accent-synapse-blue"
                onChange={() => toggleConversation(conversation.id)}
                type="checkbox"
              />
              <span>
                <span className="block font-bold text-ink">#{conversation.name}</span>
                <span className="mt-1 block text-sm text-ink-soft">
                  {conversation.is_private ? "Canal privado autorizado" : "Canal público"}
                  {conversation.topic ? ` · ${conversation.topic}` : ""}
                </span>
              </span>
            </label>
          ))}
          <button
            className="rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!selectedIds.length || isImporting}
            onClick={() => void importSelected()}
            type="button"
          >
            {isImporting ? "Importando conversas..." : `Importar ${selectedIds.length} canal(is)`}
          </button>
        </div>
      ) : null}
    </SectionCard>
  );
}

function MicrosoftImportPanel({
  accessToken,
  onImported,
  onError,
}: {
  accessToken: string;
  onImported: (result: ConnectorImportResponse) => void;
  onError: (error: string | null) => void;
}) {
  const [teams, setTeams] = useState<MicrosoftTeam[]>([]);
  const [teamId, setTeamId] = useState("");
  const [channels, setChannels] = useState<MicrosoftChannel[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<MicrosoftChannel[]>([]);
  const [sites, setSites] = useState<SharePointSite[]>([]);
  const [siteId, setSiteId] = useState("");
  const [drives, setDrives] = useState<SharePointDrive[]>([]);
  const [driveId, setDriveId] = useState("");
  const [folderId, setFolderId] = useState("");
  const [files, setFiles] = useState<SharePointFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<SharePointFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  async function loadTeams() {
    setIsLoading(true);
    onError(null);
    try {
      setTeams(await listMicrosoftTeams(accessToken));
      setTeamId("");
      setChannels([]);
      setSelectedChannels([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar as equipes.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadChannels() {
    if (!teamId) {
      return;
    }
    setIsLoading(true);
    onError(null);
    try {
      setChannels(await listMicrosoftTeamChannels({ accessToken, teamId }));
      setSelectedChannels([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar os canais.");
    } finally {
      setIsLoading(false);
    }
  }

  async function importChannels() {
    if (!teamId || !selectedChannels.length || isImporting) {
      return;
    }
    setIsImporting(true);
    onError(null);
    try {
      const result = await importMicrosoftTeamChannels({
        accessToken,
        teamId,
        channels: selectedChannels,
      });
      onImported(result);
      setSelectedChannels([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível importar os canais.");
    } finally {
      setIsImporting(false);
    }
  }

  async function loadSites() {
    setIsLoading(true);
    onError(null);
    try {
      setSites(await listSharePointSites(accessToken));
      setSiteId("");
      setDrives([]);
      setDriveId("");
      setFiles([]);
      setSelectedFiles([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar os sites.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadDrives() {
    if (!siteId) {
      return;
    }
    setIsLoading(true);
    onError(null);
    try {
      setDrives(await listSharePointDrives({ accessToken, siteId }));
      setDriveId("");
      setFiles([]);
      setSelectedFiles([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar as bibliotecas.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadFiles(nextFolderId = "") {
    if (!driveId) {
      return;
    }
    setIsLoading(true);
    onError(null);
    try {
      setFiles(await listSharePointFiles({ accessToken, driveId, folderId: nextFolderId }));
      setFolderId(nextFolderId);
      setSelectedFiles([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível carregar os arquivos.");
    } finally {
      setIsLoading(false);
    }
  }

  async function importFiles() {
    if (!driveId || !selectedFiles.length || isImporting) {
      return;
    }
    setIsImporting(true);
    onError(null);
    try {
      const result = await importSharePointFiles({ accessToken, driveId, files: selectedFiles });
      onImported(result);
      setSelectedFiles([]);
    } catch (nextError) {
      onError(nextError instanceof Error ? nextError.message : "Não foi possível importar os arquivos.");
    } finally {
      setIsImporting(false);
    }
  }

  function toggleChannel(channel: MicrosoftChannel) {
    setSelectedChannels((current) => (
      current.some((item) => item.id === channel.id)
        ? current.filter((item) => item.id !== channel.id)
        : [...current, channel]
    ));
  }

  function toggleFile(file: SharePointFile) {
    setSelectedFiles((current) => (
      current.some((item) => item.id === file.id)
        ? current.filter((item) => item.id !== file.id)
        : [...current, file]
    ));
  }

  return (
    <SectionCard
      title="Importar do Microsoft 365"
      description="A mesma conexão corporativa permite escolher histórico autorizado do Teams ou arquivos de uma biblioteca do SharePoint."
    >
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 p-4">
          <h3 className="font-bold text-ink">Microsoft Teams</h3>
          <p className="mt-1 text-sm leading-6 text-ink-soft">Escolha canais da equipe aos quais sua conta já pode acessar.</p>
          <button className="mt-4 rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white disabled:opacity-60" disabled={isLoading} onClick={() => void loadTeams()} type="button">
            {isLoading ? "Carregando..." : "Buscar equipes"}
          </button>
          {teams.length ? (
            <div className="mt-4 space-y-3">
              <select className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" onChange={(event) => setTeamId(event.target.value)} value={teamId}>
                <option value="">Selecione uma equipe</option>
                {teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
              </select>
              <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink disabled:opacity-60" disabled={!teamId || isLoading} onClick={() => void loadChannels()} type="button">Buscar canais</button>
            </div>
          ) : null}
          {channels.length ? (
            <div className="mt-4 space-y-2">
              {channels.map((channel) => (
                <label className="flex cursor-pointer gap-2 rounded-lg bg-slate-50 p-3 text-sm" key={channel.id}>
                  <input checked={selectedChannels.some((item) => item.id === channel.id)} className="mt-1 accent-synapse-blue" onChange={() => toggleChannel(channel)} type="checkbox" />
                  <span><strong>{channel.name}</strong>{channel.description ? ` · ${channel.description}` : ""}</span>
                </label>
              ))}
              <button className="rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white disabled:opacity-60" disabled={!selectedChannels.length || isImporting} onClick={() => void importChannels()} type="button">
                {isImporting ? "Importando..." : `Importar ${selectedChannels.length} canal(is)`}
              </button>
            </div>
          ) : null}
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <h3 className="font-bold text-ink">SharePoint</h3>
          <p className="mt-1 text-sm leading-6 text-ink-soft">Navegue pelas bibliotecas compartilhadas e importe somente os arquivos selecionados.</p>
          <button className="mt-4 rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white disabled:opacity-60" disabled={isLoading} onClick={() => void loadSites()} type="button">
            {isLoading ? "Carregando..." : "Buscar sites"}
          </button>
          {sites.length ? (
            <div className="mt-4 space-y-3">
              <select className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" onChange={(event) => setSiteId(event.target.value)} value={siteId}>
                <option value="">Selecione um site</option>
                {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
              </select>
              <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink disabled:opacity-60" disabled={!siteId || isLoading} onClick={() => void loadDrives()} type="button">Buscar bibliotecas</button>
            </div>
          ) : null}
          {drives.length ? (
            <div className="mt-4 space-y-3">
              <select className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" onChange={(event) => setDriveId(event.target.value)} value={driveId}>
                <option value="">Selecione uma biblioteca</option>
                {drives.map((drive) => <option key={drive.id} value={drive.id}>{drive.name}</option>)}
              </select>
              <button className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-ink disabled:opacity-60" disabled={!driveId || isLoading} onClick={() => void loadFiles()} type="button">Buscar arquivos</button>
            </div>
          ) : null}
          {files.length ? (
            <div className="mt-4 space-y-2">
              {folderId ? <button className="text-sm font-bold text-synapse-blue" onClick={() => void loadFiles("")} type="button">Voltar à raiz</button> : null}
              {files.map((file) => file.is_folder ? (
                <button className="block w-full rounded-lg bg-slate-50 p-3 text-left text-sm font-bold text-ink" key={file.id} onClick={() => void loadFiles(file.id)} type="button">Abrir pasta: {file.name}</button>
              ) : (
                <label className="flex cursor-pointer gap-2 rounded-lg bg-slate-50 p-3 text-sm" key={file.id}>
                  <input checked={selectedFiles.some((item) => item.id === file.id)} className="mt-1 accent-synapse-blue" onChange={() => toggleFile(file)} type="checkbox" />
                  <span><strong>{file.name}</strong>{file.size_bytes ? ` · ${formatBytes(file.size_bytes)}` : ""}</span>
                </label>
              ))}
              <button className="rounded-lg bg-synapse-blue px-4 py-2 text-sm font-black text-white disabled:opacity-60" disabled={!selectedFiles.length || isImporting} onClick={() => void importFiles()} type="button">
                {isImporting ? "Importando..." : `Importar ${selectedFiles.length} arquivo(s)`}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </SectionCard>
  );
}

function replaceIntegrationStatus(
  current: IntegrationStatus[],
  nextStatus: IntegrationStatus,
): IntegrationStatus[] {
  const alreadyPresent = current.some((integration) => integration.provider === nextStatus.provider);
  return alreadyPresent
    ? current.map((integration) => (
      integration.provider === nextStatus.provider ? nextStatus : integration
    ))
    : [...current, nextStatus];
}

function replaceMicrosoftStatus(
  current: IntegrationStatus[],
  nextStatus: IntegrationStatus,
): IntegrationStatus[] {
  const providers = new Set(["microsoft_teams", "sharepoint"]);
  return current.map((integration) => (
    providers.has(integration.provider)
      ? {
        ...integration,
        availability: nextStatus.availability,
        connected: nextStatus.connected,
        connected_at: nextStatus.connected_at,
        detail: nextStatus.detail,
      }
      : integration
  ));
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  return `${(size / 1024).toFixed(1)} KB`;
}
