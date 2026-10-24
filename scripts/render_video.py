#!/usr/bin/env python3
"""Deterministic Canvas export with actual video seeks and narration-driven IP."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
from runtime_support import ensure_dependencies,prepare_episode,read_episode,make_envelope,launch,open_page,write_json,binary
from approval import require_semantic

def main():
    ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);args=ap.parse_args();p=args.project.resolve()
    approval=require_semantic(p)
    ensure_dependencies(('playwright','numpy'))
    from playwright.sync_api import sync_playwright
    prepare_episode(p);e=read_episode(p);make_envelope(p,e)
    frames=round(e['duration']*e['fps']);out=p/'out';out.mkdir(exist_ok=True);qa=p/'qa';qa.mkdir(exist_ok=True)
    target=out/'final.mp4';temporary=out/'final.partial.mp4';errors=[];warnings=[];t0=time.time()
    cmd=[binary('ffmpeg'),'-v','error','-y','-f','image2pipe','-framerate',str(e['fps']),'-i','-','-i',str(p/e['audio']),'-map','0:v:0','-map','1:a:0','-frames:v',str(frames),'-t',str(e['duration']),'-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(temporary)]
    with sync_playwright() as pw:
        browser=launch(pw);page=open_page(browser,p,e,errors);enc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for i in range(frames):
                state=page.evaluate('(t)=>window.render(t)',i/e['fps']);warnings.extend(state['warnings'])
                if errors or warnings:raise RuntimeError('Render validation failed: '+repr(errors+warnings))
                enc.stdin.write(page.screenshot(type='jpeg',quality=96))
                if i and i%150==0:print(f'{i}/{frames} frames; {time.time()-t0:.1f}s',flush=True)
            enc.stdin.close()
            if enc.wait()!=0:raise RuntimeError('FFmpeg encoder failed')
        except BaseException:
            if enc.poll() is None:enc.kill();enc.wait()
            raise
        finally:browser.close()
    subprocess.run([binary('ffmpeg'),'-v','error','-i',str(temporary),'-f','null','-'],check=True)
    info=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(temporary)]))
    video=next(x for x in info['streams'] if x['codec_type']=='video')
    if int(video['nb_read_frames'])!=frames:raise RuntimeError('Export frame count mismatch')
    temporary.replace(target)
    write_json(qa/'render-report.json',{'storyboardSha256':approval['storyboardSha256'],'episodeSha256':hashlib.sha256((p/'episode.json').read_bytes()).hexdigest(),'frames':frames,'duration':e['duration'],'elapsedSeconds':round(time.time()-t0,2),'pageErrors':errors,'layoutWarnings':sorted(set(warnings)),'decodePassed':True,'probe':info,'method':'Actual canvas frames; seeked video textures; registered three-mouth sprites; narration RMS; configurable fixed-disc head pop'})
    print(str(target),flush=True)
if __name__=='__main__':main()
