#!/usr/bin/env python3
"""Render actual scene keyframes only after recorded semantic approval."""
import argparse,hashlib,json
from pathlib import Path
from runtime_support import ensure_dependencies,prepare_episode,read_episode,make_envelope,launch,open_page,write_json
from approval import require_semantic

def main():
    ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);args=ap.parse_args();p=args.project.resolve()
    approval=require_semantic(p)
    ensure_dependencies(('playwright','numpy'))
    from playwright.sync_api import sync_playwright
    prepare_episode(p);e=read_episode(p);make_envelope(p,e)
    out=p/'keyframes';out.mkdir(exist_ok=True);errors=[];warnings=[];shots=[]
    with sync_playwright() as pw:
        browser=launch(pw);page=open_page(browser,p,e,errors)
        for s in e['scenes']:
            span=s['end']-s['start'];hold=min(s['end']-1/e['fps'],s['start']+min(.65,span*.3))
            times=s.get('keyframes') or [hold]
            if not s.get('keyframes'):
                times += [min(em['end'],s['end']-1/e['fps']) for em in s.get('ip',{}).get('emphasis',[])][:1]
                if span>2:times+=[max(s['start'],s['end']-max(.15,1/e['fps']))]
            times=sorted(set(round(t,6) for t in times))[:3];frames=[]
            for i,t in enumerate(times):
                state=page.evaluate('(t)=>window.render(t)',t);warnings.extend(state['warnings'])
                path=out/(s['id']+'-'+str(i+1).zfill(2)+'.png')
                page.screenshot(path=str(path));frames.append({'path':path.relative_to(p).as_posix(),'time':t,'label':['主体呈现','重点状态','结束状态'][i]})
            shots.append({'shotId':s['id'],'start':s['start'],'end':s['end'],'keyframes':frames})
        browser.close()
    result={'storyboardSha256':approval['storyboardSha256'],'episodeSha256':hashlib.sha256((p/'episode.json').read_bytes()).hexdigest(),'shots':shots,'pageErrors':errors,'layoutWarnings':sorted(set(warnings))}
    write_json(p/'keyframes.json',result);write_json(out/'manifest.json',result)
    if errors or warnings:raise RuntimeError('Keyframe validation errors/warnings: '+repr(errors+warnings))
    print(str(p/'keyframes.json'))
if __name__=='__main__':main()
