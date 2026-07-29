"use client";

import { FormEvent, useMemo, useState } from "react";
import { useSynapseSession } from "@/components/auth-gate";
import { askCopilot, type CopilotMessagePayload } from "@/services/api";

const quickPrompts = [
  "Qual é o melhor próximo passo para usar o Synapse?",
  "Explique como devo preparar documentos para IA.",
  "Como encontro riscos e evidências salvas?",
];

export function CopilotChat() {
  const { session } = useSynapseSession();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<CopilotMessagePayload[]>([
    {
      role: "assistant",
      content:
        "Olá! Sou o Copiloto Synapse. Posso ajudar você a navegar pelo produto, entender métricas e escolher a próxima análise.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleMessages = useMemo(() => messages.slice(-8), [messages]);

  async function sendMessage(prompt: string) {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || isLoading) {
      return;
    }

    const nextMessages: CopilotMessagePayload[] = [
      ...messages,
      { role: "user", content: cleanPrompt },
    ];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setIsLoading(true);

    try {
      const data = await askCopilot({
        accessToken: session.access_token,
        messages: nextMessages,
        currentArea: "Frontend Next.js",
        context:
          "Migração SaaS B2B do Synapse AI. O frontend Next.js ainda está em esqueleto e consome a API FastAPI.",
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", content: data.answer },
      ]);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "O Copiloto não conseguiu responder agora.";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "Não consegui completar a resposta neste momento. Verifique a conexão com a API e tente novamente.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <section className="fixed bottom-4 right-4 z-50 flex w-[calc(100vw-2rem)] max-w-md flex-col items-end gap-3 sm:bottom-5 sm:right-5 sm:w-[calc(100vw-2.5rem)]">
      {isOpen ? (
        <div className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <p className="text-sm font-black text-ink">Copiloto Synapse</p>
              <p className="text-xs text-ink-soft">Conectado à API FastAPI</p>
            </div>
            <button
              aria-label="Fechar Copiloto"
              className="rounded-lg px-3 py-2 text-sm font-bold text-ink-soft hover:bg-slate-100"
              onClick={() => setIsOpen(false)}
              type="button"
            >
              Fechar
            </button>
          </div>

          <div className="max-h-[42vh] space-y-3 overflow-y-auto bg-slate-50 px-4 py-4 sm:max-h-80 sm:px-5">
            {visibleMessages.map((message, index) => (
              <div
                data-role={message.role}
                data-testid="copilot-message"
                className={
                  message.role === "user"
                    ? "ml-8 rounded-2xl bg-synapse-blue px-4 py-3 text-sm leading-6 text-white"
                    : "mr-8 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-ink"
                }
                key={`${message.role}-${index}`}
              >
                {message.content}
              </div>
            ))}
            {isLoading ? (
              <p className="text-sm font-semibold text-ink-soft">Pensando...</p>
            ) : null}
            {error ? <p className="text-sm font-semibold text-red-700">{error}</p> : null}
          </div>

          <div className="flex flex-wrap gap-2 border-t border-slate-100 px-5 py-3">
            {quickPrompts.map((prompt) => (
              <button
                className="rounded-full border border-slate-200 px-3 py-2 text-xs font-bold text-ink-soft hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                disabled={isLoading}
                key={prompt}
                onClick={() => void sendMessage(prompt)}
                type="button"
              >
                {prompt}
              </button>
            ))}
          </div>

          <form className="flex gap-2 border-t border-slate-100 p-4" onSubmit={handleSubmit}>
            <input
              className="min-w-0 flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm text-ink outline-none transition focus:border-synapse-blue focus:ring-4 focus:ring-blue-100"
              onChange={(event) => setInput(event.target.value)}
              placeholder="Pergunte ao Copiloto"
              value={input}
            />
            <button
              className="rounded-xl bg-synapse-blue px-4 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading || !input.trim()}
              type="submit"
            >
              Enviar
            </button>
          </form>
        </div>
      ) : null}

      <button
        className="rounded-full bg-ink px-4 py-3 text-xs font-black text-white shadow-2xl transition hover:bg-slate-800 sm:px-5 sm:text-sm"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        Copiloto Synapse
      </button>
    </section>
  );
}
