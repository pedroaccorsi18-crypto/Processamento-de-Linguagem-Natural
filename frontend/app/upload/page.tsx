import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";

export default function UploadPage() {
  return (
    <>
      <PageHeader
        eyebrow="Upload"
        title="Base documental"
        description="Envie documentos locais ou conecte fontes corporativas para preparar sua inteligência."
      />

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard
          title="Enviar arquivo"
          description="Área preparada para receber o fluxo de ingestão documental vindo do backend FastAPI."
        >
          <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-10 text-center">
            <p className="text-lg font-bold text-ink">Arraste documentos aqui</p>
            <p className="mt-2 text-sm text-ink-soft">
              PDF, DOCX, PPTX, XLSX, TXT, CSV, EML, áudio e transcrições.
            </p>
          </div>
        </SectionCard>

        <SectionCard
          title="Documentos recentes"
          description="Listagem futura dos documentos isolados por usuário e tenant."
        >
          <EmptyState
            title="Nenhum documento nesta interface ainda."
            description="O Streamlit permanece como referência viva enquanto a nova API recebe os endpoints de ingestão."
          />
        </SectionCard>
      </div>
    </>
  );
}
