#!/usr/bin/env python3
"""DuDu-talkvideo: reusable project commands, with a real user semantic review gate."""
from pathlib import Path
import argparse,copy,datetime,importlib.util,json,math,os,re,shutil,subprocess,sys,uuid
from approval import digest,require_semantic
from presenter import require_presenter
ROOT=Path(__file__).resolve().parents[1]
TYPES={'chapter','prompt-media','compare','flow','note','ip-scene'}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def norm(s):return ''.join(c for c in str(s).casefold() if c.isalnum())
def stamp():return datetime.datetime.now().astimezone().isoformat()
def emit(v):print(json.dumps(v,ensure_ascii=False,indent=2))
def run(cmd):subprocess.run([str(x) for x in cmd],check=True)
def executable(name):
 from runtime_support import binary
 return binary(name)
def validate_board(p):
 b=read(p/'storyboard.json');shots=b.get('shots',[])
 require_presenter(p,b)
 if not shots:raise ValueError('尚未完成语义分镜；请按内容意图编排shots，不能把自动分句当分镜。')
 ids=[s.get('id') for s in shots]
 if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('镜头id缺失或重复。')
 script=(p/'input/script.txt').read_text()
 if ''.join(norm(s.get('narration','')) for s in shots)!=norm(script):raise ValueError('分镜旁白须顺序完整覆盖input/script.txt；不能漏句、重复或未经确认改稿。')
 for s in shots:
  if not str(s.get('purpose','')).strip() or not s.get('visual',{}).get('description'):raise ValueError(s['id']+' 缺少画面目的或具体主画面说明。')
  if not isinstance(s.get('ip'),dict):raise ValueError(s['id']+' 缺少人物参与计划。')
  for a in s.get('visual',{}).get('assets',[]):
   if a.get('status') not in {'ready','pending','not-needed'}:raise ValueError(s['id']+' 素材需明确ready/pending/not-needed。')
   if a.get('status')=='ready' and a.get('path') and not (p/a['path']).is_file():raise ValueError('标为ready的素材不存在：'+a['path'])
 return b

def new(a):
 src=Path(a.script).expanduser().resolve();raw=src.read_text(encoding='utf-8-sig')
 if not norm(raw):raise ValueError('文案为空。')
 slug=re.sub(r'[^\w\u3400-\u9fff-]+','-',a.title).strip('-')[:55]
 p=Path(a.out).expanduser().resolve() if a.out else ROOT/'episodes'/f'{datetime.date.today():%Y%m%d}-{slug}'
 if p.exists():raise ValueError('目录已存在，未覆盖；使用--out指定新目录。')
 for d in ['input','brand','assets','audio','approvals','review','keyframes','qa','out']:(p/d).mkdir(parents=True,exist_ok=True)
 (p/'input/original.txt').write_text(raw);(p/'input/script.txt').write_text(raw);shutil.copy2(ROOT/'brand/style-lock.json',p/'brand/style-lock.json')
 from runtime_support import prepare_episode
 prepare_episode(p)
 ident='dudu-'+uuid.uuid4().hex[:12]
 save(p/'pipeline.json',{'projectId':ident,'title':a.title,'createdAt':stamp(),'sourceSha256':digest(p/'input/original.txt'),'projectRoot':str(ROOT),'status':'awaiting-presenter-choice'})
 save(p/'storyboard.json',{'projectId':ident,'title':a.title,'version':1,'presenterMode':'pending','shots':[]})
 save(p/'presenter-request.json',{'mode':'pending','status':'pending','question':'本期使用 通用 IP 小人物出镜，还是真人出镜？','userStatement':'','evidence':''})
 save(p/'audio-request.json',{'soundtrack':copy.deepcopy(read(p/'brand/style-lock.json')['audio']['soundtrack'])})
 save(p/'sources.json',{'sources':[],'note':'记录来源地址、日期、引用位置和素材文件；不将示意或生成内容充当事实证据。'})
 (p/'PROJECT_STATE.md').write_text('# '+a.title+'\n\n阶段：待确认出镜方式。先问清本期使用 IP 小人物还是真人，并用 presenter 命令记录；再按对应运镜编排 storyboard.json。尚无语义批准，收到用户同意后才继续配音/实际关键帧。\n')
 emit({'episode':str(p),'next':'先问清 IP 小人物还是真人，用 presenter 记录原话和出处；再编排分镜。'})

def presenter(a):
 p=Path(a.project).resolve();b=read(p/'storyboard.json')
 if (p/'approvals/semantic.json').exists():raise ValueError('已有语义审批记录；出镜方式属于语义变更，请保留旧版并准备新版审查，不在获批源文件上切换。')
 if not a.quote.strip() or not a.evidence.strip():raise ValueError('须记录用户本期选择原话和消息出处。')
 save(p/'presenter-request.json',{'mode':a.mode,'status':'confirmed','userStatement':a.quote.strip(),'evidence':a.evidence.strip(),'confirmedAt':stamp()})
 b['presenterMode']=a.mode;save(p/'storyboard.json',b)
 pipeline=p/'pipeline.json'
 if pipeline.exists():
  state=read(pipeline);state['status']='semantic-draft';save(pipeline,state)
 emit({'mode':a.mode,'next':'按出镜方式填写每镜 cameraPlan；真人模式 ip.mode=hidden，不使用 ip-scene。'})

def semantic(a):
 p=Path(a.project).resolve();validate_board(p);run([sys.executable,ROOT/'scripts/build_review.py',p,'--stage','semantic']);emit({'review':str(p/'review/index.html'),'status':'awaiting-user-semantic-approval'})

def approve(a):
 p=Path(a.project).resolve();validate_board(p)
 if not (p/'review/index.html').is_file():raise ValueError('尚未生成语义分镜HTML。')
 manifest=read(p/'review/build.json')
 if manifest.get('stage')!='semantic' or manifest.get('storyboardSha256')!=digest(p/'storyboard.json') or manifest.get('htmlSha256')!=digest(p/'review/index.html'):raise ValueError('当前HTML与语义稿不一致；先重新生成并展示semantic页面，再记录用户同意。')
 # This records evidence from an actual human message; it does not infer or grant approval.
 quote=a.quote.strip();evidence=a.evidence.strip()
 if not quote or not evidence:raise ValueError('须记录用户批准原话和消息/会话出处。')
 dst=p/'approvals/semantic.json'
 if dst.exists():
  old=read(dst);save(p/'approvals/history'/f'semantic-{datetime.datetime.now():%Y%m%d-%H%M%S-%f}.json',old)
 record={'status':'approved','approvedBy':'user','userStatement':quote,'evidence':evidence,'approvedAt':stamp(),'storyboardSha256':digest(p/'storyboard.json'),'storyboardVersion':read(p/'storyboard.json').get('version'),'reviewHtmlSha256':digest(p/'review/index.html')}
 save(dst,record);emit({'record':str(dst),'note':'仅记录真实用户同意；助手不得自行调用本命令代替用户审查。'})

def words_timeline(timing):
 chars=[];starts=[];ends=[];last=-math.inf
 for w in timing.get('words',[]):
  token=norm(w.get('word',w.get('text','')));s=float(w.get('startTime',w.get('start',0)));e=float(w.get('endTime',w.get('end',s)))
  if s<last-.05 or e<s:raise ValueError('词级时间倒序或负时长。')
  last=s
  for i,c in enumerate(token):chars.append(c);starts.append(s+(e-s)*i/max(1,len(token)));ends.append(s+(e-s)*(i+1)/max(1,len(token)))
 return ''.join(chars),starts,ends

def assemble(a):
 p=Path(a.project).resolve();require_semantic(p);b=validate_board(p);tim=read(p/'audio/timing.json');caps=read(p/'audio/captions.json');lock=read(p/'brand/style-lock.json');script=(p/'input/script.txt').read_text();clean=norm(script)
 joined,starts,ends=words_timeline(tim)
 caption_only=tim.get('timingGranularity')=='caption' and not tim.get('words')
 if not caption_only and joined!=clean:raise ValueError('本期词戳与工作稿不一致；不能借用旧配音或时间。')
 if ''.join(norm(c['text']) for c in caps)!=clean:raise ValueError('字幕没有完整覆盖工作稿。')
 fps=float(lock['canvas']['fps']);duration=float(tim['duration']);frames=round(duration*fps)
 if duration<=0 or abs(frames/fps-duration)>1e-5:raise ValueError('先将音频总时长对齐帧率。')
 if any(float(c['start'])<0 or float(c['end'])<=float(c['start']) or float(c['end'])>duration+.04 for c in caps):raise ValueError('字幕时间无效。')
 offsets=[];idx=0
 for s in b['shots']:offsets.append(idx);idx+=len(norm(s['narration']))
 if (p/'audio/shot-timing.json').is_file():
  shot_time=read(p/'audio/shot-timing.json');rows=shot_time.get('shots',[])
  if shot_time.get('storyboardSha256')!=digest(p/'storyboard.json') or [r.get('id') for r in rows]!=[s['id'] for s in b['shots']]:raise ValueError('逐镜时间文件与当前语义稿不匹配。')
  if abs(float(rows[0]['start']))>.001 or abs(float(rows[-1]['end'])-duration)>.04 or any(abs(float(rows[i]['end'])-float(rows[i+1]['start']))>.04 for i in range(len(rows)-1)):raise ValueError('逐镜时间未连续覆盖本期声音。')
  boundaries=[0.]+[round(float(r['start'])*fps)/fps for r in rows[1:]]+[duration]
 elif caption_only:raise ValueError('SRT导入需要本期audio/shot-timing.json；不能捏造逐字时间。')
 else:boundaries=[0.]+[round(starts[x]*fps)/fps for x in offsets[1:]]+[duration]
 scenes=[]
 for i,s in enumerate(b['shots']):
  item=copy.deepcopy(s.get('render',{}));typ=item.get('type',s.get('visual',{}).get('type'))
  if typ not in TYPES:raise ValueError(s['id']+' 尚未设置有效render.type。支持：'+', '.join(sorted(TYPES)))
  st,en=boundaries[i:i+2]
  if en<=st:raise ValueError(s['id']+' 镜头时长非正。')
  item.update({'id':s['id'],'type':typ,'start':round(st,6),'end':round(en,6),'title':item.get('title',s.get('screenText',''))})
  ip=copy.deepcopy(s.get('ip',{}));ip['visible']=ip.get('visible',typ!='ip-scene' and ip.get('mode','corner') not in ('hidden','scene'))
  def anchor_range(anchor,occurrence=1):
   if caption_only:raise ValueError('当前只有句级SRT。请补同音频词级对齐，或试听后填写动作绝对时间；不能伪造精确词锚点。')
   needle=norm(anchor);part=norm(s['narration']);pos=-1
   for _ in range(int(occurrence)):pos=part.find(needle,pos+1)
   if not needle or pos<0:raise ValueError(s['id']+' 找不到本句锚点 '+str(anchor))
   base=offsets[i]+pos;return starts[base],ends[base+len(needle)-1]
  emph=[]
  for e in ip.get('emphasis',[]):
   e=copy.deepcopy(e)
   if e.get('anchor'):
    x,y=anchor_range(e['anchor'],e.get('occurrence',1));e['start']=max(st,x-.10);e['end']=min(en-.05,y+float(e.get('hold',.12)))
   if 'start' not in e or 'end' not in e:raise ValueError(s['id']+' 出框必须有本句锚点或本期绝对时间。')
   e.setdefault('attack',.28);e['release']=min(float(e.get('release',.4)),max(.01,en-float(e['end'])))
   emph.append(e)
  ip['emphasis']=emph;item['ip']=ip
  if s.get('cameraPlan'):item['cameraPlan']=copy.deepcopy(s['cameraPlan'])
  for ann in item.get('annotations',[]):
   if ann.get('anchor'):ann['at']=anchor_range(ann['anchor'],ann.get('occurrence',1))[0]
  scenes.append(item)
 episode={'title':b['title'],'projectId':b['projectId'],'width':lock['canvas']['width'],'height':lock['canvas']['height'],'fps':fps,'duration':duration,'audio':'audio/mix.wav','narration':'audio/narration.wav','captions':caps,'scenes':scenes,'brand':lock,'timingGranularity':'caption' if caption_only else 'word','semanticSha256':digest(p/'storyboard.json'),'timingSha256':digest(p/'audio/timing.json')}
 if b.get('presenterMode'):episode['presenterMode']=b['presenterMode']
 save(p/'episode.json',episode);(p/'episode-data.js').write_text('window.EPISODE='+json.dumps(episode,ensure_ascii=False)+';\n')
 run([sys.executable,ROOT/'scripts/build_speech_envelope.py',p])
 emit({'episode':str(p/'episode.json'),'shots':len(scenes),'duration':duration,'frames':frames,'semanticSourceUnchanged':True})

def doctor(a):
 from doctor import inspect
 result=inspect();emit(result)
 if not result['localReady']:raise ValueError('本地环境未就绪，请按 docs/INSTALL.md 补齐依赖。')

def check(a):
 p=Path(a.project).resolve();e=read(p/'episode.json');f=p/'out/final.mp4';info=json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(f)]));v=next((x for x in info['streams'] if x['codec_type']=='video'),{});au=next((x for x in info['streams'] if x['codec_type']=='audio'),{});issues=[]
 if (v.get('width'),v.get('height'))!=(e['width'],e['height']):issues.append('分辨率不符')
 if int(v.get('nb_frames',-1))!=round(e['duration']*e['fps']):issues.append('帧数不符')
 num,den=v.get('r_frame_rate','0/1').split('/')
 if abs(float(num)/float(den)-e['fps'])>.001:issues.append('帧率不符')
 if int(au.get('sample_rate',0))!=48000 or int(au.get('channels',0))!=2:issues.append('音轨应为48kHz双声道')
 if abs(float(info['format']['duration'])-e['duration'])>.05:issues.append('成片时长不符')
 dec=subprocess.run([executable('ffmpeg'),'-v','error','-i',str(f),'-f','null','-'],capture_output=True,text=True)
 if dec.returncode or dec.stderr.strip():issues.append('完整解码异常：'+dec.stderr[-1000:])
 result={'passed':not issues,'issues':issues,'file':str(f),'duration':e['duration'],'frames':v.get('nb_frames'),'scope':'技术解码检查；还需检查内容、可读性、口型和连续运动，不等于完整人工试听。'};save(p/'qa/final-checks.json',result);emit(result)
 if issues:raise ValueError('验收未通过。')

def main():
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
 n=sub.add_parser('new');n.add_argument('--script',required=True);n.add_argument('--title',required=True);n.add_argument('--out')
 choice=sub.add_parser('presenter');choice.add_argument('project');choice.add_argument('--mode',choices=['ip','real'],required=True);choice.add_argument('--quote',required=True);choice.add_argument('--evidence',required=True)
 sub.add_parser('doctor')
 for c in ['semantic','approve','voice','audio','remix','assemble','frames','review','render','check','serve']:
  s=sub.add_parser(c);s.add_argument('project')
  if c=='approve':s.add_argument('--quote',required=True);s.add_argument('--evidence',required=True)
  if c=='serve':s.add_argument('--port',default='8866')
 a=ap.parse_args()
 if a.cmd in ['new','presenter','semantic','approve','assemble','doctor','check']:globals()[a.cmd](a);return
 p=Path(a.project).resolve()
 if a.cmd=='voice':require_semantic(p);run([executable('node'),ROOT/'scripts/synthesize.mjs','--project',p])
 elif a.cmd=='audio':require_semantic(p);run([sys.executable,ROOT/'scripts/audio_pipeline.py','--project',p])
 elif a.cmd=='remix':
  require_semantic(p);run([sys.executable,ROOT/'scripts/audio_pipeline.py','--project',p,'--remix-only']);emit({'next':'运行 assemble 刷新本期声音指纹，再渲染或审看。'})
 elif a.cmd=='frames':require_semantic(p);run([sys.executable,ROOT/'scripts/render_keyframes.py',p])
 elif a.cmd=='review':require_semantic(p);run([sys.executable,ROOT/'scripts/build_review.py',p,'--stage','keyframes'])
 elif a.cmd=='render':require_semantic(p);run([sys.executable,ROOT/'scripts/render_video.py',p])
 elif a.cmd=='serve':run([sys.executable,ROOT/'scripts/serve_review.py',p,'--port',a.port])
if __name__=='__main__':
 try:main()
 except (ValueError,FileNotFoundError) as e:sys.exit(str(e))
