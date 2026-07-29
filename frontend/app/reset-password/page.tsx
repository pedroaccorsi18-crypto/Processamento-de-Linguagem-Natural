"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isReady, setIsReady] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      setIsError(true);
      setMessage("A autenticação da plataforma ainda não está configurada.");
      return;
    }

    const client = getSupabaseBrowserClient();
    void client.auth.getSession().then(({ data }) => {
      if (data.session === null) {
        setIsError(true);
        setMessage("Este link de recuperação é inválido ou expirou. Solicite um novo link de acesso.");
      } else {
        setIsReady(true);
      }
    });
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) {
      setIsError(true);
      setMessage("As senhas informadas não coincidem.");
      return;
    }

    setIsSubmitting(true);
    setMessage(null);
    const { error } = await getSupabaseBrowserClient().auth.updateUser({ password });
    setIsSubmitting(false);
    if (error) {
      setIsError(true);
      setMessage(error.message);
      return;
    }

    setIsError(false);
    setMessage("Senha atualizada com sucesso. Você já pode entrar na plataforma.");
    setPassword("");
    setConfirmation("");
  }

  return (
    <main className="grid min-h-screen place-items-center bg-surface-subtle px-5 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-soft-card">
        <div className="flex items-center justify-between gap-4">
          <p className="text-2xl font-black text-ink">Nova senha</p>
          <Link className="text-sm font-bold text-ink-soft hover:text-synapse-blue" href="/">
            Voltar ao início
          </Link>
        </div>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          Defina uma nova senha para recuperar o acesso à sua conta.
        </p>

        {isReady ? (
          <form className="mt-7 space-y-4" onSubmit={submit}>
            <label className="block text-sm font-bold text-ink" htmlFor="new-password">
              Nova senha
            </label>
            <input
              autoComplete="new-password"
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              id="new-password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
            <label className="block text-sm font-bold text-ink" htmlFor="confirm-password">
              Confirmar nova senha
            </label>
            <input
              autoComplete="new-password"
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              id="confirm-password"
              minLength={8}
              onChange={(event) => setConfirmation(event.target.value)}
              required
              type="password"
              value={confirmation}
            />
            <button
              className="w-full rounded-xl bg-synapse-blue px-4 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting ? "Atualizando..." : "Atualizar senha"}
            </button>
          </form>
        ) : null}

        {message ? (
          <p className={`mt-5 text-sm leading-6 ${isError ? "text-red-700" : "text-emerald-700"}`}>
            {message}
          </p>
        ) : null}

        <Link className="mt-6 inline-block text-sm font-bold text-synapse-blue hover:text-blue-800" href="/dashboard">
          Ir para entrar
        </Link>
      </section>
    </main>
  );
}
