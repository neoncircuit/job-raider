/**
 * Badge shown when a generated document used a non-Ollama (cloud) provider.
 *
 * @returns A small "Cloud" label, or null when ``show`` is false.
 */
export function CloudBadge({ show }: { show: boolean }) {
  if (!show) {
    return null;
  }
  return (
    <span className="rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-warning">
      Cloud
    </span>
  );
}
