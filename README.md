# DuDu-talkvideo

**把一份文案，做成有自己 IP 的蓝白纸感讲解视频。**

这是 DuDu 用 Codex 共创的视频制作 Skill 与完整本地项目。包含固定视觉风格、段落画面判断、语义分镜、增强三栏审片台、代码动画、说话 IP，以及背景音乐和音效。

适合 AI 教程、新闻解释和个人观点。你负责内容与审看，Codex 按规则准备素材、设计画面和执行制作。

![蓝白纸感与说话IP示例](docs/preview.png)

[观看 52 秒布局样片](examples/approved-layout-52s/out/final.mp4) · [观看 16 秒说话与出框样片](examples/approved-avatar-16s/out/final.mp4)

> 这是 **Skill + 完整项目**，安装时必须保留整个仓库。新稿先审语义分镜，确认后才正式配音和制作实际关键帧。自动配音需要你自己的火山引擎 TTS 账号、对应音色权限及额度；已有录音也可以导入。安装自检不发送付费配音请求。

## 复制给 Codex 安装

已经使用 Codex 的朋友，可以直接复制下面这一段。它会要求 Codex 检查环境、安装依赖、登记 Skill，再运行离线出片测试。

```text
请帮我安装这个完整项目和 Skill：https://github.com/dudu555-djiao/DuDu-talkvideo

先阅读仓库 README.md、AGENTS.md 和 docs/INSTALL.md，再按我的操作系统完成安装。把完整仓库保存到稳定的本地目录，不要只下载 skills 子目录，也不要覆盖我已有的项目、Skill 或配置。检查并补齐 Python 3.10+、Node.js 22+、带 libx264 和 loudnorm 的 FFmpeg/FFprobe；建立项目 .venv，安装 requirements.txt 和 Playwright Chromium，然后运行 scripts/bootstrap.py --install --smoke-test。按文档登记 dudu-talkvideo Skill，保留原有用户配置。

配音密钥只在我本机私有 .env 或环境变量中配置，不要让我把密钥发到公开对话，不要复制作者或其他项目的密钥。若缺少火山 TTS 账号、音色权限或额度，完成其他安装后告诉我如何补齐，不能声称已经能自动配音。安装测试只用离线测试音，不调用付费 TTS。

最后告诉我项目路径、Skill 安装位置、自检和实际 MP4 测试结果、还缺的配置，并给我一条下一步调用示例。
```

独立提示词文件见 [docs/INSTALL_PROMPT.md](docs/INSTALL_PROMPT.md)。安装程序会保留已存在的 Skill 和 `.env`；如发现同名旧版本，由你决定如何处理。

## 它怎么做视频

```text
文案与真实素材
    ↓
语义分镜 HTML   ← 先看讲述、主画面、素材状态与 IP 安排
    ↓ 用户明确同意本版
配音与时间信息
    ↓
实际关键帧 HTML ← 从真正的渲染实现取帧，逐镜头提意见
    ↓
连续动画、音乐与音效
    ↓
内容审看与技术检查
    ↓
MP4 + SRT + 可继续修改的本期工程
```

**每个完整讲述段落先确定一种主画面。** 多句话可以在同一场景里讲完，段内用真实操作、聚焦和圈注推进。讲述任务改变时再换场景，避免几字就在人物、图解和录屏之间跳转。

| 这段话要做什么 | 优先使用的主画面 |
| --- | --- |
| 教一个操作 | 真实输入、关键操作与结果录屏 |
| 说明一个事实 | 原始出处、原文或数据，保留上下文 |
| 解释关系与差异 | 流程、对比和关系图 |
| 分享感受与判断 | IP 主讲或人物情境，判断附近保留依据 |

A/B-roll 按叙事作用区分，不按录屏、Canvas 或 Remotion 区分。左下角头像是独立讲述层，可以叠在不同主画面上；挡住信息时要退让。当前通用渲染实现是 **Canvas + Playwright + FFmpeg**，没有必装的 Remotion 或剪辑软件。

## 本次流程更新

[本期完整制作复盘](docs/WORKFLOW_REVIEW.md)总结了从文案、录音顺序、语义分镜、真实关键帧到完整动画、网页反馈、三种声音版本和局部返修的实际过程。

- 画面选择补全五类：关系图解、真实操作、原始证据/成果、IP 情境、IP＋少量文字/图形。IP 情境也可介绍工具、作类比和承接过渡。
- 录屏可按讲解重点做局部推拉与黄色笔刷，标注跟随同一媒体坐标；指定“只动手”时固定其他表情和身体。
- 新增[动效与局部返修方法](references/motion-and-revisions.md)，优先规划“修改范围＋前后各 2 秒”，满足条件再复制未改画面；通用 `render` 仍是全片渲染。
- 新增[原声与多版本交付](references/audio-delivery.md)：音效按动画、配乐按节奏，用户需要时用一条画面母版交付纯配音、配音＋音效、配音＋音效＋配乐三版。
- 新增 `scripts/plan_partial_render.py`（只规划）和 `scripts/mux_audio_variants.py`（现成 AAC 与统一画面复制封装）。两者无需调用付费 TTS；运行 `--help` 查看用法。

FredTalk 与 VideoTalkCraft 是用户指定且本机可用时的参考来源，不是安装依赖，也未将其外部素材库打包进本项目。

## 已包含的效果

- D 蓝白点阵纸感、纸条、圈注、手绘箭头、蓝边媒体窗、标题字体和字幕。
- 章节、指令与媒体、对照、流程、纸条和 IP 情境六类基础画面，可组合真实图片与视频。
- 固定角色三嘴形动画，人声停顿时闭嘴；语义重点可探出固定圆框并回位。属于有限嘴形卡通动画，不是逐音素唇形。
- 默认低音量 96 BPM 背景音乐，纸张、轻点、灵感三音按本期动作安排。旁白、音乐、音效和混音独立保存，嘴形只读旁白。
- 增强三栏工作台，保留附件、文件夹、撤回、删除、历史、即时保存和导出。没有对象源时精确编辑按钮禁用。
- 真实关键帧、完整音频与字幕对齐、逐帧导出及完整解码检查。

基础原语负责复用，复杂画面仍需 Codex 按内容扩展。文件夹里的命令不会自动替你完成事实判断、审美选择或所有新场景设计。

## 手动安装

先安装 Git、Python 3.10+、Node.js 22+、FFmpeg/FFprobe。详细平台步骤见 [安装指南](docs/INSTALL.md)。

```sh
git clone https://github.com/dudu555-djiao/DuDu-talkvideo.git
cd DuDu-talkvideo
python3 scripts/bootstrap.py --install --smoke-test
```

Windows 可将上面的 `python3` 换成 `py -3`。日常命令用 `python dudu.py`，macOS/Linux 也可以用 `./dudu`。安装建立本项目 `.venv`，不要求更改全局 Python 包。

Skill 默认链接到 `~/.agents/skills/dudu-talkvideo`，并对仍使用 `$CODEX_HOME/skills` 或 `~/.codex/skills` 的环境提供兼容入口。已有同名目录会保留。Windows 无软链接权限时使用带真实项目路径的指针安装。不要在安装后随意移动或删除仓库。

本地 Skill 目录与软链接行为参考 [官方 OpenAI Skills 文档](https://developers.openai.com/codex/skills/)。下一轮对话调用 `$dudu-talkvideo`；若未出现，重启 Codex 后再试。

## 配音配置

安装会从 `.env.example` 建立空的私有 `.env`，已有文件不覆盖。选择一种鉴权方式在本机填写。

```dotenv
# 方式 A
VOLC_TTS_API_KEY=你自己的密钥

# 或方式 B
VOLC_TTS_APP_ID=你自己的AppID
VOLC_TTS_ACCESS_TOKEN=你自己的AccessToken
```

默认预设为 `zh_male_liufei_uranus_bigtts`、`seed-tts-2.0`、速度 `-25`。需要账号实际拥有该服务和音色的调用权限；账户注册、开通和付费由本人完成。[火山 TTS 接口文档](https://www.volcengine.com/docs/6561/1598757)可用于检查服务配置。

也可以通过 `DUDU_TALKVIDEO_TTS_ENV` 指向本机另一个私有配置文件。不要上传 `.env`。`doctor` 只检查配置存在情况，不证明远端配音可用。已有配音及配套词戳/SRT 的导入方式见 [音频说明](references/audio.md)。

## 做第一期

安装完成后，在 Codex 中说下面这段，并附上自己的文案。

```text
使用 $dudu-talkvideo，按默认蓝白纸感风格制作这份文案。
请先检查真实素材需求，按完整讲述段落安排主画面，生成语义分镜 HTML 给我审看。
我同意后，再配音和制作实际关键帧。
```

命令行由 Codex 根据你的反馈调用。常用命令如下。

```sh
python dudu.py doctor
python dudu.py new --script 我的文案.txt --title 我的第一期
python dudu.py semantic episodes/实际生成的本期目录
python dudu.py serve episodes/实际生成的本期目录 --port 8866
```

`new` 只建立一期目录，不会把自动分句冒充已经设计好的分镜。Codex 需要填写 `storyboard.json`，再生成审片页。收到本期真实批准后，才进入 `voice → audio → assemble → frames → review → render → check`。详见 [命令与字段](skills/dudu-talkvideo/references/commands.md)。

## 换成自己的频道

可以复用默认示例先跑通，再替换自己的资产。

- 头像与场景在 `assets/`。更换头像后，须重新对齐 `assets/avatar/registration.json` 及对应 JS 中的嘴部区域，避免跳脸。
- 风格规范在 `brand/style-lock.json`，当前渲染器在 `runtime/renderer.js`。改配色、布局或画幅时要同步修改实际渲染实现并验收，不能只改 JSON 就假定所有画面自动适配。
- 标题和正文中文字体已捆绑，保留各自 OFL 许可证。正文优先系统黑体，缺失时使用内置 Noto Sans SC。
- 背景音乐、音效开关与音量可在本期 `audio-request.json` 覆盖。已有配音只改音乐时使用 `remix`，不必重新配音。
- 工作台模板是 `workbench/template.html`，保留这份增强版即可。

## 目录

```text
skills/dudu-talkvideo/  Codex Skill 入口
brand/                 默认风格与声音规范
assets/                IP、口型、场景与字体
runtime/               Canvas 场景与动画实现
scripts/               安装、配音、分镜、审片与渲染工具
workbench/             增强三栏工作台
references/            制作判断、声音与渲染数据说明
examples/              已完成样片
tests/                 隔离的离线安装测试
episodes/              安装后生成的每期工程，Git 忽略
```

## 使用边界与许可

当前默认横屏 1920×1080、30 fps。macOS 有本项目实际验证记录；Windows/Linux 提供跨平台安装入口，未声称已在所有系统实机验证。Linux 可能另需 Chromium 系统库，见安装指南。

内容事实、真实素材及观看体验要审看。技术检查通过不代表已完成人工全文试听，也不保证平台流量。项目不自动公开发布视频。

代码与文档使用 [MIT License](LICENSE)。字体遵循各自 OFL，示例角色与来源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。风格研究参考了 Xilo 等创作者的公开作品，本项目为独立实现，未包含他们的原视频，也不代表与其合作或获得背书。
