import { execFileSync } from "node:child_process";
import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP = "e2e-bootstrap-token-placeholder";
const ADMIN_PASSWORD = "Admin-E2E-Password-2026!";
const REVIEWER_PASSWORD = "Reviewer-E2E-Password-2026!";
const VIEWER_PASSWORD = "Viewer-E2E-Password-2026!";

async function getCsrf(request: APIRequestContext) {
  const response = await request.get(`${API}/api/v1/auth/csrf`);
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}

async function bootstrap(request: APIRequestContext, email: string, organization: string) {
  const token = await getCsrf(request);
  const response = await request.post(`${API}/api/v1/auth/bootstrap`, {
    headers: { "X-CSRF-Token": token, "X-Bootstrap-Token": BOOTSTRAP },
    data: {
      organization_name: organization,
      organization_type: "public_health",
      admin_email: email,
      admin_name: "E2E Administrator",
      password: ADMIN_PASSWORD
    }
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).organization_id as string;
}

async function resetE2EDatabase() {
  // The E2E database is disposable and explicitly constrained to local *_test
  // PostgreSQL by playwright.config.ts. Reset it before each attempt because
  // Playwright retries reuse the same service container.
  const script = [
    "from sqlalchemy import text",
    "from sqlalchemy.engine import make_url",
    "from app.core.config import settings",
    "from app.db import engine",
    "url = make_url(settings.database_url)",
    "assert (url.host or '').lower() in {'localhost', '127.0.0.1', '::1'}",
    "assert (url.database or '').lower().endswith('_test')",
    "with engine.begin() as connection:",
    "    connection.execute(text('TRUNCATE TABLE organizations, users RESTART IDENTITY CASCADE'))",
  ].join("\n");
  execFileSync("python", ["-c", script], {
    cwd: "../api",
    encoding: "utf8",
    env: process.env,
  });
}

async function seedSecondOrganization(email: string, organizationName: string) {
  // Cross-tenant authorization needs a second tenant, but public bootstrap is
  // deliberately one-time. Seed this isolated test tenant directly in the
  // disposable E2E database instead of weakening the production endpoint.
  const script = [
    "from app.db import SessionLocal",
    "from app.models import Organization, OrganizationMembership, User",
    "from app.security import _hash_password",
    "import sys",
    "email, organization_name, password = sys.argv[1:4]",
    "with SessionLocal() as db:",
    "    organization = Organization(name=organization_name, organization_type='public_health')",
    "    user = User(email=email, full_name='E2E Second Administrator', password_hash=_hash_password(password))",
    "    db.add_all([organization, user])",
    "    db.flush()",
    "    db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role='org_admin'))",
    "    db.commit()",
    "    print(organization.id)",
  ].join("\n");
  return execFileSync("python", ["-c", script, email, organizationName, ADMIN_PASSWORD], {
    cwd: "../api",
    encoding: "utf8",
    env: process.env,
  }).trim();
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function invite(page: Page, email: string, role: "reviewer" | "viewer") {
  await page.goto("/organization/access");
  await page.getByLabel("Colleague email").fill(email);
  await page.getByLabel("Role").selectOption(role);
  await page.getByRole("button", { name: "Create invitation" }).click();
  return (await page.locator(".token-panel code").innerText()).trim();
}

async function acceptInvite(page: Page, token: string, name: string, password: string) {
  await page.goto("/invite");
  await page.getByLabel("Invitation token").fill(token);
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Create password").fill(password);
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByText(/Invitation accepted/)).toBeVisible();
}

test("public, authentication and recovery screens have separate routes", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /See emerging health signals/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in securely" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();

  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in securely" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Forgot password" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Forgot your password?" })).toBeVisible();

  await page.goto("/forgot-password");
  await expect(page.getByRole("heading", { name: "Request a reset token" })).toBeVisible();
  await expect(page.getByLabel("Reset token")).toHaveCount(0);

  await page.goto("/reset-password");
  await expect(page.getByRole("heading", { name: "Complete password reset" })).toBeVisible();
  await expect(page.getByLabel("Reset token")).toBeVisible();

  await page.goto("/invite");
  await expect(page.getByRole("heading", { name: "Accept invitation" })).toBeVisible();
  await expect(page.getByLabel("Invitation token")).toBeVisible();
});

test("authenticated workspace enforces ingestion, review, role and tenant boundaries", async ({ page, browser }, testInfo) => {
  // Retries share the same PostgreSQL service, so isolate each attempt from partial setup.
  const suffix = `${process.env.GITHUB_RUN_ID ?? "local"}-${testInfo.workerIndex}-${testInfo.retry}`;
  const adminEmail = `admin-${suffix}@pulsegrid-e2e.test`;
  const reviewerEmail = `reviewer-${suffix}@pulsegrid-e2e.test`;
  const viewerEmail = `viewer-${suffix}@pulsegrid-e2e.test`;
  await resetE2EDatabase();
  const organizationId = await bootstrap(page.context().request, adminEmail, `PulseGrid E2E Authority ${suffix}`);

  await signIn(page, adminEmail, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "Account settings" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Organization access" })).toHaveCount(0);
  await page.getByRole("link", { name: "Personal settings" }).click();
  await expect(page).toHaveURL(/\\/settings\\/profile$/);
  await expect(page.getByRole("heading", { name: "Personal information" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Change password" })).toHaveCount(0);
  await page.getByRole("link", { name: "Security", exact: true }).click();
  await expect(page).toHaveURL(/\\/settings\\/security$/);
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible();
  await page.getByRole("link", { name: "Email", exact: true }).click();
  await expect(page).toHaveURL(/\\/settings\\/email$/);
  await expect(page.getByRole("heading", { name: "Change email address" })).toBeVisible();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page).toHaveURL(/\\/workspace$/);
  await expect(page.getByRole("heading", { name: "Organization command center" })).toBeVisible();
  const csv = [
    "domain,group_code,source_code,observed_date,indicator,value,denominator,unit",
    ...[10,11,9,10,11,10,9,35].map((value, index) =>
      `community,E2E-COMMUNITY,E2E-SOURCE,2026-07-${String(index+1).padStart(2,"0")},weekly_reports,${value},5000,reports`)
  ].join("\n");
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-community.csv", mimeType: "text/csv", buffer: Buffer.from(csv)
  });
  await page.getByRole("button", { name: "Import CSV" }).click();
  await expect(page.getByText(/Imported 8;/)).toBeVisible();
  await expect(page.locator(".review-card").filter({ hasText: "E2E-COMMUNITY" })).toBeVisible();

  const reviewerToken = await invite(page, reviewerEmail, "reviewer");
  const viewerToken = await invite(page, viewerEmail, "viewer");
  await page.getByRole("button", { name: "Sign out" }).click();

  await acceptInvite(page, reviewerToken, "E2E Reviewer", REVIEWER_PASSWORD);
  await signIn(page, reviewerEmail, REVIEWER_PASSWORD);
  const reviewerAlert = page.locator(".review-card").filter({ hasText: "E2E-COMMUNITY" }).first();
  await reviewerAlert.getByRole("button", { name: "Acknowledge" }).click();
  await expect(reviewerAlert.getByText(/acknowledged/)).toBeVisible();
  await reviewerAlert.getByRole("button", { name: "Start investigation" }).click();
  await expect(reviewerAlert.getByText(/investigating/)).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  await acceptInvite(page, viewerToken, "E2E Viewer", VIEWER_PASSWORD);
  await signIn(page, viewerEmail, VIEWER_PASSWORD);
  const viewerAlert = page.locator(".review-card").filter({ hasText: "E2E-COMMUNITY" }).first();
  await expect(viewerAlert).toBeVisible();
  await expect(viewerAlert.getByRole("button", { name: "Acknowledge" })).toHaveCount(0);

  const cookies = await page.context().cookies("http://127.0.0.1:3000");
  const csrfCookie = cookies.find(cookie => cookie.name === "pulsegrid_csrf");
  expect(csrfCookie).toBeTruthy();
  const deniedUploadStatus = await page.evaluate(async ({ orgId, csrfToken }) => {
    const body = new FormData();
    body.append(
      "file",
      new Blob(["domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"], { type: "text/csv" }),
      "empty.csv"
    );
    const response = await fetch("/api/v1/observations/import", {
      method: "POST",
      credentials: "include",
      headers: {
        "X-Organization-ID": orgId,
        "X-CSRF-Token": csrfToken
      },
      body
    });
    return response.status;
  }, { orgId: organizationId, csrfToken: csrfCookie!.value });
  expect(deniedUploadStatus).toBe(403);

  const otherContext = await browser.newContext();
  try {
    const otherRequest = otherContext.request;
    const otherEmail = `other-admin-${suffix}@pulsegrid-e2e.test`;
    const otherOrg = await seedSecondOrganization(otherEmail, `Other E2E Authority ${suffix}`);
    const token = await getCsrf(otherRequest);
    const login = await otherRequest.post(`${API}/api/v1/auth/login`, {
      headers: { "X-CSRF-Token": token },
      data: { email: otherEmail, password: ADMIN_PASSWORD }
    });
    expect(login.status()).toBe(200);
    const crossTenant = await otherRequest.get(`${API}/api/v1/dashboard`, {
      headers: { "X-Organization-ID": organizationId }
    });
    expect(crossTenant.status()).toBe(403);
    const ownTenant = await otherRequest.get(`${API}/api/v1/dashboard`, {
      headers: { "X-Organization-ID": otherOrg }
    });
    expect(ownTenant.status()).toBe(200);
  } finally {
    await otherContext.close();
  }

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in securely" })).toBeVisible();
  expect(await page.evaluate(async () => (await fetch("/api/v1/auth/me", { credentials: "include", cache: "no-store" })).status)).toBe(401);
});
