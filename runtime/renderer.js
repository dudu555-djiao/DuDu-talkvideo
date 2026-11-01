(()=>{'use strict';
const E=window.EPISODE,W=1920,H=1080,canvas=document.getElementById('stage'),g=canvas.getContext('2d'),fps=E.fps;
canvas.width=E.width;canvas.height=E.height;
const themeId=E.theme||E.brand?.theme||'mint',T=window.PUBLIC_THEMES[themeId];if(!T)throw Error('Unknown theme: '+themeId);
const mascotId=E.mascot||E.brand?.mascot||T.mascot;if(!['block','bird','orbit'].includes(mascotId))throw Error('Unknown mascot: '+mascotId);
const P={paper:T.bg,dot:T.soft,ink:T.ink,blue:T.main,soft:T.soft,card:T.card,muted:T.muted,onAccent:T.onAccent,accent:T.accent};window.activeTheme=themeId;window.activeMascot=mascotId;
const cx=265.4,cy=815.3,r=115.5,FONT='"PingFang SC", "Microsoft YaHei", "DuDuBody", sans-serif',TITLE='"EpisodeDisplay", sans-serif';
const cl=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),smooth=v=>{v=cl(v);return v*v*(3-2*v)};
const mouths={},media=new Map();window.ready=false;window.layoutWarnings=[];
function rr(x,y,w,h,rad,fill,stroke=null,lw=2){g.beginPath();g.roundRect(x,y,Math.max(0,w),h,rad);if(fill){g.fillStyle=fill;g.fill()}if(stroke){g.strokeStyle=stroke;g.lineWidth=lw;g.stroke()}}
function text(s,x,y,size,{font=FONT,weight=600,color=P.ink,align='left'}={}){g.save();g.font=`${weight} ${size}px ${font}`;g.fillStyle=color;g.textAlign=align;g.textBaseline='middle';g.fillText(String(s??''),x,y);g.restore()}
function fit(s,max,size,min=32,font=FONT,weight=600){g.font=`${weight} ${size}px ${font}`;while(g.measureText(s).width>max&&size>min){size--;g.font=`${weight} ${size}px ${font}`}if(g.measureText(s).width>max)window.layoutWarnings.push('Text exceeds available width: '+s);return size}
function wrap(s,x,y,width,size,lineHeight,color=P.ink,maxLines=8,align='left'){g.font=`600 ${size}px ${FONT}`;const lines=[];for(const para of String(s||'').split('\n')){let row='';for(const ch of para){if(row&&g.measureText(row+ch).width>width){lines.push(row);row=ch}else row+=ch}lines.push(row)}if(lines.length>maxLines)window.layoutWarnings.push('Text exceeds '+maxLines+' lines: '+s);lines.slice(0,maxLines).forEach((row,i)=>text(row,x,y+i*lineHeight,size,{color,align}));return lines.length*lineHeight}
function line(x1,y1,x2,y2,color=P.ink,w=4){g.save();g.lineCap='round';g.strokeStyle=color;g.lineWidth=w;g.beginPath();g.moveTo(x1,y1);g.lineTo(x2,y2);g.stroke();g.restore()}
function circle(x,y,rx,ry,p=1){if(p<=0)return;g.save();g.strokeStyle=P.blue;g.lineWidth=6;g.lineCap='round';g.beginPath();for(let i=0;i<=100*cl(p);i++){let a=i/100*Math.PI*2-.12,k=1+.009*Math.sin(a*3.1),xx=x+Math.cos(a)*rx*k,yy=y+Math.sin(a)*ry*k;i?g.lineTo(xx,yy):g.moveTo(xx,yy)}g.stroke();g.restore()}
function arrow(x,y,tx,ty,p=1){const dx=(tx-x)*p,dy=(ty-y)*p;line(x,y,x+dx,y+dy);const a=Math.atan2(dy,dx);line(x+dx,y+dy,x+dx-19*Math.cos(a-.5),y+dy-19*Math.sin(a-.5));line(x+dx,y+dy,x+dx-19*Math.cos(a+.5),y+dy-19*Math.sin(a+.5))}
function note(s,x,y,width=500){g.save();g.translate(x,y);g.rotate(-.025);g.shadowColor='#17241D20';g.shadowBlur=16;g.shadowOffsetY=10;rr(-width/2,-37,width,74,12,P.blue);g.shadowColor='transparent';text(s,0,0,fit(s,width-40,39),{color:P.onAccent,align:'center'});g.restore()}
function bg(s){g.fillStyle=P.paper;g.fillRect(0,0,W,H);if(T.layout==='split'){g.fillStyle=P.soft;g.fillRect(0,180,650,770)}text(E.series||'DuDu-talkvideo',65,40,22,{color:P.muted,weight:650});if(s.id)text(s.id,1855,40,22,{color:P.muted,align:'right'})}
function pop(s,t){return Math.max(0,...(s.ip?.emphasis||[]).map(e=>smooth((t-e.start)/(e.attack??.28))*(1-smooth((t-e.end)/(e.release??.4)))))}
const env=window.SPEECH_ENVELOPE||[],motion=[];let start=0,was=false,lastRay=.36,lastPhase=0;
for(let f=0;f<Math.round(E.duration*fps);f++){const t=f/fps,a=env[f]||0,active=a>.025;if(active&&!was)start=t;const phase=(t-start)%.5;let m=active?(phase<.1?'small':phase<.233333?'wide':phase<.366667?'small':'closed'):'closed';if(active&&m==='wide'&&a<.10)m='small';if(active){lastRay=.4+.6*a;lastPhase=Math.floor((t-start)/.133333)}motion.push({mouth:m,active,amplitude:a,ray:lastRay,rayPhase:lastPhase});was=active}
function avatar(s,t){
 if(s.ip?.visible===false||(s.type==='ip-scene'&&s.ip?.visible!==true)){window.avatarState={visible:false};return}
 const state=motion[Math.min(motion.length-1,Math.floor(t*fps))],p=pop(s,t),width=290*(1+.085*p),x=cx-width/2,y=cy-130-32*p;
 g.drawImage(mouths[state.mouth],x,y,width,width*300/320);
 window.avatarState={...state,visible:true,pop:p,cx,cy,emphasisOffsetY:-32*p,mascot:mascotId,theme:themeId};
}
function imageFit(im,x,y,w,h,fit='contain'){let iw=im.videoWidth||im.naturalWidth,ih=im.videoHeight||im.naturalHeight;const k=fit==='cover'?Math.max(w/iw,h/ih):Math.min(w/iw,h/ih);g.save();g.beginPath();g.rect(x,y,w,h);g.clip();g.drawImage(im,x+(w-iw*k)/2,y+(h-ih*k)/2,iw*k,ih*k);g.restore()}
function mediaFrame(m,x,y,w,h){g.save();g.shadowColor='#17241D25';g.shadowBlur=25;g.shadowOffsetY=16;rr(x,y,w,h,24,P.card,P.blue,7);g.shadowColor='transparent';g.beginPath();g.roundRect(x+9,y+9,w-18,h-18,17);g.clip();imageFit(media.get(m.src),x+10,y+10,w-20,h-20,m.fit||'contain');g.restore();if(m.label)note(m.label,x+w-150,y-9,260)}
function heading(s){if(s.title)text(s.title,100,148,fit(s.title,1720,68,40,TITLE,400),{font:TITLE,weight:400})}
function content(s,t){const a=smooth((t-s.start)/.23);g.save();g.globalAlpha=a;g.translate(0,14*(1-a));
if(s.type==='chapter'){const size=fit(s.title,1320,122,52,TITLE,400);g.font=`400 ${size}px ${TITLE}`;const tw=g.measureText(s.title).width,xx=(W-(tw+180))/2;g.beginPath();g.arc(xx+64,468,64,0,7);g.fillStyle=P.blue;g.fill();text(s.number||String(E.scenes.indexOf(s)+1).padStart(2,'0'),xx+64,472,54,{font:TITLE,weight:400,color:P.onAccent,align:'center'});text(s.title,xx+175,468,size,{font:TITLE,weight:400});text(s.subtitle||'',1080,613,fit(s.subtitle||'',1400,34),{color:P.muted,weight:550,align:'center'})}
else if(s.type==='prompt-media'){heading(s);rr(80,331,760,255,36,'#080A09');wrap(s.prompt,120,388,675,34,49,'#fff',4);arrow(858,460,977,442,smooth((t-s.start-.2)/.4));mediaFrame(s.media,980,214,880,502)}
else if(s.type==='compare'){heading(s);for(const [i,panel]of[s.left,s.right].entries()){const x=100+i*900;rr(x,265,820,420,24,P.card,i?P.blue:'#BBC3C3',4);note(panel.title,x+410,278,400);if(panel.media)mediaFrame(panel.media,x+28,330,764,320);else wrap(panel.text||'',x+45,372,730,39,58,P.ink,5)}}
else if(s.type==='flow'){
 heading(s);const n=s.steps.length;
 if(T.layout==='split'){
  const gap=Math.min(175,650/n);s.steps.forEach((step,i)=>{const y=270+i*gap;rr(735,y,1080,gap-18,14,P.card);text(String(i+1).padStart(2,'0'),777,y+45,36,{color:P.ink});wrap(step.title,884,y+42,860,39,48,P.ink,1);wrap(step.text||'',884,y+96,860,28,36,P.muted,1)})
 }else if(T.layout==='path'){
  const gap=n===1?0:1400/(n-1),x0=n===1?960:260;line(x0,430,x0+gap*(n-1),430,P.soft,9);
  s.steps.forEach((step,i)=>{const x=x0+i*gap;g.beginPath();g.arc(x,430,35,0,7);g.fillStyle=P.accent;g.fill();text(String(i+1),x,430,32,{color:P.onAccent,align:'center'});const width=Math.min(400,1600/n-25);wrap(step.title,x,530,width,36,48,P.ink,2,'center');wrap(step.text||'',x,658,width,27,38,P.muted,2,'center')})
 }else{
  const w=Math.min(450,1580/n-46),x0=(W-(n*w+(n-1)*45))/2;s.steps.forEach((step,i)=>{const x=x0+i*(w+45);rr(x,340,w,295,20,P.card);text(String(i+1).padStart(2,'0'),x+30,387,40,{color:P.ink});wrap(step.title,x+30,451,w-60,36,49,P.ink,2);wrap(step.text||'',x+30,548,w-60,25,35,P.muted,2);if(i<n-1)arrow(x+w+7,485,x+w+37,485)})
 }
}
else if(s.type==='note'){heading(s);g.save();g.translate(1060,480);g.rotate(-.018);g.shadowColor='#17241D18';g.shadowBlur=25;g.shadowOffsetY=16;rr(-650,-165,1300,330,5,P.card);g.shadowColor='transparent';wrap(s.text,-585,-78,1170,52,76,P.ink,3);g.restore();if(s.tag)note(s.tag,1500,315,320)}
else if(s.type==='ip-scene'){
 heading(s);if(s.background)imageFit(media.get(s.background),160,220,1600,700,'contain');
 else rr(160,250,1600,645,28,P.card);
 const state=motion[Math.min(motion.length-1,Math.floor(t*fps))];g.drawImage(mouths[state.mouth],1100,275,600,562.5);
 wrap(s.text||s.title,250,410,780,48,72,P.ink,4);
}
for(const an of s.annotations||[]){const p=smooth((t-(an.at??s.start))/.3);if(!p)continue;if(an.type==='circle')circle(an.x,an.y,an.rx||100,an.ry||60,p);else if(an.type==='arrow')arrow(an.x,an.y,an.toX,an.toY,p);else if(an.type==='note'){g.save();g.globalAlpha*=p;note(an.text,an.x,an.y,an.width||400);g.restore()}}g.restore()}
function caption(t){const c=E.captions.find(c=>t>=c.start&&t<c.end);if(!c)return;const size=fit(c.text,1710,42,32);g.font=`650 ${size}px ${FONT}`;const w=g.measureText(c.text).width+52;rr((W-w)/2,974,w,72,12,'#18211B');text(c.text,960,1009,size,{weight:650,color:'#fff',align:'center'})}
function sceneMedia(s){return [s.media,s.left?.media,s.right?.media].filter(Boolean)}
async function seek(v,time){const target=Math.min(Math.max(0,time),Math.max(0,v.duration-.001));if(Math.abs(v.currentTime-target)<.00001&&v.readyState>=2)return;await new Promise((ok,no)=>{const timer=setTimeout(()=>done(new Error('Media seek timed out: '+v.src)),10000);function done(err){clearTimeout(timer);v.removeEventListener('seeked',onseek);v.removeEventListener('error',onerr);err?no(err):ok()}function onseek(){done()}function onerr(){done(new Error('Media decoding failed: '+v.src))}v.addEventListener('seeked',onseek);v.addEventListener('error',onerr);v.currentTime=target})}
window.render=async function(t){window.layoutWarnings=[];t=cl(t,0,E.duration-1/E.fps);const s=E.scenes.find(s=>t>=s.start&&t<s.end);if(!s)throw Error('No scene at '+t);await Promise.all(sceneMedia(s).filter(m=>m.kind==='video').map(m=>seek(media.get(m.src),(m.in||0)+(t-s.start)*(m.playbackRate||1))));g.setTransform(E.width/W,0,0,E.height/H,0,0);bg(s);content(s,t);avatar(s,t);caption(t);window.currentScene=s.id;return {scene:s.id,avatar:window.avatarState,warnings:window.layoutWarnings}};
function load(src,kind='image'){if(media.has(src))return Promise.resolve(media.get(src));return new Promise((ok,no)=>{let im;if(kind==='video'){im=document.createElement('video');im.preload='auto';im.muted=true;im.playsInline=true;im.onloadeddata=()=>ok(im)}else{im=new Image();im.onload=()=>ok(im)}im.onerror=()=>no(Error('Failed asset '+src));media.set(src,im);im.src=src;if(kind==='video')im.load()})}
const all=E.scenes.flatMap(sceneMedia);for(const s of E.scenes)if(s.type==='ip-scene'&&s.background)all.push({src:s.background,kind:'image'});
const states=['closed','small','wide'];
Promise.all([Promise.all(states.map(key=>load('assets/mascots/'+mascotId+'-'+themeId+'-'+key+'.svg'))),Promise.all([document.fonts.load('156px EpisodeDisplay'),document.fonts.load('600 42px DuDuBody')]),...all.map(m=>load(m.src,m.kind))]).then(async ([images])=>{states.forEach((key,i)=>mouths[key]=images[i]);await window.render(0);window.ready=true;window.motionTimeline=motion}).catch(e=>{window.loadError=String(e);console.error(e)});
if(new URLSearchParams(location.search).get('preview')==='1'){document.body.classList.add('preview');const au=document.getElementById('mix');au.src=E.audio;document.getElementById('play').onclick=()=>au.paused?au.play():au.pause();let busy=false;async function tick(){if(window.ready&&!busy){busy=true;await window.render(au.currentTime);busy=false}requestAnimationFrame(tick)}tick()}
})();
