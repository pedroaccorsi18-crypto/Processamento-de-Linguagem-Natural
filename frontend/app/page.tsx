import Image from "next/image";
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-surface-subtle text-ink">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-6 sm:px-8 lg:px-10">
        <Link className="flex items-center gap-3 text-lg font-black tracking-tight" href="/">
          <Image alt="Símbolo do Synapse AI" height={30} priority src="/brand/synapse-mark.png" width={32} />
          Synapse AI
        </Link>
        <Link
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-ink transition hover:border-synapse-blue hover:text-synapse-blue"
          href="/dashboard"
        >
          Entrar
        </Link>
      </header>

      <section className="mx-auto flex min-h-[calc(100vh-92px)] max-w-6xl items-center px-5 pb-20 sm:px-8 lg:px-10">
        <div className="max-w-2xl">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-synapse-blue">
            Inteligência organizacional
          </p>
          <h1 className="mt-4 text-4xl font-black leading-tight tracking-tight sm:text-5xl">
            Conhecimento institucional, organizado para decisões melhores.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-ink-soft">
            Envie documentos, prepare uma base semântica e encontre respostas, riscos e planos de ação com evidências rastreáveis.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              className="rounded-lg bg-synapse-blue px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700"
              href="/dashboard"
            >
              Acessar plataforma
            </Link>
            <p className="text-sm text-ink-soft">Entre ou crie sua conta na próxima tela.</p>
          </div>

          <div className="mt-12 flex flex-col gap-4 border-t border-slate-200 pt-6 text-sm text-ink-soft sm:flex-row sm:gap-8">
            <span>Base documental privada</span>
            <span>Respostas com fontes</span>
            <span>Análises orientadas por evidências</span>
          </div>
        </div>
      </section>
    </main>
  );
}
