import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";

const workflows = [
  "Perguntar com fontes",
  "Plano de ação",
  "Inteligência organizacional",
  "Comparação documental",
  "Alertas preventivos",
  "Padrões históricos",
  "Orquestração multiagente",
];

export default function StudioPage() {
  return (
    <>
      <PageHeader
        eyebrow="Inteligência aplicada"
        title="Estúdio de IA"
        description="Escolha o escopo, faça perguntas com fontes ou gere análises especializadas em poucos passos."
      />

      <SectionCard
        title="Fluxos disponíveis"
        description="A nova UI preserva as capacidades atuais, agora organizada para chamadas REST desacopladas."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {workflows.map((workflow) => (
            <Link
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-left text-sm font-bold text-ink transition hover:border-synapse-blue hover:bg-blue-50"
              href="/upload"
              key={workflow}
            >
              <span className="block">{workflow}</span>
              <span className="mt-2 block text-xs font-medium text-ink-soft">
                Comece selecionando uma base documental.
              </span>
            </Link>
          ))}
        </div>
      </SectionCard>
    </>
  );
}
