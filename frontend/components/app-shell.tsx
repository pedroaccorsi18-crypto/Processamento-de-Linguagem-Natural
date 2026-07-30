"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AuthGate, useSynapseSession } from "@/components/auth-gate";
import { CopilotChat } from "@/components/copilot-chat";

const navigationItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Base documental" },
  { href: "/studio", label: "Diagnóstico organizacional" },
];

const secondaryNavigationItems = [
  { href: "/insights", label: "Insights" },
  { href: "/audit", label: "Evidências" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (
    pathname === "/" ||
    pathname === "/about" ||
    pathname === "/privacy" ||
    pathname === "/terms" ||
    pathname === "/reset-password"
  ) {
    return <div className="min-h-screen bg-surface-subtle">{children}</div>;
  }
  return (
    <AuthGate>
      <AuthenticatedAppShell>{children}</AuthenticatedAppShell>
    </AuthGate>
  );
}

function AuthenticatedAppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { signOut, user } = useSynapseSession();

  return (
    <div className="min-h-screen bg-surface-subtle">
      <aside className="fixed inset-y-0 left-0 hidden w-72 flex-col border-r border-white/10 bg-ink px-6 py-8 text-white lg:flex">
        <div>
          <div className="flex items-center gap-3">
            <Image alt="" height={34} priority src="/brand/synapse-mark.png" width={36} />
            <p className="text-2xl font-bold tracking-tight">Synapse AI</p>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Inteligência organizacional com rastreabilidade.
          </p>
          <p className="mt-5 truncate text-xs text-slate-400">Conta: {user.email}</p>
          <button
            className="mt-3 rounded-lg bg-white/10 px-3 py-2 text-xs font-bold text-white transition hover:bg-white/20"
            onClick={() => void signOut()}
            type="button"
          >
            Sair
          </button>
        </div>
        <nav className="mt-10 flex flex-col gap-2">
          {navigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "rounded-lg bg-white px-4 py-3 text-sm font-black text-ink"
                    : "rounded-lg px-4 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/10 hover:text-white"
                }
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
          <p className="mt-5 px-4 text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
            Inteligência e rastreabilidade
          </p>
          {secondaryNavigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "rounded-lg bg-white px-4 py-3 text-sm font-black text-ink"
                    : "rounded-lg px-4 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                }
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
          <p className="font-semibold text-white">Copiloto ativo</p>
          <p className="mt-2">Use o assistente para orientar a próxima decisão.</p>
        </div>
      </aside>

      <header className="sticky top-0 z-40 border-b border-slate-200 bg-ink px-4 py-4 text-white shadow-lg shadow-slate-950/5 lg:hidden">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Image alt="" height={24} priority src="/brand/synapse-mark.png" width={26} />
              <p className="text-lg font-black tracking-tight">Synapse AI</p>
            </div>
            <p className="mt-1 truncate text-xs text-slate-300">Conta: {user.email}</p>
          </div>
          <button
            className="shrink-0 rounded-lg bg-white/10 px-3 py-2 text-xs font-bold text-white transition hover:bg-white/20"
            onClick={() => void signOut()}
            type="button"
          >
            Sair
          </button>
        </div>
        <nav className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {navigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "whitespace-nowrap rounded-lg bg-white px-3 py-2 text-xs font-black text-ink"
                    : "whitespace-nowrap rounded-lg bg-white/10 px-3 py-2 text-xs font-bold text-slate-100"
                }
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
          {secondaryNavigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "whitespace-nowrap rounded-lg bg-white px-3 py-2 text-xs font-black text-ink"
                    : "whitespace-nowrap rounded-lg bg-white/10 px-3 py-2 text-xs font-bold text-slate-300"
                }
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <main className="lg:pl-72">
        <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-7 px-4 pb-28 pt-7 sm:px-8 lg:gap-8 lg:px-12 lg:pb-8 lg:pt-8">
          {children}
        </div>
      </main>

      <CopilotChat />
    </div>
  );
}
