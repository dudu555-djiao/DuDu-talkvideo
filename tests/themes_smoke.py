#!/usr/bin/env python3
"""Offline synthetic theme/mascot fixtures; never approves production content."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_support import prepare_episode,launch,open_page,binary


def fixture(theme,mascot,duration=6):
    common={'ip':{'visible':True,'emphasis':[]}}
    scenes=[
        dict(common,id='S01',type='chapter',start=0,end=1,title='从文案到视频',subtitle='通用模板技术演示',number='01'),
        dict(common,id='S02',type='flow',start=1,end=2,title='把制作拆成三件事',steps=[{'title':t,'text':s} for t,s in [('完整文案','整理原句'),('语义分镜','确认思路'),('实际画面','制作成片')]],ip={'visible':True,'emphasis':[{'start':1.2,'end':1.55,'attack':.2,'release':.3}]}),
        dict(common,id='S03',type='note',start=2,end=3,title='先确认，再制作',text='按内容安排主画面\n用真实素材讲清楚',tag='保留原句'),
        dict(common,id='S04',type='compare',start=3,end=4,title='两种讲述任务',left={'title':'教一个操作','text':'准备真实输入和操作录屏'},right={'title':'解释一个关系','text':'使用清楚的图解和对照'}),
        dict(common,id='S05',type='prompt-media',start=4,end=5,title='素材示意',prompt='这里展示本包的几何角色\n不是软件界面或操作证据',media={'src':f'assets/mascots/{mascot}-{theme}-closed.svg','label':'几何素材示意'}),
        dict(common,id='S06',type='ip-scene',start=5,end=6,title='一个角色，一套表达',text='旁白说完就闭嘴\n重点出现时再强调',ip={'visible':False,'emphasis':[]}),
    ]
    return dict(title='合成模板测试',series='DuDu-talkvideo · 模板示意',width=1280,height=720,fps=30,duration=duration,theme=theme,mascot=mascot,captions=[{'start':0,'end':6,'text':'通用模板示意 · 合成嘴形包络 · 静音'}],scenes=scenes)


def write_fixture(p,e):
    prepare_episode(p)
    (p/'episode-data.js').write_text('window.EPISODE='+json.dumps(e,ensure_ascii=False)+';\n')
    env=[.8 if .3<=f/30<1.2 or 2.3<=f/30<4.5 else 0 for f in range(round(e['duration']*30))]
    (p/'assets/speech-envelope.js').write_text('window.SPEECH_ENVELOPE='+json.dumps(env)+';\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--write-demos',action='store_true');a=ap.parse_args()
    from playwright.sync_api import sync_playwright
    themes=json.loads((ROOT/'brand/themes.json').read_text())
    output=ROOT/'examples/public-templates';output.mkdir(parents=True,exist_ok=True)
    report={'syntheticFixture':True,'paidTtsRequests':0,'combinations':[],'renders':[]}
    with tempfile.TemporaryDirectory(prefix='public-theme-qa-') as tmp,sync_playwright() as pw:
        browser=launch(pw)
        for theme,preset in themes.items():
            for mascot in ['block','bird','orbit']:
                p=Path(tmp)/f'{theme}-{mascot}';e=fixture(theme,mascot);write_fixture(p,e);errors=[]
                page=open_page(browser,p,e,errors)
                assert page.evaluate('window.activeTheme')==theme
                assert page.evaluate('window.activeMascot')==mascot
                assert page.evaluate('(t)=>window.render(t)',0)['avatar']['mouth']=='closed'
                assert page.evaluate('(t)=>window.render(t)',.35)['avatar']['mouth']=='small'
                assert page.evaluate('(t)=>window.render(t)',.45)['avatar']['mouth']=='wide'
                assert page.evaluate('(t)=>window.render(t)',1.5)['avatar']['mouth']=='closed'
                emphasized=page.evaluate('(t)=>window.render(t)',1.5)['avatar']
                assert emphasized['pop']>.8 and emphasized['emphasisOffsetY']<-25
                for i in range(6):
                    state=page.evaluate('(t)=>window.render(t)',i+.65)
                    assert not state['warnings'],(theme,mascot,i,state['warnings'])
                assert not errors,errors
                # Runtime readiness waits for all three SVG Image.onload events.
                # file:// pages do not consistently expose SVGs in Resource Timing.
                report['combinations'].append({'theme':theme,'mascot':mascot,'sixScenes':'passed','threeMouths':'passed','silenceAndEmphasis':'passed'})
                if a.write_demos and mascot==preset['mascot']:
                    page.evaluate('(t)=>window.render(t)',1.65)
                    page.locator('#stage').screenshot(path=str(output/f'{theme}.png'))
                    if theme in ['mint','honey','grape']:
                        demo=fixture(theme,mascot)
                        flow=demo['scenes'][1];flow.update(start=0,end=6,title='从文案到视频')
                        flow['ip']['emphasis']=[{'start':2.1,'end':2.5,'attack':.25,'release':.4}]
                        demo['scenes']=[flow];page.close();write_fixture(p,demo);page=open_page(browser,p,demo,errors)
                        target=output/f'{theme}.mp4'
                        command=[binary('ffmpeg'),'-v','error','-y','-f','image2pipe','-framerate','30','-i','pipe:0','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','6','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)]
                        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                        try:
                            for f in range(180):
                                page.evaluate('(t)=>window.render(t)',f/30)
                                proc.stdin.write(page.locator('#stage').screenshot(type='png'))
                            proc.stdin.close();err=proc.stderr.read().decode();assert proc.wait()==0,err
                        except BaseException:
                            proc.kill();proc.wait();raise
                        subprocess.run([binary('ffmpeg'),'-v','error','-i',str(target),'-f','null','-'],check=True,capture_output=True)
                        info=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(target)]))
                        v=next(s for s in info['streams'] if s['codec_type']=='video')
                        assert int(v['nb_frames'])==180 and (v['width'],v['height'])==(1280,720)
                        report['renders'].append({'theme':theme,'frames':180,'seconds':6,'resolution':'1280x720','decode':'passed','audio':'silent AAC 48kHz stereo'})
                page.close()
        browser.close()
    report['passed']=True
    dest=ROOT/'qa/themes-smoke.json';dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':True,'combinations':len(report['combinations']),'sixSceneRenders':len(report['combinations'])*6,'sampleVideos':len(report['renders']),'report':str(dest)},ensure_ascii=False))


if __name__=='__main__':main()
