#!/usr/bin/env python3
"""DuDu-talkvideo full narration, same-take timing and semantic-shot alignment."""
from __future__ import annotations
import argparse,difflib,hashlib,json,math,os,re,shutil,subprocess,tempfile,unicodedata,wave
from approval import require_semantic, digest
from pathlib import Path
import numpy as np


def load(file):
    return json.loads(file.read_text(encoding='utf-8'))


def save(file,data):
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def run(args):
    args=list(args)
    if args[0] in ('ffmpeg','ffprobe'):
        from runtime_support import binary
        args[0]=binary(args[0])
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError(f'{args[0]} 执行失败: '+p.stderr[-1600:])
    return p


def audio_duration(file):
    result=run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(file)])
    value=float(result.stdout.strip())
    if not math.isfinite(value) or value<=0:raise ValueError('配音文件时长无效。')
    return value


def normalized_characters(text):
    chars=[];positions=[]
    for i,c in enumerate(text):
        for v in unicodedata.normalize('NFKC',c).lower():
            if v.isalnum():chars.append(v);positions.append(i)
    return ''.join(chars),positions


def caption_fragments(text,maximum=22):
    """Keep every visible source character; favor punctuation and Latin words."""
    fragments=[];start=0;weight=0.0
    for i,c in enumerate(text):
        weight+=1 if '\u3400'<=c<='\u9fff' else .55
        punctuation=c in '，。！？；：\n!?;' and (weight>=6 or c in '。！？\n!?')
        latin_continuation=(i+1<len(text) and c.isascii() and c.isalnum()
                            and text[i+1].isascii() and text[i+1].isalnum())
        if punctuation or (weight>=maximum and not latin_continuation):
            if text[start:i+1].strip():fragments.append((start,i+1,text[start:i+1].strip()))
            start=i+1;weight=0
    if text[start:].strip():fragments.append((start,len(text),text[start:].strip()))
    return fragments


def make_captions(text,words,lead,duration,maximum=22):
    """Map original script onto the word stream, without losing punctuation."""
    normalized,source_positions=normalized_characters(text)
    timed=[];char_times=[]
    for word in words:
        token=str(word.get('word',''));start=float(word['startTime']);end=float(word['endTime'])
        if not(math.isfinite(start) and math.isfinite(end) and 0<=start<=end):
            raise ValueError('字级时间戳包含非法数值。')
        chars,_=normalized_characters(token)
        for i,c in enumerate(chars):
            timed.append(c)
            # Only split inside a multi-character returned word when wrapping needs it.
            char_times.append((start+(end-start)*i/max(1,len(chars)),start+(end-start)*(i+1)/max(1,len(chars))))
    timed=''.join(timed)
    if not normalized or not timed:raise ValueError('缺少能与正文对应的同次字级时间戳。')
    align=difflib.SequenceMatcher(None,normalized,timed,autojunk=False)
    if align.ratio()<.85:raise ValueError('时间戳文本与文案差异过大，需要核对本次配音正文，不能套旧字幕。')
    source_to_timed={}
    for tag,i1,i2,j1,j2 in align.get_opcodes():
        if tag=='equal':
            for k in range(i2-i1):source_to_timed[i1+k]=j1+k
        elif tag in ('replace','delete'):
            for k in range(i2-i1):source_to_timed[i1+k]=min(len(timed)-1,max(0,j1+round(k*max(0,j2-j1-1)/max(1,i2-i1-1))))
    result=[]
    for left,right,content in caption_fragments(text,maximum):
        points=[i for i,pos in enumerate(source_positions) if left<=pos<right]
        if points:
            start=char_times[source_to_timed[points[0]]][0]+lead
            end=char_times[source_to_timed[points[-1]]][1]+lead
        elif result:
            result[-1]['text']+=content;continue
        else:
            start=lead;end=lead+.12
        result.append({'start':round(start,6),'end':round(end,6),'text':content})
    for i,c in enumerate(result):
        next_start=result[i+1]['start'] if i+1<len(result) else duration-.03
        c['end']=round(min(next_start-.015,max(c['end']+.1,c['start']+.05)),6)
        if c['end']<=c['start']:c['end']=round(min(duration,c['start']+.025),6)
    if re.sub(r'\s+','',''.join(c['text'] for c in result))!=re.sub(r'\s+','',text):
        raise AssertionError('字幕分段遗漏正文，停止输出。')
    return result


def srt_stamp(t):
    ms=max(0,round(t*1000))
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def write_wav(file,arr,sr):
    file.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(file),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr)
        w.writeframes((np.clip(arr,-.99,.99)*32767).astype(np.int16).tobytes())


def fit_pcm_duration(file,duration,sr):
    # FFmpeg filter flushing can leave a WAV a few samples/frames short.
    # Only the already-padded tail is changed; raw narration is untouched.
    with wave.open(str(file),'rb') as w:
        params=w.getparams();data=w.readframes(w.getnframes())
    expected=round(duration*sr)*params.nchannels*params.sampwidth
    data=(data+bytes(max(0,expected-len(data))))[:expected]
    with wave.open(str(file),'wb') as w:
        w.setparams(params);w.writeframes(data)


def soundtrack(duration,sr,storyboard):
    n=round(duration*sr);rng=np.random.default_rng(20261022)
    bg=np.zeros((n,2));sfx=np.zeros((n,2));cues=[]
    def add(dst,start,sound,pan=0):
        i=round(start*sr)
        if i<0:sound=sound[-i:];i=0
        size=min(len(sound),n-i)
        if size<=0:return
        dst[i:i+size,0]+=sound[:size]*math.sqrt((1-pan)/2)
        dst[i:i+size,1]+=sound[:size]*math.sqrt((1+pan)/2)
    def felt(midi,length=1.6):
        t=np.arange(round(length*sr))/sr;f=440*2**((midi-69)/12)
        return (np.sin(2*np.pi*f*t)+.15*np.sin(4*np.pi*f*t))*np.exp(-t*8)*np.minimum(1,t/.009)
    def paper(length=.13):
        t=np.arange(round(length*sr))/sr;noise=rng.normal(0,1,len(t)+28)
        soft=np.convolve(noise,np.ones(20)/20,'valid')[:len(t)];v=np.diff(soft,prepend=soft[0]);v/=max(np.max(np.abs(v)),1e-8)
        return v*np.sin(np.pi*t/length)**1.3
    def tap(length=.12):
        t=np.arange(round(length*sr))/sr
        return (np.sin(2*np.pi*(290*t-190*t*t))*.75+np.sin(2*np.pi*1150*t)*.1)*np.exp(-t*55)*np.minimum(1,t/.003)
    def idea():
        v=np.zeros(round(.7*sr))
        for at,midi in [(0,79),(.075,84),(.15,88)]:
            sound=felt(midi,.5)*.28;i=round(at*sr);size=min(len(sound),len(v)-i);v[i:i+size]+=sound[:size]
        return v
    if storyboard:
        audio=storyboard.get('audio') or {}
        if audio.get('music',False):
            beat=60/float(audio.get('bpm',96));bar=8*beat
            chords=[[60,64,67,71],[57,60,64,67],[53,57,60,64],[55,59,62,67]]
            for k in range(math.ceil(duration/bar)):
                chord=chords[k%len(chords)];base=k*bar
                for offset,index in [(0,0),(1.5,2),(3,1),(4.5,3),(6,2),(7.5,1)]:
                    add(bg,base+offset*beat,felt(chord[index])*.19,-.25 if index%2 else .25)
            for k in range(math.ceil(duration/beat)):
                add(bg,k*beat,tap()*.045)
            rms=np.sqrt(np.mean(bg**2));bg*=float(audio.get('musicRMS',.018))/max(rms,1e-8)
            times=np.arange(n)/sr;bg*=(np.minimum(1,times/.35)*np.minimum(1,np.maximum(0,(duration-times)/.8)))[:,None]
        def append_cue(item,start=0,scene_relative=False):
            if isinstance(item,str):item={'kind':item,'offset':0}
            if not isinstance(item,dict):return
            # Explicit time is always global (including anchors assembled earlier).
            # Both at and offset inside a scene are relative to that scene start.
            if 'time' in item:at=float(item['time'])
            elif 'offset' in item:at=start+float(item['offset'])
            elif 'at' in item:at=(start if scene_relative else 0)+float(item['at'])
            else:at=start
            kind=str(item.get('kind',item.get('type',item.get('sound','paper'))))
            if 0<=at<duration and kind not in ('none','silent'):cues.append({'time':round(at,6),'kind':kind})
        for item in storyboard.get('cues',[]):append_cue(item)
        for i,scene in enumerate(storyboard.get('scenes',[])):
            start=float(scene.get('start',0));local=scene.get('cues',scene.get('soundCues',[]))
            if local:
                for item in local:append_cue(item,start,scene_relative=True)
            elif i>0:
                kind='idea' if scene.get('type') in ('closing','outro','close','conclusion') else 'paper'
                append_cue({'time':start+.1,'kind':kind})
        unique=[]
        for cue in sorted(cues,key=lambda c:c['time']):
            if any(c['kind']==cue['kind'] and abs(c['time']-cue['time'])<.08 for c in unique):continue
            unique.append(cue)
        cues=unique
        for cue in cues:
            kind=cue['kind']
            if kind in ('idea','spark','aha'):sound=idea()*.20
            elif kind in ('tick','check','tap'):sound=tap()*.08
            else:sound=paper()*.075
            add(sfx,cue['time'],sound)
    return bg,sfx,cues


def normalize_mix(source,target,sr,duration,settings):
    loudness=float(settings.get('lufs',-15.5));peak=float(settings.get('truePeak',-1.2))
    measure=run(['ffmpeg','-hide_banner','-nostats','-i',str(source),'-af',f'loudnorm=I={loudness}:TP={peak}:LRA=7:print_format=json','-f','null','-'])
    matches=re.findall(r'\{[\s\S]*?\}',measure.stderr)
    stats=json.loads(matches[-1])
    if not math.isfinite(float(stats['input_i'])):raise ValueError('混音信号无效或全静音。')
    filt=f'loudnorm=I={loudness}:TP={peak}:LRA=7:linear=true:'+':'.join([f'measured_I={stats["input_i"]}',f'measured_TP={stats["input_tp"]}',f'measured_LRA={stats["input_lra"]}',f'measured_thresh={stats["input_thresh"]}',f'offset={stats["target_offset"]}'])
    run(['ffmpeg','-v','error','-y','-i',str(source),'-af',filt,'-ar',str(sr),'-ac','2','-t',f'{duration:.9f}',str(target)])
    fit_pcm_duration(target,duration,sr)
    return stats


ROOT=Path(__file__).resolve().parents[1]
VOICE='zh_male_liufei_uranus_bigtts'
DEFAULTS={'voice':VOICE,'resource':'seed-tts-2.0','speed':-25,'leadIn':.2,'tail':.6,'sampleRate':48000,'lufs':-16,'truePeak':-1.5}


def script_and_shots(project):
    require_semantic(project)
    text=(project/'input/script.txt').read_text(encoding='utf-8').strip()
    storyboard=load(project/'storyboard.json'); shots=storyboard.get('shots',[])
    if not text or not shots:raise ValueError('文案或语义分镜为空。')
    ids=[s.get('id') for s in shots]
    if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('语义镜头 id 必须唯一且非空。')
    if normalized_characters(''.join(str(s.get('narration','')) for s in shots))[0]!=normalized_characters(text)[0]:
        raise ValueError('shots.narration 必须按顺序完整覆盖 input/script.txt，不能漏句或仅配音20秒。')
    return text,storyboard,shots


def settings_for(project):
    settings=DEFAULTS.copy()
    for file in [ROOT/'brand/style-lock.json',project/'brand/style-lock.json']:
        if file.exists():settings.update(load(file).get('audio',{}))
    settings.update({'voice':VOICE,'resource':'seed-tts-2.0','speed':-25,'sampleRate':48000,'lufs':-16,'truePeak':-1.5})
    return settings


def validate_words(words,duration):
    previous=-1
    for w in words:
        start=float(w['startTime']);end=float(w['endTime'])
        if not all(math.isfinite(x) for x in [start,end]) or start<0 or start<previous-.00001 or end<start or end>duration+.035:
            raise ValueError('词级时间戳无序、非法或超出配套音频时长。')
        previous=start


def char_time_map(text,words):
    source,_=normalized_characters(text);timed='';times=[]
    for w in words:
        chars,_=normalized_characters(str(w['word']));start=float(w['startTime']);end=float(w['endTime'])
        timed+=chars
        times.extend([(start+(end-start)*i/len(chars),start+(end-start)*(i+1)/len(chars)) for i in range(len(chars))])
    if not source or not timed:raise ValueError('没有可对齐的真实时间戳。')
    matcher=difflib.SequenceMatcher(None,source,timed,autojunk=False)
    if matcher.ratio()<.95:raise ValueError('正文与配套时间戳差异超过5%，需核对本次音频正文。')
    mapping={}
    for tag,i1,i2,j1,j2 in matcher.get_opcodes():
        for k in range(i2-i1):
            j=j1+k if tag=='equal' else min(len(times)-1,max(0,j1+round(k*max(0,j2-j1-1)/max(1,i2-i1-1))))
            mapping[i1+k]=times[j]
    return mapping,matcher.ratio()


def shot_times(text,shots,words,captions,duration,granularity):
    if words:
        mapping,ratio=char_time_map(text,words);cursor=0;out=[]
        for s in shots:
            size=len(normalized_characters(str(s.get('narration','')))[0])
            if not size:raise ValueError('语义镜头必须有旁白；无旁白插镜请在镜头内设计，不添加空 narration。')
            out.append({'id':s['id'],'narrationStart':mapping[cursor][0],'narrationEnd':mapping[cursor+size-1][1]})
            cursor+=size
    else:
        # Caption-only import is accepted only when each shot boundary is a real SRT boundary.
        # Never divide a subtitle duration by character count and call it word timing.
        bounds={0:0};cursor=0;starts={};ends={}
        for c in captions:
            size=len(normalized_characters(c['text'])[0]);starts[cursor]=c['start'];cursor+=size;ends[cursor]=c['end']
        out=[];cursor=0;ratio=1
        for s in shots:
            size=len(normalized_characters(str(s.get('narration','')))[0])
            if not size or cursor not in starts or cursor+size not in ends:raise ValueError('SRT导入只有句级时间；请让SRT边界覆盖镜头边界，或提供同音频词级时间戳，不能伪造逐字时间。')
            out.append({'id':s['id'],'narrationStart':starts[cursor],'narrationEnd':ends[cursor+size]});cursor+=size
    for i,s in enumerate(out):
        s['start']=0 if i==0 else out[i-1]['end']
        s['end']=duration if i==len(out)-1 else max(s['narrationEnd'],(s['narrationEnd']+out[i+1]['narrationStart'])/2)
        s['timingGranularity']=granularity
        for k in ['start','end','narrationStart','narrationEnd']:s[k]=round(s[k],6)
    return out,ratio


def read_srt(file):
    def stamp(value):
        h,m,s=re.split('[:,.]',value)[:3];ms=re.split('[:,.]',value)[3]
        return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
    result=[]
    for block in re.split(r'\n\s*\n',Path(file).read_text(encoding='utf-8-sig').replace('\r','').strip()):
        lines=block.splitlines();line=next((i for i,x in enumerate(lines) if '-->' in x),None)
        if line is None:continue
        match=re.match(r'\s*(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)',lines[line])
        if not match:raise ValueError('SRT 时间格式无效。')
        result.append({'start':stamp(match[1]),'end':stamp(match[2]),'text':' '.join(lines[line+1:]).strip()})
    if not result:raise ValueError('SRT没有字幕。')
    return result


def validate_captions(text,captions,duration):
    if normalized_characters(''.join(c['text'] for c in captions))[0]!=normalized_characters(text)[0]:raise ValueError('字幕必须完整覆盖本期旁白。')
    previous=0
    for c in captions:
        a=float(c['start']);b=float(c['end'])
        if not all(math.isfinite(x) for x in [a,b]) or a<previous-.002 or b<=a or b>duration+.035:raise ValueError('字幕时间非法、重叠或超出音频。')
        previous=b


def check(project):
    text,storyboard,shots=script_and_shots(project);audio=project/'audio';timing=load(audio/'timing.json');duration=audio_duration(audio/'mix.wav')
    if normalized_characters(timing['text'])[0]!=normalized_characters(text)[0]:raise ValueError('现成配音已过期，文本不匹配。')
    if timing.get('storyboardSha256')!=digest(project/'storyboard.json'):raise ValueError('现成配音未绑定当前已批准语义稿。')
    if abs(duration-timing['duration'])>.001:raise ValueError('音频和时间轴时长不一致。')
    if timing.get('narrationSha256')!=digest(audio/'narration.wav') or timing.get('mixSha256')!=digest(audio/'mix.wav'):raise ValueError('已处理音频被替换，需重新核对对应时间戳。')
    words=timing.get('words',[]);validate_words(words,duration);validate_captions(text,timing['captions'],duration)
    if abs(timing['durationFrames']/timing['fps']-timing['duration'])>.000001:raise ValueError('帧数和实际音频时长不一致。')
    if load(audio/'captions.json')!=timing['captions']:raise ValueError('字幕JSON与本次时间轴不一致。')
    validate_captions(text,read_srt(audio/'narration.srt'),duration)
    expected,ratio=shot_times(text,shots,words,timing['captions'],duration,timing.get('timingGranularity','word'))
    if load(audio/'shot-timing.json')['shots']!=expected:raise ValueError('镜头时间轴与本次字幕不一致。')
    return {'passed':True,'duration':duration,'durationFrames':timing['durationFrames'],'shots':len(shots),'words':len(words),'captions':len(timing['captions']),'alignmentRatio':ratio,'truncated':False}


def mix_soundtrack(project,settings,request,storyboard,timing):
    from sound_design import resolve
    audio=project/'audio';duration=float(timing['duration']);sr=48000
    design=resolve(settings,request,storyboard,timing,char_time_map,normalized_characters)
    config=design['resolved'];cues=design['cues']
    bg,sx,_=soundtrack(duration,sr,{'audio':{'music':config['music'],'bpm':config['bpm'],'musicRMS':config['musicRMS']},'cues':cues})
    # Always replace both stems, including explicit silence, to avoid stale previous mixes.
    write_wav(audio/'music.wav',bg,sr);write_wav(audio/'sfx.wav',sx,sr)
    if config['music'] or cues:
        with tempfile.TemporaryDirectory(prefix='dudu-remix-',dir=audio) as temp:
            premix=Path(temp)/'premix.wav'
            run(['ffmpeg','-v','error','-y','-i',str(audio/'narration.wav'),'-i',str(audio/'music.wav'),'-i',str(audio/'sfx.wav'),'-filter_complex','[0:a][1:a][2:a]amix=inputs=3:normalize=0:duration=longest[m]','-map','[m]','-ar',str(sr),'-ac','2',str(premix)])
            normalize_mix(premix,audio/'mix.wav',sr,duration,settings)
    else:shutil.copy2(audio/'narration.wav',audio/'mix.wav')
    design.update({'duration':duration,'durationFrames':timing['durationFrames'],'sampleRate':sr,'narrationSha256':digest(audio/'narration.wav'),'mixSha256':digest(audio/'mix.wav'),'musicSha256':digest(audio/'music.wav'),'sfxSha256':digest(audio/'sfx.wav'),'musicMeasuredRMS':float(np.sqrt(np.mean(bg**2))),'sfxMeasuredRMS':float(np.sqrt(np.mean(sx**2))),'source':'Deterministic original felt music and paper/tick/idea synthesis; narration remains a separate unchanged stem.'})
    save(audio/'soundtrack.json',design)
    return cues


def audio_report(project,cues,**extra):
    measured=run(['ffmpeg','-hide_banner','-nostats','-i',str(project/'audio/mix.wav'),'-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'])
    stats=json.loads(re.findall(r'\{[\s\S]*?\}',measured.stderr)[-1])
    report=check(project);report.update({'sampleRate':48000,'channels':2,'targetLUFS':-16,'targetTruePeak':-1.5,'measured':stats,'cues':cues,**extra})
    save(project/'audio/audio-checks.json',report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True);parser.add_argument('--check-only',action='store_true');parser.add_argument('--remix-only',action='store_true')
    parser.add_argument('--import-audio');group=parser.add_mutually_exclusive_group();group.add_argument('--timing');group.add_argument('--srt')
    args=parser.parse_args();project=Path(args.project).expanduser().resolve()
    if args.check_only:print(json.dumps(check(project),ensure_ascii=False));return
    text,storyboard,shots=script_and_shots(project);settings=settings_for(project)
    request=load(project/'audio-request.json') if (project/'audio-request.json').exists() else {}
    if args.remix_only:
        if args.import_audio or args.timing or args.srt:raise ValueError('--remix-only不能与音频导入参数同时使用。')
        check(project);timing=load(project/'audio/timing.json');before=digest(project/'audio/narration.wav')
        cues=mix_soundtrack(project,settings,request,storyboard,timing)
        if digest(project/'audio/narration.wav')!=before:raise AssertionError('重新配乐不能修改旁白。')
        timing['mixSha256']=digest(project/'audio/mix.wav');save(project/'audio/timing.json',timing)
        print(json.dumps(audio_report(project,cues,remixOnly=True,narrationUnchanged=True),ensure_ascii=False));return
    fps=float(load(project/'episode.json').get('fps',30)) if (project/'episode.json').exists() else 30
    if not math.isfinite(fps) or fps<=0:raise ValueError('fps必须大于0。')
    audio=project/'audio';audio.mkdir(parents=True,exist_ok=True);sr=48000;importing=bool(args.import_audio)
    if importing:
        if not (args.timing or args.srt):raise ValueError('导入成品需提供同音频 --timing JSON 或 --srt SRT。')
        source=Path(args.import_audio).expanduser().resolve();raw=load(Path(args.timing)) if args.timing else {'words':[]};lead=0;tail=0
        if raw.get('text') and normalized_characters(raw['text'])[0]!=normalized_characters(text)[0]:raise ValueError('导入时间戳正文与本期文案不符。')
        known_hash=raw.get('narrationSha256') or raw.get('audioSha256')
        if known_hash and known_hash!=digest(source):raise ValueError('导入音频与提供的时间戳指纹不匹配。')
        if source in [audio/'narration.wav',audio/'mix.wav']:raise ValueError('请导入独立原始文件，不覆盖当前音频来源。')
    else:
        if args.timing or args.srt:raise ValueError('--timing/--srt 必须和 --import-audio 同用。')
        source=audio/'narration-raw.wav';raw=load(audio/'narration-raw-timing.json')
        if raw.get('text','').strip()!=text:raise ValueError('原音正文与本期文案不同，不能套用旧音。')
        if raw.get('voice')!=VOICE or raw.get('resource')!='seed-tts-2.0' or raw.get('speed')!=-25:raise ValueError('原音音色/资源/速度与定版刘飞参数不符。')
        if raw.get('audioSha256') and raw['audioSha256']!=digest(source):raise ValueError('原音内容指纹不匹配，时间戳不能复用。')
        lead=float(request.get('leadIn',settings['leadIn']));tail=float(request.get('tail',settings['tail']))
    if not all(math.isfinite(x) and x>=0 for x in [lead,tail]):raise ValueError('首尾停顿非法。')
    raw_duration=audio_duration(source);words=raw.get('words',[]);validate_words(words,raw_duration)
    if not words and not args.srt:raise ValueError('缺少同次词级时间戳，不能伪造逐字字幕。')
    if words:char_time_map(text,words)
    imported_captions=read_srt(args.srt) if args.srt else None
    if imported_captions:validate_captions(text,imported_captions,raw_duration)
    with tempfile.TemporaryDirectory(prefix='dudu-audio-',dir=audio) as tmp:
        tmp=Path(tmp);decoded=tmp/'decoded.wav'
        run(['ffmpeg','-v','error','-y','-i',str(source),'-ar',str(sr),'-ac','2','-c:a','pcm_s16le',str(decoded)])
        with wave.open(str(decoded),'rb') as w:pcm=np.frombuffer(w.readframes(w.getnframes()),np.int16).reshape(-1,2).copy()
        pauses=[]
        if request.get('pauses') and importing:raise ValueError('成品音频导入保留现有时间，不额外插入停顿。')
        if request.get('pauses'):
            initial,_=shot_times(text,shots,words,[],raw_duration,'word')
            for item in request['pauses']:
                idx=next((i for i,s in enumerate(initial) if s['id']==item.get('afterShot')),None)
                if idx is None or idx==len(initial)-1:raise ValueError('停顿 afterShot 必须是非末尾镜头id。')
                extra=float(item['duration']);left=initial[idx]['narrationEnd'];right=initial[idx+1]['narrationStart']
                if not math.isfinite(extra) or not 0<extra<=2 or right-left<.04:raise ValueError('只在词级时间戳证明的句间静音内插入0–2秒；无安全间隙请人工核对。')
                lo=round((left+.01)*sr);hi=round((right-.01)*sr);window=max(1,round(.005*sr))
                choices=range(lo,max(lo+1,hi-window),window)
                cut=min(choices,key=lambda i:np.mean(pcm[i:i+window].astype(float)**2))+window//2
                pauses.append({'rawCut':cut/sr,'duration':extra,'afterShot':item['afterShot']})
        pauses.sort(key=lambda x:x['rawCut']);chunks=[np.zeros((round(lead*sr),2),np.int16)];previous=0
        for item in pauses:
            cut=round(item['rawCut']*sr);chunks.extend([pcm[previous:cut],np.zeros((round(item['duration']*sr),2),np.int16)]);previous=cut
        chunks.append(pcm[previous:]);assembled=np.concatenate(chunks)
        frames=math.ceil((len(assembled)/sr+tail)*fps-1e-9);duration=frames/fps
        assembled=np.pad(assembled,((0,round(duration*sr)-len(assembled)),(0,0)))
        pre=tmp/'prepared.wav'
        with wave.open(str(pre),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes(assembled.tobytes())
        normalize_mix(pre,audio/'narration.wav',sr,duration,settings)
        shifted=[]
        for word in words:
            start=float(word['startTime']);end=float(word['endTime']);offset=lead+sum(x['duration'] for x in pauses if start>=x['rawCut'])
            shifted.append({**word,'startTime':round(start+offset,6),'endTime':round(end+offset,6)})
        captions=imported_captions or make_captions(text,shifted,0,duration)
        validate_words(shifted,duration);validate_captions(text,captions,duration)
        granularity='word' if shifted else 'caption';aligned,ratio=shot_times(text,shots,shifted,captions,duration,granularity)
        cues=mix_soundtrack(project,settings,request,storyboard,{'text':text,'duration':duration,'durationFrames':frames,'words':shifted,'shots':aligned,'timingGranularity':granularity})
    timing={'text':text,'duration':duration,'durationFrames':frames,'fps':fps,'voice':raw.get('voice','user-provided'),'engine':'user-provided' if importing else 'Volcengine Seed TTS 2.0','sourceDuration':raw_duration,'leadIn':lead,'tail':tail,'insertedPauses':pauses,'timingSource':'Imported same-audio timing' if importing else 'Word timestamps returned by the same complete synthesis, shifted by exact inserted silence.','timingGranularity':granularity,'words':shifted,'captions':captions,'shots':aligned,'alignmentRatio':ratio,'storyboardSha256':digest(project/'storyboard.json'),'sourceSha256':digest(source),'narrationSha256':digest(audio/'narration.wav'),'mixSha256':digest(audio/'mix.wav')}
    save(audio/'timing.json',timing);save(audio/'captions.json',captions)
    save(audio/'shot-timing.json',{'duration':duration,'fps':fps,'storyboardSha256':timing['storyboardSha256'],'shots':aligned})
    srt=[]
    for i,c in enumerate(captions,1):srt.extend([str(i),f'{srt_stamp(c["start"])} --> {srt_stamp(c["end"])}',c['text'],''])
    (audio/'narration.srt').write_text('\n'.join(srt),encoding='utf-8')
    print(json.dumps(audio_report(project,cues,imported=importing),ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,KeyError,FileNotFoundError) as error:raise SystemExit(str(error))
