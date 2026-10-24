"""Resolve restrained paper/tick/idea cues from this episode's approved meaning and timing."""
import math


def resolve(settings, request, storyboard, timing, char_time_map, normalize):
    defaults={'music':True,'bpm':96,'musicRMS':.018,'sfx':True,'cuePolicy':'semantic','minimumCueGap':.6}
    defaults.update(settings.get('soundtrack') or {})
    override=request.get('soundtrack') or {}
    if not isinstance(override,dict):raise ValueError('audio-request.soundtrack须为对象。')
    config={**defaults,**override};duration=float(timing['duration']);shots=storyboard['shots'];aligned={x['id']:x for x in timing['shots']}
    for name in ['bpm','musicRMS','minimumCueGap']:
        config[name]=float(config[name])
        if not math.isfinite(config[name]) or config[name]<0:raise ValueError('无效声音参数 '+name)
    if not 0<config['bpm']<=300:raise ValueError('bpm须在0到300之间。')
    if config['musicRMS']>1:raise ValueError('musicRMS不能超过1。')
    if not isinstance(config['music'],bool) or not isinstance(config['sfx'],bool):raise ValueError('music/sfx须为true或false。')
    cursor=0;offsets={};byid={s['id']:s for s in shots};words=timing.get('words',[])
    for s in shots:offsets[s['id']]=cursor;cursor+=len(normalize(s['narration'])[0])
    mapping=char_time_map(timing['text'],words)[0] if words else None
    warnings=[];candidates=[]
    def add(cue, shot=None, basis='explicit', priority=2):
        if not isinstance(cue,dict):raise ValueError('声音事件必须为对象。')
        kind=cue.get('kind','paper');kind={'tap':'tick','check':'tick','spark':'idea','aha':'idea'}.get(kind,kind)
        if kind in ('none','silent'):return
        if kind not in ('paper','tick','idea'):raise ValueError('不支持的音效 '+str(kind))
        sid=cue.get('shotId',shot['id'] if shot else None)
        if sid is not None and sid not in byid:raise ValueError('音效指定的镜头不存在 '+str(sid))
        target=byid.get(sid);row=aligned.get(sid)
        if 'time' in cue:at=float(cue['time']);trigger='absolute-time'
        elif 'at' in cue:at=float(cue['at']);trigger='absolute-time'
        elif cue.get('anchor'):
            if mapping is None:raise ValueError('SRT仅句级时间，音效词锚点需要同音频词级时间戳或明确time；不估算逐字位置。')
            part=normalize(target['narration'] if target else timing['text'])[0];needle=normalize(cue['anchor'])[0];pos=-1
            for _ in range(int(cue.get('occurrence',1))):pos=part.find(needle,pos+1)
            if not needle or pos<0:raise ValueError('音效锚点未出现在对应旁白：'+str(cue['anchor']))
            at=mapping[(offsets[sid] if sid else 0)+pos][0];trigger='same-take-word-anchor'
        elif 'offset' in cue:
            if row is None:raise ValueError('相对offset音效必须指定镜头。')
            at=float(row['start'])+float(cue['offset']);trigger='shot-relative-offset'
        elif row is not None:at=float(row['narrationStart']);trigger='shot-narration-start'
        else:raise ValueError('全局音效必须有time或词锚点。')
        if not math.isfinite(at) or not 0<=at<duration:raise ValueError('音效时间超出本期音频。')
        if row and not float(row['start'])-.001<=at<float(row['end']):raise ValueError('音效超出指定镜头范围：'+str(sid))
        result={'time':round(at,6),'kind':kind,'shotId':sid,'basis':basis,'trigger':trigger,'priority':priority}
        if cue.get('anchor'):result['anchor']=cue['anchor']
        if 'offset' in cue:result['offset']=cue['offset']
        candidates.append(result)
    if config['sfx']:
        if 'cues' in override or 'cues' in defaults:
            cues=config.get('cues')
            if not isinstance(cues,list):raise ValueError('soundtrack.cues须为数组，空数组表示不安排音效。')
            for cue in cues:add(cue,basis='explicit-global',priority=3)
        elif config.get('cuePolicy')=='semantic':
            for shot in shots:
                sid=shot['id'];row=aligned[sid];render=shot.get('render',{});ip=shot.get('ip',{})
                if 'soundCues' in shot:
                    if not isinstance(shot['soundCues'],list):raise ValueError('shot.soundCues须为数组。')
                    for cue in shot['soundCues']:add(cue,shot,'explicit-shot',3)
                    continue
                typ=render.get('type',shot.get('visual',{}).get('type'))
                if typ in ('note','prompt-media','compare') and row['end']-row['start']>.18:add({'kind':'paper','offset':.18},shot,'paper-or-media-entry',0)
                for annotation in render.get('annotations',[]):
                    if 'at' in annotation or annotation.get('anchor'):
                        keys=['anchor','occurrence'] if annotation.get('anchor') else ['at']
                        add({'kind':'tick',**{k:annotation[k] for k in keys if k in annotation}},shot,'annotation-or-check',1)
                if ip.get('emotion')=='aha':add({'kind':'idea'},shot,'ip-aha-emotion',1)
                else:
                    for emphasis in ip.get('emphasis',[]):
                        anchor=emphasis.get('anchor','')
                        if any(token in anchor for token in ['灵感','灵光','想到','想到了','有办法','点子']):add({'kind':'idea','anchor':anchor,'occurrence':emphasis.get('occurrence',1)},shot,'explicit-insight-anchor',1)
        elif config.get('cuePolicy') not in ('none','off'):raise ValueError('cuePolicy须为semantic或none。')
    kept=[];dropped=[]
    # Explicit requests take precedence over nearby automatic cues; keep output chronological.
    for cue in sorted(candidates,key=lambda x:(-x['priority'],x['time'])):
        if any(abs(cue['time']-prior['time'])<config['minimumCueGap'] for prior in kept):dropped.append({**cue,'reason':'minimum-cue-gap'})
        else:kept.append(cue)
    kept.sort(key=lambda x:x['time']);config.pop('cues',None)
    return {'defaults':defaults,'overrides':override,'resolved':config,'cues':kept,'suppressedCues':dropped,'warnings':warnings,'timingGranularity':timing.get('timingGranularity','word')}
