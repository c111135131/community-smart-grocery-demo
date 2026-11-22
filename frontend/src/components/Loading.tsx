/** Consistent loading indicator (announced to screen readers via role="status"). */
export default function Loading({ label = "載入中…" }: { label?: string }) {
  return (
    <p role="status" className="loading">
      <span className="spinner" aria-hidden="true" />
      {label}
    </p>
  );
}
