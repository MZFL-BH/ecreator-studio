#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ECreator Studio · 底部实时章节进度条合成引擎 (chapter_bar.py)
=================================================================
在横屏/竖屏实操视频底边合成实时动态章节胶囊进度条，支持从 Markdown/JSON/命令行解析章节时间轴，
并在传入 .srt 字幕时自动将字幕上移避让进度条区域，一次性压制硬字幕与进度条。

用法:
    python3 scripts/chapter_bar.py --input temp.mp4 --output final.mp4 --from-md publish.md --srt clean.srt
    python3 scripts/chapter_bar.py --input temp.mp4 --output final.mp4 --chapters "00:00 开场; 00:30 实操; 01:45 总结"
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def find_ffmpeg_with_drawtext() -> str:
    """优先查找支持 drawtext 滤镜的 ffmpeg 可执行文件"""
    candidates = [
        shutil.which("ffmpeg"),
        str(Path.home() / "anaconda3" / "bin" / "ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        str(Path.home() / ".gemini" / "antigravity" / "bin" / "ffmpeg"),
    ]
    fallback = None
    for cand in candidates:
        if not cand or not Path(cand).exists():
            continue
        if fallback is None:
            fallback = cand
        proc = subprocess.run([cand, "-filters"], capture_output=True, text=True)
        if "drawtext" in proc.stdout or "subtitles" in proc.stdout:
            return cand
    if fallback:
        return fallback
    raise SystemExit("[错误] 未检测到可用 ffmpeg，请先安装。")


def find_chinese_font() -> str:
    """查找系统可用中文字体"""
    candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for f in candidates:
        if Path(f).exists():
            return f
    return ""


def probe_video(ffmpeg_bin: str, video_path: Path) -> tuple[int, int, float]:
    """探测视频分辨率与总时长"""
    ffprobe = str(Path(ffmpeg_bin).with_name("ffprobe"))
    if not Path(ffprobe).exists():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    out = subprocess.check_output(
        [
            ffprobe, "-v", "error",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(video_path),
        ],
        text=True,
    )
    data = json.loads(out)
    width = height = 0
    for s in data.get("streams", []):
        if "width" in s and "height" in s:
            width = int(s["width"])
            height = int(s["height"])
            break
    duration = float(data["format"]["duration"])
    return width, height, duration


def parse_timestamp(ts: str) -> float:
    """支持 MM:SS、HH:MM:SS 或纯秒数"""
    ts = ts.strip()
    if ":" in ts:
        parts = [float(p) for p in ts.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return float(ts)


def shorten_chapter_title(title: str, max_chars: int = 12) -> str:
    """精简章节标题以便在进度条格内清晰显示"""
    # 取冒号/破折号前或核心词，避免底条文字挤出格
    clean = re.sub(r"（[^）]*）|\([^)]*\)", "", title).strip()
    if "：" in clean:
        head, tail = clean.split("：", 1)
        clean = head.strip() if len(head.strip()) >= 3 else tail.strip()
    elif ":" in clean:
        head, tail = clean.split(":", 1)
        clean = head.strip() if len(head.strip()) >= 3 else tail.strip()
    if len(clean) > max_chars:
        clean = clean[: max_chars - 1] + "…"
    return clean or title[:max_chars]


def parse_chapters_from_text(raw: str, total_duration: float) -> list[dict]:
    """从文本行中提取 `00:00 标题` 或 JSON 数组"""
    stripped = raw.strip()
    if stripped.startswith("["):
        items = json.loads(stripped)
        chapters = []
        for idx, item in enumerate(items):
            start = parse_timestamp(str(item["start"]))
            end = float(item["end"]) if "end" in item else (
                parse_timestamp(str(items[idx + 1]["start"])) if idx + 1 < len(items) else total_duration
            )
            chapters.append({"start": start, "end": max(start + 0.5, end), "title": str(item["title"])})
        return chapters

    # 匹配 `00:00 标题`（支持换行或分号分隔）
    matches = []
    for line in re.split(r"[\n;；]+", raw):
        m = re.match(r"^\s*[-*•]?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)\s*$", line)
        if m:
            matches.append((parse_timestamp(m.group(1)), shorten_chapter_title(m.group(2))))

    if not matches:
        raise ValueError("未能解析到 `00:00 章节标题` 格式的章节时间轴。")

    matches.sort(key=lambda x: x[0])
    chapters = []
    for i, (start, title) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else total_duration
        if start < total_duration:
            chapters.append({"start": start, "end": min(total_duration, max(start + 0.5, end)), "title": title})
    if chapters and chapters[0]["start"] > 0:
        chapters[0]["start"] = 0.0
    if chapters:
        chapters[-1]["end"] = total_duration
    return chapters


def render_bar_strip_mov(
    chapters: list[dict],
    width: int,
    bar_height: int,
    total_duration: float,
    font_path: str,
    ffmpeg_bin: str,
    out_mov: Path,
    bar_fps: int = 4,
) -> None:
    """使用 Pillow 渲染带 Alpha 通道的紧凑型底部章节进度条视频条带"""
    font_size = max(16, int(bar_height * 0.45))
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    gap = 4
    radius = 6
    usable_w = width - gap * (len(chapters) + 1)

    # 计算每一段的像素起止位置
    seg_boxes = []
    cur_x = gap
    for i, ch in enumerate(chapters):
        ratio = max(0.04, (ch["end"] - ch["start"]) / total_duration)
        if i == len(chapters) - 1:
            seg_w = max(40, width - gap - cur_x)
        else:
            seg_w = max(40, int(usable_w * ratio))
        seg_boxes.append((cur_x, cur_x + seg_w))
        cur_x += seg_w + gap

    # 预渲染“未播放暗底图文图层”和“高亮亮底图文图层”，运行时仅按进度条 X 坐标裁剪拼接
    base_dark = Image.new("RGBA", (width, bar_height), (15, 23, 42, 210))
    draw_dark = ImageDraw.Draw(base_dark)

    base_bright = Image.new("RGBA", (width, bar_height), (15, 23, 42, 210))
    draw_bright = ImageDraw.Draw(base_bright)

    for i, ch in enumerate(chapters):
        x0, x1 = seg_boxes[i]
        # 未激活深炭磨砂底块（无论背景是浅白网页还是深色IDE都保持高对比度）
        draw_dark.rounded_rectangle([x0, 4, x1, bar_height - 4], radius=radius, fill=(30, 41, 59, 235))
        # 激活亮白底块 + 底部科技蓝指示细线
        draw_bright.rounded_rectangle([x0, 4, x1, bar_height - 4], radius=radius, fill=(248, 250, 252, 248))
        draw_bright.rectangle([x0 + 2, bar_height - 7, x1 - 2, bar_height - 4], fill=(37, 99, 235, 255))

        # 居中文字（自动截断保护不超出格宽）
        title = ch["title"]
        seg_w = x1 - x0
        while len(title) > 2:
            bbox = draw_dark.textbbox((0, 0), title, font=font)
            if (bbox[2] - bbox[0]) <= seg_w - 16:
                break
            title = title[:-2] + "…"
        bbox = draw_dark.textbbox((0, 0), title, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = x0 + (seg_w - tw) // 2
        ty = (bar_height - th) // 2 - bbox[1]
        draw_dark.text((tx, ty), title, font=font, fill=(241, 245, 249, 245))
        draw_bright.text((tx, ty), title, font=font, fill=(15, 23, 42, 255))

    # 以 rawvideo RGBA 流式喂给 ffmpeg 压成支持 Alpha 的 qtrle / prores 极小条带文件
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{width}x{bar_height}",
        "-r", str(bar_fps),
        "-i", "-",
        "-c:v", "png",
        "-t", f"{total_duration:.3f}",
        str(out_mov),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total_frames = int(total_duration * bar_fps) + 1
    assert proc.stdin is not None

    for f_idx in range(total_frames):
        t = min(total_duration, f_idx / bar_fps)
        # 计算当前时间点对应的分割 X 坐标
        split_x = gap
        for i, ch in enumerate(chapters):
            x0, x1 = seg_boxes[i]
            if t >= ch["end"]:
                split_x = x1
            elif t >= ch["start"]:
                frac = (t - ch["start"]) / max(0.01, ch["end"] - ch["start"])
                split_x = int(x0 + (x1 - x0) * frac)
                break
            else:
                break

        frame = base_dark.copy()
        if split_x > 0:
            lit = base_bright.crop((0, 0, min(width, split_x), bar_height))
            frame.paste(lit, (0, 0))
        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("章节进度条带渲染失败。")


def build_drawtext_chain(srt_path: Path, font_path: str, bottom_offset: int, width: int) -> str:
    """将 SRT 转换为带安全避让边距的 FFmpeg drawtext 滤镜链"""
    def parse_srt_ts(t: str) -> float:
        h, m, rest = t.strip().split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    def esc_dt(txt: str) -> str:
        return txt.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    font_size = max(32, int(width * 0.0235))
    blocks = re.split(r"\n\s*\n", srt_path.read_text(encoding="utf-8").strip())
    filters = []
    for b in blocks:
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            s_str, e_str = lines[1].split("-->")
            s, e = parse_srt_ts(s_str), parse_srt_ts(e_str)
            text = " ".join(lines[2:])
            if len(text) > 26:
                mid = len(text) // 2
                text = text[:mid] + "\n" + text[mid:]
            filters.append(
                f"drawtext=fontfile='{font_path}'"
                f":expansion=none"
                f":text='{esc_dt(text)}'"
                f":fontsize={font_size}:fontcolor=white:borderw=3:bordercolor=0x0F172A@0.9"
                f":box=1:boxcolor=0x0F172A@0.68:boxborderw=12"
                f":x=(w-text_w)/2:y=h-text_h-{bottom_offset}"
                f":enable='between(t,{s:.3f},{e:.3f})'"
            )
    return ",".join(filters)


def main():
    parser = argparse.ArgumentParser(description="ECreator Studio 底部实时章节进度条与字幕合成器")
    parser.add_argument("--input", required=True, help="输入视频路径 (.mp4)")
    parser.add_argument("--output", required=True, help="输出视频路径 (.mp4)")
    parser.add_argument("--chapters", help="章节 JSON 路径或 `00:00 标题; 00:30 标题` 字符串")
    parser.add_argument("--from-md", help="从 publish.md / script.md 自动读取 `00:00 标题` 章节")
    parser.add_argument("--srt", help="可选 .srt 字幕文件路径（会自动上移避让底部进度条）")
    parser.add_argument("--bar-height", type=int, default=44, help="进度条高度 px（默认 44）")
    parser.add_argument("--fps", type=int, default=4, help="进度条更新帧率（默认 4fps 丝滑且极快）")
    args = parser.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg_with_drawtext()
    font_path = find_chinese_font()
    width, height, duration = probe_video(ffmpeg_bin, in_path)

    if args.chapters:
        ch_p = Path(args.chapters).expanduser()
        raw_ch = ch_p.read_text(encoding="utf-8") if ch_p.is_file() else args.chapters
    elif args.from_md:
        raw_ch = Path(args.from_md).expanduser().read_text(encoding="utf-8")
    else:
        raise SystemExit("[错误] 请通过 --chapters 或 --from-md 提供章节时间轴。")

    chapters = parse_chapters_from_text(raw_ch, duration)
    print(f"[*] 解析到 {len(chapters)} 个章节 ({width}x{height}, {duration:.1f}s):")
    for idx, ch in enumerate(chapters, 1):
        print(f"    {idx}. {ch['start']:6.1f}s -> {ch['end']:6.1f}s | {ch['title']}")

    strip_mov = out_path.with_name(f".{out_path.stem}_chapter_strip.mov")
    print(f"[*] 正在生成底部动态章节进度条条带 ({width}x{args.bar_height}, {args.fps}fps)...")
    render_bar_strip_mov(chapters, width, args.bar_height, duration, font_path, ffmpeg_bin, strip_mov, args.fps)

    # 组合滤镜：先 overlay 底部条带，再绘制避让字幕（y 上移 bar_height + 24px）
    fc = f"[0:v][1:v]overlay=0:{height - args.bar_height}:shortest=1[withbar]"
    map_v = "[withbar]"
    if args.srt:
        srt_p = Path(args.srt).expanduser().resolve()
        dt_chain = build_drawtext_chain(srt_p, font_path, args.bar_height + 24, width)
        if dt_chain:
            fc += f";[withbar]{dt_chain}[outv]"
            map_v = "[outv]"

    vcodec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
    v_args = ["-c:v", vcodec, "-b:v", "8000k"] if vcodec == "h264_videotoolbox" else ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast"]

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(in_path),
        "-i", str(strip_mov),
        "-filter_complex", fc,
        "-map", map_v,
        "-map", "0:a",
        *v_args,
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"[*] 正在压制最终成片 -> {out_path.name} ...")
    subprocess.run(cmd, check=True)
    strip_mov.unlink(missing_ok=True)
    print(f"[√] 完成！已输出带底部章节进度条成片: {out_path}")


if __name__ == "__main__":
    main()
