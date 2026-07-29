import Link from "next/link";

export const metadata = {
  title: "Privacidade | Synapse AI",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 sm:px-10">
      <Link className="text-sm font-bold text-synapse-blue" href="/dashboard">
        Synapse AI
      </Link>
      <h1 className="mt-6 text-4xl font-black tracking-tight text-ink">Política de Privacidade</h1>
      <p className="mt-3 text-sm text-ink-soft">Última atualização: 29 de julho de 2026</p>
      <div className="mt-10 space-y-8 rounded-2xl border border-slate-200 bg-white p-8 text-sm leading-7 text-ink-soft shadow-soft-card">
        <section>
          <h2 className="text-lg font-black text-ink">Finalidade</h2>
          <p className="mt-2">O Synapse AI processa documentos e conteúdos autorizados para permitir busca, análises e relatórios solicitados pelo usuário autenticado.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Dados e isolamento</h2>
          <p className="mt-2">Cada documento, análise e conexão corporativa é associado à conta que o enviou. Credenciais de conectores são cifradas no servidor e não são exibidas pela interface.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Conectores externos</h2>
          <p className="mt-2">Google Drive, Slack, Microsoft Teams e SharePoint são conectados apenas após consentimento. O Synapse solicita acesso de leitura estritamente necessário para importar o conteúdo escolhido pelo usuário.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Retenção e exclusão</h2>
          <p className="mt-2">O usuário pode desconectar integrações a qualquer momento. Os documentos já importados permanecem na base da conta até que sejam removidos conforme os controles disponibilizados pela plataforma.</p>
        </section>
        <section>
          <h2 className="text-lg font-black text-ink">Contato</h2>
          <p className="mt-2">Para dúvidas sobre privacidade ou tratamento de dados, entre em contato pelo e-mail de suporte informado na tela de consentimento do aplicativo.</p>
        </section>
      </div>
    </main>
  );
}
