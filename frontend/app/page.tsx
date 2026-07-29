import Link from "next/link";
import Image from "next/image";

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-surface-subtle text-ink">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-5 py-6 sm:px-8 lg:px-12">
        <Link className="flex items-center gap-3 text-xl font-black tracking-tight text-ink" href="/">
          <Image alt="Símbolo do Synapse AI" height={34} priority src="/brand/synapse-mark.png" width={36} />
          Synapse AI
        </Link>
        <Link
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-ink transition hover:border-synapse-blue hover:text-synapse-blue"
          href="/dashboard"
        >
          Entrar
        </Link>
      </header>

      <section className="mx-auto grid max-w-7xl gap-10 px-5 pb-12 pt-6 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:px-12 lg:pb-14 lg:pt-10">
        <div className="flex max-w-2xl flex-col justify-center">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-synapse-blue">
            Inteligência organizacional com evidências
          </p>
          <h1 className="mt-5 text-4xl font-black leading-tight tracking-tight text-ink sm:text-5xl">
            Transforme dados ocultos em decisões que podem ser verificadas.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-ink-soft">
            O Synapse AI organiza documentos, recupera contexto relevante e apresenta respostas,
            riscos e planos de ação vinculados às fontes originais.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              className="rounded-lg bg-synapse-blue px-5 py-3 text-sm font-black text-white shadow-sm transition hover:bg-blue-700"
              href="/dashboard"
            >
              Acessar plataforma
            </Link>
            <a
              className="rounded-lg px-5 py-3 text-sm font-bold text-ink-soft transition hover:text-ink"
              href="#como-funciona"
            >
              Entender o fluxo
            </a>
          </div>
          <p className="mt-6 text-sm leading-6 text-ink-soft">
            Ambiente autenticado. Cada conta acessa somente seus próprios documentos e análises.
          </p>
        </div>

        <div className="relative min-h-[340px] sm:min-h-[380px]">
          <div className="absolute inset-0 rounded-2xl bg-ink p-5 shadow-2xl shadow-slate-300/60 sm:p-7">
            <div className="flex items-center justify-between border-b border-white/10 pb-5">
              <div>
                <p className="text-sm font-black text-white">Visão de decisão</p>
                <p className="mt-1 text-xs text-slate-400">Operação Atlas</p>
              </div>
              <span className="rounded-full bg-emerald-400/15 px-3 py-1 text-xs font-bold text-emerald-300">
                Base preparada
              </span>
            </div>
            <div className="mt-7 grid grid-cols-2 gap-3">
              <Metric label="Documentos" value="12" />
              <Metric label="Alertas" value="3" tone="amber" />
              <Metric label="Decisões" value="8" tone="blue" />
              <Metric label="Fontes" value="27" tone="green" />
            </div>
            <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
              <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-400">
                Evidência prioritária
              </p>
              <p className="mt-3 text-base font-bold leading-6 text-white">
                A homologação de segurança precisa ser concluída antes de 12 de agosto.
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Fonte recuperada: Ata da diretoria - trecho 04
              </p>
            </div>
            <div className="mt-4 flex items-center gap-3 text-sm text-slate-300">
              <span className="h-2 w-2 rounded-full bg-synapse-blue" />
              Rastreabilidade disponível para cada conclusão
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white" id="como-funciona">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
          <div className="max-w-2xl">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-synapse-blue">
              Como funciona
            </p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-ink">
              Da fonte dispersa à decisão contextualizada.
            </h2>
          </div>
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            <FlowStep
              number="01"
              title="Centralize"
              description="Envie documentos ou conecte fontes autorizadas para formar uma base documental privada."
            />
            <FlowStep
              number="02"
              title="Prepare"
              description="O Synapse extrai texto, identifica entidades e cria a base semântica pesquisável."
            />
            <FlowStep
              number="03"
              title="Decida com evidências"
              description="Faça perguntas, gere análises e confira os trechos que sustentam cada resultado."
            />
          </div>
        </div>
      </section>

      <section className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-16 sm:px-8 lg:flex-row lg:items-end lg:justify-between lg:px-12 lg:py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-synapse-blue">
            PLN aplicado
          </p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-ink">
            RAG, NER e análise organizacional em uma experiência auditável.
          </h2>
        </div>
        <Link
          className="w-fit rounded-lg bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700"
          href="/dashboard"
        >
          Começar agora
        </Link>
      </section>
    </main>
  );
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "amber" | "blue" | "green" | "neutral";
}) {
  const tones = {
    amber: "text-amber-300",
    blue: "text-blue-300",
    green: "text-emerald-300",
    neutral: "text-white",
  };

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs font-semibold text-slate-400">{label}</p>
      <p className={`mt-2 text-3xl font-black ${tones[tone]}`}>{value}</p>
    </div>
  );
}

function FlowStep({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <article className="border-t-2 border-slate-200 pt-5">
      <p className="text-sm font-black text-synapse-blue">{number}</p>
      <h3 className="mt-3 text-xl font-black text-ink">{title}</h3>
      <p className="mt-3 max-w-sm text-sm leading-6 text-ink-soft">{description}</p>
    </article>
  );
}
