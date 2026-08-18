/**
 * EC signed-in browser walk audit — reads .env locally, outputs JSON report only.
 * Usage: node scripts/ec_browser_walk_audit.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT_DIR = join(ROOT, '.playwright-mcp');
const VIEWPORT = { width: 1440, height: 900 };

function loadEnv() {
  const env = {};
  for (const line of readFileSync(join(ROOT, '.env'), 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const i = trimmed.indexOf('=');
    if (i < 0) continue;
    env[trimmed.slice(0, i)] = trimmed.slice(i + 1);
  }
  return env;
}

function y(box) {
  return box ? Math.round(box.y) : -1;
}

async function waitAnswer(page) {
  const answer = page.locator('[data-ec-layer="soc-answer"]');
  if (await answer.isVisible()) return;
  const skip = page.getByRole('button', { name: 'Skip to answer' });
  try {
    await skip.waitFor({ state: 'visible', timeout: 8000 });
    await skip.click({ force: true });
  } catch {
    // journey may already be complete
  }
  const synthesizing = page.getByText(/Synthesizing governed analyst summary/i);
  if (await synthesizing.isVisible().catch(() => false)) {
    await synthesizing.waitFor({ state: 'hidden', timeout: 10000 });
  }
  await page.locator('[data-ec-layer="soc-answer"]').waitFor({ timeout: 60000 });
}

async function runScenarioById(page, scenarioId, queries) {
  await page.selectOption('#ec-scenario-select', scenarioId);
  const apiQuery = queries[scenarioId] ?? '';
  await page.locator('textarea').first().fill(apiQuery);
  await page.getByRole('button', { name: 'Send investigation query' }).click();
  await waitAnswer(page);
  await page.waitForTimeout(400);
}

async function measure(page) {
  const answer = page.locator('[data-ec-layer="soc-answer"]');
  const followups = page.locator('[data-ec-followups="true"]');
  const readiness = page.locator('[data-ec-section="action-readiness"]');
  const drawer = page.locator('[data-ec-layer="investigation-path"]');

  const answerBox = await answer.boundingBox();
  const followBox = await followups.boundingBox();
  const readyBox = (await readiness.count()) ? await readiness.boundingBox() : null;

  const layer1Text = (await answer.innerText()).slice(0, 4000);
  const drawerClosedText = (await drawer.isVisible()) ? (await drawer.innerText()).slice(0, 2000) : '';

  const splMarkers = ['index=', 'sourcetype=', 'stats ', '| search', 'export_customer'];
  const drawerOpenSpl = { before: false, after: false };
  drawerOpenSpl.before = splMarkers.some((m) => drawerClosedText.toLowerCase().includes(m));

  await drawer.locator('summary').click();
  await page.waitForTimeout(300);
  const drawerOpenText = (await drawer.innerText()).slice(0, 6000);
  drawerOpenSpl.after = splMarkers.some((m) => drawerOpenText.toLowerCase().includes(m));

  return {
    answer_top: y(answerBox),
    followups_top: y(followBox),
    readiness_top: y(readyBox),
    followups_visible_without_scroll: followBox != null && followBox.y < VIEWPORT.height,
    readiness_visible_without_scroll: readyBox != null && readyBox.y < VIEWPORT.height,
    layer1_has_raw_spl: splMarkers.some((m) => layer1Text.toLowerCase().includes(m)),
    layer2_has_spl_when_open: drawerOpenSpl.after,
    drawer_closed_has_spl: drawerOpenSpl.before,
    snippets: {
      layer1_head: layer1Text.slice(0, 500),
      drawer_head: drawerOpenText.slice(0, 400),
    },
  };
}

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });
  const env = loadEnv();
  const username = env.APP_AUTH_USER;
  const password = env.APP_AUTH_PASSWORD;
  if (!username || !password) throw new Error('APP_AUTH_USER/PASSWORD missing');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: VIEWPORT });

  const report = { viewport: VIEWPORT, scenarios: {} };

  await page.goto('http://127.0.0.1:3010/scenarios', { waitUntil: 'networkidle' });
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByText('AI Investigation Cockpit').waitFor({ timeout: 30000 });
  await page.waitForFunction(() => document.querySelector('#ec-scenario-select')?.options.length > 1);

  const catalog = await fetch('http://127.0.0.1:8010/api/demo/experience-center/scenarios').then((r) => r.json());
  const queries = Object.fromEntries(catalog.scenarios.map((s) => [s.scenario_id, s.query]));

  await runScenarioById(page, 's1_governed_splunk_investigation', queries);
  report.scenarios.S1 = await measure(page);
  report.scenarios.S1.direct_answer_three_systems =
    /three internal systems/i.test(report.scenarios.S1.snippets.layer1_head) &&
    /firewall|broader|not yet complete/i.test(report.scenarios.S1.snippets.layer1_head);
  await page.screenshot({ path: join(OUT_DIR, 'walk-s1.png') });

  await runScenarioById(page, 's2_ai_prompt_injection', queries);
  report.scenarios.S2 = await measure(page);
  report.scenarios.S2.attack_chain_present =
    (await page.locator('[data-ec-section="attack-chain"]').count()) > 0;
  await page.screenshot({ path: join(OUT_DIR, 'walk-s2.png') });

  await runScenarioById(page, 's3_firewall_team_coordination', queries);
  const s3Await = await measure(page);
  const workflowAwait = await page.locator('[data-ec-section="workflow-transition"]').count();
  await page.screenshot({ path: join(OUT_DIR, 'walk-s3-await.png') });

  const ingestChip = page.getByRole('button', { name: /Review firewall-team reply/i });
  if (await ingestChip.count()) {
    await ingestChip.click();
    await waitAnswer(page);
    await page.waitForTimeout(500);
  }
  const s3After = await measure(page);
  const workflowAfter = await page.locator('[data-ec-section="workflow-transition"]').innerText().catch(() => '');
  await page.screenshot({ path: join(OUT_DIR, 'walk-s3-ingest.png') });
  report.scenarios.S3 = {
    awaiting: s3Await,
    after_ingest: s3After,
    workflow_strip_visible: workflowAwait > 0,
    workflow_changed:
      workflowAfter.includes('Reply received') || workflowAfter.includes('Evidence updated'),
    inbound_panel: (await page.locator('[data-ec-section="coordination-inbound"]').count()) > 0,
  };

  await runScenarioById(page, 's5_cisco_hardening_remediation', queries);
  report.scenarios.S5 = await measure(page);
  report.scenarios.S5.resource_composition =
    (await page.locator('[data-ec-section="resource-composition"]').count()) > 0;
  const policyChip = page.getByRole('button', { name: /Show hardening policy/i });
  if (await policyChip.count()) {
    await policyChip.click();
    await waitAnswer(page);
    await page.waitForTimeout(500);
  }
  const layer1AfterPolicy = await page.locator('[data-ec-layer="soc-answer"]').innerText();
  report.scenarios.S5.policy_visible_after_chip =
    layer1AfterPolicy.includes('version 14 must be upgraded to version 15');
  await page.screenshot({ path: join(OUT_DIR, 'walk-s5-initial.png') });
  await page.screenshot({ path: join(OUT_DIR, 'walk-s5-policy.png') });

  await runScenarioById(page, 's7_conflicting_ot_evidence', queries);
  report.scenarios.S7 = await measure(page);
  report.scenarios.S7.conflict_card =
    (await page.locator('[data-ec-section="conflict-sources"]').count()) > 0;
  report.scenarios.S7.path_chips =
    await page.getByRole('button', { name: /Path A|Path B|inventory|OT inventory/i }).count();
  await page.screenshot({ path: join(OUT_DIR, 'walk-s7.png') });

  await browser.close();

  const outPath = join(OUT_DIR, 'ec-walk-report.json');
  writeFileSync(outPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ ok: true, report_path: outPath }));
}

main().catch((err) => {
  console.error(JSON.stringify({ ok: false, error: String(err) }));
  process.exit(1);
});
