import UploadForm from "../components/upload-form";
import ReviewPanel from "../components/review-panel";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Dashboard = {
  community_observations: number;
  workforce_observations: number;
  pending_alerts: number;
  recent_observations: Array<{id:string;domain:string;group_code:string;observed_date:string;indicator:string;value:number;unit:string}>;
};

type AlertItem = {id:string;domain:string;group_code:string;observed_date:string;indicator:string;value:number;unit:string;baseline:number|null;score:number|null;severity:string;status:string;explanation:string};

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API}${path}`, { cache: "no-store" });
    if (!response.ok) return fallback;
    return await response.json() as T;
  } catch { return fallback; }
}

export default async function Home() {
  const dashboard = await getJson<Dashboard>("/api/v1/dashboard", {
    community_observations:0, workforce_observations:0, pending_alerts:0, recent_observations:[]
  });
  const alerts = await getJson<{items:AlertItem[]}>("/api/v1/alerts?status=all", {items:[]});
  return <main>
    <header>
      <div><h1>PulseGrid Health</h1><p className="muted">Population &amp; Workforce Health Intelligence</p></div>
      <strong>Phase 1 · End-to-end MVP</strong>
    </header>
    <div className="notice">Synthetic demonstration environment. Signals are statistical candidates, not diagnoses or confirmed outbreaks. Human review is required.</div>
    <section className="grid">
      <article className="card"><div className="muted">Community observations</div><div className="metric">{dashboard.community_observations}</div></article>
      <article className="card"><div className="muted">Workforce observations</div><div className="metric">{dashboard.workforce_observations}</div></article>
      <article className="card"><div className="muted">Candidate alerts awaiting review</div><div className="metric">{dashboard.pending_alerts}</div></article>
    </section>
    <section className="card section"><h2>Data ingestion</h2><p className="muted">Upload only authorised, aggregate CSV data. Never upload identifiable patient or employee records.</p><UploadForm /></section>
    <section className="card section"><h2>Candidate alerts</h2>
      {alerts.items.length === 0 ? <p className="muted">No candidate alerts currently available. Import the synthetic datasets to populate this view.</p> :
      <ReviewPanel initialAlerts={alerts.items} />}
    </section>
    <section className="card section"><h2>Recent observations</h2>
      {dashboard.recent_observations.length === 0 ? <p className="muted">No data imported yet.</p> :
      <div className="table-wrap"><table><thead><tr><th>Date</th><th>Domain / group</th><th>Indicator</th><th>Value</th></tr></thead><tbody>
      {dashboard.recent_observations.map((item) => <tr key={item.id}><td>{item.observed_date}</td><td>{item.domain} / {item.group_code}</td><td>{item.indicator}</td><td>{item.value} {item.unit}</td></tr>)}
      </tbody></table></div>}
    </section>
  </main>;
}
