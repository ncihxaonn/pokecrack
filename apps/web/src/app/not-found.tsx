import Link from "next/link";

export default function NotFound() {
  return (
    <section className="page-shell state-page" aria-labelledby="not-found-title">
      <span className="status-code">404_NOT_FOUND</span>
      <h1 id="not-found-title">No published observation exists here.</h1>
      <p>The entity may be missing, unpublished, or outside the current aggregate snapshot.</p>
      <Link className="button" href="/">Return to dashboard</Link>
    </section>
  );
}
