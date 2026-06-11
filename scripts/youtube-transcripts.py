#!/usr/bin/env python3
"""
youtube-transcripts.py — YouTube 频道字幕提取工具

两步工作流：
  第一步：列出频道所有视频（--list），看清楚再决定要哪些
  第二步：提取指定视频的字幕（--select 或不加参数则全部提取）

用法示例：
  # 第一步：列出所有视频（不下载任何东西）
  python scripts/youtube-transcripts.py https://www.youtube.com/@simonscrapes --list

  # 第二步：提取指定编号的视频（编号来自 --list 输出）
  python scripts/youtube-transcripts.py https://www.youtube.com/@simonscrapes --select 1,5,12
  python scripts/youtube-transcripts.py https://www.youtube.com/@simonscrapes --select 1-10,15,20-25

  # 提取全部
  python scripts/youtube-transcripts.py https://www.youtube.com/@simonscrapes

  # 测试用：只取前 3 个
  python scripts/youtube-transcripts.py https://www.youtube.com/@simonscrapes --limit 3

依赖：yt-dlp（需已安装），Chrome 浏览器已登录 YouTube
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# ── 视频列表获取 ──────────────────────────────────────────────────────────────

def get_video_list(channel_url: str) -> list[dict]:
    """获取频道所有视频元数据（不下载视频）。"""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings",
         channel_url + "/videos"],
        capture_output=True, text=True,
    )
    videos = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                v = json.loads(line)
                videos.append({
                    "index":    v.get("playlist_index", 0),
                    "id":       v.get("id", ""),
                    "title":    v.get("title", "Unknown"),
                    "duration": v.get("duration_string", "?"),
                    "url":      f"https://www.youtube.com/watch?v={v.get('id', '')}",
                })
            except json.JSONDecodeError:
                pass
    return videos


# ── --list 模式 ───────────────────────────────────────────────────────────────

def cmd_list(videos: list[dict]) -> None:
    """打印所有视频的编号、标题、时长、URL，供用户查看后决定提取哪些。"""
    print(f"\n共 {len(videos)} 个视频\n")
    print(f"{'#':>4}  {'时长':>8}  {'标题':<70}  URL")
    print("-" * 120)
    for v in videos:
        print(f"{v['index']:>4}  {v['duration']:>8}  {v['title']:<70}  {v['url']}")
    print()
    print("用 --select 指定要提取的视频编号，例如：")
    print("  --select 1,5,12          提取第 1、5、12 个视频")
    print("  --select 1-10,20-25      提取第 1-10 和第 20-25 个视频")
    print("  （不加 --select 则提取全部）")


# ── --select 解析 ─────────────────────────────────────────────────────────────

def parse_select(select_str: str, max_index: int) -> set[int]:
    """
    解析选择字符串，返回视频编号集合。
    支持格式：'1,3,5-10,20' → {1, 3, 5, 6, 7, 8, 9, 10, 20}
    """
    selected = set()
    for part in select_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            selected.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            selected.add(int(part))
    return {i for i in selected if 1 <= i <= max_index}


# ── 字幕下载 & 清洗 ───────────────────────────────────────────────────────────

def clean_srt(srt_content: str) -> str:
    """将 SRT 字幕转为纯文本，去除时间戳和滚动重复行。"""
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    phrases = []
    for block in blocks:
        lines = block.strip().splitlines()
        text_lines = []
        for line in lines:
            line = line.strip()
            if re.match(r'^\d+$', line):
                continue
            if re.match(r'^\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->', line):
                continue
            line = re.sub(r'<[^>]+>', '', line).strip()
            if line:
                text_lines.append(line)
        if text_lines:
            phrases.append(text_lines[-1])

    deduped, prev = [], None
    for phrase in phrases:
        if phrase != prev:
            deduped.append(phrase)
            prev = phrase
    return ' '.join(deduped)


def download_transcript(video_id: str, tmpdir: str, browser: str = "chrome") -> tuple[str | None, str | None]:
    """下载字幕（优先中文，兜底英文），返回 (纯文本, 语言轨道)。"""
    subprocess.run(
        ["yt-dlp", "--cookies-from-browser", browser,
         "--write-subs", "--write-auto-subs", "--skip-download",
         "--sub-langs", "zh-Hans,zh,zh-CN,en",
         "--convert-subs", "srt", "--no-warnings",
         "-o", os.path.join(tmpdir, f"{video_id}.%(ext)s"),
         f"https://www.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True,
    )
    for lang in ["zh-Hans", "zh", "zh-CN", "en"]:
        path = os.path.join(tmpdir, f"{video_id}.{lang}.srt")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return clean_srt(f.read()), lang
    return None, None


# ── 提取主流程 ────────────────────────────────────────────────────────────────

def cmd_extract(videos: list[dict], output_dir: Path, browser: str, delay: float) -> None:
    """提取指定视频列表的字幕并保存。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    results, success, failed = [], 0, 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, v in enumerate(videos, 1):
            print(f"[{i}/{len(videos)}] #{v['index']} {v['title'][:60]} ({v['duration']})")

            transcript, lang = download_transcript(v["id"], tmpdir, browser)

            results.append({**v, "lang": lang, "transcript": transcript})

            if transcript:
                safe_title = re.sub(r'[^\w\s-]', '', v["title"])[:80].strip()
                txt_path = output_dir / f"{v['index']:03d}_{v['id']}_{safe_title}.txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"# {v['title']}\n")
                    f.write(f"URL: {v['url']}\n")
                    f.write(f"字幕语言：{lang}\n\n")
                    f.write(transcript)
                success += 1
                print(f"  ✓ [{lang}] {len(transcript)} 字符 → {txt_path.name}")
            else:
                failed += 1
                print(f"  ✗ 无字幕")

            if i < len(videos) and delay > 0:
                time.sleep(delay)

    combined = output_dir / "all_transcripts.json"
    with open(combined, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n完成！成功 {success} 个，无字幕 {failed} 个")
    print(f"输出目录：{output_dir.resolve()}")
    print(f"合并 JSON：{combined.resolve()}")


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YouTube 频道字幕提取工具（先 --list 查看，再 --select 提取）"
    )
    parser.add_argument("channel_url", help="频道 URL，如 https://www.youtube.com/@simonscrapes")
    parser.add_argument("--list",    action="store_true", help="列出所有视频，不提取字幕")
    parser.add_argument("--select",  default="",  help="指定提取的视频编号，如 '1,5,10-20'")
    parser.add_argument("--limit",   type=int, default=0, help="调试用：只处理前 N 个视频")
    parser.add_argument("--output",  default="./transcripts", help="字幕输出目录（默认 ./transcripts）")
    parser.add_argument("--browser", default="chrome", help="浏览器 cookies 来源（默认 chrome）")
    parser.add_argument("--delay",   type=float, default=1.0, help="视频间请求间隔秒数（默认 1.0）")
    args = parser.parse_args()

    print(f"正在获取视频列表：{args.channel_url}")
    videos = get_video_list(args.channel_url)

    if not videos:
        print("错误：无法获取视频列表，请检查 URL 是否正确。")
        sys.exit(1)

    print(f"共找到 {len(videos)} 个视频")

    # --list：只展示列表，不提取
    if args.list:
        cmd_list(videos)
        return

    # --select：筛选指定视频
    if args.select:
        selected_indices = parse_select(args.select, len(videos))
        videos = [v for v in videos if v["index"] in selected_indices]
        if not videos:
            print(f"错误：--select '{args.select}' 没有匹配到任何视频。")
            sys.exit(1)
        print(f"已选择 {len(videos)} 个视频")

    # --limit：调试截断
    if args.limit > 0:
        videos = videos[: args.limit]
        print(f"调试模式：只处理前 {len(videos)} 个视频")

    cmd_extract(videos, Path(args.output), args.browser, args.delay)


if __name__ == "__main__":
    main()
