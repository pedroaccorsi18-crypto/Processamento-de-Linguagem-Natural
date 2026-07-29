import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  description: string;
  children?: ReactNode;
};

export function SectionCard({ title, description, children }: SectionCardProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft-card">
      <div>
        <h2 className="text-xl font-black tracking-tight text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-ink-soft">{description}</p>
      </div>
      {children ? <div className="mt-6">{children}</div> : null}
    </section>
  );
}
