
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = "";

type Org = {
  id: string;
  name: string;
  organization_type: string;
  role: "org_admin" | "analyst" | "reviewer" | "viewer";
};

type Me = {
  id: string;
  email: string;
  full_name: string;
  organizations: Org[];
  session_expires_at: string;
};

type AlertItem = {
  id: string;
  domain: string;
  group_code: string;
  observed_date: string;
  indicator: string;
  value: number;
  unit: string;
  baseline: number | null;
  score: number | null;
  severity: string;
  status: string;
  explanation: string;
};

type Dashboard = {
  community_observations: number;
  workforce_observations: number;
  pending_alerts: number;
  recent_observations: Array<{
    id: string;
    domain: string;
    group_code: string;
    observed_date: string;
    indicator: string;
    value: number;
    unit: string;
  }>;
};

type AiInterpretation = {
  hypothesis: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  confidence_label: "low" | "moderate" | "high";
};

type AiExplanation = {
  summary: string;
  possible_interpretations: AiInterpretation[];
  data_quality_caveats: string[];
  review_questions: string[];
  recommended_review_steps: string[];
  limitations: string[];
  requires_human_review: true;
  classification: "candidate_signal";
  evidence_ids: string[];
};

type AiInsight = {
  explanation: AiExplanation;
  quantitative_evidence: {
    current_observation: {
      value: number;
      unit: string;
      date: string;
    };
    historical_baseline: {
      value: number | null;
      unit: string;
      method: string;
      version: string;
    };
    detector: {
      robust_score: number | null;
      threshold: number;
      history_count: number;
      reason: string;
    };
    history: Array<Record<string, unknown>>;
    workforce_cohort_eligible: boolean;
  };
  provider: string;
  model: string;
  schema_version: string;
  notice: string;
};

const emptyDashboard: Dashboard = {
  community_observations: 0,
  workforce_observations: 0,
  pending_alerts: 0,
  recent_observations: [],
};

const roleNames: Record<string, string> = {
  org_admin: "Organization administrator",
  analyst: "Analyst",
  reviewer: "Reviewer",
  viewer: "Read-only viewer",
};

export default function Workspace() {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const [identityLoading, setIdentityLoading] = useState(true);
  const [csrf, setCsrf] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [orgId, setOrgId] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard>(emptyDashboard);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [inviteToken, setInviteToken] = useState("");
  const [inviteInput, setInviteInput] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [invitePassword, setInvitePassword] = useState("");
  const [csv, setCsv] = useState<File | null>(null);
  const [findings, setFindings] = useState<Record<string, string>>({});
  const [actions, setActions] = useState<Record<string, string>>({});
  const [rationales, setRationales] = useState<Record<string, string>>({});
  const [histories, setHistories] = useState<Record<string, string>>({});
  const [historyBusy, setHistoryBusy] = useState("");
  const [aiInsights, setAiInsights] = useState<Record<string, AiInsight>>({});
  const [aiBusy, setAiBusy] = useState("");
  const [profileName, setProfileName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [emailCurrentPassword, setEmailCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [emailToken, setEmailToken] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgType, setOrgType] = useState("");
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetPassword, setResetPassword] = useState("");

  const requestCsrf = useCallback(async () => {
    const r = await fetch(`${API}/api/v1/auth/csrf`, {
      credentials: "include",
      cache: "no-store",
    });
    const d = await r.json();

    if (!r.ok) {
      throw new Error(d.detail ?? "Unable to establish CSRF protection");
    }

    setCsrf(d.csrf_token);
    return d.csrf_token as string;
  }, []);

  const loadIdentity = useCallback(async () => {
    const r = await fetch(`${API}/api/v1/auth/me`, {
      credentials: "include",
      cache: "no-store",
    });

    if (!r.ok) {
      setMe(null);
      setOrgId("");
      setIdentityLoading(false);
      return;
    }

    const d = (await r.json()) as Me;
    setMe(d);
    setOrgId((current) =>
      d.organizations.some((o) => o.id === current)
        ? current
        : (d.organizations[0]?.id ?? "")
    );
    setIdentityLoading(false);
  }, []);

  const apiFetch = useCallback(
    async (path: string, init: RequestInit = {}) => {
      if (!orgId) {
        throw new Error("Select an organization first.");
      }

      const headers = new Headers(init.headers);
      headers.set("X-Organization-ID", orgId);

      if (
        init.method &&
        init.method.toUpperCase() !== "GET" &&
        init.method.toUpperCase() !== "HEAD"
      ) {
        if (!csrf) {
          throw new Error(
            "Security token unavailable. Refresh the workspace and sign in again."
          );
        }

        headers.set("X-CSRF-Token", csrf);
      }

      return fetch(`${API}${path}`, {
        ...init,
        headers,
        credentials: "include",
        cache: "no-store",
      });
    },
    [orgId, csrf]
  );

  const loadWorkspace = useCallback(async () => {
    if (!me || !orgId) return;

    try {
      const [d, a] = await Promise.all([
        apiFetch("/api/v1/dashboard"),
        apiFetch("/api/v1/alerts?status=all"),
      ]);

      if (d.status === 401 || a.status === 401) {
        setMe(null);
        setMessage("Your session has expired. Please sign in again.");
        return;
      }

      if (!d.ok || !a.ok) {
        throw new Error("Unable to load this organization's workspace.");
      }

      setDashboard((await d.json()) as Dashboard);
      const alertData = await a.json();
      setAlerts((alertData.items ?? []) as AlertItem[]);
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Workspace load failed"
      );
    }
  }, [me, orgId, apiFetch]);

  useEffect(() => {
    requestCsrf()
      .then(loadIdentity)
      .catch((e) => {
        setIdentityLoading(false);
        setMessage(e instanceof Error ? e.message : "Connection failed");
      });
  }, [requestCsrf, loadIdentity]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") ?? params.get("invite");
    if (!token) return;
    if (pathname === "/invite") setInviteInput(token);
    if (pathname === "/reset-password") setResetToken(token);
    if (pathname === "/verify-email-change") setEmailToken(token);
    window.history.replaceState({}, "", window.location.pathname);
  }, [pathname]);

  useEffect(() => {
    if (identityLoading) return;
    const protectedPaths = ["/workspace", "/settings", "/organization/access", "/verify-email-change"];
    if (protectedPaths.includes(pathname) && !me) router.replace("/login");
    if (me && pathname === "/login") router.replace("/workspace");
  }, [identityLoading, me, pathname, router]);

  useEffect(() => {
    if (me && orgId) loadWorkspace();
  }, [me, orgId, loadWorkspace]);

  const currentOrg = useMemo(
    () => me?.organizations.find((o) => o.id === orgId) ?? null,
    [me, orgId]
  );

  const canIngest =
    currentOrg?.role === "org_admin" || currentOrg?.role === "analyst";

  const canReview =
    currentOrg?.role === "org_admin" || currentOrg?.role === "reviewer";

  async function saveProfile(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const r = await fetch(`${API}/api/v1/auth/profile`, { method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ full_name: profileName.trim() }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Profile update failed");
      await loadIdentity(); setMessage("Your name has been updated.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Profile update failed"); }
    finally { setBusy(false); }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const r = await fetch(`${API}/api/v1/auth/password/change`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Password change failed");
      setCurrentPassword(""); setNewPassword(""); setMessage("Password changed. Other active sessions were revoked.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Password change failed"); }
    finally { setBusy(false); }
  }

  async function requestEmailChange(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const r = await fetch(`${API}/api/v1/auth/email/change/request`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ new_email: newEmail, current_password: emailCurrentPassword }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Email verification request failed");
      setMessage("Verification sent to the new address. Enter the one-time token below.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Email change failed"); }
    finally { setBusy(false); }
  }

  async function confirmEmailChange(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const r = await fetch(`${API}/api/v1/auth/email/change/confirm`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ token: emailToken }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Email confirmation failed");
      setEmailToken(""); await loadIdentity(); setMessage("Email address changed successfully.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Email confirmation failed"); }
    finally { setBusy(false); }
  }

  async function saveOrganization(event: FormEvent) {
    event.preventDefault(); if (!orgId) return; setBusy(true); setMessage("");
    try {
      const r = await apiFetch(`/api/v1/auth/organizations/${orgId}`, { method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: orgName.trim(), organization_type: orgType.trim() }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Organization update failed");
      await loadIdentity(); setMessage("Organization details updated.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Organization update failed"); }
    finally { setBusy(false); }
  }

  async function requestPasswordReset(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const token = csrf || await requestCsrf();
      const r = await fetch(`${API}/api/v1/auth/password/forgot`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ email: forgotEmail }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Password reset request failed");
      setMessage("If that account exists, a password-reset email has been sent.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Password reset request failed"); }
    finally { setBusy(false); }
  }

  async function completePasswordReset(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const token = csrf || await requestCsrf();
      const r = await fetch(`${API}/api/v1/auth/password/reset`, { method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ token: resetToken, new_password: resetPassword }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "Password reset failed");
      setResetToken(""); setResetPassword(""); setMessage("Password reset. You can now sign in.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Password reset failed"); }
    finally { setBusy(false); }
  }

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");

    try {
      const token = csrf || (await requestCsrf());

      const r = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token,
        },
        body: JSON.stringify({ email, password }),
      });

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Sign-in failed");
      }

      setPassword("");
      await requestCsrf();
      await loadIdentity();
      router.replace("/workspace");

      setMessage(
        "Signed in. Choose an authorized organization if you belong to more than one."
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);

    try {
      const r = await fetch(`${API}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });

      if (!r.ok) {
        const d = await r.json();
        throw new Error(d.detail ?? "Sign-out failed");
      }

      setMe(null);
      setOrgId("");
      setAlerts([]);
      setDashboard(emptyDashboard);
      setCsrf("");

      await requestCsrf();
      router.replace("/login");
      setMessage("You have signed out.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Sign-out failed");
    } finally {
      setBusy(false);
    }
  }

  async function acceptInvite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");

    try {
      const token = csrf || (await requestCsrf());

      const r = await fetch(
        `${API}/api/v1/auth/invitations/accept`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": token,
          },
          body: JSON.stringify({
            token: inviteInput.trim(),
            full_name: inviteName,
            password: invitePassword,
          }),
        }
      );

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Invitation acceptance failed");
      }

      setInviteInput("");
      setInvitePassword("");
      setMessage(
        "Invitation accepted. Sign in using the invited email address."
      );
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Invitation acceptance failed"
      );
    } finally {
      setBusy(false);
    }
  }

  async function createInvite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setInviteToken("");

    try {
      const r = await apiFetch(
        `/api/v1/auth/organizations/${orgId}/invitations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: inviteEmail,
            role: inviteRole,
          }),
        }
      );

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Invitation failed");
      }

      setInviteToken(d.invitation_token);
      setInviteEmail("");

      setMessage(
        "Invitation created. Deliver the token to the intended recipient through a secure channel; email delivery is not configured."
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Invitation failed");
    } finally {
      setBusy(false);
    }
  }

  async function importCsv(event: FormEvent) {
    event.preventDefault();

    if (!csv) return;

    setBusy(true);
    setMessage("");

    try {
      const body = new FormData();
      body.append("file", csv);

      const r = await apiFetch("/api/v1/observations/import", {
        method: "POST",
        body,
      });

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Import failed");
      }

      setMessage(
        `Imported ${d.accepted}; duplicates ${d.duplicates}; rejected ${d.rejected}; candidate alerts created ${d.alerts_created}.`
      );

      setCsv(null);
      await loadWorkspace();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function review(
    alert: AlertItem,
    endpoint: string,
    body?: object
  ) {
    setBusy(true);
    setMessage("");

    try {
      const r = await apiFetch(
        `/api/v1/alerts/${alert.id}/${endpoint}`,
        {
          method: "POST",
          headers: body
            ? { "Content-Type": "application/json" }
            : undefined,
          body: body ? JSON.stringify(body) : undefined,
        }
      );

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Review action failed");
      }

      setMessage("Review action saved.");
      await loadWorkspace();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Review action failed");
    } finally {
      setBusy(false);
    }
  }

  async function generateAiExplanation(alert: AlertItem) {
    setAiBusy(alert.id);
    setMessage("");

    try {
      const r = await apiFetch(
        `/api/v1/ai/alerts/${alert.id}/explanation`,
        { method: "POST" }
      );

      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "AI explanation unavailable");
      }

      setAiInsights((v) => ({
        ...v,
        [alert.id]: d as AiInsight,
      }));
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "AI explanation unavailable"
      );
    } finally {
      setAiBusy("");
    }
  }

  async function viewHistory(id: string) {
    setHistoryBusy(id);

    try {
      const r = await apiFetch(`/api/v1/alerts/${id}/history`);
      const d = await r.json();

      if (!r.ok) {
        throw new Error(d.detail ?? "Unable to load review history");
      }

      setHistories((v) => ({
        ...v,
        [id]: JSON.stringify(d, null, 2),
      }));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "History unavailable");
    } finally {
      setHistoryBusy("");
    }
  }

  if (pathname === "/") {
    return (
      <main className="landing-shell">
        <header className="landing-header">
          <Link href="/" className="landing-brand"><span className="brand-mark">P</span><span>PulseGrid Health</span></Link>
          <nav aria-label="Main navigation">
            <a href="#platform">Platform</a>
            <a href="#how-it-works">How it works</a>
            <Link className="button-secondary" href={me ? "/workspace" : "/login"}>{me ? "Open workspace" : "Sign in"}</Link>
          </nav>
        </header>
        <section className="landing-hero">
          <div className="landing-copy">
            <p className="eyebrow">POPULATION &amp; WORKFORCE HEALTH INTELLIGENCE</p>
            <h1>See emerging health signals. Make better-informed decisions.</h1>
            <p className="landing-lede">PulseGrid Health helps authorized public-health and workforce teams organize aggregate observations, identify unusual patterns, and coordinate evidence-led human review.</p>
            <div className="landing-actions">
              <Link className="landing-primary" href={me ? "/workspace" : "/login"}>{me ? "Go to workspace" : "Sign in to PulseGrid"} <span aria-hidden="true">→</span></Link>
              <a className="landing-secondary" href="#platform">Explore the platform</a>
            </div>
            <p className="landing-footnote">Access is organization-based. New users join through an invitation from an organization administrator.</p>
          </div>
          <div className="landing-visual" aria-label="Illustration of connected health intelligence signals">
            <div className="visual-orbit orbit-one"></div><div className="visual-orbit orbit-two"></div>
            <div className="visual-core"><span className="visual-pulse"></span><strong>PulseGrid</strong><small>HEALTH INTELLIGENCE</small></div>
            <div className="visual-node node-one"><span>Community</span><strong>Signals</strong></div>
            <div className="visual-node node-two"><span>Workforce</span><strong>Trends</strong></div>
            <div className="visual-node node-three"><span>Human</span><strong>Review</strong></div>
          </div>
        </section>
        <section className="landing-trust">
          <span>AGGREGATE DATA</span><span>EXPLAINABLE SIGNALS</span><span>HUMAN-LED REVIEW</span><span>ORGANIZATION ACCESS</span>
        </section>
        <section id="platform" className="landing-section">
          <p className="eyebrow">THE PLATFORM</p>
          <h2>From observations to informed action</h2>
          <p className="muted landing-section-intro">A structured workspace for teams that need to review population and workforce health indicators responsibly.</p>
          <div className="landing-features">
            <article><span className="feature-number">01</span><h3>Bring data together</h3><p>Import authorized aggregate observations and view recent data in one organization workspace.</p></article>
            <article><span className="feature-number">02</span><h3>Identify candidate signals</h3><p>Review statistical deviations with quantitative context, baselines, and data-quality caveats.</p></article>
            <article><span className="feature-number">03</span><h3>Coordinate human review</h3><p>Assign review responsibilities, record findings, and retain an auditable history of decisions.</p></article>
          </div>
        </section>
        <section id="how-it-works" className="landing-bottom">
          <div><p className="eyebrow">BUILT FOR RESPONSIBLE USE</p><h2>Decision support, with people in control.</h2><p>Signals are statistical candidates—not diagnoses, confirmed outbreaks, or clinical predictions. Human review is required. PulseGrid Health is designed for aggregate data; do not upload identifiable patient or employee records.</p></div>
          <Link className="landing-primary" href={me ? "/workspace" : "/login"}>{me ? "Open your workspace" : "Access your workspace"} <span aria-hidden="true">→</span></Link>
        </section>
        <footer className="landing-footer"><span>© {new Date().getFullYear()} PulseGrid Health</span><span>Population &amp; workforce health intelligence</span><Link href="/invite">Have an invitation?</Link></footer>
      </main>
    );
  }

  if (pathname === "/login") {
    return (
      <main className="auth-shell auth-single">
        <section className="auth-brand">
          <Link href="/" className="back-link">← PulseGrid Health</Link>
          <p className="eyebrow">SECURE ORGANIZATION ACCESS</p>
          <h1>Welcome back</h1>
          <p className="muted">Sign in to continue to your organization health intelligence workspace.</p>
        </section>
        <section className="card auth-card">
          <h2>Sign in</h2>
          <form className="stack" onSubmit={signIn}>
            <label>Email<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
            <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            <button disabled={busy}>{busy ? "Signing in…" : "Sign in securely"}</button>
          </form>
          <div className="auth-links"><Link href="/forgot-password">Forgot your password?</Link><Link href="/invite">Accept an invitation</Link></div>
          {message && <p className="status-message" role="status">{message}</p>}
        </section>
        <p className="footnote auth-footnote">No public self-registration. Access is provided by an organization administrator.</p>
      </main>
    );
  }

  if (pathname === "/forgot-password") {
    return (
      <main className="auth-shell auth-single">
        <section className="auth-brand"><Link href="/login" className="back-link">← Back to sign in</Link><p className="eyebrow">ACCOUNT RECOVERY</p><h1>Reset your password</h1><p className="muted">Enter the email address associated with your PulseGrid Health account. If the account exists, we will send a one-time reset token.</p></section>
        <section className="card auth-card">
          <h2>Request a reset token</h2>
          <form className="stack" onSubmit={requestPasswordReset}>
            <label>Email<input type="email" autoComplete="email" required value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} /></label>
            <button disabled={busy}>{busy ? "Sending…" : "Send reset instructions"}</button>
          </form>
          {message && <p className="status-message" role="status">{message}</p>}
          <div className="auth-links"><Link href="/reset-password">I already have a reset token</Link></div>
        </section>
      </main>
    );
  }

  if (pathname === "/reset-password") {
    return (
      <main className="auth-shell auth-single">
        <section className="auth-brand"><Link href="/login" className="back-link">← Back to sign in</Link><p className="eyebrow">ACCOUNT RECOVERY</p><h1>Choose a new password</h1><p className="muted">Paste the one-time token from your password-reset email and choose a new password.</p></section>
        <section className="card auth-card">
          <h2>Complete password reset</h2>
          <form className="stack" onSubmit={completePasswordReset}>
            <label>Reset token<input required value={resetToken} onChange={(e) => setResetToken(e.target.value)} /></label>
            <label>New password<input type="password" minLength={12} autoComplete="new-password" required value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} /></label>
            <button disabled={busy}>{busy ? "Resetting…" : "Reset password"}</button>
          </form>
          {message && <p className="status-message" role="status">{message}</p>}
        </section>
      </main>
    );
  }

  if (pathname === "/invite") {
    return (
      <main className="auth-shell auth-single">
        <section className="auth-brand"><Link href="/login" className="back-link">← Back to sign in</Link><p className="eyebrow">ORGANIZATION INVITATION</p><h1>Join your organization</h1><p className="muted">Use the single-use invitation token provided by your PulseGrid Health organization administrator.</p></section>
        <section className="card auth-card">
          <h2>Accept invitation</h2>
          <form className="stack" onSubmit={acceptInvite}>
            <label>Invitation token<input required value={inviteInput} onChange={(e) => setInviteInput(e.target.value)} /></label>
            <label>Full name<input required minLength={2} autoComplete="name" value={inviteName} onChange={(e) => setInviteName(e.target.value)} /></label>
            <label>Create password<input type="password" required minLength={12} autoComplete="new-password" value={invitePassword} onChange={(e) => setInvitePassword(e.target.value)} /></label>
            <button disabled={busy}>{busy ? "Accepting…" : "Accept invitation"}</button>
          </form>
          {message && <p className="status-message" role="status">{message}</p>}
        </section>
      </main>
    );
  }

  if (pathname === "/verify-email-change") {
    if (identityLoading || !me) return <main className="auth-shell"><p className="muted">Checking your account session…</p></main>;
    return (
      <main className="auth-shell auth-single">
        <section className="auth-brand"><Link href="/settings" className="back-link">← Account settings</Link><p className="eyebrow">EMAIL VERIFICATION</p><h1>Confirm your new email</h1><p className="muted">Enter the one-time verification token sent to your new email address. You must be signed in to the account that requested the change.</p></section>
        <section className="card auth-card">
          <h2>Confirm email change</h2>
          <form className="stack" onSubmit={confirmEmailChange}>
            <label>Email verification token<input required value={emailToken} onChange={(e) => setEmailToken(e.target.value)} /></label>
            <button disabled={busy}>{busy ? "Confirming…" : "Confirm new email"}</button>
          </form>
          {message && <p className="status-message" role="status">{message}</p>}
        </section>
      </main>
    );
  }

  if (identityLoading && ["/workspace", "/settings", "/organization/access"].includes(pathname)) {
    return <main className="auth-shell"><p className="muted">Loading your secure workspace…</p></main>;
  }

  if (pathname === "/settings") {
    if (!me) return null;
    return (
      <main>
        <header className="app-header">
          <div><p className="eyebrow">PULSEGRID HEALTH</p><h1>Account settings</h1><p className="muted">Manage your personal account and organization details.</p></div>
          <div className="user-menu"><span>{me.full_name}<small>{me.email}</small></span><button className="button-secondary" onClick={signOut} disabled={busy}>Sign out</button></div>
        </header>
        <nav className="workspace-nav" aria-label="Workspace navigation"><Link href="/workspace">Workspace</Link><Link href="/settings" aria-current="page">Account settings</Link>{currentOrg?.role === "org_admin" && <Link href="/organization/access">Organization access</Link>}</nav>
        <section className="card section">
          <h2>Personal account</h2>
          <p className="muted">These controls are available only to you while signed in.</p>
          <div className="auth-grid">
            <form className="stack" onSubmit={saveProfile}><h3>Personal information</h3><label>Full name<input required minLength={2} value={profileName || me.full_name} onChange={(e) => setProfileName(e.target.value)} /></label><button disabled={busy}>Save name</button></form>
            <form className="stack" onSubmit={changePassword}><h3>Change password</h3><label>Current password<input type="password" required autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} /></label><label>New password<input type="password" required minLength={12} autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></label><button disabled={busy}>Change password</button></form>
            <form className="stack" onSubmit={requestEmailChange}><h3>Change email</h3><p className="muted">A verification token will be sent to the new address.</p><label>New email<input type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)} /></label><label>Confirm with current password<input type="password" required autoComplete="current-password" value={emailCurrentPassword} onChange={(e) => setEmailCurrentPassword(e.target.value)} /></label><button className="button-secondary" disabled={busy}>Send verification</button></form>
          </div>
          <div className="auth-links"><Link href="/verify-email-change">I have an email verification token</Link></div>
        </section>
        {currentOrg?.role === "org_admin" && <section className="card section"><h2>Organization profile</h2><p className="muted">Changes here apply to the active organization, not your personal account.</p><form className="stack" onSubmit={saveOrganization}><label>Organization name<input required minLength={2} value={orgName || currentOrg.name} onChange={(e) => setOrgName(e.target.value)} /></label><label>Organization type<input required minLength={2} maxLength={80} value={orgType || currentOrg.organization_type} onChange={(e) => setOrgType(e.target.value)} /></label><button disabled={busy}>Save organization details</button></form></section>}
        {message && <p className="status-message" role="status">{message}</p>}
      </main>
    );
  }

  if (pathname === "/organization/access") {
    if (!me || currentOrg?.role !== "org_admin") return <main className="auth-shell"><p className="muted">Organization administrator access is required.</p><Link href="/workspace">Return to workspace</Link></main>;
    return (
      <main>
        <header className="app-header"><div><p className="eyebrow">PULSEGRID HEALTH</p><h1>Organization access</h1><p className="muted">Invite colleagues and assign the minimum role they need.</p></div><div className="user-menu"><span>{me.full_name}<small>{me.email}</small></span><button className="button-secondary" onClick={signOut} disabled={busy}>Sign out</button></div></header>
        <nav className="workspace-nav" aria-label="Workspace navigation"><Link href="/workspace">Workspace</Link><Link href="/settings">Account settings</Link><Link href="/organization/access" aria-current="page">Organization access</Link></nav>
              {currentOrg?.role === "org_admin" && (
        <section className="card section">
          <h2>Organization access</h2>
          <p className="muted">
            Invite a colleague with the minimum role needed. The invitation
            token is displayed once and must be delivered securely.
          </p>

          <form className="invite-form" onSubmit={createInvite}>
            <label>
              Colleague email
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </label>

            <label>
              Role
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
              >
                <option value="analyst">
                  Analyst — ingest data and run detection
                </option>
                <option value="reviewer">
                  Reviewer — investigate and resolve alerts
                </option>
                <option value="viewer">
                  Viewer — read-only access
                </option>
                <option value="org_admin">
                  Organization administrator
                </option>
              </select>
            </label>

            <button disabled={busy}>Create invitation</button>
          </form>

          {inviteToken && (
            <div className="token-panel">
              <strong>One-time invitation token</strong>
              <code>{inviteToken}</code>
              <button
                className="button-secondary"
                onClick={() =>
                  navigator.clipboard?.writeText(inviteToken)
                }
              >
                Copy token
              </button>
            </div>
          )}
        </section>
      )}
        {message && <p className="status-message" role="status">{message}</p>}
      </main>
    );
  }

  if (!me) return null;

  return (
    <main>
      <header className="app-header">
        <div>
          <p className="eyebrow">
            POPULATION &amp; WORKFORCE HEALTH INTELLIGENCE
          </p>
          <h1>PulseGrid Health</h1>
          <p className="muted">Organization workspace</p>
        </div>

        <div className="user-menu">
          <span>
            {me.full_name}
            <small>{me.email}</small>
          </span>

          <button
            className="button-secondary"
            onClick={signOut}
            disabled={busy}
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="workspace-nav" aria-label="Workspace navigation">
        <Link href="/workspace" aria-current="page">Workspace</Link>
        <Link href="/settings">Account settings</Link>
        {currentOrg?.role === "org_admin" && <Link href="/organization/access">Organization access</Link>}
      </nav>

      <div className="workspace-bar">
        <label>
          Active organization
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
          >
            {me.organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>

        {currentOrg && (
          <span className="role-chip">
            {roleNames[currentOrg.role] ?? currentOrg.role}
          </span>
        )}

        <button
          className="button-secondary refresh"
          onClick={loadWorkspace}
          disabled={busy}
        >
          Refresh data
        </button>
      </div>

      <div className="notice">
        Synthetic demonstration environment. Signals are not diagnoses,
        clinical predictions or outbreak declarations. Human review is
        required. Never upload identifiable patient or employee records.
      </div>

      {message && (
        <p className="status-message" role="status">
          {message}
        </p>
      )}

      <section className="grid">
        <article className="card metric-card">
          <div className="muted">Community observations</div>
          <div className="metric">
            {dashboard.community_observations}
          </div>
        </article>

        <article className="card metric-card">
          <div className="muted">Workforce observations</div>
          <div className="metric">
            {dashboard.workforce_observations}
          </div>
        </article>

        <article className="card metric-card">
          <div className="muted">
            Candidate alerts awaiting review
          </div>
          <div className="metric">
            {dashboard.pending_alerts}
          </div>
        </article>
      </section>

      {canIngest && (
        <section className="card section">
          <h2>Data ingestion</h2>
          <p className="muted">
            Import authorized aggregate observations from a validated CSV
            file.
          </p>

          <form className="upload" onSubmit={importCsv}>
            <label>
              Aggregate CSV dataset
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) =>
                  setCsv(e.target.files?.[0] ?? null)
                }
              />
            </label>

            <button disabled={!csv || busy}>
              {busy ? "Importing…" : "Import CSV"}
            </button>
          </form>
        </section>
      )}

      <section className="card section">
        <div className="section-heading">
          <div>
            <h2>Candidate alerts</h2>
            <p className="muted">
              Evidence-backed signals awaiting or undergoing human review.
            </p>
          </div>
        </div>

        {alerts.length === 0 ? (
          <p className="muted">
            No candidate alerts in this organization.
          </p>
        ) : (
          <div className="review-list">
            {alerts.map((a) => (
              <article className="review-card" key={a.id}>
                <div className="review-heading">
                  <strong>
                    {a.domain} / {a.group_code}
                  </strong>
                  <span className="pending">
                    {a.severity} · {a.status.replaceAll("_", " ")}
                  </span>
                </div>

                <p>
                  {a.indicator} · {a.observed_date} · {a.value} {a.unit}
                </p>

                <p className="muted">{a.explanation}</p>

                <button
                  className="button-secondary"
                  disabled={
                    aiBusy === a.id ||
                    busy ||
                    (!canReview && currentOrg?.role !== "analyst")
                  }
                  onClick={() => generateAiExplanation(a)}
                >
                  {aiBusy === a.id
                    ? "Analysing evidence…"
                    : "Generate AI evidence explanation"}
                </button>

                {aiInsights[a.id] && (
                  <div className="ai-insight">
                    <strong>AI evidence interpretation</strong>
                    <p>{aiInsights[a.id].explanation.summary}</p>

                    <p className="muted">
                      Candidate signal only · Human review required
                    </p>

                    <div>
                      <strong>
                        Quantitative evidence · server-derived
                      </strong>

                      <p>
                        Current observation:{" "}
                        {
                          aiInsights[a.id].quantitative_evidence
                            .current_observation.value
                        }{" "}
                        {
                          aiInsights[a.id].quantitative_evidence
                            .current_observation.unit
                        }{" "}
                        (
                        {
                          aiInsights[a.id].quantitative_evidence
                            .current_observation.date
                        }
                        )
                      </p>

                      <p>
                        Historical baseline:{" "}
                        {
                          aiInsights[a.id].quantitative_evidence
                            .historical_baseline.value ?? "Not available"
                        }{" "}
                        {
                          aiInsights[a.id].quantitative_evidence
                            .historical_baseline.unit
                        }
                      </p>

                      <p>
                        Robust score:{" "}
                        {
                          aiInsights[a.id].quantitative_evidence.detector
                            .robust_score ?? "Not calculable"
                        }{" "}
                        · Threshold:{" "}
                        {
                          aiInsights[a.id].quantitative_evidence.detector
                            .threshold
                        }{" "}
                        · Historical observations:{" "}
                        {
                          aiInsights[a.id].quantitative_evidence.detector
                            .history_count
                        }
                      </p>
                    </div>

                    {aiInsights[a.id].explanation.possible_interpretations.map(
                      (item, i) => (
                        <div key={i}>
                          <strong>
                            Hypothesis ({item.confidence_label})
                          </strong>
                          <p>{item.hypothesis}</p>
                          <small>
                            Evidence:{" "}
                            {[
                              ...item.supporting_evidence_ids,
                              ...item.contradicting_evidence_ids,
                            ].join(", ")}
                          </small>
                        </div>
                      )
                    )}

                    {aiInsights[a.id].explanation.data_quality_caveats
                      .length > 0 && (
                      <div>
                        <strong>Data-quality caveats</strong>
                        <ul>
                          {aiInsights[
                            a.id
                          ].explanation.data_quality_caveats.map(
                            (x, i) => (
                              <li key={i}>{x}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}

                    {aiInsights[a.id].explanation.review_questions
                      .length > 0 && (
                      <div>
                        <strong>Questions for reviewer</strong>
                        <ul>
                          {aiInsights[
                            a.id
                          ].explanation.review_questions.map(
                            (x, i) => (
                              <li key={i}>{x}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}

                    <small>
                      Evidence references:{" "}
                      {aiInsights[a.id].explanation.evidence_ids.join(
                        ", "
                      )}
                    </small>
                  </div>
                )}

                {canReview && (
                  <div className="review-actions">
                    {a.status === "pending_review" && (
                      <button
                        disabled={busy}
                        onClick={() => review(a, "acknowledge")}
                      >
                        Acknowledge
                      </button>
                    )}

                    {a.status === "acknowledged" && (
                      <button
                        disabled={busy}
                        onClick={() => review(a, "investigation")}
                      >
                        Start investigation
                      </button>
                    )}

                    {a.status === "investigating" && (
                      <div className="review-form">
                        <label>
                          Investigation findings
                          <textarea
                            value={findings[a.id] ?? ""}
                            onChange={(e) =>
                              setFindings((v) => ({
                                ...v,
                                [a.id]: e.target.value,
                              }))
                            }
                            placeholder="Record evidence reviewed and limitations"
                          />
                        </label>

                        <button
                          disabled={
                            busy ||
                            (findings[a.id] ?? "").trim().length < 10
                          }
                          onClick={() =>
                            review(a, "findings", {
                              findings: findings[a.id],
                              disposition: "monitor",
                            })
                          }
                        >
                          Save findings
                        </button>

                        <label>
                          Response action
                          <textarea
                            value={actions[a.id] ?? ""}
                            onChange={(e) =>
                              setActions((v) => ({
                                ...v,
                                [a.id]: e.target.value,
                              }))
                            }
                            placeholder="Describe a proportionate follow-up action"
                          />
                        </label>

                        <button
                          disabled={
                            busy ||
                            (actions[a.id] ?? "").trim().length < 10
                          }
                          onClick={() =>
                            review(a, "actions", {
                              action_type: "follow_up",
                              description: actions[a.id],
                              owner_role: "review team",
                            })
                          }
                        >
                          Add response action
                        </button>

                        <label>
                          Resolution rationale
                          <textarea
                            value={rationales[a.id] ?? ""}
                            onChange={(e) =>
                              setRationales((v) => ({
                                ...v,
                                [a.id]: e.target.value,
                              }))
                            }
                            placeholder="Explain the evidence-based disposition"
                          />
                        </label>

                        <button
                          disabled={
                            busy ||
                            (rationales[a.id] ?? "").trim().length < 10
                          }
                          onClick={() =>
                            review(a, "resolve", {
                              rationale: rationales[a.id],
                              disposition: "monitoring",
                            })
                          }
                        >
                          Close review
                        </button>
                      </div>
                    )}
                  </div>
                )}

                <button
                  className="button-secondary"
                  disabled={historyBusy === a.id}
                  onClick={() => viewHistory(a.id)}
                >
                  {historyBusy === a.id
                    ? "Loading…"
                    : "View review history"}
                </button>

                {histories[a.id] && (
                  <pre className="history-view">
                    {histories[a.id]}
                  </pre>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card section">
        <h2>Recent observations</h2>

        {dashboard.recent_observations.length === 0 ? (
          <p className="muted">No observations imported yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Domain / group</th>
                  <th>Indicator</th>
                  <th>Value</th>
                </tr>
              </thead>

              <tbody>
                {dashboard.recent_observations.map((o) => (
                  <tr key={o.id}>
                    <td>{o.observed_date}</td>
                    <td>
                      {o.domain} / {o.group_code}
                    </td>
                    <td>{o.indicator}</td>
                    <td>
                      {o.value} {o.unit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer className="footnote">
        Access is enforced by the API for every request. Interface controls
        are convenience only; server-side roles and organization membership
        remain authoritative.
      </footer>
    </main>
  );
}
