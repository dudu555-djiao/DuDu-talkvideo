# DuDu-talkvideo 音频制作

本项目复用了已验证的火山 HTTP 合成实现，默认音色是 **刘飞** `zh_male_liufei_uranus_bigtts`，资源 `seed-tts-2.0`，速度 `-25`。旁白完整合成，保留同次合成的词级时间戳；实际音频决定时长，禁止截成 20 秒、循环旧声音或借用别期字幕。

指定本人克隆音色、导入多段录音、使用 VideoTalkCraft 音效或交付多个声音版本时，先读 [原声与多版本交付](audio-delivery.md)。用户当次录音和音色要求优先于默认预设；成品录音不重复 TTS。

## 开始条件

先完成 `storyboard.json` 和语义分镜 HTML，等待用户明确同意。脚本要求 `approvals/semantic.json` 中 `status=approved`、`approvedBy=user`、非空 `userStatement`，且 `storyboardSha256` 等于当前语义分镜文件的 SHA-256。任何字节修改都会使批准失效。代理必须记录用户真实原话，不能自行构造生产批准。

`input/script.txt` 是本期工作稿，`input/original.txt` 保存原稿。`storyboard.json.shots` 的 `narration` 按顺序完整覆盖工作稿。语义稿通过后保持原字节，音频结果和时间轴写在 `audio/`，不会改语义稿或 `episode.json`；主流程再完成 assemble。

## CLI

从项目根运行；每期目录可以是绝对路径或当前目录下的 `episodes/<本期名>`。

```sh
# 无网络、无配音费用，仅核对批准和全文覆盖；不读取凭据。
node scripts/synthesize.mjs --project episodes/本期 --check-only

# 生成完整旁白与同次词级时间戳；内容+参数+音频指纹匹配时复用缓存。
node scripts/synthesize.mjs --project episodes/本期

# 对原音加首尾留白、整帧对齐，生成字幕和逐镜时间；约 -16 LUFS。
python3 scripts/audio_pipeline.py --project episodes/本期

# 无网络，复查现成音频、字戳、字幕、逐镜边界与文件指纹。
python3 scripts/audio_pipeline.py --project episodes/本期 --check-only
```

默认新增开头 0.2 秒、结尾 0.6 秒；只有补零和整帧向上取整，没有删除原声。后处理目标 48 kHz、双声道、约 -16 LUFS，真峰值目标不高于 -1.5 dBTP；实际测量保存到 `audio/audio-checks.json`。正式视频默认启用已认可52秒样片的轻背景乐与稀疏动作音效。默认参数由brand/style-lock.json.audio.soundtrack提供，new命令会复制到本期audio-request.json；本期可覆盖。

### 本机依赖

- Node 支持 `fetch` 和 `process.loadEnvFile`（本机现成 Node 可用）。
- Python 3 + NumPy。
- FFmpeg、FFprobe；支持 PATH 或当前用户 `~/.local/bin`。
- 当前可用 Python：项目 `.venv` 内的 Python。换电脑时选择安装了 NumPy 的 Python，无须绑定这个绝对路径。

### 凭据

只读取环境变量，或 `DUDU_TALKVIDEO_TTS_ENV` 指定的本机文件；未指定时读取本项目根目录 `.env`（由安装程序从空模板建立，Git忽略）。支持 `VOLC_TTS_API_KEY`，或 `VOLC_TTS_APP_ID` + `VOLC_TTS_ACCESS_TOKEN`。

**项目不包含 `.env`、密钥或原始鉴权日志。** 程序不打印密钥，不自动切换到其它音色或 macOS say。失败不自动反复付费请求。若长稿超出服务限制，明确按完整章节拆分，并逐章保存同次音频与字戳后连接；现有脚本不隐式拆分，也不会截掉尾部。

## 导入用户成品录音

导入独立音频文件及同一音频的时间戳，保留现有首尾和停顿，对旁白做响度处理、重采样及不足一帧的尾部补零，再按本期声音配置配乐。若输入已经是含配乐的成品混音，明确将music与sfx都设为false，避免重复铺底；人物嘴形仍应提供独立人声。

```sh
python3 scripts/audio_pipeline.py --project episodes/本期 \
  --import-audio /absolute/path/voice.wav \
  --timing /absolute/path/timing.json
```

时间戳 JSON 为 `{ "text": "完整旁白", "words": [{"word":"文字", "startTime":0.2, "endTime":0.5}] }`，时间单位秒且针对输入音频；支持本项目输出的 `timing.json`。不能把 raw 字戳套到加过停顿的 final 音频。可另有 `voice` 标记，用户录音不强制伪标刘飞。

只有 SRT 时：

```sh
python3 scripts/audio_pipeline.py --project episodes/本期 \
  --import-audio /absolute/path/voice.wav \
  --srt /absolute/path/voice.srt
```

SRT 必须完整覆盖文案且每个语义镜头边界也是 SRT 边界。导入后标记 `timingGranularity=caption`，`words=[]`。不将整句时长按字数分配后假称逐字时间。要在句中精确触发某词的动作，需补充同音频词级对齐或实际试听锚点。人物停顿闭嘴仍由旁白 WAV 的真实音量包络控制。

## 自然停顿和声音设计

新建一期自动建立 `audio-request.json`，正式视频的默认值如下；首尾留白和额外停顿按需要另外填写：

```json
{
  "soundtrack": {
    "music": true,
    "bpm": 96,
    "musicRMS": 0.018,
    "sfx": true,
    "cuePolicy": "semantic"
  }
}
```

停顿只允许在同次字戳证明的镜头间隔中插入：找到间隙低能量位置，插入静音，所有后续词级时间精确顺延；无安全间隙时拒绝插入。不要每句都机械加停顿。用户成品音频导入保留已有停顿，不再插入。

声音事件 `time` 是合成后全局秒数，须以本次配音关键位置为依据。支持 `paper`、`tap/tick/check`、`idea/spark/aha`。音乐为低音量程序化felt旋律，默认96 BPM，开头淡入、结尾淡出。保持52秒参照的音色和轻节奏，时长随本期声音延展，不循环旧旁白。所有混音最后重新测量响度，旁白保持清楚。

### 音效跟随画面

默认按本期分镜选少量事件：纸条/媒体入场对应paper，具有真实时间锚点的圈注/核对对应tick，明确aha/灵感才对应idea。并非每个镜头都加音效，更不跟着嘴形逐次加声。为某镜头写明计划时，使用该镜头的soundCues，例如：

```json
"soundCues": [{"kind":"tick", "anchor":"待确认"}]
```

anchor必须能在本镜头真实词戳里定位；只有SRT句级时间时，补词级对齐或填写核对过的time。shot内offset相对本镜头起点，time始终是全局秒。`soundCues: []` 表示该镜头不自动配音效。本期 `soundtrack.cues` 若显式提供（包括空数组），覆盖自动事件；不再重复叠加。

### 纯旁白与只改配乐

口型检查或用户明确要求纯旁白时，使用：

```json
{"soundtrack":{"music":false,"sfx":false}}
```

只关闭music可保留动作音效；只关闭sfx可保留背景音乐。关闭时对应独立音轨写为静音，避免遗留旧声音文件造成误用。

已有本期narration.wav与配套时间，只改配乐或音效时：

```sh
./dudu remix EPISODE
./dudu assemble EPISODE
```

remix仅重新合成声音，不重做TTS、不再次插首尾/停顿、不改旁白及字幕时间。assemble刷新声音指纹后再做预览或渲染。已有实际配音的锚点才用于混音；语义批准要求保持不变。

## 输出与主流程对接

- `audio/narration-raw.wav`、`audio/narration-raw-timing.json`：同次合成原件、文字、参数和音频指纹。
- `audio/narration.wav`：人物说话包络的来源，不能从加音乐的 mix 提取嘴形。
- `audio/music.wav`、`audio/sfx.wav`：独立配乐与音效，关闭时为等长静音。
- `audio/soundtrack.json`：本期生效配置、实际触发时间及选择依据。
- `audio/mix.wav`：成片声音。
- `audio/timing.json`：`duration`、`durationFrames`、`fps`、`words`、`captions`、`shots`、停顿偏移与来源指纹。
- `audio/captions.json`、`audio/narration.srt`：完整字幕。
- `audio/shot-timing.json`：`{duration,fps,storyboardSha256,shots:[{id,start,end,narrationStart,narrationEnd,timingGranularity}]}`。镜头 `start/end` 覆盖完整音频，之间的边界取相邻讲解的停顿中点；`narrationStart/End` 只覆盖该镜头真实口播。供主流程 assemble 读取。
- `audio/audio-checks.json`：实际时长、文字覆盖、时间戳/镜头数、响度测量。

在含多个汉字的一个真实返回词内，仅字幕换行/镜头边界需要时对这个词的区间细分；不宣称音素级对口型。低置信词、特定强调词须结合实际音频检查。画面关键动作锚点还要结合词级时间或人工核对，不能把逐镜起止当成所有动作的时间。

## 2026-10-24 离线验收

使用原有 16 秒动作试片与 52 秒讲解片的成品录音及同次字戳，没有请求新配音：

- 16 秒：15.933333 秒、478 帧、4 个语义镜头、45 个词级条目；全文和字幕一致，测得约 -16.30 LUFS / -1.50 dBTP。
- 52 秒：52.033333 秒、1561 帧、9 个语义镜头、181 个词级条目；未截断，测得约 -15.99 LUFS / -3.31 dBTP。
- 两个流程均确认：缺批准拒绝；语义稿内容指纹变化后拒绝；通过后的时间戳、字幕、镜头边界与音频指纹复查通过。
- 字幕/时长/响度属于机器检查，不替代中文听审。没有声称已完成独立人工试听。
- 额外验证：16 秒原始一次合成录音在第一镜头间隙插入 0.15 秒，原声不删减，字戳精确顺延，结果仍为 478 帧；52 秒 SRT 导入完整保留 1561 帧，明确 `words=[]`、`timingGranularity=caption`，9 个镜头按真实字幕边界对齐。
