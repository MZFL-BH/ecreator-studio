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
        "📝 10分钟爆款脚本生成 (generate_script.py: 传入选题生成短句重音脚本与三平台文案)",
        "🎨 预渲染高清对比卡片 (render_cards.py: Pillow 生成 1080x1920 对比/金句卡)",
        "✂️ 智能切除口播气口 (cut_silence.py: FFmpeg 自动切除静音停顿)",
        "📊 发后数据体检与复盘 (review.py: 赞播比/赞藏比/90天推荐池/P0诊断)",
        "🚀 多平台校验与草稿分发 (distribute.py: 封面比例校验 + video-publisher + 飞书核对明细)",
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

### 4. 📝 10分钟爆款脚本生成
运行 `generate_script.py "<选题名称>" -t benchmark -c "<对标痛点>" -e "<实测证据>" --author "<作者名>" -o <输出目录>`：
- 自动生成带黄金 3 秒、重音标记与画中画指示的 `script.md`；
- 自动生成小红书、B站、抖音、X 多平台文案 `publish.md` 与含 YouTube 必填字段的 `video_publisher_package.json`。

### 5. 🎨 预渲染高清对比卡片
运行 `render_cards.py --type hook --title "<主标题>" --subtitle "<副标题>" --output <输出路径.png> [--duration 5]`：
- 基于 Pillow 渲染 `1080x1920` 竖版金句卡或对比卡（`--type comparison`），传入 `--duration > 0` 时可顺带导出 FFmpeg MP4 片段。

### 6. ✂️ 智能切除口播气口
运行 `cut_silence.py --input <输入视频.mp4> --output <输出视频.mp4> --noise -30dB --duration 0.4`：
- 基于 FFmpeg `silencedetect` 自动扫描并切除超过指定时长的静音/思考停顿片段。

### 7. 📊 发后数据体检与复盘
运行 `review.py <工程目录> --views <播放量> --likes <点赞> --saves <收藏> --bounce2s <跳出率> --retention5s <完播率> --notes "<观察备注>"`：
- 自动计算赞播比与赞藏比，输出 🔴 P0 / 🟠 P1 / 🟡 P2 级别体检报告 `review.md`。

### 8. ☁️ 单独同步飞书多维表格
运行 `feishu_sync.py <工程目录> [--sync-platforms]`：
- 秒级同步本地工程状态、分镜完成度、核心痛点与产物清单至飞书多维表格「AI自媒体自动化·选题与出片总表」；
- 带 `--sync-platforms` 时，自动读取 `preflight_report.json` 或 `~/.video-publisher/v2-jobs/*/state.json`，把各平台实际标题、定时时间、封面与卡点明细写入「分平台分发与数据明细」子表。
- 跨账号复用：支持通过 `~/.config/ecreator-studio/feishu.json`（兼容 `~/.config/creator-studio/feishu.json`）或环境变量 `FEISHU_BASE_URL` / `FEISHU_SUBTABLE_URL` 覆盖为个人飞书表。

### 9. 🚀 多平台校验、草稿分发与外置技能联动
1. **口播精剪（外置可选技能）**：原始口播素材可先经 `cangshu-koubo-wudongxiao` / `cangshu-koubo-motion-edit` 产出成片；
2. **多平台打包校验与安全分发**：成片与封面就位后，运行 `python3 scripts/distribute.py <工程目录> --platforms xiaohongshu,douyin,wechat_channels,youtube,bilibili,x --check-only` 校验文案、视频与多比例封面；前置安装 `video-publisher` 与 `ego-browser` 并完成账号 onboarding 后，加 `--run --confirm-original-rights --sync-feishu` 即可统一推进到最终发布按钮前并自动把核对明细回写飞书。
3. **⚠️ 封面视觉升级待优化事项（V2 Backlog）**：当前多比例封面仅在视频抽帧基础上做信息卡片叠加，人物主体分离、视觉层次与强点击钩子仍有较大提升空间，后续版本将继续专项打磨。

---

## 参考方法论与实战指南
- [01 选题与对标侦察指南](./references/01_topic_research.md)
- [02 脚本与分镜抗压指南](./references/02_script_storyboard.md)
- [03 剪辑与字幕优化指南](./references/03_editing_workflow.md)
- [04 发布分发与数据复盘指南](./references/04_distribution_analytics.md)
- [05 六年自媒体老兵核心实战铁律](./references/05_veteran_rules.md)
