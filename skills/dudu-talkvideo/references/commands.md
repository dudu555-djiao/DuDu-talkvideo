# 项目执行

项目根是完整仓库目录。下例 `python dudu.py` 或 `./dudu` 自动选择本项目Python；也可用配置好的Python执行 `scripts/workflow.py`。`EPISODE` 均替换为该期的实际路径。

```sh
./dudu doctor
./dudu new --script /实际文案.txt --title 本期标题
# 先取得本期用户选择，原话/出处替换为真实消息；mode 可选 ip 或 real
./dudu presenter EPISODE --mode real --quote '本期用真人出镜' --evidence '本期用户消息标识'
./dudu semantic EPISODE
./dudu serve EPISODE --port 8866
```

`new` 自动建立待确认的 `presenter-request.json` 与声音配置，保存 `input/original.txt` 与工作稿 `input/script.txt`，不自动把分句当成已完成分镜。先问清IP或真人，用 `presenter` 记录本期真实选择，再按模式填写分镜；未确认不能运行semantic。真人镜头须 `ip.mode=hidden`，不使用ip-scene。每镜cameraPlan写主体、景别/构图、运动及依据，soundPlan写声音意图。`semantic` 生成原三栏 `review/index.html`。浏览器操作按项目当前模型要求执行。`serve` 提供项目意见自动保存API；优先沿用原端口/浏览器，旧记录初次迁移后其他浏览器可从项目恢复。浏览器本身的localStorage/IndexedDB仍各自独立。打开 `http://127.0.0.1:<port>/review/` 使用本期数据，不要直接打开未绑定的 `workbench/template.html`；工作台细节见 [workbench-ui.md](workbench-ui.md)。


收到用户对本版语义分镜的真实同意后才记录（以下是命令格式，不是已有授权）：

```sh
./dudu approve EPISODE --quote '用户本次批准原话' --evidence '所在会话或消息标识'
./dudu voice EPISODE
./dudu audio EPISODE
./dudu assemble EPISODE
./dudu frames EPISODE
./dudu review EPISODE
./dudu render EPISODE
./dudu check EPISODE
```

成品配音导入见项目 `references/audio.md`，不要重复TTS。语义已批准而素材待补时，可以采集素材；不要把 `pending` 当作已可用于正式成片。语义源 `storyboard.json` 不回填技术时间，组装输出 `episode.json`，关键帧清单独立存 `keyframes.json`。

## 语义字段

```json
{
  "projectId": "new命令生成的稳定ID",
  "title": "本期标题",
  "version": 1,
  "presenterMode": "ip",
  "shots": [{
    "id": "s01",
    "narration": "本镜头对应的完整旁白。",
    "purpose": "让观众看见实际输入和输出之间的变化",
    "visual": {
      "type": "prompt-media",
      "description": "左侧原始输入，右侧实际结果；讲到待确认时圈住对应单元格",
      "assets": [{"path":"assets/result.png","kind":"image","source":"本期实际操作截图","status":"ready"}],
      "focus": "待确认单元格"
    },
    "screenText": "缺信息，标待确认",
    "estimatedDuration": 5,
    "ip": {"mode":"corner","emotion":"explaining","emphasis":[{"anchor":"待确认"}]},
    "cameraPlan": {"subject":"真实结果与角落通用 IP","framing":"左右对照；IP不挡结果","movement":"先全貌再聚焦待确认单元格","reason":"让观众看清缺项及填写依据"},
    "soundPlan": "聚焦保持安静；核对动作可考虑本地轻点，获批后试听选定",
    "render": {"type":"prompt-media","prompt":"输入内容","media":{"src":"assets/result.png","kind":"image","label":"实际结果"}},
    "soundCues": [{"kind":"tick","anchor":"完整旁白"}],
    "review": {"status":"pending","notes":""}
  }]
}
```

镜头不是按句号机械分割；上述只是字段例子，不是可以不取证就交付的正式分镜。素材状态用 `ready/pending/not-needed`；网页意见中的“通过”不能被助手自动视为本期整体授权。

`render` 可在语义期填写计划，技术期若需要更丰富的布局数据，写入 `episode.json`/本期实现；若改变用户已审过的主画面、逻辑或实质内容，则回到新版语义审查。`assemble` 使用本期词戳：旁白顺序完整覆盖 `input/script.txt`，屏幕字可提炼；`ip.emphasis[].anchor` 必须出现在本镜头原句，重复词可用 `occurrence` 指定第几次。

只改已有本期配乐/音效时，修改audio-request.json后运行 `./dudu remix EPISODE`，再 `./dudu assemble EPISODE` 刷新声音指纹；不用重新TTS。口型测试或纯旁白可将soundtrack.music与soundtrack.sfx同时设为false。

## 新对话恢复

先读每期 `PROJECT_STATE.md`、`storyboard.json`、`approvals/semantic.json` 与 `feedback/latest.json`，按附件路径直接读取原始文件，并检查有无 `feedback/conflicts/`；旧版未同步时再读现有意见导出。确认当前版本再继续。不要因为换对话丢失审批，也不要把早期样片的审批泛化到新稿。

## 局部返修与声音版本

这两项独立工具不改既有 `render` 的全片行为。先阅读项目 `references/motion-and-revisions.md`、`references/audio-delivery.md`。

```sh
python scripts/plan_partial_render.py BASE.mp4 --range 10:15 --range 42:48 --handle 2 --output patch-plan.json
python scripts/mux_audio_variants.py PICTURE.mp4 variants.json --report variants-report.json
```

前者只规划修改范围、前后缓冲与候选 GOP 边界，不执行渲染；实际绘帧和拼接由本期实现执行并验证。后者将同一画面与现成兼容 AAC 音轨复制封装成多版，不混音、不调用 TTS、不重绘画面。不要虚构 `dudu patch` 命令或把本期写死的秒数用于新片。

`variants.json` 是数组，路径相对该 JSON 所在目录：

```json
[
  {"id":"voice","audio":"voice.m4a","output":"out/01-voice.mp4"},
  {"id":"sfx","audio":"voice-sfx.m4a","output":"out/02-sfx.mp4"},
  {"id":"music","audio":"voice-sfx-music.m4a","output":"out/03-music.mp4"}
]
```

AAC 也可直接来自已有同时间轴 MP4 的唯一音轨。工具拒绝覆盖和明显的音画时长不符；只容许编码包时长的舍入差异，不自动截短或补齐。两工具可传 `--ffprobe`，封装工具另可传 `--ffmpeg` 指定可执行文件；详细参数以 `--help` 为准。
