# 实际渲染数据与边界

本公开版默认薄荷绿小方块，支持三种几何角色及六套配色；模板与选择方式见themes.md。Canvas renderer 为可复用实现，逐帧由同一时间函数渲染；真实视频每一帧等待 `seeked` 完成。不是由语义文字随机猜画面。新工作台和分镜由主流程生成，渲染器只执行审核后的镜头设计。

## 目录与运行

`python3 scripts/render_keyframes.py EPISODE` 或 `python3 scripts/render_video.py EPISODE`。

两者均先调用 `approval.require_semantic(EPISODE)`，要求真实用户批准原话、对应 storyboard.json 原始 SHA。不自行批准；关键帧也必须在该门禁后。语义文件不随配音对齐改写，后续时间落在 episode.json。`runtime_support.prepare_episode` 将通用 runtime、assets 复制到本期目录，输出不依赖作者电脑绝对路径。运行时优先当前 Python/Chromium/FFmpeg；优先项目 .venv、Playwright Chromium 与 PATH 中的视频工具，缺失时显示安装提示。可通过 DUDU_PYTHON、DUDU_CHROME、DUDU_FFMPEG、DUDU_FFPROBE 配置路径。

每期：index.html、renderer.js、episode.json、episode-data.js、assets/、audio/narration.wav（纯人声）、audio/mix.wav（混音）。索引页面 `?preview=1` 可播放；本机 HTTP 服务预览更方便。`prepare_episode` 可反复执行，会更新模板与公共资产，保留本期音频、语义、批准和渲染数据。

## episode.json

```json
{
  "title":"本期标题", "series":"DuDu · AI",
  "semanticSha256":"获批storyboard.json的SHA256", "timingSha256":"可选audio/timing.json的SHA256",
  "width":1920,"height":1080,"fps":30,"duration":12,
  "audio":"audio/mix.wav","narration":"audio/narration.wav",
  "captions":[{"start":0.2,"end":3.3,"text":"本期字幕"}],
  "scenes":[{
    "id":"S01","type":"chapter","start":0,"end":12,
    "title":"先看结果，再讲方法","subtitle":"一次讲清一个重点","number":"01",
    "ip":{"visible":true,"emphasis":[{"start":3.2,"end":4.4,"attack":0.28,"release":0.4}]},
    "annotations":[{"type":"circle","at":3.2,"x":1280,"y":468,"rx":180,"ry":80}],
    "keyframes":[0.7,3.8,11.8]
  }]
}
```

episode.semanticSha256 必须等于当前获批语义文件 SHA，镜头 id 与顺序必须与 storyboard.shots 一致；提供 timingSha256 时也检查当前时间戳，旧配音或改稿后必须重新 assemble。

所有时间都是本期全局秒，不是镜头内部秒。坐标是 1920×1080 设计坐标，渲染器等比映射到输出宽高；默认保持 16:9。每期 duration × fps 为整数。scenes 排列连续、首镜从 0 开始、末镜至 duration，禁止重叠、空隙。字幕可有停顿空隙，不可互相重叠。混音时长应与 duration 一致；句尾静音请实际补齐。媒体只接受本期内部相对文件路径。视频需要足够覆盖镜头的真实时长，禁止静默冻结末帧冒充动态素材。

## 场景原语

| type | 内容字段 | 布局 |
|---|---|---|
| chapter | title、subtitle?、number? | 中央章节标题 + 主题色序号圆 |
| prompt-media | title?、prompt、media | 左黑色指令卡 + 右主题边框真实媒体窗 + 箭头 |
| compare | title?、left/right 各含 title、text? 或 media? | 左右两块结果/观点对照 |
| flow | title?、steps:[{title,text?}] | 1–4 个流程节点，按主题使用横排、分栏或路径布局 |
| note | title?、text、tag? | 内容板 + 可选主题色纸条 |
| ip-scene | title?、text、background? | 通用几何角色与内容板；可选用户自己的背景；默认隐藏重复角标 |

`media={src,kind:'image'|'video',in?:0,playbackRate?:1,fit?:'contain'|'cover',label?}`。image 必须是真实本期图片文件；视频 `in` 为原素材入点，播放时间 `in+(t-scene.start)*playbackRate`。支持同一画面的多个媒体，等待每个寻帧。不能用这里的 UI 原语代替应当出现的实录、结果和证据。

`annotations`：circle={at,x,y,rx,ry}；arrow={at,x,y,toX,toY}；note={at,x,y,text,width?}。以明确的目标位置配置，不能随机撒圈。素材窗口、标题、纸条可复用；新画面超出原语时扩展 renderer 并逐帧验收，不强行塞进模板。

## IP 口型与强调

- 角色使用assets/mascots内固定几何SVG的closed/small/wide三态；无旧图口部ROI或私人角色贴图。
- 以 narration.wav 20ms 窗、5ms hop 的 RMS 分析，80ms 停顿门限；音量阈值打开后按 0.5s 三口型循环（闭口/小口/张口）切换。属于声音驱动逐帧有限动画，不声称逐音素精确对口型。
- 没有声音时闭嘴。音乐/音效不驱动说话。原素材视频在画面渲染器中静音；需要保留的原素材音频必须按同样的入点、时长、速率和全局时间先混入 mix.wav。
- `ip.visible=false` 隐藏角标，适合证据细节全屏。普通场景默认 visible=true；ip-scene 默认隐藏角标，主画面已有人物，只有明确 ip.visible=true 才双重展示。ip-scene的主角色同样由当前旁白包络驱动三嘴形，不重复叠加角标。旧pose字段不再支持。
- `emphasis.start` 开始上移与放大，attack 到达强调位；end 是保持结束，release 回位。end+release 必须在本镜头范围内，避免切镜截断动作。
- 重点完全由本期语义/配音锚点配置，渲染器无例句或写死时间。

## 关键帧与验收

默认每镜头 1–3 张，优先主体稳定呈现、强调最大状态、结束状态；也可显式 scenes[].keyframes 给全局秒。实际 runtime 截图到 keyframes/S01-01.png，生成 keyframes.json / keyframes/manifest.json：

```json
{"storyboardSha256":"...","episodeSha256":"...","shots":[{"shotId":"S01","start":0,"end":12,"keyframes":[{"path":"keyframes/S01-01.png","time":0.7,"label":"主体呈现"}]}]}
```

语义批准不会因 sidecar 更新失效。新改语义必须再次审查；页面意见不自动等于批准。字体/媒体加载错误、字幕或正文超出支持行数、音频时长不合、素材不足、寻帧超时都会报错。成片先输出 partial.mp4，完整解码及帧数验收后再替换 final.mp4；验证记录 qa/render-report.json。
