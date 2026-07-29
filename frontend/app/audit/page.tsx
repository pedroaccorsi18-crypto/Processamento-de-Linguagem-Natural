"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { useSynapseSession } from "@/components/auth-gate";
import { listStudioHistory, type StudioHistoryEntry } from "@/services/api";

export default function AuditPage() {
  const { session } = useSynapseSession();
  const [history, setHistory] = useState<StudioHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    listStudioHistory(session.access_token, 80)
      .then((entries) => {
        if (isMounted) {
          setHistory(entries);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Não foi possível carregar a auditoria.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [session.access_token]);

  const audit = useMemo(() => buildAudit(history), [history]);
  const exportContent = useMemo(() => buildMarkdownExport(history), [history]);

  return (
    <>
      <PageHeader
        eyebrow="Auditoria"
        title="Trilha de evidências"
        description="Revise documentos, perguntas, respostas, fontes e pacotes auditáveis gerados pelo Synapse AI."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Registros" value={String(history.length)} description="Análises salvas." tone="blue" />
        <KpiCard label="Fontes" value={String(audit.sourceCount)} description="Evidências citadas." tone="green" />
        <KpiCard label="Documentos" value={String(audit.documentCount)} description="Arquivos referenciados." tone="amber" />
        <KpiCard label="Modelos" value={String(audit.modelCount)} description="Modelos registrados." tone="red" />
      </section>

      {error ? (
        <section className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm font-semibold text-red-900">
          {error}
        </section>
      ) : null}

      <SectionCard
        title="Pacote de evidências"
        description="Auditoria gerada a partir do histórico salvo no Estúdio, com respostas, documentos e fontes recuperadas."
      >
        {isLoading ? (
          <p className="rounded-xl bg-slate-50 p-4 text-sm font-semibold text-ink-soft">
            Carregando trilha de evidências...
          </p>
        ) : history.length === 0 ? (
          <EmptyState
            title="A trilha de auditoria ainda está vazia."
            description="Salve uma análise no Estúdio de IA para que ela apareça aqui com rastreabilidade, documentos e fontes."
            action="Explorar Estúdio de IA"
            actionHref="/studio"
          />
        ) : (
          <div className="space-y-5">
            <a
              className="inline-flex rounded-lg bg-synapse-blue px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-700"
              download="pacote_evidencias_synapse.md"
              href={`data:text/markdown;charset=utf-8,${encodeURIComponent(exportContent)}`}
            >
              Baixar pacote de evidências
            </a>
            <AuditTimeline entries={history} />
          </div>
        )}
      </SectionCard>
    </>
  );
}

function AuditTimeline({ entries }: { entries: StudioHistoryEntry[] }) {
  return (
    <div className="space-y-4">
      {entries.map((entry) => (
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft-card" key={entry.id}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-lg font-black text-ink">{entry.title || "Análise salva"}</h3>
              <p className="mt-1 text-xs font-medium text-ink-soft">
                {entry.document_filename ?? "Escopo documental"} · {formatDate(entry.created_at)}
              </p>
            </div>
            <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-ink-soft">
              {entry.status}
            </span>
          </div>

          {entry.question ? (
            <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-ink">
              <strong>Pergunta: </strong>
              {entry.question}
            </p>
          ) : null}

          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-ink-soft">
            {entry.answer || "Resposta não registrada."}
          </p>

          {entry.sources.length > 0 ? (
            <details className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-bold text-ink">
                Fontes recuperadas ({entry.sources.length})
              </summary>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {entry.sources.map((source, index) => (
                  <SourceCard index={index + 1} key={`${entry.id}-${index}`} source={source} />
                ))}
              </div>
            </details>
          ) : (
            <p className="mt-4 rounded-xl bg-amber-50 p-4 text-sm font-semibold text-amber-900">
              Este registro não possui fontes salvas.
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

function SourceCard({ source, index }: { source: Record<string, unknown>; index: number }) {
  const filename = readText(source, "filename") ?? "Documento sem nome";
  const excerpt = readText(source, "content") ?? readText(source, "excerpt");
  const chunkIndex = source.chunk_index ?? 0;
  const similarity = typeof source.similarity === "number" ? source.similarity.toFixed(3) : null;

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
      <p className="font-black text-ink">
        Fonte {index}: {filename}
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        Trecho {String(chunkIndex)}
        {similarity ? ` · similaridade ${similarity}` : ""}
      </p>
      {excerpt ? <p className="mt-3 line-clamp-5 leading-6 text-ink-soft">{excerpt}</p> : null}
    </article>
  );
}

function buildAudit(entries: StudioHistoryEntry[]) {
  const documents = new Set<string>();
  const models = new Set<string>();
  let sourceCount = 0;

  for (const entry of entries) {
    if (entry.document_filename) {
      documents.add(entry.document_filename);
    }
    if (entry.model) {
      models.add(entry.model);
    }
    sourceCount += entry.sources.length;
    for (const source of entry.sources) {
      const filename = readText(source, "filename");
      if (filename) {
        documents.add(filename);
      }
    }
  }

  return {
    sourceCount,
    documentCount: documents.size,
    modelCount: models.size,
  };
}

function buildMarkdownExport(entries: StudioHistoryEntry[]): string {
  const lines = [
    "# Pacote de evidências - Synapse AI",
    "",
    `Gerado em: ${new Date().toLocaleString("pt-BR")}`,
    `Registros: ${entries.length}`,
    "",
  ];

  for (const entry of entries) {
    lines.push(`## ${entry.title || "Análise salva"}`);
    lines.push("");
    lines.push(`- Data: ${formatDate(entry.created_at)}`);
    lines.push(`- Documento: ${entry.document_filename ?? "Escopo documental"}`);
    lines.push(`- Modelo: ${entry.model ?? "Não informado"}`);
    lines.push(`- Status: ${entry.status}`);
    if (entry.question) {
      lines.push("");
      lines.push(`**Pergunta:** ${entry.question}`);
    }
    lines.push("");
    lines.push("**Resposta:**");
    lines.push("");
    lines.push(entry.answer || "Resposta não registrada.");
    lines.push("");
    if (entry.sources.length > 0) {
      lines.push("**Fontes:**");
      for (const [index, source] of entry.sources.entries()) {
        lines.push(
          `${index + 1}. ${readText(source, "filename") ?? "Documento sem nome"} - trecho ${
            source.chunk_index ?? 0
          }`,
        );
      }
      lines.push("");
    }
  }

  return lines.join("\n");
}

function readText(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Data não informada";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
