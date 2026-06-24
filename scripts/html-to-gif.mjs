#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const DEFAULT_HTML = "prototype/Skill.prototype";
const DEFAULT_OUTPUT = "artifacts/skill-demo.gif";
const MAC_CHROME =
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PLAYWRIGHT_CACHE = resolve(
  process.env.HOME ?? "",
  "Library/Caches/ms-playwright",
);

function parseArgs(argv) {
  const options = {
    html: DEFAULT_HTML,
    output: DEFAULT_OUTPUT,
    width: 1200,
    height: 820,
    fps: 12,
    step: 45,
    holdFrames: 8,
  };

  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      positional.push(arg);
      continue;
    }

    const [key, inlineValue] = arg.slice(2).split("=");
    const value = inlineValue ?? argv[++i];
    if (value === undefined) {
      throw new Error(`Missing value for --${key}`);
    }

    if (["width", "height", "fps", "step", "holdFrames"].includes(key)) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue) || numberValue <= 0) {
        throw new Error(`--${key} must be a positive number`);
      }
      options[key] = numberValue;
    } else {
      throw new Error(`Unknown option --${key}`);
    }
  }

  if (positional[0]) options.html = positional[0];
  if (positional[1]) options.output = positional[1];
  return options;
}

function toTargetUrl(input) {
  if (/^https?:\/\//.test(input) || input.startsWith("file://")) {
    return input;
  }

  const htmlPath = resolve(input);
  if (!existsSync(htmlPath)) {
    throw new Error(`HTML file not found: ${htmlPath}`);
  }
  return pathToFileURL(htmlPath).href;
}

function runFfmpeg(framePattern, output, fps) {
  mkdirSync(dirname(output), { recursive: true });

  const ext = extname(output).toLowerCase();
  let args;

  if (ext === ".mp4") {
    args = [
      "-y", "-framerate", String(fps), "-i", framePattern,
      "-c:v", "libx264", "-crf", "16", "-preset", "slow",
      "-pix_fmt", "yuv420p", "-vf", "scale=1440:-2:flags=lanczos",
      "-movflags", "+faststart",
      output,
    ];
  } else if (ext === ".webm") {
    args = [
      "-y", "-framerate", String(fps), "-i", framePattern,
      "-c:v", "libvpx-vp9", "-crf", "20", "-b:v", "0",
      "-pix_fmt", "yuv420p", "-vf", "scale=1440:-2:flags=lanczos",
      output,
    ];
  } else {
    // GIF fallback
    args = [
      "-y", "-framerate", String(fps), "-i", framePattern,
      "-vf", `fps=${fps},scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3`,
      "-loop", "0",
      output,
    ];
  }

  const result = spawnSync("ffmpeg", args, { stdio: "inherit" });
  if (result.status !== 0) {
    throw new Error("ffmpeg failed");
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const output = resolve(options.output);
  const frameDir = resolve(
    "artifacts",
    "gif-captures",
    `${new Date().toISOString().replace(/[:.]/g, "-")}-${basenameWithoutExt(options.html)}`,
  );
  mkdirSync(frameDir, { recursive: true });

  const launchOptions = findHeadlessShell()
    ? { executablePath: findHeadlessShell() }
    : existsSync(MAC_CHROME)
      ? { executablePath: MAC_CHROME }
      : {};
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({
    viewport: { width: options.width, height: options.height },
    deviceScaleFactor: 2,
  });

  let frame = 0;
  const capture = async () => {
    frame += 1;
    await page.screenshot({
      path: `${frameDir}/frame-${String(frame).padStart(5, "0")}.png`,
    });
  };

  const hold = async () => {
    for (let i = 0; i < options.holdFrames; i += 1) {
      await capture();
    }
  };

  const scrollSection = async () => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(120);
    await hold();

    const maxScroll = await page.evaluate(
      () => document.documentElement.scrollHeight - window.innerHeight,
    );
    for (let y = 0; y <= maxScroll; y += options.step) {
      await page.evaluate((top) => window.scrollTo(0, top), y);
      await page.waitForTimeout(20);
      await capture();
    }
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await hold();
  };

  const scrollElement = async (selector) => {
    await page.evaluate((targetSelector) => {
      const target = document.querySelector(targetSelector);
      if (target) target.scrollTop = 0;
    }, selector);
    await page.waitForTimeout(120);
    await hold();

    const maxScroll = await page.evaluate((targetSelector) => {
      const target = document.querySelector(targetSelector);
      if (!target) return 0;
      return Math.max(0, target.scrollHeight - target.clientHeight);
    }, selector);

    for (let y = 0; y <= maxScroll; y += options.step) {
      await page.evaluate(
        ({ targetSelector, top }) => {
          const target = document.querySelector(targetSelector);
          if (target) target.scrollTop = top;
        },
        { targetSelector: selector, top: y },
      );
      await page.waitForTimeout(20);
      await capture();
    }

    await page.evaluate((targetSelector) => {
      const target = document.querySelector(targetSelector);
      if (target) target.scrollTop = target.scrollHeight;
    }, selector);
    await hold();
  };

  const recordTabs = async () => {
    const tabs = await page.evaluate(() =>
      Array.from(document.querySelectorAll(".nav-item[data-tab]"))
        .map((button) => button.getAttribute("data-tab"))
        .filter(Boolean),
    );

    if (tabs.length === 0) return false;

    for (const tab of tabs) {
      await page.evaluate((tabName) => {
        document.querySelector(`.nav-item[data-tab="${tabName}"]`)?.click();
      }, tab);
      await page.waitForTimeout(320);
      await hold();
      await scrollElement(`#tab-${tab}`);
    }

    return true;
  };

  await page.goto(toTargetUrl(options.html), { waitUntil: "networkidle" });
  await page.addStyleTag({
    content: `
      html { scroll-behavior: auto !important; }
      *, *::before, *::after {
        animation-duration: 0.001s !important;
        animation-delay: 0s !important;
        transition-duration: 0.001s !important;
      }
    `,
  });

  const handledTabs = await recordTabs();
  if (handledTabs) {
    await browser.close();
    runFfmpeg(`${frameDir}/frame-%05d.png`, output, options.fps);
    console.log(`GIF written: ${output}`);
    console.log(`Frames kept: ${frameDir}`);
    return;
  }

  const buttons = await page.evaluate(() => {
    return ["btng", "btns", "btnb"].filter((id) => document.getElementById(id));
  });

  if (buttons.length === 0) {
    await scrollSection();
  } else {
    for (const buttonId of buttons) {
      await page.evaluate((id) => document.getElementById(id)?.click(), buttonId);
      await page.waitForTimeout(180);
      await scrollSection();
    }
  }

  await browser.close();

  runFfmpeg(`${frameDir}/frame-%05d.png`, output, options.fps);
  console.log(`GIF written: ${output}`);
  console.log(`Frames kept: ${frameDir}`);
}

function basenameWithoutExt(input) {
  const normalized = input.replace(/\/+$/, "");
  const last = normalized.split(/[\\/]/).pop() || "page";
  const extension = extname(last);
  return extension ? last.slice(0, -extension.length) : last;
}

function findHeadlessShell() {
  if (!existsSync(PLAYWRIGHT_CACHE)) return undefined;

  const shellPaths = readdirSync(PLAYWRIGHT_CACHE)
    .filter((entry) => entry.startsWith("chromium_headless_shell-"))
    .sort()
    .reverse()
    .map((entry) =>
      join(
        PLAYWRIGHT_CACHE,
        entry,
        "chrome-headless-shell-mac-arm64",
        "chrome-headless-shell",
      ),
    )
    .filter((candidate) => existsSync(candidate));

  return shellPaths[0];
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
