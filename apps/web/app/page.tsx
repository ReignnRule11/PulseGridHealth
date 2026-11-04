const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default async function Home() {
  let apiStatus = "Not checked";
  try {
    const response = await fetch(`${API}/health`, { cache: "no-store" });
    apiStatus = response.ok ? "API reachable" : "API returned an error";
  } catch {
    apiStatus = "API not reachable";
  }

  return (
    <main>
      <header>
        <div>
          <h1>PulseGrid Health</h1>
          <p className="muted">Population &amp; Workforce Health Intelligence</p>
        </div>
        <strong>Phase 1 · Foundation</strong>
      </header>
      <div className="notice">
        Synthetic demonstration environment. Statistical signals require human review;
        this product does not diagnose disease or declare outbreaks.
      </div>
      <section className="grid">
        <article className="card"><div className="muted">Community intelligence</div><div className="metric">—</div><p className="muted">Connect data ingestion to populate this view.</p></article>
        <article className="card"><div className="muted">Workforce intelligence</div><div className="metric">—</div><p className="muted">Aggregate workforce signals only.</p></article>
        <article className="card"><div className="muted">Candidate alerts</div><div className="metric">—</div><p className="muted">No alert is a diagnosis or confirmed event.</p></article>
        <article className="card"><div className="muted">Backend status</div><div className="metric" style={{fontSize:20}}>{apiStatus}</div><p className="muted">Health endpoint: {API}/health</p></article>
      </section>
    </main>
  );
}
