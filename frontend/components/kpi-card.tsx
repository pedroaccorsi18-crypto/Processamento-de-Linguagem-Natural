type KpiCardProps = {
  label: string;
  value: string;
  description: string;
  tone?: "blue" | "green" | "amber" | "red";
};

const toneClass = {
  blue: "border-blue-200 bg-blue-50 text-blue-700",
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  red: "border-red-200 bg-red-50 text-red-700",
};

export function KpiCard({ label, value, description, tone = "blue" }: KpiCardProps) {
  return (
    <section className={`rounded-xl border p-5 shadow-soft-card ${toneClass[tone]}`}>
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-3 text-3xl font-black text-ink">{value}</p>
      <p className="mt-2 text-sm leading-6 text-ink-soft">{description}</p>
    </section>
  );
}
