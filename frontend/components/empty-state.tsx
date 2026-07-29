import Link from "next/link";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: string;
  actionHref?: string;
};

export function EmptyState({
  title,
  description,
  action,
  actionHref,
}: EmptyStateProps) {
  return (
    <section className="rounded-2xl border border-blue-100 bg-blue-50 p-6 text-blue-900">
      <p className="text-base font-bold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-blue-800">{description}</p>
      {action && actionHref ? (
        <Link
          className="mt-4 inline-flex rounded-lg bg-synapse-blue px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-700"
          href={actionHref}
        >
          {action}
        </Link>
      ) : null}
    </section>
  );
}
