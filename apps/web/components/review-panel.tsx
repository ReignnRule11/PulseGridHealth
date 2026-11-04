"use client";

import { useState } from "react";

type AlertItem = { id:string; domain:string; group_code:string; observed_date:string; indicator:string; value:number; unit:string; baseline:number|null; score:number|null; severity:string; status:string; explanation:string };
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ReviewPanel({ initialAlerts }: { initialAlerts: AlertItem[] }) {
  const [alerts, setAlerts] = useState(initialAlerts);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [findings, setFindings] = useState<Record<string,string>>({});
  const [rationales, setRationales] = useState<Record<string,string>>({});
  const [actions, setActions] = useState<Record<string,string>>({});
  async function post(id:string, endpoint:string, body?:object) {
    setBusy(id); setMessage("");
    try {
      const response = await fetch(`${API}/api/v1/alerts/${id}/${endpoint}`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body: body ? JSON.stringify(body) : undefined
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Request failed");
      setAlerts(current => current.map(a => a.id === id ? {...a, status:data.status ?? (endpoint === "resolve" ? "resolved" : a.status)} : a));
      setMessage("Review update saved.");
      if (endpoint === "acknowledge" || endpoint === "investigation" || endpoint === "resolve") {
        const refreshed = await fetch(`${API}/api/v1/alerts?status=${endpoint === "resolve" ? "resolved" : "pending_review"}`, {cache:"no-store"});
        if (refreshed.ok && endpoint !== "resolve") {
          const result = await refreshed.json();
          setAlerts(current => [...current.filter(a => a.id !== id), ...(result.items as AlertItem[]).filter(a => !current.some(c => c.id === a.id))]);
        }
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Request failed"); }
    finally { setBusy(null); }
  }
  if (!alerts.length) return <p className="muted">No candidate alerts currently available. Import synthetic datasets to populate this view.</p>;
  return <div className="review-list">
    {message && <p className="review-message" role="status">{message}</p>}
    {alerts.map(alert => <article className="review-card" key={alert.id}>
      <div className="review-heading"><strong>{alert.domain} / {alert.group_code}</strong><span className="pending">{alert.severity} · {alert.status.replaceAll("_"," ")}</span></div>
      <p>{alert.indicator} · {alert.observed_date} · {alert.value} {alert.unit}</p>
      <p className="muted">{alert.explanation}</p>
      {alert.status === "pending_review" && <button disabled={!!busy} onClick={() => post(alert.id,"acknowledge")}>Acknowledge</button>}
      {alert.status === "acknowledged" && <button disabled={!!busy} onClick={() => post(alert.id,"investigation")}>Start investigation</button>}
      {alert.status === "investigating" && <div className="review-form">
        <label>Investigation findings<textarea value={findings[alert.id] ?? ""} onChange={e=>setFindings(v=>({...v,[alert.id]:e.target.value}))} placeholder="Record evidence reviewed and limitations" /></label>
        <button disabled={!!busy || (findings[alert.id] ?? "").trim().length < 10} onClick={() => post(alert.id,"findings",{findings:findings[alert.id],disposition:"monitor"})}>Save findings</button>
        <label>Response action<textarea value={actions[alert.id] ?? ""} onChange={e=>setActions(v=>({...v,[alert.id]:e.target.value}))} placeholder="Describe a proportionate follow-up action" /></label>
        <button disabled={!!busy || (actions[alert.id] ?? "").trim().length < 10} onClick={() => post(alert.id,"actions",{action_type:"follow_up",description:actions[alert.id],owner_role:"review team"})}>Add response action</button>
        <label>Resolution rationale<textarea value={rationales[alert.id] ?? ""} onChange={e=>setRationales(v=>({...v,[alert.id]:e.target.value}))} placeholder="Explain the evidence-based disposition" /></label>
        <button disabled={!!busy || (rationales[alert.id] ?? "").trim().length < 10} onClick={() => post(alert.id,"resolve",{rationale:rationales[alert.id],disposition:"monitoring"})}>Close review</button>
      </div>}
      {busy === alert.id && <small>Saving…</small>}
    </article>)}
  </div>;
}
