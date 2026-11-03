# DuDu-talkvideo

先读 README.md、PROJECT_STATE.md、brand/style-lock.json、skills/dudu-talkvideo/SKILL.md。这是完整的本地项目，安装时不能只复制 Skill 子目录。

默认薄荷绿小方块（theme=mint, mascot=block），另有折纸鸟、小轨道及六套配色。新一期默认仅旁白，背景音乐和音效关闭，需要时明确开启。主画面按完整讲述段落选择，段内通过操作、聚焦和圈注推进；讲述任务改变时才换主场景。真实操作与事实用真实材料，缺素材标待补。

新一期先问清通用IP或真人出镜，用presenter记录真实选择；分镜cameraPlan按模式分别设计。新文案先做语义分镜 HTML。收到用户对本版的明确同意，才正式配音和渲染实际关键帧。用本项目增强三栏工作台；保留附件、撤回、历史和导出等功能。测试批准不得用于生产。

用 `python dudu.py` 或 `./dudu`，优先项目 .venv。安装按 docs/INSTALL.md，`python scripts/bootstrap.py --install --smoke-test`；自检无 TTS 网络请求。凭据仅用本人私有 .env 或环境变量，不读取其他 Skill 的密钥，不上传 .env。

episodes/ 是本地制作目录，不提交公开仓库。不要覆盖用户已有 Skill、项目、素材或配置。公开发布视频仍需用户当次授权。公开仓库只收通用几何角色，不能重新加入作者私人角色或旧样片。旧克隆应重新克隆，不合并旧历史。

工作台意见、附件与历史自动保存到每期feedback/，优先直接读取latest.json及附件路径；原浏览器存储和导出保留。feedback、录音、用户截图、私人角色及其演示不得提交公开仓库。
