#!/usr/bin/env node
/** Complete approved narration -> one take, own word timestamps and audio fingerprint. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {synthesize} from './lib/tts.mjs';
import {fileDigest} from './lib/content-cache.mjs';
import {requireScript} from './lib/approval.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function argument(name){const i=process.argv.indexOf(name);return i<0?null:process.argv[i+1];}
function redact(value){let s=String(value);for(const key of ['VOLC_TTS_API_KEY','VOLC_TTS_APP_ID','VOLC_TTS_ACCESS_TOKEN']){const secret=process.env[key];if(secret)s=s.split(secret).join('[redacted]');}return s;}
try{
 const given=argument('--project');if(!given)throw new Error('用法: node scripts/synthesize.mjs --project <每期目录> [--check-only]');
 const project=path.resolve(given),text=fs.readFileSync(path.join(project,'input','script.txt'),'utf8').trim();
 requireScript(project,text);
 const audio={voice:'zh_male_liufei_uranus_bigtts',resource:'seed-tts-2.0',speed:-25,style:'年轻自然的普通话男声，像一位聪明又亲切的朋友在分享经验，语气明快、有一点好奇和灵感，表达清楚，有自然停顿，不要广告腔，不要播音腔，不要幼儿化。'};
 for(const lockFile of [path.join(root,'brand','style-lock.json'),path.join(project,'brand','style-lock.json')]){
  if(fs.existsSync(lockFile)){const lock=JSON.parse(fs.readFileSync(lockFile,'utf8'));if(lock.audio?.style)audio.style=lock.audio.style;}
 }
 if(process.argv.includes('--check-only')){
  console.log(JSON.stringify({approved:true,characters:text.length,voice:audio.voice,resource:audio.resource,speed:audio.speed,networkRequested:false}));
 } else {
  // The local credential source remains outside the reusable project. Never copy its contents.
  const envFile=process.env.DUDU_TALKVIDEO_TTS_ENV||path.join(root,'.env');
  if(fs.existsSync(envFile))process.loadEnvFile(envFile);
  else if(process.env.DUDU_TALKVIDEO_TTS_ENV)throw new Error('指定的本机TTS凭据文件不存在。');
  Object.assign(process.env,{TTS_ENGINE:'volc',VOLC_TTS_VOICE:audio.voice,VOLC_TTS_RESOURCE_ID:audio.resource,VOLC_TTS_SPEED:String(audio.speed),VOLC_TTS_STYLE:audio.style});
  const out=path.join(project,'audio','narration-raw.wav');
  const result=await synthesize(text,out,{voice:audio.voice,project});
  if(!Array.isArray(result.words)||!result.words.length)throw new Error('同次合成没有返回词级时间戳；保留原音检查，不套旧字幕。');
  const timing={text,...audio,duration:result.duration,words:result.words,audioSha256:fileDigest(out),timingSource:'Word timestamps returned by this complete TTS take; raw audio has no added lead-in.'};
  const target=path.join(project,'audio','narration-raw-timing.json'),tmp=target+'.tmp';fs.writeFileSync(tmp,JSON.stringify(timing,null,2));fs.renameSync(tmp,target);
  console.log(JSON.stringify({audio:out,timing:target,duration:result.duration,words:result.words.length,voice:audio.voice}));
 }
}catch(error){
 console.error(redact(error?.message||error));
 console.error('本步骤不换音色、不自动反复请求。若接口拒绝长稿，先按完整章节制定分批方案并逐章保留同次音频/时间戳，不截成20秒。');
 process.exitCode=1;
}
