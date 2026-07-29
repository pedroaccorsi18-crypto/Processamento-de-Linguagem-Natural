import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        eyebrow="Área autenticada"
        title="Dashboard executivo"
        description="Leitura consolidada da base documental, riscos, planos de ação e inteligência salva."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Base pronta" value="0 de 0" description="Documentos preparados para IA." />
        <KpiCard label="Evidências" value="0" description="Registros auditáveis salvos." tone="green" />
        <KpiCard label="Riscos" value="0" description="Alertas preventivos detectados." tone="amber" />
        <KpiCard label="A confirmar" value="0" description="Itens sem responsável ou prazo." tone="red" />
      </section>

      <SectionCard
        title="Próximo melhor passo"
        description="Quando o backend estiver conectado, este bloco será alimentado pelos mesmos dados do Synapse atual."
      >
        <EmptyState
          title="Nenhuma inteligência carregada ainda."
          description="Conecte a API FastAPI ao painel para exibir documentos, alertas e recomendações em tempo real."
          action="Ir para Base documental"
        />
      </SectionCard>
    </>
  );
}
