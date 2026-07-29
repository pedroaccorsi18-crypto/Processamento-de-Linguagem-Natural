"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";

import {
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase";

type AuthContextValue = {
  session: Session;
  user: User;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useSynapseSession(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("A sessão do Synapse não está disponível.");
  }
  return value;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      setIsLoading(false);
      return;
    }

    const client = getSupabaseBrowserClient();
    void client.auth
      .getSession()
      .then(async ({ data }) => {
        const shouldRefresh =
          data.session?.expires_at !== undefined &&
          data.session.expires_at * 1_000 <= Date.now() + 60_000;
        if (shouldRefresh) {
          const { data: refreshed, error } = await client.auth.refreshSession();
          setSession(error ? null : refreshed.session);
        } else {
          setSession(data.session);
        }
      })
      .catch(() => setSession(null))
      .finally(() => setIsLoading(false));
    const { data } = client.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIsLoading(false);
    });

    return () => data.subscription.unsubscribe();
  }, []);

  if (!isSupabaseConfigured()) {
    return <ConfigurationRequired />;
  }
  if (isLoading) {
    return <LoadingAccess />;
  }
  if (session === null) {
    return <SignInCard />;
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session.user,
        signOut: async () => {
          await getSupabaseBrowserClient().auth.signOut();
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function LoadingAccess() {
  return (
    <main className="grid min-h-screen place-items-center bg-surface-subtle px-5">
      <p className="text-sm font-semibold text-ink-soft">Confirmando acesso seguro...</p>
    </main>
  );
}

function ConfigurationRequired() {
  return (
    <main className="grid min-h-screen place-items-center bg-surface-subtle px-5">
      <section className="max-w-lg rounded-2xl border border-amber-200 bg-amber-50 p-7 text-amber-950 shadow-soft-card">
        <p className="text-lg font-black">A plataforma está sendo configurada.</p>
        <p className="mt-2 text-sm leading-6">
          A autenticação segura ainda não recebeu as configurações públicas do Supabase.
          Tente novamente em alguns instantes.
        </p>
      </section>
    </main>
  );
}

function SignInCard() {
  const [mode, setMode] = useState<"signIn" | "signUp">("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    const client = getSupabaseBrowserClient();
    const result =
      mode === "signIn"
        ? await client.auth.signInWithPassword({ email, password })
        : await client.auth.signUp({ email, password });

    setIsSubmitting(false);
    if (result.error) {
      setIsError(true);
      setMessage(result.error.message);
      return;
    }

    setIsError(false);
    setMessage(
      mode === "signUp"
        ? "Conta criada. Confirme seu e-mail para concluir o acesso."
        : "Acesso confirmado.",
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-surface-subtle px-5 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-soft-card">
        <p className="text-2xl font-black text-ink">Synapse AI</p>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          Entre para acessar sua base documental privada e as análises da sua conta.
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-bold text-ink" htmlFor="synapse-email">
            E-mail
          </label>
          <input
            autoComplete="email"
            className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
            id="synapse-email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
          <label className="block text-sm font-bold text-ink" htmlFor="synapse-password">
            Senha
          </label>
          <input
            autoComplete={mode === "signIn" ? "current-password" : "new-password"}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
            id="synapse-password"
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {message ? (
            <p className={isError ? "text-sm text-red-700" : "text-sm text-emerald-700"}>
              {message}
            </p>
          ) : null}
          <button
            className="w-full rounded-xl bg-synapse-blue px-4 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Aguarde..." : mode === "signIn" ? "Entrar" : "Criar conta"}
          </button>
        </form>
        <button
          className="mt-5 text-sm font-bold text-synapse-blue hover:text-blue-800"
          onClick={() => {
            setMode((current) => (current === "signIn" ? "signUp" : "signIn"));
            setMessage(null);
          }}
          type="button"
        >
          {mode === "signIn" ? "Criar uma conta" : "Já tenho uma conta"}
        </button>
      </section>
    </main>
  );
}
