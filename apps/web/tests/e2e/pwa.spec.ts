import { test, expect } from "@playwright/test";

test("publishes installable PWA metadata", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBeTruthy();

  const manifest = await response.json();
  expect(manifest.name).toBe("PulseGrid Health");
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.icons).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ src: "/icon.svg", type: "image/svg+xml" })
    ])
  );
});

test("serves a same-origin service worker without API response caching", async ({ request }) => {
  const response = await request.get("/sw.js");
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-type"]).toContain("javascript");

  const worker = await response.text();
  expect(worker).toContain('request.mode !== "navigate"');
  expect(worker).toContain('url.pathname.startsWith("/api/")');
  expect(worker).toContain('caches.open(CACHE_NAME)');
});

test("offline fallback fits a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/offline");
  await expect(page.getByRole("heading", { name: "You’re offline" })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth
  );
  expect(hasHorizontalOverflow).toBeFalsy();
});
