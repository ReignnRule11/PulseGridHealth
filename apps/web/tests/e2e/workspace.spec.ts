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

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function invite(page: Page, email: string, role: "reviewer" | "viewer") {
  await page.getByLabel("Colleague email").fill(email);
  await page.getByLabel("Role").selectOption(role);
  await page.getByRole("button", { name: "Create invitation" }).click();
  return (await page.locator(".token-panel code").innerText()).trim();
}

async function acceptInvite(page: Page, token: string, name: string, password: string) {
  await page.getByLabel("Invitation token").fill(token);
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Create password").fill(password);
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByText(/Invitation accepted/)).toBeVisible();
}

test("authenticated workspace enforces ingestion, review, role and tenant boundaries", async ({ page, browser }, testInfo) => {
  // Retries share the same PostgreSQL service, so isolate each attempt from partial setup.
  const suffix = `${process.env.GITHUB_RUN_ID ?? "local"}-${testInfo.workerIndex}-${testInfo.retry}`;
  const adminEmail = `admin-${suffix}@pulsegrid-e2e.test`;
  const reviewerEmail = `reviewer-${suffix}@pulsegrid-e2e.test`;
  const viewerEmail = `viewer-${suffix}@pulsegrid-e2e.test`;
  const organizationId = await bootstrap(page.context().request, adminEmail, `PulseGrid E2E Authority ${suffix}`);

  await signIn(page, adminEmail, ADMIN_PASSWORD);
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

  const cookies = await page.context().cookies(API);
  const csrfCookie = cookies.find(cookie => cookie.name === "pulsegrid_csrf");
  expect(csrfCookie).toBeTruthy();
  const deniedUpload = await page.context().request.post(`${API}/api/v1/observations/import`, {
    headers: { "X-Organization-ID": organizationId, "X-CSRF-Token": csrfCookie!.value },
    multipart: { file: { name: "empty.csv", mimeType: "text/csv", buffer: Buffer.from("domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n") } }
  });
  expect(deniedUpload.status()).toBe(403);

  const otherContext = await browser.newContext();
  try {
    const otherRequest = otherContext.request;
    const otherOrg = await bootstrap(otherRequest, `other-admin-${suffix}@pulsegrid-e2e.test`, `Other E2E Authority ${suffix}`);
    const token = await getCsrf(otherRequest);
    const login = await otherRequest.post(`${API}/api/v1/auth/login`, {
      headers: { "X-CSRF-Token": token },
      data: { email: `other-admin-${suffix}@pulsegrid-e2e.test`, password: ADMIN_PASSWORD }
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
  expect((await page.context().request.get(`${API}/api/v1/auth/me`)).status()).toBe(401);
});
