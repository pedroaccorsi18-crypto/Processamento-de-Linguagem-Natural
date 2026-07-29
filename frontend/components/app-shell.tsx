import Link from "next/link";
import type { ReactNode } from "react";
import { CopilotChat } from "@/components/copilot-chat";

const navigationItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Base documental" },
  { href: "/studio", label: "Estúdio de IA" },
  { href: "/insights", label: "Insights" },
  { href: "/audit", label: "Evidências" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-subtle">
      <aside className="fixed inset-y-0 left-0 hidden w-72 flex-col border-r border-white/10 bg-ink px-6 py-8 text-white lg:flex">
        <div>
          <p className="text-2xl font-bold tracking-tight">Synapse AI</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Inteligência organizacional com rastreabilidade.
          </p>
        </div>
        <nav className="mt-10 flex flex-col gap-2">
          {navigationItems.map((item) => (
            <Link
              className="rounded-lg px-4 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/10 hover:text-white"
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
          <p className="font-semibold text-white">Copiloto ativo</p>
          <p className="mt-2">Use o assistente para orientar a próxima decisão.</p>
        </div>
      </aside>

      <main className="lg:pl-72">
        <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-8 px-5 py-8 sm:px-8 lg:px-12">
          {children}
        </div>
      </main>

      <CopilotChat />
    </div>
  );
}
