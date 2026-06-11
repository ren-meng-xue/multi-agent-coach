#!/usr/bin/env node
/**
 * record-0-1-demo.mjs
 * 全自动录制从 0 到 1 的完整产品演示视频
 * 流程：Dashboard（无简历重定向到 Settings）→ 上传简历 → 等 AI 评估 → Coach → Interview 5 轮 Q&A
 * 用法：node scripts/record-0-1-demo.mjs
 */

import { spawn, execSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { setTimeout as sleep } from "node:timers/promises";
import { tmpdir } from "node:os";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(join(__dirname, ".."));
const BACKEND_DIR = join(ROOT, "backend");
const FRONTEND_DIR = join(ROOT, "frontend");

// ─────────────────────────────────────────────
//  配置
// ─────────────────────────────────────────────
const RESUME_PDF  = "/Users/xuebao/Desktop/任孟雪_AI_Agent.pdf";
const OUTPUT_MP4  = join(ROOT, "artifacts/full-0-1-demo.mp4");
const VIDEO_DIR   = join(tmpdir(), `coach-0-1-${Date.now()}`);
const BACKEND     = "http://localhost:8000";
const FRONTEND    = "http://localhost:3000";
const TOKEN       = "dev-auth-bypass-token";

// ─────────────────────────────────────────────
//  5 轮预设答案（AI Agent 工程师岗位）
// ─────────────────────────────────────────────
const ANSWERS = [
  // Q1 项目架构
  "我最近主导了一个多 Agent 面试 Coach 平台。整体分五个阶段：Prepare → Interview → Evaluate → Coach → Report。核心是 Chief Interviewer ReAct Loop，最多四轮迭代防死循环，每轮调度 Evaluator 和 Question Designer 两个子 Agent 协作。技术栈是 FastAPI 加 Celery 加 Redis，Agent 层基于 Claude API 实现结构化 tool use，候选人画像以 JSONB 格式存在 PostgreSQL 跨 session 持续积累，SSE 实时把 Agent 思考路径推送到前端。",

  // Q2 ReAct 与防死循环
  "ReAct 是 Reasoning 加 Acting 的结合——模型先推理选工具，执行后拿到观察结果，再循环推理。在 Chief Interviewer 里防死循环有两层：第一是 max_iterations=4 的硬限制，超了直接截断不依赖模型判断；第二是 system prompt 里注入明确终止条件，出完指定题数强制结束。另外对于并发写入，Evaluator 更新 candidate_memory 时用 SELECT FOR UPDATE 悲观锁保证原子性，避免 Question Designer 同时读到脏数据。",

  // Q3 并发与 SSE
  "并发一致性踩过坑。Evaluator 写 candidate_memory 时如果 Question Designer 同时读，可能拿到脏数据。解法是数据库层用 SELECT FOR UPDATE 悲观锁，读-改-写原子操作。SSE 推送用 Redis Pub/Sub 解耦——Celery task 发布事件，SSE handler 订阅转发前端，写路径和推送路径完全独立。Celery task 设 acks_late=True 保证失败可重试。生产上 Nginx 还要加 X-Accel-Buffering: no，否则默认 buffer 会让事件推送卡住。",

  // Q4 长期记忆
  "candidate_memory 存在 PostgreSQL 的 JSONB 字段里，按维度组织：技术深度、表达清晰度、压力反应。每场面试结束后 Evaluator merge 新信号保留历史权重衰减，Coach Agent 读取全量记忆生成训练计划。局限是 session 增多后全量读取的 token 消耗线性增长，context window 膨胀。下一步引入 pgvector，把面试片段向量化，Coach Agent 按语义相关性检索历史信号，不用全量加载，控制 token 成本同时提升响应速度。",

  // Q5 SSE 生产坑
  "SSE 生产踩了几个坑。第一，Nginx 默认 buffer 响应，必须加 X-Accel-Buffering: no 才能让事件实时到客户端。第二，断开重连用 EventSource 的 onerror 加指数退避，避免瞬断丢数据。第三，heartbeat 每 15 秒发一条 comment，防负载均衡超时切断。最关键的是 Celery task 里不能直接写 SSE 响应，必须通过 Redis Pub/Sub 中转，task 和 HTTP 连接生命周期完全解耦，task 失败不影响前端连接状态，这是整个流式架构最核心的设计决策。",
];

// ─────────────────────────────────────────────
//  工具
// ─────────────────────────────────────────────
const log = (msg) => console.log(`[0-1-demo] ${msg}`);
const err = (msg) => console.error(`[0-1-demo] ✗ ${msg}`);

function proxyEnv() {
  return {
    ...process.env,
    DEV_AUTH_BYPASS: "1",
    NEXT_PUBLIC_DEV_AUTH_BYPASS: "1",
    http_proxy: "http://127.0.0.1:7897",
    https_proxy: "http://127.0.0.1:7897",
    ALL_PROXY: "http://127.0.0.1:7897",
  };
}

async function isAlive(url) {
  try {
    // redirect: 'manual' 避免跟踪 Clerk 外部跳转导致超时
    await fetch(url, { signal: AbortSignal.timeout(3000), redirect: "manual" });
    return true;
  } catch {
    return false;
  }
}

async function waitReady(url, label, maxMs = 120_000) {
  log(`等待 ${label} 就绪...`);
  const deadline = Date.now() + maxMs;
  let i = 0;
  while (Date.now() < deadline) {
    if (await isAlive(url)) {
      log(`${label} ✓ (轮询第 ${i + 1} 次成功)`);
      return;
    }
    if (i % 5 === 0) log(`仍在等待 ${label}... (${i * 2}s)`);
    await sleep(2000);
    i++;
  }
  throw new Error(`${label} 超时未就绪`);
}

const procs = [];
let frontendReady = false;

function startProc(cmd, args, cwd, label) {
  const p = spawn(cmd, args, {
    cwd,
    env: proxyEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  p.stdout.on("data", (d) => {
    const str = d.toString();
    if (label === "frontend" && str.includes("✓ Ready")) {
      frontendReady = true;
    }
    process.stdout.write(`  [${label}] ${d}`);
  });
  p.stderr.on("data", (d) => process.stderr.write(`  [${label}] ${d}`));
  p.on("exit", (code) => {
    if (code !== 0 && code !== null) err(`${label} exited with ${code}`);
  });
  procs.push(p);
  return p;
}

async function waitFrontendReady(maxMs = 120_000) {
  log("等待 Frontend 就绪...");
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    if (frontendReady) { log("Frontend ✓"); return; }
    await sleep(500);
  }
  throw new Error("Frontend 超时未就绪");
}

function killAll() {
  for (const p of procs) {
    try { p.kill("SIGTERM"); } catch {}
  }
  try {
    execSync("pkill -f 'uvicorn app.main:app' 2>/dev/null || true", { shell: true });
    execSync("pkill -f 'celery.*worker' 2>/dev/null || true", { shell: true });
    execSync("pkill -f 'next dev' 2>/dev/null || true", { shell: true });
  } catch {}
}

async function typeSlowly(page, text, msPerChar = 55) {
  const ta = page.locator("textarea");
  await ta.click();
  await ta.fill("");
  for (const ch of text) {
    await ta.type(ch);
    await sleep(msPerChar + Math.random() * 25);
  }
}

async function waitTextareaEnabled(page, timeout = 180_000) {
  await page.waitForFunction(
    () => {
      const ta = document.querySelector("textarea");
      return ta && !ta.disabled;
    },
    null,
    { timeout },
  );
}

// ─────────────────────────────────────────────
//  录制主逻辑
// ─────────────────────────────────────────────
async function record() {
  mkdirSync(VIDEO_DIR, { recursive: true });
  log(`视频录制临时目录: ${VIDEO_DIR}`);

  const browser = await chromium.launch({
    headless: false,
    args: ["--window-size=1440,900"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: VIDEO_DIR, size: { width: 1440, height: 900 } },
  });

  const page = await context.newPage();
  let videoPath = null;

  try {
    // ── 步骤 1：进入 Coach（无简历 → 自动重定向到 Settings）────────
    log("步骤 1: 进入 Coach 页面（展示未登录绕过 + 无简历状态）...");
    await page.goto(`${FRONTEND}/coach`);
    await sleep(3000);
    await page.screenshot({ path: "/tmp/debug-01-coach-initial.png" });

    // ── 步骤 2：前往 Settings 上传简历 ──────────────────────────────
    log("步骤 2: 前往 Settings 页面上传简历...");
    await page.goto(`${FRONTEND}/settings`);
    // 等待 ResumeCard 加载
    await page.waitForSelector('input[type="file"]', { state: "attached", timeout: 30_000 });
    await sleep(1500);
    await page.screenshot({ path: "/tmp/debug-02-settings-loaded.png" });

    log(`上传简历: ${RESUME_PDF}`);
    await page.setInputFiles('input[type="file"]', RESUME_PDF);

    // 等待"已成功绑定演练上下文"出现（简历解析完成）
    log("等待简历解析并绑定演练上下文...");
    await page.waitForSelector('text=已成功绑定演练上下文', { timeout: 90_000 });
    log("简历绑定成功 ✓");
    await sleep(2000);
    await page.screenshot({ path: "/tmp/debug-03-resume-bound.png" });

    // 等待 AI 简历诊断建议出现（如果有）
    try {
      await page.waitForSelector('text=简历洞察与诊断建议', { timeout: 60_000 });
      log("AI 简历诊断建议已显示 ✓");
      await sleep(5000); // 让观众看清诊断内容
    } catch {
      log("AI 诊断建议未出现（跳过），继续流程");
      await sleep(3000);
    }

    await page.screenshot({ path: "/tmp/debug-04-resume-evaluation.png" });

    // ── 步骤 3：回到 Coach 页面，发起面试 ───────────────────────────
    log("步骤 3: 回到 Coach 页面准备开始面试...");
    await page.goto(`${FRONTEND}/coach`);
    await sleep(3000);
    await page.screenshot({ path: "/tmp/debug-05-coach-with-resume.png" });

    log("点击开始面试...");
    const startBtn = page
      .locator('button:has-text("直接开始面试"), button:has-text("常规开始一场面试")')
      .first();
    await startBtn.waitFor({ state: "visible", timeout: 15_000 });
    await startBtn.click();

    // ── 步骤 4：Interview 5 轮 Q&A ──────────────────────────────────
    log("步骤 4: 等待面试页面加载...");
    await page.waitForURL(/\/interview/, { timeout: 30_000 });
    await sleep(1000);

    log("等待 Prepare 阶段完成 + 第一题就绪...");
    await waitTextareaEnabled(page, 240_000);
    log("第一题已就绪 ✓");
    await sleep(3000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.screenshot({ path: "/tmp/debug-06-first-question.png" });

    for (let i = 0; i < ANSWERS.length; i++) {
      if (i > 0) {
        log(`等待第 ${i + 1} 题加载完成...`);
        await waitTextareaEnabled(page, 180_000);
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      }

      const readPause = 2500 + Math.random() * 1000;
      log(`第 ${i + 1} 题：阅读 ${(readPause / 1000).toFixed(1)}s...`);
      await sleep(readPause);

      log(`打入第 ${i + 1} 轮答案...`);
      await typeSlowly(page, ANSWERS[i], 55);
      await sleep(600);

      await page.locator('button[type="submit"]').click();
      log(`第 ${i + 1} 轮已提交`);
      await page.screenshot({ path: `/tmp/debug-q${i + 1}-submitted.png` });
    }

    // 等待最后一轮 AI 响应渲染完成
    log("等待最终 AI 响应渲染（15s）...");
    await sleep(15_000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await sleep(3000);
    await page.screenshot({ path: "/tmp/debug-07-final-state.png" });

  } finally {
    videoPath = await page.video()?.path().catch((e) => {
      err(`获取视频路径失败：${e}`);
      return null;
    });
    if (videoPath) log(`视频暂存：${videoPath}`);
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  return videoPath;
}

// ─────────────────────────────────────────────
//  转码
// ─────────────────────────────────────────────
function convert(webmPath) {
  log(`转码中: ${webmPath} → ${OUTPUT_MP4}`);
  mkdirSync(dirname(OUTPUT_MP4), { recursive: true });

  const result = spawnSync(
    "ffmpeg",
    [
      "-y",
      "-i", webmPath,
      "-vcodec", "libx264",
      "-crf", "23",
      "-preset", "fast",
      "-movflags", "+faststart",
      "-pix_fmt", "yuv420p",
      OUTPUT_MP4,
    ],
    { stdio: "inherit" },
  );

  if (result.status !== 0) throw new Error("ffmpeg 转码失败");
  log(`✅ 视频已保存：${OUTPUT_MP4}`);
}

// ─────────────────────────────────────────────
//  主程序
// ─────────────────────────────────────────────
async function main() {
  if (!existsSync(RESUME_PDF)) {
    err(`简历文件不存在：${RESUME_PDF}`);
    process.exit(1);
  }

  try {
    log("清理残留进程...");
    killAll();
    await sleep(2000);

    log("清理数据库测试数据（dev-auth-bypass-token 用户）...");
    execSync("uv run python scripts/clean_test_user.py", {
      cwd: BACKEND_DIR,
      env: proxyEnv(),
      stdio: "inherit",
    });

    log("启动 Docker 依赖 (postgres + redis)...");
    execSync("docker compose up -d postgres redis", {
      cwd: ROOT,
      stdio: "inherit",
    });
    await sleep(3000);

    log("启动 Backend + Celery...");
    startProc(
      "uv",
      ["run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
      BACKEND_DIR,
      "backend",
    );
    startProc(
      "uv",
      ["run", "celery", "-A", "app.tasks:celery_app", "worker", "--loglevel=warning"],
      BACKEND_DIR,
      "celery",
    );

    log("启动 Frontend (NEXT_PUBLIC_DEV_AUTH_BYPASS=1)...");
    startProc("pnpm", ["dev", "--port", "3000"], FRONTEND_DIR, "frontend");

    await waitReady(`${BACKEND}/api/v1/health`, "Backend");
    await waitFrontendReady();

    // 验证 bypass 已生效
    const bypassCheck = await fetch(`${BACKEND}/api/v1/user/profile`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
      signal: AbortSignal.timeout(3000),
    }).catch(() => null);
    if (!bypassCheck || bypassCheck.status === 401) {
      throw new Error("DEV_AUTH_BYPASS 未生效，请检查后端配置");
    }
    log("DEV_AUTH_BYPASS 验证 ✓");

    const videoPath = await record();
    if (videoPath) {
      convert(videoPath);
    } else {
      throw new Error("视频路径为空，录制失败");
    }

    log("🎉 录制完成！");
    log(`视频位置：${OUTPUT_MP4}`);

  } catch (e) {
    err(String(e.stack || e));
    process.exitCode = 1;
  } finally {
    log("清理后台进程...");
    killAll();
  }
}

process.on("SIGINT", () => {
  log("收到 Ctrl+C，清理中...");
  killAll();
  process.exit(1);
});

main();
