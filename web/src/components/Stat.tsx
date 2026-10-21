export function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="border border-border bg-surface px-5 py-4">
      <div className="text-sm font-bold uppercase tracking-wide text-muted">
        {label}
      </div>
      <div className="mt-1 text-3xl font-extrabold tabular-nums">{value}</div>
      {note ? <div className="mt-1 text-sm text-muted">{note}</div> : null}
    </div>
  );
}
