# 公开版验证记录

## 1.3.0 · 2026-10-25

在既有项目 .venv 中运行 `scripts/bootstrap.py --smoke-test`：语义批准门禁、实际关键帧、审片 HTML、人物测试以及 3 秒/90 帧 MP4 和完整解码均通过。Skill 结构校验通过；本轮未请求付费配音，也未修改远端 TTS 配置。

新增 `python tests/media_helpers_smoke.py`，在自动清理的临时目录用合成媒体验证 19 项行为：

- CFR/分数帧率、非零起点和 VFR 的识别，范围排序、前后缓冲、边界扩展与合并；拒绝非法/非有限数值和错误 JSON。
- 统一画面与两条 AAC 复制封装后的流 hash、完整解码帧数与音画时间；不覆盖现有产物，拒绝时长不符、WAV、重复 ID。
- 对母版或后续音轨来源带内嵌软字幕的情况提前拒绝，不产生残留成片，也不静默丢字幕。

这些测试验证规划和封装工具；规划器没有执行局部绘帧，不能把测试描述为自动 GOP 拼接已经完成。实际一期的局部渲染案例和检查范围见 [完整复盘](WORKFLOW_REVIEW.md)。

独立 Skill 前向评估验证：已有批准的局部返修不要求新增审批；缺 FredTalk/VideoTalkCraft 时可独立实现；只改画面时复制旧音轨；新稿仍停在语义批准节点。评估发现的严格范围限制和软字幕保留问题已补规则与测试。

GitHub Actions 已增加同一 helper 测试，远端执行结果以该提交的 Actions 为准。当前新增工具实测环境为 macOS；未据此宣称所有平台都已实机覆盖。

## 1.2.0 历史验证

版本 1.2.0，2026-10-24。

在 macOS Apple Silicon 上建立新的项目 .venv，由 requirements.txt 安装 NumPy 2.5.4、Playwright 1.64.1。使用 Python 3.12.14、Node.js 24.16.0 和 FFmpeg/FFprobe 8.1.2 验证。未依赖作者其他 Skill 的 Python 包或配音凭据。

运行 `scripts/bootstrap.py --install` 完成项目环境、浏览器与隔离目标 Skill 安装；没有覆盖作者当前生产 Skill。随后使用新 .venv 执行 `scripts/bootstrap.py --smoke-test`。

## 已通过

- 默认新一期启用背景音乐和动作音效。
- 语义审片 HTML 实际生成。
- 未批准时，voice、audio、assemble、frames、review、render 六个后续命令均拒绝。
- 隔离 QA 目录内使用明确标记的合成测试批准与测试音；该记录不会保存为正式一期批准。
- 导入合成测试音和测试时间数据，生成实际关键帧与关键帧审片 HTML。
- 浏览器实际加载内置中文字体，测试说话时张嘴、停顿闭嘴和重点越框。
- 实际输出 640×360、30 fps、3 秒、90 帧 MP4，并完成整条解码检查。
- 语义源与旁白文件指纹在制作中保持一致。
- Skill 结构检查、Python 语法检查与 JavaScript 语法检查通过。

全程未请求付费 TTS，也未声称远端配音账号已经配置成功。测试音仅为技术验证，不用于演示自然人声品质。现有 16 秒与 52 秒 MP4 另作为视觉与人物效果演示保留。

仓库另包含 Ubuntu 的 GitHub Actions 工作流，执行依赖安装及同一离线出片检查；每次运行结果以仓库 Actions 页面为准。Windows 安装入口尚未实机覆盖。
