import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";

export default function InsightsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Insights consolidados"
        title="Insights organizacionais"
        description="Investigue riscos, planos, padrões e achados especializados sem misturar operação com análise executiva."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Alertas" value="0" description="Sinais preventivos detectados." tone="amber" />
        <KpiCard label="Críticos" value="0" description="Exigem validação imediata." tone="red" />
        <KpiCard label="Planos" value="0" description="Planos de ação salvos." tone="blue" />
        <KpiCard label="Achados" value="0" description="Padrões e agentes especializados." tone="green" />
      </section>

      <SectionCard title="Mapa de riscos" description="Área reservada para gráficos e filtros cruzados.">
        <EmptyState
          title="Nenhum insight carregado no frontend novo."
          description="A próxima fase vai conectar esses cards às rotas FastAPI de análises e histórico."
        />
      </SectionCard>
    </>
  );
}
