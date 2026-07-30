"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useSynapseSession } from "@/components/auth-gate";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StudioHistory, StudioResult } from "@/components/studio-result";
import {
  listStudioDocuments,
  listStudioHistory,
  prepareStudioDocuments,
  runStudioAnalysis,
  type StudioAnalysisResponse,
  type StudioDocument,
  type StudioHistoryEntry,
  type StudioWorkflow,
} from "@/services/api";

type WorkflowDefinition = {
  id: StudioWorkflow;
  label: string;
  description: string;
  minimumDocuments: number;
  needsQuestion?: boolean;
};

const workflows: WorkflowDefinition[] = [
  {
    id: "action_plan",
    label: "Plano de ação",
    description: "Transforma decisões, riscos e pendências em ações acompanháveis.",
    minimumDocuments: 1,
  },
  {
    id: "sentiment_analysis",
    label: "Sentimentos organizacionais",
    description: "Avalia sinais de tom, tensão, confiança e risco no conteúdo.",
    minimumDocuments: 1,
  },
  {
    id: "preventive_alerts",
    label: "Alertas preventivos",
    description: "Antecipa riscos, prazos críticos e lacunas de acompanhamento.",
    minimumDocuments: 1,
  },
];

export default function StudioPage() {
  const { session } = useSynapseSession();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<StudioDocument[]>([]);
  const [history, setHistory] = useState<StudioHistoryEntry[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [workflow, setWorkflow] = useState<StudioWorkflow>("action_plan");
  const [question, setQuestion] = useState("");
  const [saveToHistory, setSaveToHistory] = useState(true);
  const [lastAnalysis, setLastAnalysis] = useState<StudioAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeOperation, setActiveOperation] = useState<"prepare" | "analysis" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedDocuments = useMemo(
    () => documents.filter((document) => selectedDocumentIds.includes(document.id)),
    [documents, selectedDocumentIds],
  );
  const workflowDefinition = workflows.find((item) => item.id === workflow) ?? workflows[0];
  const selectedScopeIsPrepared =
    selectedDocuments.length > 0 && selectedDocuments.every((document) => document.prepared_for_ai);
  const hasEnoughDocuments = selectedDocuments.length >= workflowDefinition.minimumDocuments;

  const refreshStudioData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDocuments, nextHistory] = await Promise.all([
        listStudioDocuments(session.access_token),
        listStudioHistory(session.access_token, 50),
      ]);
      setDocuments(nextDocuments);
      setHistory(nextHistory);
      setSelectedDocumentIds((currentSelection) => {
        const availableIds = new Set(nextDocuments.map((document) => document.id));
        const retainedIds = currentSelection.filter((documentId) => availableIds.has(documentId));
        return retainedIds.length > 0
          ? retainedIds
          : nextDocuments.slice(0, 1).map((document) => document.id);
      });
    } catch (nextError) {
      setError(messageFromError(nextError, "Não foi possível carregar o Estúdio de IA agora."));
    } finally {
      setIsLoading(false);
    }
  }, [session.access_token]);

  useEffect(() => {
    void refreshStudioData();
  }, [refreshStudioData]);

  function toggleDocument(documentId: string) {
    setNotice(null);
    setError(null);
    setSelectedDocumentIds((currentSelection) =>
      currentSelection.includes(documentId)
        ? currentSelection.filter((id) => id !== documentId)
        : [...currentSelection, documentId],
    );
  }

  useEffect(() => {
    window.localStorage.setItem(
      "synapse:studio:selectedDocumentIds",
      JSON.stringify(selectedDocumentIds),
    );
  }, [selectedDocumentIds]);

  async function handlePrepare() {
    if (selectedDocumentIds.length === 0) {
      setError("Selecione pelo menos um documento para preparar a base semântica.");
      return;
    }

    setActiveOperation("prepare");
    setError(null);
    setNotice(null);
    try {
      const response = await prepareStudioDocuments({
        accessToken: session.access_token,
        selectedDocumentIds,
      });
      setNotice(response.message);
      await refreshStudioData();
    } catch (nextError) {
      setError(messageFromError(nextError, "Não foi possível preparar o escopo para IA."));
    } finally {
      setActiveOperation(null);
    }
  }

  async function handleRunAnalysis() {
    if (!hasEnoughDocuments) {
      setError(
        workflowDefinition.minimumDocuments === 2
          ? "Selecione pelo menos dois documentos para executar a comparação."
          : "Selecione pelo menos um documento para executar esta análise.",
      );
      return;
    }
    if (!selectedScopeIsPrepared) {
      setError("Prepare a base semântica deste escopo antes de iniciar a análise.");
      return;
    }
    if (workflowDefinition.needsQuestion && !question.trim()) {
      setError("Digite uma pergunta clara para consultar a base documental.");
      return;
    }

    setActiveOperation("analysis");
    setError(null);
    setNotice(null);
    try {
      const response = await runStudioAnalysis({
        accessToken: session.access_token,
        workflow,
        selectedDocumentIds,
        question: workflowDefinition.needsQuestion ? question.trim() : undefined,
        saveToHistory,
      });
      setLastAnalysis(response);
      setNotice(response.message);
      if (response.saved_to_history) {
        const nextHistory = await listStudioHistory(session.access_token, 50);
        setHistory(nextHistory);
      }
    } catch (nextError) {
      setError(messageFromError(nextError, "Não foi possível concluir a análise agora."));
    } finally {
      setActiveOperation(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Diagnóstico assistido"
        title="Diagnóstico Organizacional"
        description="Defina um escopo privado, prepare a busca semântica e gere um diagnóstico com plano de ação, sentimentos e alertas preventivos."
      />

      {error ? (
        <p
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold leading-6 text-red-800"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold leading-6 text-emerald-800"
          role="status"
        >
          {notice}
        </p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <SectionCard
          title="1. Defina o escopo"
          description="Selecione apenas documentos que pertencem ao mesmo contexto ou decisão. A IA consultará exclusivamente este conjunto."
        >
          <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-semibold text-ink-soft">
              {selectedDocumentIds.length} documento(s) no escopo
            </p>
            <button
              className="w-fit rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-ink transition hover:border-synapse-blue hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading || activeOperation !== null}
              onClick={() => void refreshStudioData()}
              type="button"
            >
              Atualizar documentos
            </button>
          </div>

          {isLoading ? <p className="mt-5 text-sm text-ink-soft">Carregando documentos...</p> : null}
          {!isLoading && documents.length === 0 ? (
            <div className="mt-5">
              <EmptyState
                title="Sua base ainda não tem conteúdo analisável."
                description="Envie um arquivo com texto extraível para preparar o primeiro escopo de IA."
                action="Enviar documento"
                actionHref="/upload"
              />
            </div>
          ) : null}
          {!isLoading && documents.length > 0 ? (
            <details className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-bold text-ink">
                Selecionar documentos ({documents.length})
                <span className="ml-2 text-xs font-medium text-ink-soft">
                  {selectedDocumentIds.length} no escopo atual
                </span>
              </summary>
              <div className="mt-4 space-y-3">
              {documents.map((document) => {
                const isSelected = selectedDocumentIds.includes(document.id);
                return (
                  <label
                    className={`flex cursor-pointer gap-3 rounded-xl border p-4 transition ${
                      isSelected
                        ? "border-synapse-blue bg-blue-50"
                        : "border-slate-200 bg-white hover:border-blue-200"
                    }`}
                    key={document.id}
                  >
                    <input
                      checked={isSelected}
                      className="mt-1 h-4 w-4 accent-blue-600"
                      disabled={activeOperation !== null}
                      onChange={() => toggleDocument(document.id)}
                      type="checkbox"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-bold text-ink">
                        {document.filename}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-ink-soft">
                        {document.text_char_count.toLocaleString("pt-BR")} caracteres ·{" "}
                        {document.status}
                      </span>
                    </span>
                    <span
                      className={`h-fit rounded-full px-2 py-1 text-xs font-bold ${
                        document.prepared_for_ai
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-900"
                      }`}
                    >
                      {document.prepared_for_ai
                        ? `${document.indexed_chunk_count} trechos prontos`
                        : "Pendente de preparação"}
                    </span>
                  </label>
                );
              })}
              </div>
            </details>
          ) : null}
        </SectionCard>

        <SectionCard
          title="2. Prepare para IA"
          description="Esta etapa cria os trechos e vetores privados usados pela busca semântica. Repita apenas quando trocar o escopo ou enviar novos documentos."
        >
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-bold text-ink">
              {selectedScopeIsPrepared ? "Escopo pronto para análise" : "Preparação necessária"}
            </p>
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              {selectedScopeIsPrepared
                ? "Você pode executar quantas análises precisar sem repetir a preparação."
                : "A preparação organiza o conteúdo selecionado em trechos pesquisáveis e não gera uma resposta por si só."}
            </p>
          </div>
          <button
            className="mt-5 w-full rounded-xl bg-synapse-blue px-4 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={selectedDocumentIds.length === 0 || activeOperation !== null || selectedScopeIsPrepared}
            onClick={() => void handlePrepare()}
            type="button"
          >
            {activeOperation === "prepare"
              ? "Preparando base semântica..."
              : selectedScopeIsPrepared
                ? "Base semântica pronta"
                : "Preparar base semântica"}
          </button>
          {activeOperation === "prepare" ? (
            <p className="mt-3 text-center text-sm font-semibold text-synapse-blue" role="status">
              Extraindo contexto e criando os índices privados do escopo...
            </p>
          ) : null}
        </SectionCard>
      </div>

      <SectionCard
        title="3. Gere uma análise"
        description="Escolha uma leitura especializada. O resultado usa somente os documentos selecionados acima e pode ser salvo para auditoria."
      >
        <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
          <label className="block text-sm font-bold text-ink" htmlFor="studio-workflow">
            Tipo de análise
            <select
              className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              disabled={activeOperation !== null}
              id="studio-workflow"
              onChange={(event) => {
                setWorkflow(event.target.value as StudioWorkflow);
                setError(null);
                setNotice(null);
              }}
              value={workflow}
            >
              {workflows.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-ink-soft">
            <p className="font-bold text-ink">{workflowDefinition.label}</p>
            <p className="mt-2">{workflowDefinition.description}</p>
            {workflowDefinition.minimumDocuments > 1 ? (
              <p className="mt-2 font-semibold text-amber-800">
                Esta análise exige pelo menos dois documentos.
              </p>
            ) : null}
          </div>
        </div>

        {workflowDefinition.needsQuestion ? (
          <label className="mt-5 block text-sm font-bold text-ink" htmlFor="studio-question">
            Pergunta para a base
            <textarea
              className="mt-2 min-h-32 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              disabled={activeOperation !== null}
              id="studio-question"
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ex.: Quais decisões, riscos e prazos críticos aparecem neste escopo?"
              value={question}
            />
          </label>
        ) : null}

        <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm text-ink">
          <input
            checked={saveToHistory}
            className="mt-1 h-4 w-4 accent-blue-600"
            disabled={activeOperation !== null}
            onChange={(event) => setSaveToHistory(event.target.checked)}
            type="checkbox"
          />
          <span>
            <strong className="block">Salvar no histórico e na trilha de evidências</strong>
            <span className="mt-1 block leading-6 text-ink-soft">
              Mantém o resultado disponível para auditoria, padrões históricos e acompanhamento posterior.
            </span>
          </span>
        </label>

        <button
          className="mx-auto mt-5 block rounded-xl bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={
            activeOperation !== null ||
            !hasEnoughDocuments ||
            !selectedScopeIsPrepared ||
            (workflowDefinition.needsQuestion && !question.trim())
          }
          onClick={() => void handleRunAnalysis()}
          type="button"
        >
          {activeOperation === "analysis" ? "A IA está analisando o escopo..." : "Gerar Diagnóstico"}
        </button>
        {activeOperation === "analysis" ? (
          <p className="mt-3 text-sm font-semibold text-synapse-blue" role="status">
            A resposta pode levar alguns instantes em análises mais profundas. Mantenha esta tela aberta.
          </p>
        ) : null}
      </SectionCard>

      {lastAnalysis ? <StudioResult analysis={lastAnalysis} /> : null}

      <SectionCard
        title="Histórico de diagnósticos"
        description="Análises salvas por esta conta, com respostas e fontes preservadas para consulta posterior."
      >
        <details
          className="rounded-xl border border-slate-200 bg-slate-50 p-4"
          id="history"
          open={searchParams.has("history")}
        >
          <summary className="cursor-pointer text-sm font-bold text-ink">
            Ver diagnósticos salvos ({history.length})
          </summary>
          <div className="mt-4">
            <StudioHistory entries={history} highlightedEntryId={searchParams.get("history")} />
          </div>
        </details>
      </SectionCard>
    </>
  );
}

function messageFromError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
