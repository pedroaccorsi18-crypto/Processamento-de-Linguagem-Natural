import Link from "next/link";

export const metadata = {
  title: "Synapse AI | Inteligência organizacional",
  description:
    "Plataforma de inteligência organizacional com busca semântica, rastreabilidade e conectores corporativos.",
};

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16 sm:px-10">
      <Link className="text-sm font-bold text-synapse-blue" href="/dashboard">
        Synapse AI
      </Link>
      <p className="mt-10 text-xs font-black uppercase tracking-widest text-synapse-blue">
        Inteligência organizacional
      </p>
      <h1 className="mt-3 max-w-3xl text-4xl font-black tracking-tight text-ink sm:text-5xl">
        Decisões mais claras a partir do conhecimento que já existe na sua organização.
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-8 text-ink-soft">
        O Synapse AI organiza documentos autorizados, recupera evidências relevantes e
        transforma conteúdo disperso em análises rastreáveis para equipes.
      </p>

      <section className="mt-12 grid gap-5 md:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft-card">
          <h2 className="font-black text-ink">Fontes autorizadas</h2>
          <p className="mt-3 text-sm leading-6 text-ink-soft">
            Conecte arquivos locais, Google Drive, Slack, Microsoft Teams e SharePoint
            somente com consentimento explícito.
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft-card">
          <h2 className="font-black text-ink">Respostas com evidências</h2>
          <p className="mt-3 text-sm leading-6 text-ink-soft">
            Pergunte, compare e gere planos de ação com referências aos trechos que
            sustentam cada conclusão.
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft-card">
          <h2 className="font-black text-ink">Controle por conta</h2>
          <p className="mt-3 text-sm leading-6 text-ink-soft">
            Documentos e credenciais de conectores permanecem isolados para a conta que
            realizou a conexão.
          </p>
        </article>
      </section>

      <footer className="mt-14 flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold text-synapse-blue">
        <Link href="/privacy">Política de Privacidade</Link>
        <Link href="/terms">Termos de Uso</Link>
      </footer>
    </main>
  );
}
