"use client";

import { useEffect, useState } from "react";
import { useSynapseSession } from "@/components/auth-gate";
import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { getDashboardStats, type DashboardStats } from "@/services/api";

export default function DashboardPage() {
  const { session } = useSynapseSession();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [hasLoadError, setHasLoadError] = useState(false);

  useEffect(() => {
    let isMounted = true;

    getDashboardStats(session.access_token)
      .then((nextStats) => {
        if (isMounted) {
          setStats(nextStats);
        }
      })
      .catch(() => {
        if (isMounted) {
          setHasLoadError(true);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [session.access_token]);

  return (
    <>
      <PageHeader
        eyebrow="Área autenticada"
        title="Dashboard executivo"
        description="Leitura consolidada da base documental, riscos, planos de ação e inteligência salva."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Base pronta"
          value={stats ? String(stats.base_ready) : "--"}
          description="Documentos preparados para IA."
        />
        <KpiCard
          label="Evidências"
          value={stats ? String(stats.evidence_count) : "--"}
          description="Registros auditáveis salvos."
          tone="green"
        />
        <KpiCard
          label="Riscos"
          value={stats ? String(stats.risk_count) : "--"}
          description="Alertas preventivos detectados."
          tone="amber"
        />
        <KpiCard
          label="A confirmar"
          value={stats ? String(stats.pending_confirmation_count) : "--"}
          description="Itens sem responsável ou prazo."
          tone="red"
        />
      </section>

      {hasLoadError ? (
        <p className="text-sm text-amber-700">
          Os indicadores não puderam ser atualizados agora. Tente novamente em instantes.
        </p>
      ) : null}

      <SectionCard
        title="Próximo melhor passo"
        description="Este bloco será alimentado pelos mesmos dados do Synapse atual conforme os próximos endpoints forem migrados."
      >
        <EmptyState
          title="Nenhuma inteligência carregada ainda."
          description="Conecte a base documental para exibir documentos, alertas e recomendações em tempo real."
          action="Ir para Base documental"
          actionHref="/upload"
        />
      </SectionCard>
    </>
  );
}
