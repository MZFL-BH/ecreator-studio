---
name: ecreator-studio
description: >-
  全流程自媒体创作者工作流（ECreator Studio，适配全平台作品系列 E-Lab / Ethan 实测）。当用户提到自媒体、短视频创作、选题调研、脚本分镜打磨、视频粗剪/字幕、多平台分发或数据复盘时使用。该技能内置交互式下拉执行门禁，支持全流程各环节的快速代操与执行。
---

# ECreator Studio · 自媒体全链路作战工作流（系列：E-Lab）

本技能为 **Ethan（全平台主系列：`E-Lab` / Ethan 实测）** 及开源自媒体创作者提供全生命周期生产支持。涵盖从灵感选题到发布复盘的完整链路，支持交互式选择与全自动动手代操。

---

## 阶段一：交互式下拉执行门禁（强制先验）

当该技能被触发时，**不要直接假设用户需求并堆砌长篇文字**。必须优先使用 `ask_question` 工具向用户抛出交互式单选下拉菜单，列出具体可执行的作战动作：

```json
{
  "questions": [
    {
      "question": "请从下方选择你要执行的 ECreator Studio 作战动作：",
      "options": [
        "(Recommended) 🎯 选题雷达与85分团队打分 (scout_topics.py: 扫描GitHub/HN/HF情报并裁决)",
        "⚡️ 阿杜模式·60fps代码动效与真人小窗混剪 (adu_motion.py: 60fps动效/字级高亮/真人小窗交接)",
        "🎙️ 对标扒取与Whisper打轴 (transcribe.py: yt-dlp+Whisper毫秒级转写+FFmpeg封装)",
        "🎬 一键流水线总装 (pipeline.py: 压制-14 LUFS + 封面截帧 + 飞书入库)",
        "📝 双角磨本 & 10分钟脚本定稿 (Writer×Viewer 交叉对齐爽点 + generate_script.py 锁定发前盲测单)",
        "🎨 预渲染高清对比卡片 (render_cards.py: Pillow 生成 1080x1920 对比/金句卡)",
        "✂️ 智能切除口播气口 (cut_silence.py: FFmpeg 自动切除静音停顿)",
        "📊 发后数据体检与复盘 (review.py: 赞播比/赞藏比/90天推荐池/P0诊断)",
        "🚀 发前2分钟盲测 & 多平台草稿分发 (对照盲测单抽帧/前15秒复核 -> distribute.py)",
        "☁️ 单独同步飞书多维表格 (feishu_sync.py: 本地物料与云端总表/核对子表同步)"
      ],
      "is_multi_select": false
    }
  ]
}
```

---

## 阶段二：选择后立即执行对应作业

用户选定对应动作后，Agent 立即定位目标工程目录（未指定时默认最新的工程或当前目录），并直接运行对应的底座脚本：

### 0. 🎯 选题雷达与 85 分 Rubric 评审 (cheat-on-content 规范)
运行 `scout_topics.py [选题名称] [--scan] [--recommend] [--save] [--init] [--sync-feishu]`：
- 抓取 GitHub Trending、Hacker News AI 争议榜与 Hugging Face 每日论文突破；
- 运行 **cheat-on-content 7 维度 Rubric 模型** (ER 顿悟感×1.5、HP 痛点狠话×1.5、QL 抄作业度×1.5、NA 递进弧线×1.0、AB 受众面×1.0、SR 风口共振×1.0、SAT 撕滤镜×1.0)；
- 换算为百分制综合分，严守 **`>= 85 分` (composite >= 8.5)** 的 S 级准入门槛；
- 自动生成 12 位稳定 hash id，持久化维护符合 `candidate-schema` 协议的 `candidates.md` 候选池；
- 支持 `--recommend` 排序推荐高质量储备，支持 `--init` 一键联动 `generate_script.py` 初始化出片工程。

### 1. 🎙️ 对标扒取与 Whisper 打轴 (yt-dlp + Whisper + FFmpeg)
运行 `transcribe.py <URL 或 本地音视频> [-o 输出目录] [--model base] [--embed]`：
- 传入网络链接（B站/抖音短链/YouTube）：`yt-dlp` 极速无损抓取，FFmpeg 转换 16kHz 高速音频缓存；
- 传入本地录制视频：调用本地 OpenAI Whisper 毫秒级打轴转写，输出 `.srt` 字幕、`.txt` 全文文稿与黄金 Hook 提炼；
- 支持 `--embed`：调用 FFmpeg 直接将 `.srt` 封装入成片软字幕轨。

### 2. ⚡️ 动效混剪与真人小窗引擎 (adu_motion.py)
- **核心模式**：真人全屏开场撕营销 ➡️ 动态缩入右下角圆角小窗 ➡️ 切回真人全屏特写点破潜规则 ➡️ 展示流程卡 ➡️ 指引资料包。
- **命令流水线**：
  - `python3 scripts/adu_motion.py init <工程目录> --topic "选题名称"`：初始化 60fps HTML5/Canvas 动效场景模板、`studio.html` 工作台与 `audio/sfx/*.wav` 音效；
  - `python3 scripts/adu_motion.py voice <工程目录>`（可选）：调用 `edge-tts` 生成配音母带；
  - `python3 scripts/adu_motion.py align <工程目录>`：本地 Whisper 提取毫秒级时间戳并输出 `audio/subtitles.srt` 与 `audio/subtitles.ass`；
  - `python3 scripts/adu_motion.py assemble <工程目录> [--cam <真人视频.mp4>]`：将渲染好的 `temp_scenes/merged_raw.mp4`、人声与音效按 `-14 LUFS` 混音总装为 `output/final_video.mp4`。

### 3. 🎬 一键流水线总装
运行 `pipeline.py <工程目录>`（需存在视频文件；如已安装外置 `ffmpeg-skill` / `oil-cover` 会联动执行，未安装时明确提示跳过）：
- 若已安装 `ffmpeg-skill`，执行 `-14 LUFS` 响度标准化与口播去静音；
- 若已安装 `oil-cover`，调用 `--skip-generate` 从视频截取封面候选帧至 `<视频名>.oil-cover/`；
- 执行 `feishu_sync.py` 将最新物料状态推入飞书多维表格。

### 4. 📝 双角磨本 & 10分钟爆款脚本定稿
在正式生成或落盘 `script.md` 之前，**先执行 5~8 分钟的「作家 × 挑剔观众」双角色交叉对练**（详情规范见 [02_script_storyboard.md](./references/02_script_storyboard.md)）：
- **角色切换**：手头有实操干货时由用户演作家、Agent 演 5 秒划走的挑剔路人；转化外网观点（如 `Deep Signal` 池）或卡灵感时由 Agent 先出 2~3 个切角初稿、用户来审稿毙掉虚话；
- **硬过三关**：① 前 5 秒废话清零与结果前置；② Before/After 真界面录屏证据清单（严禁把提词用的导播网页当正片录制）；③ 砍枝聚焦单一爽点，口播压在 450~600 字（1.5~2.5 分钟高密度）；
- **写脚本时同步锁死「发前 2 分钟盲测验收单」**：将开拍纯净镜头清单、前 15 秒必须交付的钩子与核心 Before/After 画面一并写入 `script.md` 顶部；再联动 `generate_script.py "<选题名称>" -t benchmark -c "<对标痛点>" -e "<实测证据>" --author "<作者名>" -o <输出目录>` 输出 `script.md`、`publish.md` 与 `video_publisher_package.json`。

### 5. 🎨 预渲染高清对比卡片
运行 `render_cards.py --type hook --title "<主标题>" --subtitle "<副标题>" --output <输出路径.png> [--duration 5]`：
- 基于 Pillow 渲染 `1080x1920` 竖版金句卡或对比卡（`--type comparison`），传入 `--duration > 0` 时可顺带导出 FFmpeg MP4 片段。

### 6. ✂️ 智能切除口播气口与实时章节进度条
运行 `cut_silence.py --input <输入视频.mp4> --output <输出视频.mp4> --noise -30dB --duration 0.4`：
- 基于 FFmpeg `silencedetect` 自动扫描并切除超过指定时长的静音/思考停顿片段。

运行 `chapter_bar.py --input <视频.mp4> --output <带进度条成片.mp4> --from-md <publish.md 或 script.md> [--srt <字幕.srt>]`：
- 自动提取 `00:00 章节短标题` 生成底部实时高亮分段章节进度条（已播/当前段白底蓝线平滑推进，未播段深炭磨砂底）；
- 传入 `--srt` 时同步烧录硬字幕，并自动将字幕上抬避让进度条区域。

### 7. 📊 发后数据体检与复盘
运行 `review.py <工程目录> --views <播放量> --likes <点赞> --saves <收藏> --bounce2s <跳出率> --retention5s <完播率> --notes "<观察备注>"`：
- 自动计算赞播比与赞藏比，输出 🔴 P0 / 🟠 P1 / 🟡 P2 级别体检报告 `review.md`。

### 8. ☁️ 单独同步飞书多维表格
运行 `feishu_sync.py <工程目录> [--sync-platforms]`：
- 秒级同步本地工程状态、分镜完成度、核心痛点与产物清单至飞书多维表格「AI自媒体自动化·选题与出片总表」；
- 带 `--sync-platforms` 时，自动读取 `preflight_report.json` 或 `~/.video-publisher/v2-jobs/*/state.json`，把各平台实际标题、定时时间、封面与卡点明细写入「分平台分发与数据明细」子表。
- 跨账号复用：支持通过 `~/.config/ecreator-studio/feishu.json`（兼容 `~/.config/creator-studio/feishu.json`）或环境变量 `FEISHU_BASE_URL` / `FEISHU_SUBTABLE_URL` 覆盖为个人飞书表。

### 9. 🚀 发前盲测、多平台校验与草稿分发
1. **口播精剪（外置可选技能）**：原始口播素材可先经 `cangshu-koubo-wudongxiao` / `cangshu-koubo-motion-edit` 产出成片；
2. **发前 2 分钟冷血盲测门禁（Pre-Release Gate）**：在进入分发之前，从成片抽取前 `15s` 字幕与 `0s / 3s / 15s / 45s` 关键帧，由 Agent 以“完全没看过脚本的新观众”视角对照 `script.md` 顶部预先锁定的盲测验收单复核——若前 5 秒仍出现“哈喽大家好”、露出杂乱书签栏/导播提词网页、或未在前半段亮出约定 Before/After 实机画面，优先拦截并重录 10 秒开头，不带病硬发；
3. **多平台打包校验与安全分发**：盲测通过且封面就位后，运行 `python3 scripts/distribute.py <工程目录> --platforms xiaohongshu,douyin,wechat_channels,youtube,bilibili,x --check-only` 校验文案、视频与多比例封面；前置安装 `video-publisher` 与 `ego-browser` 并完成账号 onboarding 后，加 `--run --confirm-original-rights --sync-feishu` 即可统一推进到最终发布按钮前并自动把核对明细回写飞书。
3. **🎨 封面复用实验清单（下期视频 2 选 1 固化）**：已确立首版 `E-Lab` 视觉基线（浅奶油/雾蓝网格底 + 顶部独立品牌锁标 + `4+4` 主标题/高对比实心胶囊 + 右侧 8° 轻透视裁切证据窗 + 代码确定性合成 `ethan-cutout.png` 三画幅）。为消除此前 `agent-native` 三轮生图（Base/Refined/Brand Boost 9 次调用）的 Token 与配额消耗，**下期新视频优先做一次二选一实测并定型默认方案**：
   - **方案 A（零 API 本地模板流）**：用 `ecreator-studio` HTML/CSS 无头渲染模板 + `ethan-cutout.png` 直出 `3:4`/`4:3`/`16:9`，零生图费用、中文锐度最高，优先用于录屏界面本身干净的实操期数；
   - **方案 B（单轮直出 AI 重绘流）**：固化已验证过关的三画幅 Prompt 骨架走 `oil-cover` 单轮直出（必要时叠 HTML 品牌补丁），跳过多轮试错，仅在原始界面极杂乱需 AI 概括重绘时启用。

---

## 参考方法论与实战指南
- [01 选题与对标侦察指南](./references/01_topic_research.md)
- [02 脚本与分镜抗压指南](./references/02_script_storyboard.md)
- [03 剪辑与字幕优化指南](./references/03_editing_workflow.md)
- [04 发布分发与数据复盘指南](./references/04_distribution_analytics.md)
- [05 六年自媒体老兵核心实战铁律](./references/05_veteran_rules.md)
