"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useSynapseSession } from "@/components/auth-gate";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import {
  downloadDocument,
  listDocuments,
  uploadDocument,
  type SynapseDocument,
} from "@/services/api";

const acceptedFormats = ".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.json,.vtt,.eml,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg";

export default function UploadPage() {
  const { session } = useSynapseSession();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<SynapseDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const nextDocuments = await listDocuments(session.access_token);
      setDocuments(nextDocuments);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Nao foi possivel carregar documentos.");
    }
  }, [session.access_token]);

  useEffect(() => {
    let isActive = true;
    void loadDocuments().finally(() => {
      if (isActive) {
        setIsLoading(false);
      }
    });
    return () => {
      isActive = false;
    };
  }, [loadDocuments]);

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
      setError(nextError instanceof Error ? nextError.message : "Nao foi possivel processar o arquivo.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDownload(document: SynapseDocument) {
    try {
      setError(null);
      await downloadDocument(session.access_token, document);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Nao foi possivel baixar o arquivo.");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Base documental"
        title="Ingestao documental"
        description="Envie arquivos da sua conta para extrair texto, preservar o original e preparar a proxima analise."
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <SectionCard
          title="Enviar arquivo"
          description="O Synapse extrai o conteudo, salva o documento com isolamento por conta e preserva o arquivo original para download."
        >
          <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center">
            <p className="text-lg font-bold text-ink">Selecione um documento</p>
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              PDF, DOCX, PPTX, XLSX, TXT, CSV, JSON, EML e arquivos de audio ate 10 MB.
            </p>
            <input
              accept={acceptedFormats}
              className="mt-6 block w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-sm file:font-bold file:text-blue-700"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
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
          {message ? <p className="mt-4 text-sm font-semibold text-emerald-700">{message}</p> : null}
          {error ? <p className="mt-4 text-sm font-semibold text-red-700">{error}</p> : null}
        </SectionCard>

        <SectionCard
          title="Fontes corporativas"
          description="A conexao com Google Drive, Slack, Teams e SharePoint sera migrada mantendo as credenciais segregadas por conta."
        >
          <p className="rounded-xl bg-slate-50 p-4 text-sm leading-6 text-ink-soft">
            Nesta primeira entrega da API, o upload local esta disponivel. Os conectores existentes
            continuam funcionando na plataforma Streamlit enquanto chegam a esta interface nova.
          </p>
        </SectionCard>
      </div>

      <SectionCard
        title="Documentos recentes"
        description="Arquivos visiveis apenas para a conta autenticada nesta sessao."
      >
        {isLoading ? <p className="text-sm text-ink-soft">Carregando documentos...</p> : null}
        {!isLoading && documents.length === 0 ? (
          <EmptyState
            title="Sua base documental esta vazia."
            description="Envie o primeiro arquivo para criar uma base privada de conhecimento."
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
                    {document.text_char_count.toLocaleString("pt-BR")} caracteres extraidos · {document.status}
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
                  <span className="text-sm font-semibold text-amber-700">Original indisponivel</span>
                )}
              </article>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  return `${(size / 1024).toFixed(1)} KB`;
}
