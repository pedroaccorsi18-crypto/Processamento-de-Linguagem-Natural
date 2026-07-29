"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useSynapseSession } from "@/components/auth-gate";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import {
  beginGoogleDriveAuthorization,
  completeGoogleDriveAuthorization,
  disconnectGoogleDrive,
  downloadDocument,
  importGoogleDriveFiles,
  listDocuments,
  listGoogleDriveFiles,
  listIntegrations,
  uploadDocument,
  type GoogleDriveFile,
  type IntegrationStatus,
  type SynapseDocument,
} from "@/services/api";

const acceptedFormats = ".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.json,.vtt,.eml,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg";
const maxUploadSizeBytes = 10 * 1024 * 1024;
const googleStateKey = "synapse.google-drive.oauth-state";
const googleVerifierKey = "synapse.google-drive.pkce-verifier";

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
    const expectedState = window.sessionStorage.getItem(googleStateKey);
    const codeVerifier = window.sessionStorage.getItem(googleVerifierKey);
    if (expectedState !== state || !codeVerifier) {
      setError("Não foi possível validar o retorno do Google Drive. Inicie a conexão novamente.");
      router.replace("/upload");
      return;
    }

    setIsConnectingDrive(true);
    void completeGoogleDriveAuthorization({
      accessToken: session.access_token,
      code,
      state,
      codeVerifier,
    })
      .then((googleStatus) => {
        setIntegrations((current) => replaceIntegrationStatus(current, googleStatus));
        setMessage("Google Drive conectado com sucesso. Escolha uma pasta para importar arquivos.");
        setError(null);
      })
      .catch((nextError) => {
        setError(nextError instanceof Error ? nextError.message : "Não foi possível concluir a conexão com o Google Drive.");
      })
      .finally(() => {
        window.sessionStorage.removeItem(googleStateKey);
        window.sessionStorage.removeItem(googleVerifierKey);
        setIsConnectingDrive(false);
        router.replace("/upload");
      });
  }, [router, searchParams, session.access_token]);

  const googleDrive = integrations.find((integration) => integration.provider === "google_drive");

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
      window.sessionStorage.setItem(googleStateKey, authorization.state);
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
            {integrations.filter((integration) => integration.provider !== "google_drive").map((integration) => (
              <article className="rounded-xl bg-slate-50 p-4" key={integration.provider}>
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold text-ink">{integration.label}</p>
                  <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-bold text-slate-600">
                    Em preparação
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-ink-soft">{integration.detail}</p>
              </article>
            ))}
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

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  return `${(size / 1024).toFixed(1)} KB`;
}
