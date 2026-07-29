type EmptyStateProps = {
  title: string;
  description: string;
  action?: string;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <section className="rounded-2xl border border-blue-100 bg-blue-50 p-6 text-blue-900">
      <p className="text-base font-bold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-blue-800">{description}</p>
      {action ? (
        <button className="mt-4 rounded-lg bg-synapse-blue px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-700">
          {action}
        </button>
      ) : null}
    </section>
  );
}
