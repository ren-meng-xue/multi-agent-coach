#!/usr/bin/env node
/**
 * record-interview-demo.mjs
 * 全自动录制 multi-agent-coach 面试演示视频，输出到 resume/assets/multi-agent-coach-demo.mp4
 * 用法：node scripts/record-interview-demo.mjs
 */

import { spawn, execSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, unlinkSync, copyFileSync } from "node:fs";
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
//  常量
// ─────────────────────────────────────────────
const RESUME_PDF   = "/Users/xuebao/Desktop/任孟雪_AI_Agent.pdf";
const OUTPUT_MP4   = "/Users/xuebao/learn/AI项目/resume/assets/multi-agent-coach-demo.mp4";
const VIDEO_DIR    = join(tmpdir(), `coach-demo-${Date.now()}`);
const BACKEND      = "http://localhost:8000";
const FRONTEND     = "http://localhost:3000";
const TOKEN        = "dev-auth-bypass-token";

// ─────────────────────────────────────────────
//  题库 Markdown
// ─────────────────────────────────────────────
const QA_BANK_MD = `## 项目讲解

### Q1-项目架构
**问题：** 介绍一下你最近做的核心 AI Agent 项目，整体架构是什么样的？
**参考答案：** 多 Agent 面试 Coach 平台，Chief Interviewer ReAct Loop

## 技术题

### Q2-ReAct防死循环
**问题：** 请解释 ReAct 模式，以及你在项目里是如何防止 Agent 死循环的？
**参考答案：** max_iterations=4 硬限制

### Q3-并发一致性
**问题：** 多个子 Agent 并发时，你怎么保证 candidate_memory 写入的一致性？
**参考答案：** SELECT FOR UPDATE 悲观锁

### Q4-长期记忆
**问题：** 你的候选人长期记忆方案是怎么设计的？局限在哪，下一步怎么优化？
**参考答案：** JSONB + pgvector

### Q5-SSE生产
**问题：** SSE 流式推送在生产部署中踩过哪些坑，你是怎么解决的？
**参考答案：** Nginx buffering, heartbeat, Redis Pub/Sub 解耦
`;

// ─────────────────────────────────────────────
//  5 轮预设回答
// ─────────────────────────────────────────────
const ANSWERS = [
  // Q1 项目架构
  "我最近完成了一个多 Agent 面试 Coach 平台，整体分五个阶段：Prepare → Interview → Evaluate → Coach → Report。核心是 Chief Interviewer ReAct Loop，最多四轮迭代防死循环，每轮调度两个专家子 Agent：Evaluator 实时打分并更新候选人画像，Question Designer 做规则校验和去重出题。技术栈是 FastAPI 加 Celery 加 Redis，Agent 层基于 Claude API 实现结构化 tool use，候选人画像以 JSONB 格式存在 PostgreSQL 里跨 session 持续积累。",

  // Q2 ReAct
  "ReAct 是 Reasoning 加 Acting 的结合——模型先推理选工具，执行后拿到观察结果，再循环推理。在 Chief Interviewer 里每轮模型判断候选人当前表现，决定调 Evaluator 还是 Question Designer，拿到结构化结果后再决定是否继续。防死循环两层保障：第一是 max_iterations=4 的硬限制，超了直接截断；第二是在 system prompt 里注入明确终止条件，出完指定题数就强制结束循环，不依赖模型自主判断。",

  // Q3 并发一致性
  "这是踩过坑的地方。Evaluator 写 candidate_memory 时如果 Question Designer 同时在读可能拿到脏数据。解法是在数据库层用 SELECT FOR UPDATE 做悲观锁，保证 Evaluator 的读-改-写是原子操作。事件流用 Redis Pub/Sub 解耦——Celery task 发布事件，SSE handler 订阅转发给前端，写路径和推送路径完全独立，任一侧崩溃不影响另一侧。另外 Celery task 设 acks_late=True 保证失败可以重试。",

  // Q4 长期记忆
  "candidate_memory 存在 PostgreSQL 的 JSONB 字段里，按维度组织，比如技术深度、表达清晰度、压力反应。每场面试结束后 Evaluator merge 新信号进去保留历史权重衰减，Coach Agent 读取全量记忆生成训练计划。局限是 session 增多后全量读取的 token 消耗线性增长，context window 会膨胀。优化方向是引入 pgvector，把面试片段向量化存储，Coach Agent 按语义相关性检索历史信号而不是全量加载。",

  // Q5 SSE 生产
  "踩过几个坑。第一是 Nginx 默认 buffer 响应，必须加 X-Accel-Buffering: no 才能让事件实时到客户端。第二是断开重连，用 EventSource 的 onerror 加指数退避，避免瞬断就丢数据。第三是 heartbeat，每 15 秒发一条 comment 防负载均衡超时切断。最关键的是 Celery task 里不能直接写 SSE 响应，必须通过 Redis Pub/Sub 中转，task 和 HTTP 连接生命周期完全解耦，task 失败不影响前端连接状态。",
];

// ─────────────────────────────────────────────
//  工具函数
// ─────────────────────────────────────────────
const log = (msg) => console.log(`[demo] ${msg}`);
const err = (msg) => console.error(`[demo] ✗ ${msg}`);

function proxyEnv() {
  return {
    ...process.env,
    DEV_AUTH_BYPASS: "1",
    http_proxy: "http://127.0.0.1:7897",
    https_proxy: "http://127.0.0.1:7897",
    ALL_PROXY: "http://127.0.0.1:7897",
    VIRTUAL_ENV: undefined,
  };
}

async function isAlive(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(2000) });
    return r.ok || r.status < 500;
  } catch {
    return false;
  }
}

async function waitReady(url, label, maxMs = 90_000) {
  log(`等待 ${label} 就绪...`);
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    if (await isAlive(url)) { log(`${label} ✓`); return; }
    await sleep(2000);
  }
  throw new Error(`${label} 在 ${maxMs / 1000}s 内未就绪`);
}

// ─────────────────────────────────────────────
//  服务管理
// ─────────────────────────────────────────────
const procs = [];

function startProc(cmd, args, cwd, label) {
  const p = spawn(cmd, args, {
    cwd,
    env: proxyEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  p.stdout.on("data", (d) => process.stdout.write(`  [${label}] ${d}`));
  p.stderr.on("data", (d) => process.stderr.write(`  [${label}] ${d}`));
  p.on("exit", (code) => { if (code !== 0 && code !== null) err(`${label} exited with ${code}`); });
  procs.push(p);
  return p;
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

async function isBypassActive() {
  try {
    const r = await fetch(`${BACKEND}/api/v1/user/qa-bank/summary`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
      signal: AbortSignal.timeout(3000),
    });
    return r.status !== 401;
  } catch {
    return false;
  }
}

async function startServices() {
  // 检查服务是否已在运行且 bypass 已激活
  const backendAlive  = await isAlive(`${BACKEND}/api/v1/health`);
  const frontendAlive = await isAlive(FRONTEND);

  if (backendAlive && frontendAlive && await isBypassActive()) {
    log("服务已就绪且 DEV_AUTH_BYPASS 已激活，跳过启动");
    return false;
  }

  // 强制重启：确保 DEV_AUTH_BYPASS=1 生效
  log("清理残留进程...");
  try {
    execSync("pkill -f 'uvicorn app.main:app' 2>/dev/null || true", { shell: true });
    execSync("pkill -f 'celery.*worker' 2>/dev/null || true", { shell: true });
    execSync("pkill -f 'next dev' 2>/dev/null || true", { shell: true });
  } catch {}
  await sleep(2000);

  log("启动 Docker 依赖 (postgres + redis)...");
  execSync("docker compose up -d postgres redis", { cwd: ROOT, stdio: "inherit" });
  await sleep(3000);

  log("启动 Backend...");
  execSync(
    "uv run celery -A app.tasks:celery_app purge -f 2>/dev/null || true",
    { cwd: BACKEND_DIR, env: proxyEnv(), shell: true },
  );
  startProc("uv", ["run", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"], BACKEND_DIR, "backend");
  startProc("uv", ["run", "celery", "-A", "app.tasks:celery_app", "worker", "--loglevel=warning"], BACKEND_DIR, "celery");

  log("启动 Frontend...");
  startProc("pnpm", ["dev", "--port", "3000"], FRONTEND_DIR, "frontend");

  await waitReady(`${BACKEND}/api/v1/health`, "Backend");
  await waitReady(FRONTEND, "Frontend");

  // 验证 bypass 生效
  if (!await isBypassActive()) {
    throw new Error("DEV_AUTH_BYPASS 未生效，请检查后端配置");
  }
  log("DEV_AUTH_BYPASS ✓");
  return true;
}

// ─────────────────────────────────────────────
//  API 调用
// ─────────────────────────────────────────────
async function apiPost(path, formData) {
  const r = await fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}` },
    body: formData,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`POST ${path} → ${r.status}: ${text}`);
  }
  return r.json();
}

async function uploadResume() {
  if (!existsSync(RESUME_PDF)) throw new Error(`简历不存在：${RESUME_PDF}`);
  log("上传简历...");
  const fd = new FormData();
  fd.append("file", new Blob([await (await import("node:fs/promises")).readFile(RESUME_PDF)], { type: "application/pdf" }), "任孟雪_AI_Agent.pdf");
  const res = await apiPost("/api/v1/user/resume", fd);
  log(`简历上传成功：${res.data?.resume_filename}`);
}

async function uploadQABank() {
  log("上传题库...");
  const fd = new FormData();
  fd.append("file", new Blob([QA_BANK_MD], { type: "text/markdown" }), "qa-bank.md");
  const res = await apiPost("/api/v1/user/qa-bank/upload", fd);
  log(`题库上传：${JSON.stringify(res.data)}`);
}

async function resetSession(targetRole) {
  const r = await fetch(`${BACKEND}/api/v1/interview/reset`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ target_role: targetRole }),
  });
  if (!r.ok) log(`reset 失败 (${r.status})，继续`);
  else log("会话已重置");
}

// ─────────────────────────────────────────────
//  Playwright 录制
// ─────────────────────────────────────────────
async function waitTextareaEnabled(page, timeout = 150_000) {
  // 注意：waitForFunction 第二参数是 arg，第三参数才是 options
  await page.waitForFunction(
    () => {
      const ta = document.querySelector("textarea");
      return ta && !ta.disabled;
    },
    null,
    { timeout },
  );
}

async function typeSlowly(page, text, msPerChar = 60) {
  const ta = page.locator("textarea");
  await ta.click();
  // 先清空再逐字输入，模拟真实打字
  await ta.fill("");
  for (const ch of text) {
    await ta.type(ch);
    await sleep(msPerChar + Math.random() * 30);
  }
}

async function submit(page) {
  await page.locator('button[type="submit"]').click();
}

async function recordInterview() {
  mkdirSync(VIDEO_DIR, { recursive: true });

  const INTERVIEW_CONTEXT = {
    target_role: "AI Agent 工程师",
    use_qa_bank: true,
    user_background: "熟悉 ReAct 模式、多 Agent 协作、SSE 流式推送、FastAPI + Celery 后端",
  };

  const browser = await chromium.launch({
    headless: false,
    args: ["--window-size=1440,900"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: VIDEO_DIR, size: { width: 1440, height: 900 } },
  });

  // 在所有页面导航前预注入 sessionStorage，避免先访问 /coach 露出历史数据
  await context.addInitScript((ctx) => {
    sessionStorage.setItem("interview_context", JSON.stringify(ctx));
  }, INTERVIEW_CONTEXT);

  const page = await context.newPage();
  let videoPath = null;

  try {
    // ── 直接跳转到 /interview ────────────────────────────────────
    await resetSession(INTERVIEW_CONTEXT.target_role);

    log("直接导航到 /interview...");
    await page.goto(`${FRONTEND}/interview`);

    // ── 等待 Prepare 阶段完成 ────────────────────────────────────
    // ── 等待 Prepare 完成 + 第一题出现 ─────────────────────────────
    log("等待 Prepare 阶段完成 + 第一题加载（工具调用可视化中）...");
    // prepare 完成后 AI 直接出题，textarea 变可用
    await waitTextareaEnabled(page, 240_000);
    log(`Prepare 完成，第一题已就绪，当前 URL：${page.url()}`);
    await page.screenshot({ path: "/tmp/debug-02-prepare-done.png" });

    // 停顿 3 秒，让题目完整渲染后再开始答题
    await sleep(3000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    // ── 5 轮 Q&A ─────────────────────────────────────────────────
    for (let i = 0; i < ANSWERS.length; i++) {
      // 第 2 题起：等 AI 上一轮评分完成并出好下一题
      if (i > 0) {
        log(`等待第 ${i + 1} 题加载完成...`);
        await waitTextareaEnabled(page);
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      }

      await page.screenshot({ path: `/tmp/debug-q${i + 1}.png` });

      const readPause = 2500 + Math.random() * 1000;
      log(`第 ${i + 1} 题：阅读 ${(readPause / 1000).toFixed(1)}s...`);
      await sleep(readPause);

      log(`打入第 ${i + 1} 轮回答...`);
      await typeSlowly(page, ANSWERS[i], 55);
      await sleep(600);
      await submit(page);
      log(`第 ${i + 1} 轮回答已提交`);
    }

    // ── 等待最后一轮 AI 评分完成后再关闭 ─────────────────────────
    log("等待最终 AI 响应渲染（12s）...");
    await sleep(12_000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await sleep(3000);

  } finally {
    // 注意：finally 不能 return，否则会吞掉 try 中的异常
    videoPath = await page.video().path().catch((e) => {
      err(`获取视频路径失败：${e}`);
      return null;
    });
    if (videoPath) log(`视频暂存：${videoPath}`);
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  if (!videoPath) throw new Error("视频路径为空，录制失败");
  return videoPath;
}

// ─────────────────────────────────────────────
//  视频转码
// ─────────────────────────────────────────────
function convertVideo(webmPath) {
  log("转码 webm → mp4...");
  const outputDir = dirname(OUTPUT_MP4);
  mkdirSync(outputDir, { recursive: true });

  const result = spawnSync("ffmpeg", [
    "-y",
    "-i", webmPath,
    "-vcodec", "libx264",
    "-crf", "23",
    "-preset", "fast",
    "-movflags", "+faststart",
    "-pix_fmt", "yuv420p",
    OUTPUT_MP4,
  ], { stdio: "inherit" });

  if (result.status !== 0) throw new Error("ffmpeg 转码失败");
  log(`✅ 视频已保存：${OUTPUT_MP4}`);
}

// ─────────────────────────────────────────────
//  主流程
// ─────────────────────────────────────────────
async function main() {
  let weStarted = false;

  try {
    weStarted = await startServices();
    await uploadResume();
    await uploadQABank();

    const webmPath = await recordInterview();
    convertVideo(webmPath);

    log("🎉 录制完成！");
    log(`视频位置：${OUTPUT_MP4}`);
  } catch (e) {
    err(String(e));
    process.exitCode = 1;
  } finally {
    if (weStarted) {
      log("关闭服务...");
      killAll();
    }
  }
}

// ─────────────────────────────────────────────
//  信号处理
// ─────────────────────────────────────────────
process.on("SIGINT", () => {
  log("收到 Ctrl+C，清理中...");
  killAll();
  process.exit(1);
});

main();
