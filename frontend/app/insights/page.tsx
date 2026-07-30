"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { useSynapseSession } from "@/components/auth-gate";
import { listStudioHistory, type StudioHistoryEntry } from "@/services/api";

type RiskLevel = "Crítico" | "Alto" | "Médio" | "Baixo";

const riskTone: Record<RiskLevel, string> = {
  Crítico: "bg-red-600",
  Alto: "bg-amber-500",
  Médio: "bg-blue-500",
  Baixo: "bg-emerald-500",
};

export default function InsightsPage() {
  const { session } = useSynapseSession();
  const [history, setHistory] = useState<StudioHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    listStudioHistory(session.access_token, 50)
      .then((entries) => {
        if (isMounted) {
          setHistory(entries);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Não foi possível carregar os insights.");
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

  const insights = useMemo(() => buildInsights(history), [history]);

  return (
    <>
      <PageHeader
        eyebrow="Insights consolidados"
        title="Insights organizacionais"
        description="Investigue riscos, planos, padrões e achados especializados sem misturar operação com análise executiva."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Alertas"
          value={String(insights.alerts)}
          description="Sinais preventivos detectados nas análises."
          tone="amber"
        />
        <KpiCard
          label="Críticos"
          value={String(insights.critical)}
          description="Achados que exigem validação imediata."
          tone="red"
        />
        <KpiCard
          label="Planos"
          value={String(insights.actionPlans)}
          description="Planos de ação salvos no histórico."
          tone="blue"
        />
        <KpiCard
          label="Achados"
          value={String(insights.findings)}
          description="Padrões, comparações e agentes especializados."
          tone="green"
        />
      </section>

      {error ? (
        <section className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm font-semibold text-red-900">
          {error}
        </section>
      ) : null}

      <SectionCard
        title="Mapa de riscos"
        description="Leitura executiva gerada a partir das análises salvas no Estúdio de IA."
      >
        {isLoading ? (
          <p className="rounded-xl bg-slate-50 p-4 text-sm font-semibold text-ink-soft">
            Carregando inteligência salva...
          </p>
        ) : history.length === 0 ? (
          <EmptyState
            title="Nenhum insight salvo ainda."
            description="Gere uma análise no Estúdio de IA e salve no histórico para alimentar o mapa de riscos, planos e evidências."
            action="Abrir Estúdio de IA"
            actionHref="/studio"
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
            <RiskDistribution distribution={insights.riskDistribution} total={insights.riskTotal} />
            <RecentFindings entries={history.slice(0, 6)} />
          </div>
        )}
      </SectionCard>
    </>
  );
}

function RiskDistribution({
  distribution,
  total,
}: {
  distribution: Record<RiskLevel, number>;
  total: number;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
      <h3 className="text-base font-black text-ink">Distribuição por severidade</h3>
      <p className="mt-2 text-sm leading-6 text-ink-soft">
        Estimativa baseada nos termos e categorias das análises salvas.
      </p>
      <div className="mt-5 space-y-4">
        {(Object.keys(distribution) as RiskLevel[]).map((level) => {
          const value = distribution[level];
          const width = total > 0 ? Math.max((value / total) * 100, value > 0 ? 8 : 0) : 0;
          return (
            <div key={level}>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-bold text-ink">{level}</span>
                <span className="text-ink-soft">{value}</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-white">
                <div
                  className={`h-full rounded-full ${riskTone[level]}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RecentFindings({ entries }: { entries: StudioHistoryEntry[] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="text-base font-black text-ink">Achados recentes</h3>
      <div className="mt-4 space-y-3">
        {entries.map((entry) => (
          <Link
            className="block rounded-xl border border-slate-200 bg-slate-50 p-4 transition hover:border-synapse-blue hover:bg-blue-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
            href={`/studio?history=${encodeURIComponent(entry.id)}#history`}
            key={entry.id}
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 className="font-bold text-ink">{entry.title || "Análise salva"}</h4>
                <p className="mt-1 text-xs font-medium text-ink-soft">
                  {entry.document_filename ?? "Escopo documental"} · {formatDate(entry.created_at)}
                </p>
              </div>
              <span className="w-fit rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800">
                {entry.sources.length} fonte(s)
              </span>
            </div>
            <p className="mt-3 line-clamp-3 text-sm leading-6 text-ink-soft">
              {entry.answer || entry.question || "Sem resumo textual disponível."}
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}

function buildInsights(entries: StudioHistoryEntry[]) {
  const riskDistribution: Record<RiskLevel, number> = {
    Crítico: 0,
    Alto: 0,
    Médio: 0,
    Baixo: 0,
  };

  let alerts = 0;
  let actionPlans = 0;
  let findings = 0;

  for (const entry of entries) {
    const searchable = `${entry.title} ${entry.question} ${entry.answer} ${JSON.stringify(entry.metadata)}`.toLowerCase();
    if (searchable.includes("alerta") || searchable.includes("risco")) {
      alerts += 1;
    }
    if (searchable.includes("plano") || searchable.includes("ação") || searchable.includes("acao")) {
      actionPlans += 1;
    }
    if (
      searchable.includes("padrão") ||
      searchable.includes("padrao") ||
      searchable.includes("agente") ||
      searchable.includes("compar")
    ) {
      findings += 1;
    }

    if (searchable.includes("crítico") || searchable.includes("critico")) {
      riskDistribution.Crítico += 1;
    } else if (searchable.includes("alto") || searchable.includes("alta")) {
      riskDistribution.Alto += 1;
    } else if (searchable.includes("médio") || searchable.includes("medio") || searchable.includes("moderado")) {
      riskDistribution.Médio += 1;
    } else {
      riskDistribution.Baixo += 1;
    }
  }

  const critical = riskDistribution.Crítico;
  const riskTotal = Object.values(riskDistribution).reduce((sum, value) => sum + value, 0);

  return {
    alerts,
    critical,
    actionPlans,
    findings,
    riskDistribution,
    riskTotal,
  };
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Data não informada";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
