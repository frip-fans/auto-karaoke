"""Export an offline manual singer-labeling page."""
import json
import os
from urllib.parse import quote
from .alignment import reviewed_timing
from .project import read_json
from .singers import profiles, map_path, validate_map


def export_review(project):
    lines = reviewed_timing(project)['lines']
    annotations = read_json(map_path(project))
    available = profiles(project, annotations.get('singers'))
    validate_map(annotations, lines, available)
    audio = project.output('vocals-for-transcription.flac')
    if not audio.exists(): audio = project.output('vocals.wav')
    if not audio.is_file(): raise ValueError('Prepare vocals before exporting the annotation page')
    target = project.output('singer-review.html')
    data = {'annotations': annotations, 'profiles': available,
            'options': list(available),
            'lines': [{'id': line['id'], 'text': line['text'], 'start': line['start'], 'end': line['end']} for line in lines],
            'audio': quote(os.path.relpath(audio, target.parent)),
            'map_path': str(map_path(project)), 'filename': map_path(project).name}
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    target.write_text(HTML.replace('/*DATA*/', payload), encoding='utf-8')
    print(target)


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>分唱审核</title>
<style>
body{font:16px system-ui,sans-serif;background:#111620;color:#edf1f8;max-width:1100px;margin:24px auto;padding:0 20px}h1{font-size:26px}p{line-height:1.6;color:#bbc5d6}header{position:sticky;top:0;background:#111620;padding:12px 0;z-index:1;border-bottom:1px solid #344155}audio{width:100%;margin:10px 0}button,select,input{font:inherit;border:1px solid #566277;border-radius:6px;padding:7px;background:#202c3d;color:white}button{cursor:pointer}button:hover{background:#344661}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px 8px;border-bottom:1px solid #344155}td.lyric{min-width:180px}.note{display:block;font-size:13px;color:#b0bed1;margin-top:6px}small{color:#bcc7da}.pill{font-size:13px}#path{overflow-wrap:anywhere}#status{min-height:24px;color:#bde7cd}.mapping label{margin-right:18px;display:inline-block;margin-bottom:8px}td input{width:180px}a{color:#a8d8ff}
</style>
<h1>分唱审核：歌手 A / B / 合唱</h1>
<p>试听每一句，再选择演唱者。请手工标记演唱者；合唱指两位歌手同时演唱。修改保存在当前页面，关闭前请下载标记文件。</p>
<header><div class="mapping" id="mapping"></div><audio id="audio" controls preload="metadata"></audio>
<div class="toolbar"><button id="save">下载标记文件</button><label>载入已有标记 <input id="load" type="file" accept=".json,application/json"></label><span id="count"></span></div>
<div id="status" role="status"></div></header>
<p>下载后替换这个本地文件，再重新生成字幕和视频：<br><code id="path"></code></p>
<table><thead><tr><th>试听</th><th>歌词</th><th>演唱者</th><th>审核 / 备注</th></tr></thead><tbody id="rows"></tbody></table>
<script>
const data=/*DATA*/;
let doc=data.annotations, stopAt=null;
const audio=document.getElementById('audio');audio.src=data.audio;
document.getElementById('path').textContent=data.map_path;
function rowInfo(id){let value=doc.lines[id];if(typeof value==='string')value={singer:value};return doc.lines[id]=value||{singer:'unknown',status:'draft',note:''};}
function status(text){document.getElementById('status').textContent=text;}
function time(t){return Math.floor(t/60)+':'+String(Math.floor(t%60)).padStart(2,'0');}
function count(){const n=data.lines.filter(l=>rowInfo(l.id).status==='confirmed').length;document.getElementById('count').textContent=`已确认 ${n} / ${data.lines.length} 句`;}
function play(line){stopAt=line.end+0.25;audio.currentTime=Math.max(0,line.start-0.25);audio.play().catch(()=>status('无法播放音频，请确认页面与人声文件仍在同一项目目录。'));}
audio.addEventListener('timeupdate',()=>{if(stopAt!==null&&audio.currentTime>=stopAt){audio.pause();stopAt=null;}});
function draw(){
 const mapping=document.getElementById('mapping');mapping.replaceChildren();doc.voice_mapping ||= {};
 for(const voice of ['A','B']){
  if(!data.options.includes(voice))continue;
  const label=document.createElement('label');label.textContent=`${voice} 对应：`;
  const select=document.createElement('select');select.setAttribute('aria-label',`${voice} 的姓名`);
  for(const [id,p] of [[voice,{label:'暂不指定姓名'}],...Object.entries(data.profiles).filter(([id])=>!['A','B','duet','unknown'].includes(id))]){
   const o=document.createElement('option');o.value=id;o.textContent=p.label;select.append(o);
  }
  select.value=doc.voice_mapping[voice]||voice;
  select.onchange=()=>{if(select.value===voice)delete doc.voice_mapping[voice];else doc.voice_mapping[voice]=select.value;status('姓名对应已修改，请下载保存。');};label.append(select);mapping.append(label);
 }
 const rows=document.getElementById('rows');rows.replaceChildren();
 for(const line of data.lines){
  const item=rowInfo(line.id),tr=document.createElement('tr');
  const playCell=document.createElement('td'),button=document.createElement('button');button.textContent='▶ '+time(line.start);button.onclick=()=>play(line);playCell.append(button);
  const lyric=document.createElement('td');lyric.className='lyric';lyric.textContent=line.text;
  const note=document.createElement('small');note.className='note';note.textContent=line.id+(item.confidence!==undefined?` · 模型自报置信度 ${Math.round(item.confidence*100)}%`:'');lyric.append(note);
  const who=document.createElement('td'),select=document.createElement('select');select.setAttribute('aria-label',line.id+' 演唱者');
  for(const id of data.options){const o=document.createElement('option');o.value=id;o.textContent=data.profiles[id]?.label||id;select.append(o);}
  select.value=item.singer;select.style.color=data.profiles[item.singer]?.color||'#fff';who.append(select);
  const edit=document.createElement('td'),confirm=document.createElement('button'),comment=document.createElement('input');comment.setAttribute('aria-label',line.id+' 备注');comment.value=item.note||'';
  const update=()=>{confirm.textContent=item.status==='confirmed'?'✓ 已确认':'确认此句';count();};
  select.onchange=()=>{item.singer=select.value;item.status='confirmed';select.style.color=data.profiles[item.singer]?.color||'#fff';update();status('标记已修改，请下载保存。');};
  confirm.onclick=()=>{item.status=item.status==='confirmed'?'draft':'confirmed';update();status('审核状态已修改，请下载保存。');};
  comment.onchange=()=>{item.note=comment.value;status('备注已修改，请下载保存。');};edit.append(confirm,document.createElement('br'),comment);update();tr.append(playCell,lyric,who,edit);rows.append(tr);
 }count();
}
document.getElementById('save').onclick=()=>{
 const blob=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=data.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status('已下载。请替换上面列出的标记文件，再生成字幕。');
};
document.getElementById('load').onchange=async event=>{
 try{const value=JSON.parse(await event.target.files[0].text());const ids=new Set(data.lines.map(l=>l.id));
  if(value.schema_version!==1||!value.lines||Object.keys(value.lines).some(id=>!ids.has(id)))throw Error('行 ID 与本曲不匹配');
  for(const v of Object.values(value.lines)){const sid=typeof v==='string'?v:v?.singer;if(!data.options.includes(sid))throw Error('未知演唱者标记');}
  for(const [k,v] of Object.entries(value.voice_mapping||{})){if(!['A','B'].includes(k)||!data.profiles[v])throw Error('姓名对应无效');}
  doc=value;draw();status('已载入本地标记。');
 }catch(error){status('载入失败：'+error.message);}
};draw();
</script></html>'''
