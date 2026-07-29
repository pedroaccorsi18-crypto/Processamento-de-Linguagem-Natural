import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";

export default function AuditPage() {
  return (
    <>
      <PageHeader
        eyebrow="Auditoria"
        title="Trilha de evidências"
        description="Revise documentos, perguntas, respostas, fontes e pacotes auditáveis gerados pelo Synapse AI."
      />

      <SectionCard
        title="Pacote de evidências"
        description="A futura integração REST vai disponibilizar exportações premium sem acoplar a interface ao Streamlit."
      >
        <EmptyState
          title="A trilha de auditoria ainda está vazia nesta nova interface."
          description="Depois que os endpoints de auditoria forem migrados, os registros aparecerão aqui com download e rastreabilidade."
          action="Preparar exportação"
        />
      </SectionCard>
    </>
  );
}
