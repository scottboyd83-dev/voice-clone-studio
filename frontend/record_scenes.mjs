// Records the demo scenes as separate webm clips via Playwright.
import { chromium } from "playwright";
import { mkdirSync, renameSync, readdirSync, existsSync } from "fs";

const RAW = new URL("../demo/raw/", import.meta.url).pathname;
mkdirSync(RAW, { recursive: true });

const browser = await chromium.launch();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function scene(name, fn) {
  if (existsSync(`${RAW}${name}.webm`)) {
    console.log(`skipping ${name} (already recorded)`);
    return;
  }
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: RAW, size: { width: 1280, height: 800 } },
  });
  const page = await ctx.newPage();
  await page.goto("http://localhost:5173");
  await page.waitForSelector(".voice-card", { timeout: 30000 });
  await fn(page);
  const video = page.video();
  await ctx.close();
  const path = await video.path();
  renameSync(path, `${RAW}${name}.webm`);
  console.log(`recorded ${name}`);
}

const tab = (page, label) => page.click(`.tab:has-text("${label}")`);

// 0: title overlay -> voice library
await scene("scene0", async (page) => {
  await page.evaluate(() => {
    const el = document.createElement("div");
    el.id = "demo-title";
    el.style.cssText =
      "position:fixed;inset:0;z-index:1000;background:#0b0b0d;display:flex;" +
      "flex-direction:column;align-items:center;justify-content:center;gap:14px;" +
      "transition:opacity 1s ease";
    el.innerHTML =
      '<div style="font-family:\'Instrument Serif\',serif;font-style:italic;font-size:64px;color:#e8e4dc">Voice <span style="color:#f5a524">Clone</span> Studio</div>' +
      '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;letter-spacing:.25em;text-transform:uppercase;color:#8b8778">Local · Private · Yours</div>';
    document.body.appendChild(el);
  });
  await sleep(3000);
  await page.evaluate(() => {
    const el = document.getElementById("demo-title");
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 1000);
  });
  await sleep(1500);
  await page.hover(".voice-card >> nth=0");
  await sleep(2500);
  await page.hover(".voice-card >> nth=1");
  await sleep(4000);
});

// 1: new voice modal with reading script
await scene("scene1", async (page) => {
  await page.click('button:has-text("+ New Voice")');
  await page.waitForSelector(".script-card");
  await page.fill('input[placeholder*="Scott"]', "My voice");
  await sleep(5500);
});

// 2: generate speech live (payoff at the end; sped up in assembly)
await scene("scene2", async (page) => {
  await tab(page, "Generate");
  await page.waitForSelector("textarea");
  await page.type("textarea", "This is my cloned voice, generated live, on my own Mac.", { delay: 30 });
  await page.click('main button.btn.primary:has-text("Generate")');
  await page.waitForSelector(".generating", { timeout: 10000 });
  await page.waitForSelector(".player", { timeout: 120000 });
  await sleep(2500);
});

// 3: recording studio prompts
await scene("scene3", async (page) => {
  await tab(page, "Studio");
  await page.waitForSelector(".script-card");
  await sleep(2200);
  await page.click('button:has-text("Skip →")');
  await sleep(2200);
  await page.click('button:has-text("Skip →")');
  await sleep(4000);
});

// 4: train tab
await scene("scene4", async (page) => {
  await tab(page, "Train");
  await page.waitForSelector('input[placeholder*="fine-tuned"]');
  await page.fill('input[placeholder*="fine-tuned"]', "Scott — fine-tuned v1");
  await sleep(3000);
  await page.hover('input[type="range"] >> nth=0');
  await sleep(4000);
});

// 5: voice changer
await scene("scene5", async (page) => {
  await tab(page, "Convert");
  await page.waitForSelector('.page-title:has-text("Voice Changer")');
  await sleep(6500);
});

// 6: history
await scene("scene6", async (page) => {
  await tab(page, "History");
  await page.waitForSelector(".history-item");
  await sleep(2500);
  await page.hover(".history-item >> nth=0");
  await sleep(2000);
  await page.mouse.wheel(0, 300);
  await sleep(4500);
});

await browser.close();
console.log("all scenes:", readdirSync(RAW).join(", "));
