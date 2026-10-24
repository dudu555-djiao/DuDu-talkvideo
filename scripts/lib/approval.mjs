import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
export function requireSemantic(project) {
  if (!project) throw new Error('配音必须提供本期目录并先获得语义分镜批准。');
  const storyboard=path.join(project,'storyboard.json'),record=path.join(project,'approvals','semantic.json');
  if (!fs.existsSync(storyboard)||!fs.existsSync(record)) throw new Error('先展示语义分镜 HTML 并等待用户同意；没有批准记录。');
  const a=JSON.parse(fs.readFileSync(record,'utf8'));
  const hash=createHash('sha256').update(fs.readFileSync(storyboard)).digest('hex');
  if(a.status!=='approved'||a.approvedBy!=='user'||!String(a.userStatement||'').trim()) throw new Error('缺少用户明确批准语义分镜的原话。');
  if(a.storyboardSha256!==hash) throw new Error('语义分镜已变更，先展示新版 HTML 并获得用户同意。');
  return a;
}
export function requireScript(project,text) {
  requireSemantic(project);
  const normalize=s=>String(s).normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
  const storyboard=JSON.parse(fs.readFileSync(path.join(project,'storyboard.json'),'utf8'));
  const script=fs.readFileSync(path.join(project,'input','script.txt'),'utf8').trim();
  if(!script||script!==text.trim()||normalize((storyboard.shots||[]).map(s=>s.narration||'').join(''))!==normalize(script)) throw new Error('语义镜头旁白必须按顺序完整覆盖本期文案；禁止只配音前20秒。');
  return storyboard;
}
