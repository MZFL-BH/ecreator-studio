#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ECreator Studio · 多平台分发编排桥接脚本 (distribute.py)
=======================================================
整合 `video-publisher`（基于 ego-browser 的草稿安全分发管线）与 `feishu_sync.py`：
1. 调用 `check-package.mjs` 按平台逐一校验视频、封面比例（3:4 / 4:3 / 16:9）、标题权重与话题标签；
2. 仅在 `video-publisher` 完成 onboarding 且用户显式执行 `--run` 时，调用 `run-safe-platforms.sh` 上传并填好草稿（严格停在最终发布按钮前）；
3. 支持附带 `--sync-feishu` 将状态回写到飞书多维表格；X (Twitter) 文案由 `video_publisher_package.json` 的 `xTwitter` 字段承载，交由 ego-browser 另行发帖。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_video_publisher_dir() -> Path:
    """按环境变量与常见 skill 目录解析 video-publisher 所在路径"""
    candidates = []
    if os.environ.get("VIDEO_PUBLISHER_DIR"):
        candidates.append(Path(os.environ["VIDEO_PUBLISHER_DIR"]).expanduser())
    candidates.extend([
        Path.home() / ".gemini" / "config" / "skills" / "video-publisher",
        Path.home() / ".agents" / "skills" / "video-publisher",
    ])
    for cand in candidates:
        if cand.is_dir():
            return cand
    return candidates[0]


VIDEO_PUBLISHER_DIR = resolve_video_publisher_dir()
SUPPORTED_VP_PLATFORMS = ("xiaohongshu", "douyin", "bilibili", "wechat_channels", "youtube")


def find_node() -> str:
    node = shutil.which("node")
    if node:
        return node
    nvm_node = Path.home() / ".nvm" / "versions" / "node"
    if nvm_node.exists():
        candidates = sorted(nvm_node.glob("*/bin/node"), reverse=True)
        if candidates:
            return str(candidates[0])
    raise SystemExit("未找到 node 可执行文件，请先安装 Node.js 或配置 PATH。")


def resolve_package(target: str) -> Path:
    p = Path(target).expanduser().resolve()
    if p.is_file():
        return p
    if p.is_dir():
        for name in ("video_publisher_package.json", "publish_package.json", "package.json"):
            cand = p / name
            if cand.is_file():
                return cand
    raise SystemExit(f"找不到分发包 JSON: {target}")


def run_checks(node: str, pkg_path: Path, vp_platforms: list[str], check_x: bool) -> bool:
    check_mjs = VIDEO_PUBLISHER_DIR / "scripts" / "check-package.mjs"
    if not check_mjs.exists():
        raise SystemExit(f"未找到 video-publisher 校验脚本: {check_mjs}")

    all_ok = True
    for plat in vp_platforms:
        res = subprocess.run(
            [node, str(check_mjs), plat, str(pkg_path)],
            capture_output=True,
            text=True,
        )
        print(f"=== [{plat}] check-package (exit={res.returncode}) ===")
        if res.stdout.strip():
            print(res.stdout.strip())
        if res.stderr.strip():
            print(res.stderr.strip(), file=sys.stderr)
        if res.returncode != 0:
            all_ok = False

    if check_x:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        tweets = data.get("xTwitter", {}).get("tweets", [])
        ok_x = isinstance(tweets, list) and len(tweets) > 0 and all(isinstance(t, str) and t.strip() for t in tweets)
        print(f"=== [x_twitter] check-package (ok={ok_x}, tweets={len(tweets)}) ===")
        if not ok_x:
            all_ok = False
    return all_ok


def check_onboarding(node: str) -> tuple[bool, dict]:
    cfg_mjs = VIDEO_PUBLISHER_DIR / "scripts" / "config.mjs"
    res = subprocess.run([node, str(cfg_mjs), "status"], capture_output=True, text=True)
    try:
        info = json.loads(res.stdout)
    except Exception:
        info = {"raw": res.stdout, "stderr": res.stderr}
    return res.returncode == 0 and not info.get("onboardingRequired", True), info


def main():
    parser = argparse.ArgumentParser(description="ECreator Studio 多平台分发桥接工具")
    parser.add_argument("target", help="工程目录或 video_publisher_package.json 路径")
    parser.add_argument("--platforms", default="xiaohongshu,douyin,bilibili", help="逗号分隔平台列表，如 xiaohongshu,douyin,bilibili,x")
    parser.add_argument("--task-suffix", default="", help="本次分发的 taskSpace 后缀")
    parser.add_argument("--check-only", action="store_true", help="仅校验封面比例与文案规范，不启动浏览器")
    parser.add_argument("--run", action="store_true", help="执行 video-publisher 草稿上传与填表（停在最终发布按钮前）")
    parser.add_argument("--confirm-original-rights", action="store_true", help="明确确认勾选原创/自制声明")
    parser.add_argument("--sync-feishu", action="store_true", help="同时同步工程状态到飞书多维表格")
    args = parser.parse_args()

    pkg_path = resolve_package(args.target)
    node = find_node()
    requested = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    vp_platforms = [p for p in requested if p in SUPPORTED_VP_PLATFORMS]
    check_x = "x" in requested or "twitter" in requested

    ok = run_checks(node, pkg_path, vp_platforms, check_x)
    if not ok:
        print("[!] 校验未通过，请先修复上述封面比例或文案超限问题。", file=sys.stderr)
        sys.exit(1)

    if args.run and not args.check_only and vp_platforms:
        onboarded, cfg_info = check_onboarding(node)
        if not onboarded:
            print("[!] video-publisher 尚未完成 onboarding，拒绝猜测账号配置。", file=sys.stderr)
            print(json.dumps(cfg_info, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(2)

        runner = VIDEO_PUBLISHER_DIR / "scripts" / "run-safe-platforms.sh"
        suffix = args.task_suffix or pkg_path.parent.name
        cmd = [
            "bash",
            str(runner),
            "--package", str(pkg_path),
            "--task-suffix", suffix,
            "--platforms", ",".join(vp_platforms),
        ]
        if args.confirm_original_rights:
            cmd.append("--confirm-original-rights")
        print(f"[→] 启动 video-publisher 草稿管线: {' '.join(cmd)}")
        vp_res = subprocess.run(cmd)
        if vp_res.returncode not in (0, 10):
            sys.exit(vp_res.returncode)

    if args.sync_feishu:
        feishu_py = Path(__file__).resolve().parent / "feishu_sync.py"
        subprocess.run(
            [sys.executable, str(feishu_py), str(pkg_path.parent), "--sync-platforms"],
            check=True,
        )


if __name__ == "__main__":
    main()
