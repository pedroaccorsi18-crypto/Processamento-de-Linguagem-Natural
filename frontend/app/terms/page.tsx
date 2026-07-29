import Link from "next/link";

export const metadata = {
  title: "Termos de Uso | Synapse AI",
};

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 sm:px-10">
      <Link className="text-sm font-bold text-synapse-blue" href="/dashboard">
        Synapse AI
      </Link>
      <h1 className="mt-6 text-4xl font-black tracking-tight text-ink">Termos de Uso</h1>
      <p className="mt-3 text-sm text-ink-soft">Última atualização: 29 de julho de 2026</p>
      <div className="mt-10 space-y-8 rounded-2xl border border-slate-200 bg-white p-8 text-sm leading-7 text-ink-soft shadow-soft-card">
        <section>
          <h2 className="text-lg font-black text-ink">Uso autorizado</h2>
          <p className="mt-2">O usuário é responsável por ter autorização para enviar documentos e conectar fontes corporativas à sua conta no Synapse AI.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Acesso de leitura</h2>
          <p className="mt-2">Os conectores externos são usados exclusivamente para leitura e importação do conteúdo selecionado. O Synapse AI não publica, edita ou exclui conteúdo nas fontes conectadas.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Análises assistidas por IA</h2>
          <p className="mt-2">As respostas e relatórios são apoio à decisão. Cabe ao usuário validar informações relevantes antes de tomar decisões operacionais, jurídicas, financeiras ou estratégicas.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Segurança da conta</h2>
          <p className="mt-2">Mantenha suas credenciais de acesso protegidas e desconecte integrações que não sejam mais necessárias.</p>
        </section>
      </div>
    </main>
  );
}
