import type { StudioAnalysisResponse, StudioHistoryEntry } from "@/services/api";

type ResultRecord = Record<string, unknown>;

const collectionLabels: Record<string, string> = {
  agent_outputs: "Pareceres especializados",
  alerts: "Alertas identificados",
  consensus: "Consensos encontrados",
  conflicts: "Conflitos identificados",
  dominant_signals: "Sinais dominantes",
  findings: "Achados estruturados",
  issues: "Inconsistências identificadas",
  items: "Itens recomendados",
  patterns: "Padrões reconhecidos",
  recommendations: "Recomendações",
  signals: "Sinais identificados",
};

export function StudioResult({ analysis }: { analysis: StudioAnalysisResponse }) {
  const artifact = resolveArtifact(analysis.result);
  const summary = firstText(artifact, [
    "answer",
    "executive_summary",
    "summary",
    "overall_sentiment",
  ]);
  const collections = findCollections(artifact);
  const sources = asRecords(artifact.sources);

  return (
    <section
      className="rounded-2xl border border-emerald-200 bg-white p-6 shadow-soft-card"
      role="status"
    >
      <div className="flex flex-col gap-3 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">
            Análise concluída
          </p>
          <h2 className="mt-2 text-2xl font-black text-ink">{analysis.message}</h2>
        </div>
        <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
          {analysis.saved_to_history ? "Salvo no histórico" : "Resultado desta sessão"}
        </span>
      </div>

      {summary ? <p className="mt-6 whitespace-pre-wrap text-sm leading-7 text-ink">{summary}</p> : null}

      {collections.length > 0 ? (
        <div className="mt-6 space-y-6">
          {collections.map((collection) => (
            <div key={collection.key}>
              <h3 className="text-base font-black text-ink">{collection.label}</h3>
              <div className="mt-3 space-y-3">
                {collection.items.map((item, index) => (
                  <ResultItem item={item} key={`${collection.key}-${index}`} position={index + 1} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {sources.length > 0 ? <SourceList sources={sources} /> : null}

      {analysis.persistence_warning ? (
        <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          {analysis.persistence_warning}
        </p>
      ) : null}
    </section>
  );
}

export function StudioHistory({ entries }: { entries: StudioHistoryEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="rounded-xl bg-slate-50 p-4 text-sm leading-6 text-ink-soft">
        Nenhuma análise foi salva por esta conta ainda.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <details className="rounded-xl border border-slate-200 bg-white p-4" key={entry.id}>
          <summary className="cursor-pointer list-none pr-8 text-sm font-bold text-ink">
            {entry.title}
            <span className="mt-1 block text-xs font-medium text-ink-soft">
              {entry.document_filename ? `${entry.document_filename} · ` : ""}
              {formatDate(entry.created_at)}
            </span>
          </summary>
          <div className="mt-4 border-t border-slate-100 pt-4 text-sm leading-6 text-ink-soft">
            {entry.question ? (
              <p>
                <strong className="text-ink">Pergunta: </strong>
                {entry.question}
              </p>
            ) : null}
            <p className="mt-3 whitespace-pre-wrap text-ink">{entry.answer}</p>
            {entry.sources.length > 0 ? <SourceList sources={entry.sources} compact /> : null}
          </div>
        </details>
      ))}
    </div>
  );
}

function ResultItem({ item, position }: { item: unknown; position: number }) {
  if (!isRecord(item)) {
    return <p className="rounded-xl bg-slate-50 p-4 text-sm text-ink">{formatValue(item)}</p>;
  }

  const title = firstText(item, ["task", "title", "agent_name", "category"]) ?? `Item ${position}`;
  const fields = Object.entries(item).filter(([key]) => !isAuxiliaryKey(key));

  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <h4 className="font-bold text-ink">{title}</h4>
      <dl className="mt-3 grid gap-3 text-sm leading-6 sm:grid-cols-2">
        {fields.map(([key, value]) => (
          <div className={isLongValue(value) ? "sm:col-span-2" : ""} key={key}>
            <dt className="text-xs font-bold uppercase tracking-wide text-ink-soft">
              {fieldLabel(key)}
            </dt>
            <dd className="mt-1 whitespace-pre-wrap text-ink">{formatValue(value)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function SourceList({ sources, compact = false }: { sources: ResultRecord[]; compact?: boolean }) {
  return (
    <details className={compact ? "mt-4" : "mt-6 rounded-xl bg-slate-50 p-4"}>
      <summary className="cursor-pointer text-sm font-bold text-ink">
        Fontes e evidências ({sources.length})
      </summary>
      <div className="mt-4 space-y-3">
        {sources.map((source, index) => {
          const filename = firstText(source, ["filename"]) ?? "Documento sem nome";
          const excerpt = firstText(source, ["content", "excerpt"]);
          const similarity = source.similarity;
          return (
            <article
              className="rounded-lg border border-slate-200 bg-white p-3 text-sm"
              key={`${filename}-${index}`}
            >
              <p className="font-bold text-ink">{filename}</p>
              <p className="mt-1 text-xs text-ink-soft">
                Trecho {formatValue(source.chunk_index ?? 0)}
                {typeof similarity === "number" ? ` · similaridade ${similarity.toFixed(3)}` : ""}
              </p>
              {excerpt ? <p className="mt-3 whitespace-pre-wrap leading-6 text-ink-soft">{excerpt}</p> : null}
            </article>
          );
        })}
      </div>
    </details>
  );
}

function resolveArtifact(result: ResultRecord): ResultRecord {
  for (const key of ["rag_answer", "action_plan", "snapshot", "report"]) {
    const candidate = result[key];
    if (isRecord(candidate)) {
      return candidate;
    }
  }
  return result;
}

function findCollections(record: ResultRecord): { key: string; label: string; items: unknown[] }[] {
  return Object.keys(collectionLabels)
    .map((key) => {
      const value = record[key];
      return Array.isArray(value) && value.length > 0
        ? { key, label: collectionLabels[key], items: value }
        : null;
    })
    .filter((value): value is { key: string; label: string; items: unknown[] } => value !== null);
}

function asRecords(value: unknown): ResultRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function isRecord(value: unknown): value is ResultRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function firstText(record: ResultRecord, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return null;
}

function isAuxiliaryKey(key: string): boolean {
  return ["title", "task", "agent_name", "category", "source_refs", "related_records"].includes(key);
}

function isLongValue(value: unknown): boolean {
  return typeof value === "string" && value.length > 80;
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    agent_id: "Agente",
    alert_type: "Tipo",
    confidence: "Confiança",
    current_signal: "Sinal atual",
    deadline: "Prazo",
    description: "Descrição",
    documents: "Documentos",
    dominant_signals: "Sinais dominantes",
    evidence: "Evidência",
    historical_evidence: "Evidência histórica",
    impact: "Impacto",
    intensity: "Intensidade",
    interpretation: "Interpretação",
    issue_type: "Tipo de inconsistência",
    mission: "Missão",
    overall_sentiment: "Sentimento geral",
    owner: "Responsável",
    polarity: "Polaridade",
    priority: "Prioridade",
    recommendation: "Recomendação",
    recurrence: "Recorrência",
    responsible: "Responsável",
    risk: "Risco",
    risk_level: "Nível de risco",
    severity: "Severidade",
    status: "Status",
    summary: "Síntese",
    trigger: "Gatilho",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Não informado";
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).join(", ");
  }
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, item]) => `${fieldLabel(key)}: ${formatValue(item)}`)
      .join(" · ");
  }
  return String(value);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Data não informada";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
