export default function Loading() {
  return (
    <div className="page-shell" aria-live="polite" aria-busy="true">
      <span className="eyebrow">Loading</span>
      <div className="loading-line loading-line--wide" />
      <div className="loading-grid">
        {Array.from({ length: 4 }, (_, index) => <div className="loading-card" key={index} />)}
      </div>
      <span className="sr-only">Loading dashboard data</span>
    </div>
  );
}
