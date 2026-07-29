type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
};

export function PageHeader({ eyebrow, title, description }: PageHeaderProps) {
  return (
    <header className="max-w-4xl">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-synapse-blue">
        {eyebrow}
      </p>
      <h1 className="mt-4 text-4xl font-black tracking-tight text-ink sm:text-5xl">
        {title}
      </h1>
      <p className="mt-4 text-lg leading-8 text-ink-soft">{description}</p>
    </header>
  );
}
