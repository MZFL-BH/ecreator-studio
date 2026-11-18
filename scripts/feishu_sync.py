#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Feishu Bitable Sync Tool for Creator Studio
-------------------------------------------
自动解析本地自媒体选题工程目录，将标题、分镜状态、核心痛点、产物清单与素材路径
一键无缝同步至飞书多维表格「AI自媒体自动化·选题与出片总表」。

支持单目录同步与全量素材目录扫描同步。
"""

import os
import sys
import json
import re
import argparse
import subprocess
from pathlib import Path

# 默认飞书多维表格配置（他人复用时可通过 ~/.config/creator-studio/feishu.json 或环境变量覆盖）
_DEFAULT_FEISHU_BASE_URL = "https://my.feishu.cn/base/KWl2bUe9fa5CKvsctVjcSb59nVb?table=tblKLLxJdPltUSA5&view=vewgDwbRSG"
_DEFAULT_FEISHU_SUBTABLE_URL = "https://my.feishu.cn/base/KWl2bUe9fa5CKvsctVjcSb59nVb?table=tblMSFUmoFx8YEX4&view=vewmaAjzhI"
DEFAULT_SPACE_NAME = "creator-feishu-sync"
DEFAULT_PROFILE_ID = os.environ.get("EGO_PROFILE_ID", "Profile 1")

_DEFAULT_FIELD_IDS = {
    "title": "fldMBxOfhS",        # 选题标题 (Text)
    "status": "fldDnDxtyr",       # 流程状态 (Single Select)
    "ref_link": "fldorZE7Oc",     # 对标参考链接 (URL)
    "hook": "fldw722Mbu",         # 核心爆点/痛点 (Text)
    "path": "fld3sPw8TB",         # 本地素材路径 (Text)
    "assets": "fldXDDYDhM",       # 成片与文案 (Text)
    "platforms": "fldJoy3bbJ",    # 分发平台 (Multi Select)
    "views": "fldWqEuIEh"         # 全网播放数据 (Number)
}

_DEFAULT_SUBTABLE_FIELD_IDS = {
    "topic": "fldnREQayU",          # 选题名称 (Text)
    "platform": "fldVagiZla",       # 平台 (Single Select)
    "status": "fld6ykUcuQ",         # 分发状态 (Single Select)
    "schedule_time": "fldHarOhYF",  # 定时与发布时间 (Text)
    "actual_title": "flduMEXEm1",   # 实际标题与短标题 (Text)
    "check_details": "fldadDUNWz",  # 核对明细 (Text)
    "space_or_link": "fldw7sdoZE",  # Ego空间与链接 (Text)
    "views": "fld9n3dJgm",          # 播放量 (Number)
    "likes": "fld9E93WiB",          # 点赞 (Number)
    "saves": "fldmM7Futb",          # 收藏 (Number)
    "comments": "fldFdKOfHR",       # 评论 (Number)
    "bounce_2s": "fldKWW8aXM",      # 前2秒跳出率(%) (Number)
    "retention_5s": "fldkiTWTQh",   # 5秒完播率(%) (Number)
    "diagnosis": "fldq7oZUpb",      # 复盘诊断结论 (Text)
}


def _load_feishu_config():
    """加载飞书多维表格配置，支持外部配置文件与环境变量覆盖以方便跨账号复用"""
    cfg_path = Path(os.environ.get("CREATOR_STUDIO_FEISHU_CONFIG") or (Path.home() / ".config" / "creator-studio" / "feishu.json")).expanduser()
    cfg = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    base_url = os.environ.get("FEISHU_BASE_URL") or cfg.get("base_url") or _DEFAULT_FEISHU_BASE_URL
    subtable_url = os.environ.get("FEISHU_SUBTABLE_URL") or cfg.get("subtable_url") or _DEFAULT_FEISHU_SUBTABLE_URL
    field_ids = {**_DEFAULT_FIELD_IDS, **(cfg.get("field_ids") or {})}
    if os.environ.get("FEISHU_FIELD_IDS"):
        field_ids.update(json.loads(os.environ["FEISHU_FIELD_IDS"]))
    subtable_field_ids = {**_DEFAULT_SUBTABLE_FIELD_IDS, **(cfg.get("subtable_field_ids") or {})}
    if os.environ.get("FEISHU_SUBTABLE_FIELD_IDS"):
        subtable_field_ids.update(json.loads(os.environ["FEISHU_SUBTABLE_FIELD_IDS"]))
    return base_url, subtable_url, field_ids, subtable_field_ids


FEISHU_BASE_URL, FEISHU_SUBTABLE_URL, FIELD_IDS, SUBTABLE_FIELD_IDS = _load_feishu_config()

PLATFORM_DISPLAY_MAP = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "wechat_channels": "微信视频号",
    "youtube": "YouTube",
    "bilibili": "B站",
    "x": "X",
}


def parse_project_dir(dir_path: Path) -> dict:
    """解析单个视频工程目录的元信息与产物状态"""
    dir_path = dir_path.resolve()
    if not dir_path.is_dir():
        return None

    dir_name = dir_path.name
    # 过滤非工程目录（如隐藏目录、纯封面图库、通用辅助文件夹）
    if dir_name.startswith(".") or dir_name in ["封面合集", "品牌资产", "other", "grokbot-ui-shots", "剪辑提升", "剪辑精进"]:
        return None

    # 1. 寻找脚本文件
    script_candidates = list(dir_path.glob("*脚本*.md")) + list(dir_path.glob("*script*.md"))
    script_file = script_candidates[0] if script_candidates else None

    # 2. 寻找发布文案
    publish_candidates = list(dir_path.glob("*发布*.md")) + list(dir_path.glob("publish*.md")) + list(dir_path.glob("04-小红书*.md"))
    publish_file = publish_candidates[0] if publish_candidates else None

    # 3. 寻找口播字幕
    voice_candidates = list(dir_path.glob("voiceover*.txt")) + list(dir_path.glob("*字幕*.md")) + list(dir_path.glob("*字幕*.txt"))
    voice_file = voice_candidates[0] if voice_candidates else None

    # 4. 寻找视频产物（兼容 delivery/、output/、cangshu 的 edit_* 目录）
    videos = (
        list(dir_path.glob("*.mp4"))
        + (list((dir_path / "delivery").glob("*.mp4")) if (dir_path / "delivery").exists() else [])
        + (list((dir_path / "output").glob("*.mp4")) if (dir_path / "output").exists() else [])
        + [p for p in dir_path.glob("edit_*/*成片*.mp4")]
        + [p for p in dir_path.glob("edit_*/cut.mp4")]
    )
    seen_v = set()
    video_names = []
    for v in videos:
        rp = str(v.resolve())
        if rp not in seen_v:
            seen_v.add(rp)
            video_names.append(v.name)

    # 没有脚本且没有视频的目录大概率不是视频工程
    if not script_file and not videos:
        return None

    # --- 提炼选题标题 ---
    title = ""
    hook = ""
    if script_file and script_file.exists():
        try:
            content = script_file.read_text(encoding="utf-8")
            # 提取第一个 # 一级标题
            h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            
            # 提取黄金 3 秒 / Hook / 痛点
            hook_match = re.search(r"(?:HOOK|出镜 ①|开头|痛点).*?\n(?:.*?\n){0,3}?(?:口播|台词)[:：]\s*(.+)", content)
            if hook_match:
                hook = hook_match.group(1).strip()
            elif h1_match:
                # 备选提取正文首段有实质内容的文字
                paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.strip().startswith("#")]
                if paragraphs:
                    hook = paragraphs[0][:150].replace("\n", " ")
        except Exception:
            pass

    # 若未提取到标题，回退使用目录名清洗版
    if not title:
        # 去掉如 20261030- 前缀
        clean_name = re.sub(r"^\d{4,8}-?", "", dir_name)
        title = clean_name.strip() or dir_name

    # --- 判定流程状态 ---
    # 状态池: 待确认 | 脚本已出 | 待录制出镜 | 成片已渲染 | 已分发
    status = "待确认"
    has_final_video = any(re.search(r"(final|v\d+).*\.mp4", v, re.IGNORECASE) for v in video_names)
    has_silent_draft = any("silent" in v.lower() for v in video_names) or (dir_path / "NEXT-FOR-ETHAN.md").exists()
    has_published_flag = (dir_path / "08-发布检查清单.md").exists() or (dir_path / "published.flag").exists()
    has_review = (dir_path / "review.md").exists()

    views_count = 0
    if has_review:
        status = "已复盘"
        try:
            rev_text = (dir_path / "review.md").read_text(encoding="utf-8")
            vm = re.search(r'\*\*总播放量\*\*\s*\|\s*([\d,]+)', rev_text)
            if vm:
                views_count = int(vm.group(1).replace(",", ""))
        except Exception:
            pass
    elif has_published_flag:
        status = "已分发"
    elif has_final_video:
        status = "成片已渲染"
    elif has_silent_draft:
        status = "待录制出镜"
    elif script_file:
        status = "脚本已出"

    # --- 产物文件清单汇总 ---
    asset_list = []
    if script_file:
        asset_list.append(script_file.name)
    if publish_file:
        asset_list.append(publish_file.name)
    if voice_file:
        asset_list.append(voice_file.name)
    for v in video_names[:2]:
        asset_list.append(v)
    if len(video_names) > 2:
        asset_list.append(f"+{len(video_names)-2}个视频")

    covers = list(dir_path.glob("封面*.png")) + list(dir_path.glob("*封面*.png"))
    if covers:
        asset_list.append(f"封面({len(covers)}张)")

    assets_str = ", ".join(asset_list)

    # 默认分发平台
    platforms = ["B站", "小红书", "抖音", "视频号"]

    return {
        "title": title,
        "status": status,
        "ref_link": "",
        "hook": hook[:200] if hook else "针对目标用户核心工作流的痛点实测与效率对比",
        "path": str(dir_path),
        "assets": assets_str,
        "platforms": platforms,
        "views": views_count
    }


def sync_record_via_browser(record: dict) -> bool:
    """通过 ego-browser 调用已登录的飞书会话，将记录提交到多维表格"""
    m = re.search(r"/base/([A-Za-z0-9]+)", FEISHU_BASE_URL)
    base_token = m.group(1) if m else "KWl2bUe9fa5CKvsctVjcSb59nVb"
    node_script = f"""
let task;
try {{
    task = await taskSpace("{DEFAULT_SPACE_NAME}", {{ profileId: "{DEFAULT_PROFILE_ID}" }});
}} catch (e) {{
    if (e.message && e.message.includes("already exists")) {{
        task = await taskSpace("{DEFAULT_SPACE_NAME}");
    }} else {{
        throw e;
    }}
}}
const page = task.page("p1");

const record = {json.dumps(record, ensure_ascii=False)};

// 1. 确保在目标表格页面
const currentUrl = await page.url();
if (!currentUrl.includes("{base_token}")) {{
    console.log("Navigating to Bitable...");
    await page.goto("{FEISHU_BASE_URL}", {{ waitUntil: "domcontentloaded", timeout: 30000 }});
    await page.waitForTimeout(4000);
}}

// 2. 清理残余遮罩/抽屉
await page.evaluate(() => {{
    const closeBtn = document.querySelector('.bitable-card-modal-header-v2-btn-close');
    if (closeBtn) closeBtn.click();
    const mask = document.querySelector('.bitable-drawer-card-mask');
    if (mask) mask.click();
}});
await page.waitForTimeout(500);

// 3. 点击「添加记录」
console.log("Opening Add Record modal...");
await page.click('.bitable-add-record-toolbar-button__main');
await page.waitForTimeout(1500);

// 辅助方法：填充 Slate 编辑器字段
async function fillField(fieldId, text) {{
    if (!text) return;
    const selector = `[data-field-id="${{fieldId}}"] [contenteditable="true"]`;
    const exists = await page.evaluate((sel) => !!document.querySelector(sel), selector);
    if (exists) {{
        await page.click(selector);
        await page.waitForTimeout(100);
        await page.keyboard.press('Meta+A');
        await page.keyboard.press('Backspace');
        await page.keyboard.type(text);
        await page.waitForTimeout(200);
    }}
}}

// 4. 填充 选题标题
await fillField("{FIELD_IDS['title']}", record.title);

// 5. 选中 流程状态
if (record.status) {{
    await page.evaluate((targetStatus) => {{
        const el = document.querySelector('[data-field-id="{FIELD_IDS['status']}"]');
        if (el) {{
            const pills = Array.from(el.querySelectorAll('li.b-select-option'));
            const matched = pills.find(p => p.innerText.trim() === targetStatus);
            if (matched) matched.click();
        }}
    }}, record.status);
    await page.waitForTimeout(300);
}}

// 6. 填充 对标参考链接
if (record.ref_link) {{
    await fillField("{FIELD_IDS['ref_link']}", record.ref_link);
}}

// 7. 填充 核心爆点/痛点
if (record.hook) {{
    await fillField("{FIELD_IDS['hook']}", record.hook);
}}

// 8. 填充 本地素材路径
if (record.path) {{
    await fillField("{FIELD_IDS['path']}", record.path);
}}

// 9. 填充 成片与文案清单
if (record.assets) {{
    await fillField("{FIELD_IDS['assets']}", record.assets);
}}

// 10. 勾选 分发平台
if (record.platforms && record.platforms.length > 0) {{
    await page.evaluate((targetPlatforms) => {{
        const el = document.querySelector('[data-field-id="{FIELD_IDS['platforms']}"]');
        if (el) {{
            const pills = Array.from(el.querySelectorAll('li.b-select-option'));
            pills.forEach(p => {{
                if (targetPlatforms.includes(p.innerText.trim())) {{
                    p.click();
                }}
            }});
        }}
    }}, record.platforms);
    await page.waitForTimeout(300);
}}

// 11. 填充 全网播放数据
if (record.views !== undefined) {{
    const numSel = '#number-editor-input-{FIELD_IDS['views']}';
    const exists = await page.evaluate((sel) => !!document.querySelector(sel), numSel);
    if (exists) {{
        await page.fill(numSel, String(record.views));
        await page.waitForTimeout(200);
    }}
}}

// 12. 点击「提交」
console.log("Submitting record...");
await page.evaluate(() => {{
    const card = document.querySelector('.bitable-card-modal-v2');
    if (card) {{
        const btn = Array.from(card.querySelectorAll('button')).find(b => b.innerText.trim() === '提交');
        if (btn) btn.click();
    }}
}});
await page.waitForTimeout(2500);

// 关闭抽屉并清理临时同步空间
await page.evaluate(() => {{
    const closeBtn = document.querySelector('.bitable-card-modal-header-v2-btn-close');
    if (closeBtn) closeBtn.click();
}});
await page.waitForTimeout(800);
await task.finish({{ keep: [] }});
console.log("SUCCESS_SYNC_RECORD");
"""

    # 调用 ego-browser 运行该嵌入脚本
    ego_bin = "ego-browser"
    fallback_ego = Path.home() / ".local" / "bin" / "ego-browser"
    if fallback_ego.exists():
        ego_bin = str(fallback_ego)
    proc = subprocess.run(
        [ego_bin, "nodejs"],
        input=node_script,
        text=True,
        capture_output=True
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and "SUCCESS_SYNC_RECORD" in output:
        return True
    else:
        print(f"[-] 同步失败: {output}")
        return False


def _load_latest_vp_states(package_path: Path) -> dict:
    """读取 ~/.video-publisher/v2-jobs/*/state.json 中与当前分发包匹配的各平台最新核对状态"""
    jobs_root = Path.home() / ".video-publisher" / "v2-jobs"
    if not jobs_root.exists():
        return {}
    target_resolved = str(package_path.resolve())
    merged = {}
    candidates = []
    for state_file in jobs_root.glob("*/state.json"):
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(Path(data.get("packagePath", "")).expanduser().resolve()) == target_resolved:
            candidates.append((data.get("updatedAt", ""), data))
    candidates.sort(key=lambda item: item[0])
    for _, job in candidates:
        for plat, pinfo in (job.get("platforms") or {}).items():
            merged[plat] = pinfo
    return merged


def build_platform_preflight_records(dir_path: Path, topic_title: str) -> list[dict]:
    """从 preflight_report.json 或 video_publisher_package.json + state.json 生成分平台核对明细行"""
    dir_path = dir_path.resolve()
    report_file = dir_path / "preflight_report.json"
    if report_file.exists():
        data = json.loads(report_file.read_text(encoding="utf-8"))
        raw_records = data.get("records") or data.get("platforms") or []
        out = []
        for item in raw_records:
            out.append({
                "topic": item.get("topic") or topic_title,
                "platform": item.get("platform", ""),
                "status": item.get("status", "草稿已就绪"),
                "schedule_time": item.get("schedule_time", ""),
                "actual_title": item.get("actual_title", ""),
                "check_details": item.get("check_details", ""),
                "space_or_link": item.get("space_or_link", ""),
            })
        return [r for r in out if r["platform"]]

    pkg_file = dir_path / "video_publisher_package.json"
    if not pkg_file.exists():
        return []
    pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
    vp_states = _load_latest_vp_states(pkg_file)

    title_map = {
        "xiaohongshu": pkg.get("xhsTitle") or pkg.get("title", ""),
        "douyin": pkg.get("douyinTitle") or pkg.get("title", ""),
        "wechat_channels": pkg.get("wechatTitle") or pkg.get("title", ""),
        "bilibili": pkg.get("bilibiliTitle") or pkg.get("title", ""),
        "youtube": pkg.get("youtubeTitle") or pkg.get("title", ""),
    }
    records = []
    for key in ("xiaohongshu", "douyin", "wechat_channels", "youtube", "bilibili"):
        st = vp_states.get(key)
        if not st and not title_map.get(key):
            continue
        ready = bool(st and st.get("ready"))
        blocker_msg = (st or {}).get("verdict", {}).get("blocker", {})
        if isinstance(blocker_msg, dict):
            blocker_msg = blocker_msg.get("message", "")
        status = "草稿已就绪" if ready else "卡点待处理"
        details = "已通过 video-publisher 门禁核验" if ready else (blocker_msg or "待运行分发草稿管线")
        space_id = (st or {}).get("taskSpaceId")
        records.append({
            "topic": topic_title,
            "platform": PLATFORM_DISPLAY_MAP.get(key, key),
            "status": status,
            "schedule_time": "",
            "actual_title": title_map.get(key, ""),
            "check_details": details,
            "space_or_link": f"Ego Space {space_id}" if space_id else "",
        })

    x_tweets = (pkg.get("xTwitter") or {}).get("tweets") or []
    if x_tweets:
        records.append({
            "topic": topic_title,
            "platform": "X",
            "status": "草稿已就绪" if not vp_states else "卡点待处理",
            "schedule_time": "",
            "actual_title": x_tweets[0].splitlines()[0][:80],
            "check_details": f"X 文案共 {len(x_tweets)} 条；视频与发帖弹窗按脚本或人工确认",
            "space_or_link": "",
        })
    return records


def sync_platform_records_via_browser(records: list[dict], screenshot_path: str = "") -> bool:
    """将分平台核对明细批量写入飞书「分平台分发与数据明细」子表"""
    if not records:
        return True

    space_name = f"{DEFAULT_SPACE_NAME}-sub"
    fids = SUBTABLE_FIELD_IDS
    node_script = f"""
let task;
try {{
    task = await taskSpace("{space_name}", {{ profileId: "{DEFAULT_PROFILE_ID}" }});
}} catch (e) {{
    if (e.message && (e.message.includes("already exists") || e.message.includes("user"))) {{
        task = await taskSpace("{space_name}-" + Date.now(), {{ profileId: "{DEFAULT_PROFILE_ID}" }});
    }} else {{
        throw e;
    }}
}}
const page = task.page("p1");
const records = {json.dumps(records, ensure_ascii=False)};

console.log("Navigating to Feishu subtable...");
await page.goto("{FEISHU_SUBTABLE_URL}", {{ waitUntil: "domcontentloaded", timeout: 30000 }});
await page.waitForTimeout(4500);

await page.evaluate(() => {{
    const close = document.querySelector('.ud__modal-close, [class*="modal"] [class*="close"]');
    if (close) close.click();
    const closeCard = document.querySelector('.bitable-card-modal-header-v2-btn-close');
    if (closeCard) closeCard.click();
}});
await page.waitForTimeout(500);

async function fillTextField(fieldId, text) {{
    if (!text) return;
    const selector = `[data-field-id="${{fieldId}}"] [contenteditable="true"]`;
    const exists = await page.evaluate((sel) => !!document.querySelector(sel), selector);
    if (exists) {{
        await page.click(selector);
        await page.waitForTimeout(100);
        await page.keyboard.press('Meta+A');
        await page.keyboard.press('Backspace');
        await page.keyboard.insertText(String(text));
        await page.waitForTimeout(150);
    }}
}}

async function selectSingleOption(fieldId, targetText) {{
    if (!targetText) return;
    const found = await page.evaluate(([fid, target]) => {{
        const el = document.querySelector(`[data-field-id="${{fid}}"]`);
        if (!el) return true;
        const pills = Array.from(el.querySelectorAll('li.b-select-option'));
        const matched = pills.find(p => p.innerText.trim() === target);
        if (matched) {{
            matched.click();
            return true;
        }}
        return false;
    }}, [fieldId, targetText]);
    if (!found) {{
        const focused = await page.evaluate((fid) => {{
            const wrap = document.querySelector(`[data-field-id="${{fid}}"]`);
            if (!wrap) return false;
            const trigger = wrap.querySelector('.b-select-selector, .b-select, [class*="select"]');
            if (trigger) trigger.click();
            const inp = wrap.querySelector('input');
            if (inp) {{
                inp.focus();
                return true;
            }}
            return false;
        }}, fieldId);
        if (focused) {{
            await page.waitForTimeout(200);
            await page.keyboard.insertText(String(targetText));
            await page.waitForTimeout(350);
            const clicked = await page.evaluate(([fid, target]) => {{
                const el = document.querySelector(`[data-field-id="${{fid}}"]`);
                const pills = Array.from(el?.querySelectorAll('li.b-select-option') || []);
                const exact = pills.find(p => p.innerText.trim() === target);
                if (exact) {{
                    exact.click();
                    return true;
                }}
                return false;
            }}, [fieldId, targetText]);
            if (!clicked) {{
                await page.keyboard.press('Enter');
            }}
        }}
    }}
    await page.waitForTimeout(250);
}}

for (const rec of records) {{
    await page.click('.bitable-add-record-toolbar-button__main');
    await page.waitForTimeout(1200);

    await fillTextField("{fids['topic']}", rec.topic);
    await selectSingleOption("{fids['platform']}", rec.platform);
    await selectSingleOption("{fids['status']}", rec.status);
    await fillTextField("{fids['schedule_time']}", rec.schedule_time);
    await fillTextField("{fids['actual_title']}", rec.actual_title);
    await fillTextField("{fids['check_details']}", rec.check_details);
    await fillTextField("{fids['space_or_link']}", rec.space_or_link);

    await page.evaluate(() => {{
        const card = document.querySelector('.bitable-card-modal-v2');
        if (card) {{
            const btn = Array.from(card.querySelectorAll('button')).find(b => b.innerText.trim() === '提交');
            if (btn) btn.click();
        }}
    }});
    await page.waitForTimeout(1800);

    await page.evaluate(() => {{
        const closeBtn = document.querySelector('.bitable-card-modal-header-v2-btn-close');
        if (closeBtn) closeBtn.click();
    }});
    await page.waitForTimeout(500);
    console.log("Synced platform row:", rec.platform);
}}

const shotPath = {json.dumps(screenshot_path)};
if (shotPath) {{
    await page.waitForTimeout(800);
    await page.screenshot({{ path: shotPath }});
}}
await task.finish({{ keep: [] }});
console.log("SUCCESS_SYNC_SUBTABLE");
"""
    ego_bin = "ego-browser"
    fallback_ego = Path.home() / ".local" / "bin" / "ego-browser"
    if fallback_ego.exists():
        ego_bin = str(fallback_ego)
    proc = subprocess.run(
        [ego_bin, "nodejs"],
        input=node_script,
        text=True,
        capture_output=True
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and "SUCCESS_SYNC_SUBTABLE" in output:
        return True
    print(f"[-] 子表同步失败: {output}")
    return False


def main():
    parser = argparse.ArgumentParser(description="飞书多维表格自动化同步工具")
    parser.add_argument("target", nargs="?", default=".", help="待同步的选题工程目录路径（默认当前目录）")
    parser.add_argument("--scan", action="store_true", help="扫描目标目录下所有子工程批量同步")
    parser.add_argument("--sync-platforms", action="store_true", help="同步分平台发前核对明细至「分平台分发与数据明细」子表")
    parser.add_argument("--platforms-only", action="store_true", help="仅同步分平台子表，跳过主表新增（避免重复建行）")
    parser.add_argument("--screenshot", default="", help="可选：子表写入完成后的截图保存路径")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()

    if args.scan:
        print(f"[*] 开始扫描目录: {target_path}")
        subdirs = sorted([d for d in target_path.iterdir() if d.is_dir()])
        records_to_sync = []
        for d in subdirs:
            rec = parse_project_dir(d)
            if rec:
                records_to_sync.append(rec)
        
        print(f"[+] 识别出 {len(records_to_sync)} 个有效自媒体工程:")
        for r in records_to_sync:
            print(f"  - [{r['status']}] {r['title']} ({Path(r['path']).name})")
        
        print("\n[*] 开始批量同步至飞书多维表格...")
        success_count = 0
        for r in records_to_sync:
            print(f" -> 正在推送: {r['title']} ...")
            if sync_record_via_browser(r):
                print(f"    [OK] 成功")
                success_count += 1
            else:
                print(f"    [FAIL] 失败")
        print(f"\n[√] 批量同步完成: 成功 {success_count} / {len(records_to_sync)}")

    else:
        rec = parse_project_dir(target_path)
        if not rec:
            print(f"[-] 目录 {target_path} 未识别到有效的脚本或视频产物。")
            sys.exit(1)

        if not args.platforms_only:
            print(f"[*] 解析到自媒体工程信息:")
            print(f"  - 选题标题:   {rec['title']}")
            print(f"  - 流程状态:   {rec['status']}")
            print(f"  - 核心痛点:   {rec['hook']}")
            print(f"  - 交付清单:   {rec['assets']}")
            print(f"  - 素材路径:   {rec['path']}")
            print(f"  - 分发平台:   {', '.join(rec['platforms'])}")
            print(f"\n[*] 正在同步主表至飞书...")

            if sync_record_via_browser(rec):
                print(f"[√] 成功同步至飞书「AI自媒体自动化·选题与出片总表」！")
            else:
                print(f"[-] 主表同步失败，请检查浏览器会话状态。")

        if args.sync_platforms or args.platforms_only:
            plat_records = build_platform_preflight_records(target_path, rec["title"])
            if not plat_records:
                print("[!] 未找到分平台核对记录或分发包。")
            else:
                print(f"\n[*] 正在同步 {len(plat_records)} 条分平台核对明细至飞书子表...")
                if sync_platform_records_via_browser(plat_records, screenshot_path=args.screenshot):
                    print(f"[√] 成功写入「分平台分发与数据明细」子表（共 {len(plat_records)} 条）！")
                else:
                    print("[-] 子表同步失败，请检查浏览器会话状态。")


if __name__ == "__main__":
    main()
