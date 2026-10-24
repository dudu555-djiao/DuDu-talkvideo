# 项目执行

项目根为完整仓库目录。Windows或跨平台可用 `python dudu.py` 替代 `./dudu`。下例 `./dudu` 自动选择带依赖的Python；也可用配置好的Python执行 `scripts/workflow.py`。`EPISODE` 均替换为该期的实际路径。

```sh
./dudu doctor
./dudu new --script /实际文案.txt --title 本期标题
./dudu semantic EPISODE
./dudu serve EPISODE --port 8866
```

`new` 自动建立启用轻背景乐和稀疏动作音效的 `audio-request.json`，并保存 `input/original.txt` 与工作稿 `input/script.txt`，不自动把分句当成已完成分镜。助手填写 `storyboard.json` 后 `semantic` 生成 `review/index.html`。在Codex浏览器打开终端给出的 localhost 地址。相同项目保持固定端口/浏览器以保留本地意见，外部浏览器访问不同origin不共享意见。

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

先读每期 `PROJECT_STATE.md`、`storyboard.json`、`approvals/semantic.json` 与现有意见导出；确认当前版本再继续。不要因为换对话丢失审批，也不要把早期样片的审批泛化到新稿。
