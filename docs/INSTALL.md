# 安装与首次配置

目标是让完整项目、Python 环境、浏览器、视频工具、中文字体和 Skill 入口可用。配音账号和密钥由使用者本人提供；安装不会创建账号、购买额度或请求付费配音。

## 1. 下载完整项目

```sh
git clone https://github.com/dudu555-djiao/DuDu-talkvideo.git
cd DuDu-talkvideo
```

也可使用 GitHub Code → Download ZIP 并解压到稳定目录。不要只用通用 Skill Installer 下载 `skills/dudu-talkvideo` 子目录，这个项目的运行代码与素材在仓库其他目录。

## 2. 系统依赖

需要 Python 3.10+、Node.js 22+，以及提供 `ffmpeg`、`ffprobe` 命令且支持 `libx264`、`loudnorm` 的 FFmpeg。代码没有 npm 依赖。

### macOS

已有 Homebrew 时可用下列命令；没有时让 Codex 根据本机条件选择安装方式，不覆盖现有环境。

```sh
brew install python node ffmpeg
```

### Windows

可用系统包管理器或官方安装程序安装 Python、Node.js LTS 和 FFmpeg。已有 winget 时可参考下列命令，由 Codex 先检查是否已安装以及当前可用的软件包。

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Gyan.FFmpeg -e
```

安装后可能需要新开终端，让 PATH 生效。确认 `python --version` 或 `py -3 --version`、`node --version`、`ffmpeg -version`、`ffprobe -version` 可用。Windows 入口为 `python dudu.py` 或 `dudu.cmd`。

### Linux

通过发行版包管理器安装 Python、venv 支持、FFmpeg，再安装满足版本要求的 Node.js。Ubuntu/Debian 常见基础包为 `python3 python3-venv python3-pip ffmpeg`；发行版的 Node.js 版本可能过旧，需要由 Codex 选择合适的 Node.js 安装方式。

Playwright Chromium 还需要系统动态库。安装 Python 环境后，如浏览器无法启动，可运行下列命令；系统库安装可能需要管理员权限。

```sh
.venv/bin/python -m playwright install-deps chromium
```

如果二进制不在 PATH，可设置 `DUDU_NODE`、`DUDU_FFMPEG`、`DUDU_FFPROBE`、`DUDU_CHROME`。`DUDU_PYTHON` 可以指定项目 Python。这些是当前进程的环境变量，不需要复制作者电脑上的路径。

## 3. 安装项目环境与 Skill

```sh
python3 scripts/bootstrap.py --install --smoke-test
```

Windows 通常使用 `py -3 scripts/bootstrap.py --install --smoke-test`。

安装程序会依次完成以下操作。

1. 建立 `.venv`，安装 `requirements.txt` 的 Python 依赖。
2. 安装 Playwright Chromium。已有兼容浏览器时，可用 `--skip-browser-install`，自检仍须实际启动浏览器。
3. 从空模板创建 `.env`，保留已存在文件。
4. 将 Skill 链接到用户技能目录，并建立兼容旧目录的入口。已有同名 Skill 不覆盖；如冲突，先核对版本，不要删除用户旧文件。
5. 运行依赖检查，再做不联网配音的实际 3 秒渲染测试，生成 90 帧 MP4 并完整解码。

主 Skill 目录为 `~/.agents/skills/dudu-talkvideo`；兼容目录为 `$CODEX_HOME/skills/dudu-talkvideo`，未设置时使用 `~/.codex/skills/dudu-talkvideo`。Windows 无软链接权限时，安装器保存带项目根路径的指针文件。

自定义安装目标可用 `--skill-dir /路径/dudu-talkvideo`。相同名称的两个不同 Skill 不会被自动合并，出现多版本时请让 Codex 说明各自路径。

## 4. 本人配置配音

在自己的电脑本地编辑项目根 `.env`，填写 `VOLC_TTS_API_KEY`，或 `VOLC_TTS_APP_ID` 与 `VOLC_TTS_ACCESS_TOKEN` 二选一。不要把密钥发到公开聊天、README、issue 或 Git。

默认使用刘飞预设、Seed TTS 2.0 和速度 -25。实际服务权限、音色和计费额度需要本人账号具备。自动配音的正文会发送到火山 TTS；真实素材、审片网页和本地渲染在本机处理。

可以通过 `DUDU_TALKVIDEO_TTS_ENV` 指向另一个私有配置文件。安装器和 doctor 不读取其他 Skill 的配置，也不调用作者的服务账号。

没有配音凭据时，仍可查看已有样片、设计语义分镜、运行离线自检，或导入本人已经制作的配音与同音频词戳/SRT。不能将“本地环境检查通过”写成“自动配音全部配置成功”。

## 5. 验收与开始使用

```sh
python dudu.py doctor
python scripts/bootstrap.py --smoke-test
```

建议使用 `.venv/bin/python scripts/bootstrap.py --smoke-test`；Windows 为 `.venv\Scripts\python.exe scripts\bootstrap.py --smoke-test`。`python dudu.py` 会自动选择项目 .venv，无需先激活。

报告 `localReady=true` 表示本地依赖就绪；`ttsCredentialsConfigured` 仅表示凭据字段已填，不证明远端可用。安装结果保存在本机 `installation-check.json`，该文件不会提交 Git。

下一轮对话调用 `$dudu-talkvideo` 并给文案；未发现技能时重启 Codex。新一期先交语义 HTML，用户确认后才配音、渲染实际关键帧和完整视频。

## 更新与移除

更新前保留本期工程、私有 .env 和本地修改，再拉取仓库更新并重新运行安装检查。不要以 `git reset --hard` 覆盖使用者的自定义资产。

移除时先核对 Skill 软链接或指针确实指向本项目，再只移除该入口。完整项目中的 `episodes/`、本地资产与私有配置需要本人决定是否保留。
