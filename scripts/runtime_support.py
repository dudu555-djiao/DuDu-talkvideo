"""Portable helpers shared by preview, keyframes and final rendering."""
from pathlib import Path
import hashlib, importlib.util, json, math, os, re, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parent.parent

def ensure_dependencies(names=('playwright',)):
    missing=[n for n in names if importlib.util.find_spec(n) is None]
    if not missing:return
    candidates=[Path(os.environ.get('DUDU_PYTHON','/nonexistent')),ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')]
    for p in candidates:
        if p.exists() and str(p)!=sys.executable:
            test=subprocess.run([str(p),'-c',';'.join('import '+n for n in names)],capture_output=True)
            if test.returncode==0:os.execv(str(p),[str(p),*sys.argv])
    raise RuntimeError('Python dependencies missing: '+', '.join(missing)+'. Install with python3 -m pip install '+ ' '.join(missing))

def binary(name):
    candidates=[os.environ.get('DUDU_'+name.upper()),shutil.which(name),str(Path.home()/'.local/bin'/name),'/opt/homebrew/bin/'+name,'/usr/local/bin/'+name]
    for p in candidates:
        if p and Path(p).is_file():return p
    raise RuntimeError(name+' not found on PATH; set DUDU_'+name.upper())

def launch(pw):
    try:return pw.chromium.launch(headless=True,args=['--allow-file-access-from-files'])
    except Exception as first:
        for p in [os.environ.get('DUDU_CHROME'),'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']:
            if p and Path(p).exists():return pw.chromium.launch(executable_path=p,headless=True,args=['--allow-file-access-from-files'])
        raise RuntimeError('No Chromium runtime. Run python3 -m playwright install chromium') from first

def prepare_episode(project):
    p=Path(project).resolve();p.mkdir(parents=True,exist_ok=True)
    for f in (ROOT/'runtime').iterdir():
        if f.is_file():shutil.copy2(f,p/f.name)
    shutil.copytree(ROOT/'assets',p/'assets',dirs_exist_ok=True)
    env=p/'assets/speech-envelope.js'
    if not env.exists():env.write_text('window.SPEECH_ENVELOPE=[];\n')
    return p

def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def local_file(p,path):
    if not isinstance(path,str) or not path or '://' in path or Path(path).is_absolute():raise ValueError('Assets must use episode-relative paths: '+str(path))
    f=(p/path).resolve()
    if not f.is_relative_to(p.resolve()):raise ValueError('Asset escapes episode folder: '+path)
    if not f.is_file():raise ValueError('Missing asset: '+str(f))
    return f

def read_episode(p):
    e=json.loads((p/'episode.json').read_text())
    board_file=p/'storyboard.json'
    if not board_file.is_file():raise ValueError('Missing semantic storyboard')
    board_sha=hashlib.sha256(board_file.read_bytes()).hexdigest()
    if e.get('semanticSha256')!=board_sha:raise ValueError('episode.json is stale: semantic SHA differs; reassemble from the approved storyboard')
    board=json.loads(board_file.read_text())
    if [s.get('id') for s in e.get('scenes',[])]!=[s.get('id') for s in board.get('shots',[])]:raise ValueError('Episode scene IDs/order differ from semantic storyboard')
    if e.get('timingSha256'):
        timing=p/'audio/timing.json'
        if not timing.is_file() or hashlib.sha256(timing.read_bytes()).hexdigest()!=e['timingSha256']:raise ValueError('Audio timing changed; reassemble episode.json')
    for key in ['duration','fps','width','height']:
        if not finite(e.get(key)) or e[key]<=0:raise ValueError('Invalid '+key)
    if e['width']%2 or e['height']%2:raise ValueError('Output dimensions must be even')
    if abs(e['duration']*e['fps']-round(e['duration']*e['fps']))>.02:raise ValueError('Duration must align to the frame grid')
    if not e.get('scenes'):raise ValueError('No scenes')
    allowed={'chapter','prompt-media','compare','flow','note','ip-scene'};previous=0;ids=set()
    for s in e['scenes']:
        if not isinstance(s.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]+',s['id']) or s['id'] in ids:raise ValueError('Scene IDs must be unique safe identifiers (letters/numbers/_/-)')
        ids.add(s['id'])
        if s.get('type') not in allowed:raise ValueError('Unsupported scene type '+str(s.get('type')))
        if not all(finite(s.get(k)) for k in ['start','end']) or s['end']<=s['start'] or abs(s['start']-previous)>1e-5:raise ValueError('Scene gap/overlap/invalid timing: '+s['id'])
        previous=s['end']
        if s['type']=='chapter' and not s.get('title'):raise ValueError('Chapter title required')
        if s['type']=='prompt-media' and not s.get('media'):raise ValueError('prompt-media needs real media')
        if s['type']=='compare' and not all(s.get(x) for x in ['left','right']):raise ValueError('Compare needs left and right')
        if s['type']=='flow' and not 1<=len(s.get('steps',[]))<=4:raise ValueError('Flow supports 1–4 steps')
        if s['type']=='ip-scene' and 'pose' in s and (type(s['pose']) is not int or s['pose'] not in [0,1,2]):raise ValueError('IP scene pose must be 0, 1 or 2')
        for em in s.get('ip',{}).get('emphasis',[]):
            if not all(finite(em.get(k)) for k in ['start','end']) or not s['start']<=em['start']<=em['end']<=s['end']:raise ValueError('Invalid emphasis timing: '+s['id'])
            if em.get('attack',.28)<=0 or em.get('release',.4)<=0:raise ValueError('Emphasis attack/release must be positive')
            if em['end']+em.get('release',.4)>s['end']+.001:raise ValueError('Emphasis release crosses scene boundary: '+s['id'])
        for t in s.get('keyframes',[]):
            if not finite(t) or not s['start']<=t<s['end']:raise ValueError('Keyframe outside scene '+s['id'])
        for m in [s.get('media'),s.get('left',{}).get('media'),s.get('right',{}).get('media')]:
            if not m:continue
            local_file(p,m.get('src'))
            if m.get('kind','image') not in ['image','video']:raise ValueError('Invalid media kind')
            if m.get('kind')=='video':
                info=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(p/m['src'])]))
                length=float(info['format']['duration']);rate=m.get('playbackRate',1);begin=m.get('in',0)
                if not finite(rate) or rate<=0 or not finite(begin) or begin<0 or begin+(s['end']-s['start'])*rate>length+.05:raise ValueError('Video is too short / invalid trim for '+s['id'])
        if s.get('background'):local_file(p,s['background'])
    if abs(previous-e['duration'])>1e-5:raise ValueError('Scenes must cover the complete duration')
    prev=0
    for c in e.get('captions',[]):
        if not all(finite(c.get(k)) for k in ['start','end']) or not 0<=c['start']<c['end']<=e['duration']+.001 or c['start']<prev-.001:raise ValueError('Invalid/overlapping caption timing')
        if not c.get('text'):raise ValueError('Caption is empty')
        prev=c['end']
    e.setdefault('captions',[])
    audio=local_file(p,e.get('audio'));narration=local_file(p,e.get('narration','audio/narration.wav'))
    info=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-show_format','-of','json',str(audio)]))
    if abs(float(info['format']['duration'])-e['duration'])>max(.08,1/e['fps']):raise ValueError('Audio duration differs from episode duration; pad/trim explicitly first')
    (p/'episode-data.js').write_text('window.EPISODE='+json.dumps(e,ensure_ascii=False)+';\n')
    return e

def make_envelope(p,e):
    from build_speech_envelope import build
    return build(p,e['fps'],round(e['duration']*e['fps']),e.get('narration','audio/narration.wav'))

def open_page(browser,p,e,errors):
    page=browser.new_page(viewport={'width':e['width'],'height':e['height']},device_scale_factor=1)
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto((p/'index.html').as_uri());page.wait_for_function('window.ready===true || window.loadError',timeout=60000)
    error=page.evaluate('window.loadError')
    if error:raise RuntimeError(error)
    return page

def write_json(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
