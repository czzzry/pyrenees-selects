import path from "node:path";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const testData = path.resolve(`.tmp-browser-acceptance-${process.env.SELECTS_BROWSER_PORT}`);
test.describe.configure({ mode: "serial" });

async function tabTo(page, locator, limit = 120) {
  await locator.waitFor({ state: "attached" });
  for (let index = 0; index < limit; index += 1) {
    await page.keyboard.press("Tab");
    if (await locator.evaluate(node => node === document.activeElement)) return;
  }
  throw new Error(`Keyboard focus did not reach ${await locator.evaluate(node => node.outerHTML.slice(0, 160))}`);
}

test("neutral overnight journey remains usable, accessible and responsive", async ({ page }, testInfo) => {
  const consoleProblems = [];
  page.on("console", message => {
    if (["error", "warning"].includes(message.type())) consoleProblems.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", error => consoleProblems.push(`pageerror: ${error.message}`));

  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await page.getByRole("button", { name: "Explore a small sample project" }).click();

  await expect(page.getByRole("heading", { name: "A clear plan before the long work." })).toBeVisible({ timeout: 90_000 });
  for (const label of [
    "Ready sources", "Duplicates ignored", "Portrait", "No source audio",
    "Variable frame rate", "Very short", "Broken / offline", "Unsupported files",
    "Estimated artifacts", "Safety reserve", "Free here"
  ]) await expect(page.locator("#planView").getByText(label, { exact: true })).toBeVisible();

  const planAudit = await new AxeBuilder({ page }).disableRules(["video-caption"]).analyze();
  expect(planAudit.violations.filter(item => ["serious", "critical"].includes(item.impact))).toEqual([]);

  await page.getByRole("button", { name: "Start overnight preparation" }).click();
  await expect(page.getByRole("heading", { name: "Finding moments worth your time." })).toBeVisible();
  const pause = page.getByRole("button", { name: "Pause safely" });
  if (await pause.isVisible()) {
    await pause.click();
    await expect(page.getByRole("button", { name: "Resume preparation" })).toBeVisible();
    await page.getByRole("button", { name: "Resume preparation" }).click();
  }

  const reviewReady = page.getByRole("button", { name: "Review ready proposals" });
  await expect(reviewReady).toBeEnabled({ timeout: 90_000 });
  await reviewReady.click();
  await expect(page.getByRole("heading", { name: "Proposed moments" })).toBeVisible();
  const candidateView = page.locator("#candidateView");
  const firstProposal = candidateView.locator("[data-candidate]").first();
  await expect(firstProposal).toBeVisible();
  await firstProposal.click();
  await candidateView.getByRole("button", { name: "Open full source" }).click();
  await expect(candidateView.getByRole("button", { name: "Back to proposed sample" })).toBeVisible();
  await expect(candidateView.locator("video")).toHaveAttribute("src", /\/sources\/.+\/media/);
  await candidateView.getByRole("spinbutton", { name: "In", exact: true }).fill("4.125");
  await candidateView.getByRole("spinbutton", { name: "Out", exact: true }).fill("9.875");
  await candidateView.locator("fieldset.segmented label").filter({ hasText: "Keep" }).click();
  await candidateView.getByLabel("Comment").fill("Open on the measured movement; preserve the source sound.");
  await candidateView.getByLabel("Story role").selectOption("opening");
  await candidateView.getByLabel("Source audio").selectOption("preserve");
  await candidateView.getByRole("button", { name: "Save decision" }).click();
  await expect(candidateView.getByRole("status")).toHaveText("Saved. This decision and comment will survive regeneration.");

  await page.reload();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Proposed moments" })).toBeVisible();
  await candidateView.locator("[data-candidate]").first().click();
  await expect(candidateView.getByLabel("Comment")).toHaveValue("Open on the measured movement; preserve the source sound.");
  await expect(candidateView.getByRole("spinbutton", { name: "In", exact: true })).toHaveValue("4.13");
  await expect(candidateView.getByRole("spinbutton", { name: "Out", exact: true })).toHaveValue("9.88");

  await page.getByRole("button", { name: "Assemble", exact: true }).click();
  const assembleView = page.locator("#assembleView");
  await assembleView.locator("#alternateList [data-add]").first().click();
  await assembleView.getByRole("button", { name: "Save new version" }).click();
  await expect(assembleView.getByRole("status")).toContainText("Saved version");
  await assembleView.getByRole("button", { name: "Render low-resolution preview" }).click();
  await expect(assembleView.getByRole("status")).toContainText("Preview ready", { timeout: 90_000 });
  await assembleView.getByRole("button", { name: "Export to DaVinci Resolve" }).click();
  await expect(assembleView.getByRole("status")).toHaveText("Resolve handoff written successfully.");
  await expect(assembleView.getByText("Handoff ready")).toBeVisible();

  await page.getByRole("button", { name: "Review", exact: true }).click();

  await page.setViewportSize({ width: 500, height: 900 });
  const layout = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    offenders: [...document.querySelectorAll("body *")]
      .filter(node => node.offsetParent !== null)
      .map(node => ({ selector: `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ""}${node.className && typeof node.className === "string" ? `.${node.className.trim().replace(/\s+/g, ".")}` : ""}`, left: node.getBoundingClientRect().left, right: node.getBoundingClientRect().right }))
      .filter(node => node.left < -0.5 || node.right > window.innerWidth + 0.5),
    controls: [...document.querySelectorAll("button:not([hidden]), input:not([hidden]), select:not([hidden])")]
      .filter(node => node.offsetParent !== null)
      .map(node => {
        const target = ["radio", "checkbox"].includes(node.type) ? node.closest("label") || node : node;
        return {
          selector: `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ""}${node.name ? `[name=${node.name}]` : ""}`,
          size: Math.min(target.getBoundingClientRect().width, target.getBoundingClientRect().height)
        };
      })
  }));
  expect(layout.offenders).toEqual([]);
  expect(layout.document).toBeLessThanOrEqual(layout.viewport);
  expect(layout.controls.filter(control => control.size < 44)).toEqual([]);

  const reviewAudit = await new AxeBuilder({ page }).disableRules(["video-caption"]).analyze();
  expect(reviewAudit.violations.filter(item => ["serious", "critical"].includes(item.impact))).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("review-narrow.png"), fullPage: true });

  const emptyProject = await page.evaluate(async ({ sourcePath }) => {
    const response = await fetch("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Empty neutral project", target_duration_seconds: 60, source_path: sourcePath })
    });
    return response.json();
  }, { sourcePath: path.join(testData, "empty-footage") });
  await page.evaluate(projectId => localStorage.setItem("selects-project", projectId), emptyProject.project.id);
  await page.reload();
  await expect(page.getByRole("heading", { name: "This folder has no video Selects can prepare." })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("empty-folder.png"), fullPage: true });

  expect(consoleProblems).toEqual([]);
});

test("core editorial actions are keyboard operable", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#projectSelect")).toBeVisible();
  const sampleId = await page.evaluate(async () => {
    const { projects } = await (await fetch("/api/projects")).json();
    return projects.find(project => project.name === "Sample · Coastal weekend").id;
  });
  await page.evaluate(projectId => localStorage.setItem("selects-project", projectId), sampleId);
  await page.reload();
  await expect(page.locator("#projectSelect")).toHaveValue(sampleId);

  const reviewTab = page.getByRole("button", { name: "Review", exact: true });
  await tabTo(page, reviewTab);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Proposed moments" })).toBeVisible();

  const candidateView = page.locator("#candidateView");
  const firstProposal = candidateView.locator("[data-candidate]").first();
  await tabTo(page, firstProposal);
  await page.keyboard.press("Enter");
  const checkedDecision = candidateView.locator('input[name="candidateDecision"]:checked');
  await tabTo(page, checkedDecision);
  await page.keyboard.press("ArrowRight");
  await expect(candidateView.locator('input[name="candidateDecision"][value="maybe"]')).toBeChecked();
  const comment = candidateView.getByLabel("Comment");
  await tabTo(page, comment);
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.type("Keyboard-reviewed exact source range.");
  const save = candidateView.getByRole("button", { name: "Save decision" });
  await tabTo(page, save);
  await page.keyboard.press("Enter");
  await expect(candidateView.getByRole("status")).toContainText("Saved.");

  const assembleTab = page.getByRole("button", { name: "Assemble", exact: true });
  await tabTo(page, assembleTab);
  await page.keyboard.press("Enter");
  const saveVersion = page.locator("#assembleView").getByRole("button", { name: "Save new version" });
  await tabTo(page, saveVersion);
  await page.keyboard.press("Enter");
  await expect(page.locator("#assembleView").getByRole("status")).toContainText("Saved version");
});
