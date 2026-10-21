"""Jalsa single-page UI. Transcript stays in the browser; only AI calls send
text to the server (which forwards to Gemini and stores nothing)."""

JALSA_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jalsa — free AI meeting notes</title>
<style>
:root{--bg:#0f1420;--card:#182032;--line:#263252;--txt:#e8edf7;--dim:#9aa7c4;
--acc:#5eead4;--acc2:#fbbf24;--bad:#f87171}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Nastaliq Urdu",sans-serif;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:20px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.logo{font-size:30px}
h1{margin:0;font-size:24px}
.sub{color:var(--dim);margin:2px 0 14px}
.pill{margin-left:auto;font-size:12px;padding:4px 12px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
.pill.on{color:#06281f;background:var(--acc);border-color:var(--acc);font-weight:700}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
label{display:block;font-size:13px;color:var(--dim);margin:10px 0 4px}
input[type=text],textarea,select{width:100%;background:#0d1322;border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:10px;font-size:14px;font-family:inherit}
textarea{min-height:180px;resize:vertical}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
button{background:var(--acc);color:#06281f;border:0;border-radius:10px;padding:10px 18px;font-weight:700;font-size:14px;cursor:pointer}
button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
button.sm{padding:6px 12px;font-size:12px}
button:disabled{opacity:.5;cursor:wait}
.chk{display:flex;gap:8px;align-items:center;font-size:14px}
.sec{border-top:1px solid var(--line);padding:12px 0}
.sec h3{margin:0 0 8px;font-size:15px;display:flex;align-items:center;gap:8px}
.sec h3 .copy{margin-left:auto}
ul{margin:6px 0;padding-left:20px}
li{margin:4px 0}
.warn{color:var(--acc2);font-size:13px}
.err{color:var(--bad);font-size:13px}
.ai-badge{font-size:11px;color:#06281f;background:var(--acc);border-radius:6px;padding:2px 8px;font-weight:700}
.rb-badge{font-size:11px;color:var(--acc2);border:1px solid var(--acc2);border-radius:6px;padding:2px 8px}
blockquote{border-left:3px solid var(--acc);margin:8px 0;padding:6px 12px;color:var(--dim);font-style:italic}
.stats{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--dim)}
.stats b{color:var(--txt)}
.chat-box{display:flex;gap:8px;margin-top:8px}
#chatLog{max-height:260px;overflow:auto}
.msg{margin:8px 0;padding:8px 12px;border-radius:10px;font-size:14px}
.msg.q{background:#0d1322;border:1px solid var(--line)}
.msg.a{background:#13251f;border:1px solid #1f4d3f}
footer{color:var(--dim);font-size:12px;margin:24px 0;text-align:center}
@media print{.no-print{display:none}body{background:#fff;color:#000}.card{background:#fff;border-color:#ccc}}
</style>
</head>
<body>
<div class="wrap">
<header>
<span class="logo">🎙️</span>
<h1>Jalsa <span style="font-weight:400;color:var(--dim)">جلسہ</span></h1>
<span class="pill" id="aiPill">AI: checking…</span>
</header>
<p class="sub">Transcript in → meeting minutes out. <b>Free, unlimited, koi per-meeting cut-off nahi.</b>
Urdu, Roman-Urdu aur English — teeno samajhta hai.</p>

<div class="card no-print">
<label>Meeting title</label>
<input type="text" id="title" placeholder="e.g. Weekly team sync — 21 Oct">
<label>Transcript (paste text, ya .txt / .vtt / .srt file upload karo)</label>
<textarea id="transcript" placeholder="Ali: Assalam-o-Alaikum, chalo shuru karte hain…&#10;Sara: Budget finalize ho gaya, launch March mein hoga…"></textarea>
<div class="row">
<button class="ghost sm" id="sampleBtn">Sample transcript bhardo</button>
<input type="file" id="fileIn" accept=".txt,.vtt,.srt,.md" style="font-size:13px">
<label class="chk" style="margin:0"><input type="checkbox" id="useAi" checked> AI minutes (Gemini)</label>
<select id="lang" style="width:auto">
<option value="en">Minutes: English</option>
<option value="ur">Minutes: اردو</option>
</select>
</div>
<div class="row">
<button id="goBtn">Minutes banao</button>
<span class="warn" id="inWarn"></span>
</div>
</div>

<div class="card" id="outCard" style="display:none">
<div class="row" style="margin-top:0">
<h2 style="margin:0" id="outTitle"></h2>
<span id="aiBadge"></span>
<button class="ghost sm no-print" id="dlBtn">⬇ Markdown</button>
<button class="ghost sm no-print" id="printBtn">🖨 Print</button>
</div>
<div class="stats" id="statsRow"></div>
<div id="warnBox"></div>
<div class="sec"><h3>📌 TL;DR <button class="ghost sm copy no-print" data-sec="tldr">Copy</button></h3><ul id="secTldr"></ul></div>
<div class="sec"><h3>✅ Decisions <button class="ghost sm copy no-print" data-sec="dec">Copy</button></h3><ul id="secDec"></ul></div>
<div class="sec"><h3>📋 Action items <button class="ghost sm copy no-print" data-sec="act">Copy</button></h3><ul id="secAct"></ul></div>
<div class="sec"><h3>❓ Open questions <button class="ghost sm copy no-print" data-sec="q">Copy</button></h3><ul id="secQ"></ul></div>
<div class="sec"><h3>💬 Key quotes <button class="ghost sm copy no-print" data-sec="quo">Copy</button></h3><div id="secQuo"></div></div>

<div class="sec no-print">
<h3>🤖 Meeting se sawal poocho</h3>
<div id="chatLog"></div>
<div class="chat-box">
<input type="text" id="chatQ" placeholder="e.g. Zubair ne kya promise kiya tha?">
<button class="sm" id="chatBtn">Poochho</button>
</div>
<p class="warn" style="font-size:12px">Jawab sirf transcript se aayega — jo likha nahi, wo banaya nahi jayega.</p>
</div>
</div>

<footer>
Jalsa is an original, free tool — not affiliated with Otter.ai or any meeting-notes product.<br>
Transcript browser mein rehta hai; AI use par hi server ko bheja jata hai, kuch store/train nahi hota.
AI features owner ke free Gemini quota par chalte hain — rule-based engine hamesha free aur unlimited hai.
</footer>
</div>

<script>
let MINUTES=null, AI_ON=false;
const $=id=>document.getElementById(id);

fetch('/jalsa/api/ai-status').then(r=>r.json()).then(j=>{
  AI_ON=j.ai_available;
  const p=$('aiPill');
  p.textContent='AI: '+(AI_ON?'ON':'rule-based mode');
  p.classList.toggle('on',AI_ON);
  if(!AI_ON) $('useAi').checked=false;
}).catch(()=>{$('aiPill').textContent='AI: rule-based mode';$('useAi').checked=false;});

$('sampleBtn').onclick=()=>{ $('transcript').value=SAMPLE;
  $('title').value='Product launch planning — sample'; };
$('fileIn').onchange=e=>{
  const f=e.target.files[0]; if(!f) return;
  const r=new FileReader();
  r.onload=()=>{ $('transcript').value=r.result;
    if(!$('title').value) $('title').value=f.name.replace(/\\.[a-z0-9]+$/i,''); };
  r.readAsText(f);
};

const SAMPLE=`Ali: Assalam-o-Alaikum everyone, chalo aaj ka agenda shuru karte hain. Pehla point: website launch.
Sara: Design finalize ho gaya hai, lekin payment page par abhi testing baqi hai.
Ali: Testing kab tak complete hogi?
Sara: I will finish payment testing by Friday, aur phir staging par deploy karungi.
Zubair: We decided to launch on 15th March, marketing usi hisaab se plan karegi.
Sara: Marketing budget approve ho gaya? 2 lakh ka proposal tha.
Ali: Haan, budget approved. Zubair, tum vendor se final quote le lo by Wednesday.
Zubair: Theek hai, I will get the vendor quote by Wednesday.
Sara: Ek sawal — kya humein Urdu version bhi launch par chahiye ya baad mein?
Ali: Good question. We agreed: Urdu version phase 2 mein aayega, English pehle.
Zubair: Aur support ke liye WhatsApp number activate karna hoga before launch.
Ali: Theek hai, to summarize: launch 15 March, testing Friday tak, quote Wednesday tak.`;

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

$('goBtn').onclick=async()=>{
  const t=$('transcript').value.trim();
  if(!t){$('inWarn').textContent='Pehle transcript paste karo.';return;}
  $('inWarn').textContent='';$('goBtn').disabled=true;$('goBtn').textContent='Ban raha hai…';
  try{
    const r=await fetch('/jalsa/api/minutes',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:$('title').value,transcript:t,lang:$('lang').value,use_ai:$('useAi').checked})});
    const j=await r.json();
    if(j.error){$('inWarn').textContent=j.error;$('inWarn').className='err';return;}
    render(j);
    localStorage.setItem('jalsa_last',JSON.stringify({title:$('title').value,t:t}));
  }catch(e){$('inWarn').textContent='Server se rabta nahi ho saka.';$('inWarn').className='err';}
  $('goBtn').disabled=false;$('goBtn').textContent='Minutes banao';
};

function li(spk,txt){return '<li>'+(spk?'<b>'+esc(spk)+':</b> ':'')+esc(txt)+'</li>';}

function render(j){
  MINUTES=j.minutes;
  $('outCard').style.display='block';
  $('outTitle').textContent=MINUTES.title;
  $('aiBadge').innerHTML=j.ai?'<span class="ai-badge">AI minutes</span>':'<span class="rb-badge">rule-based</span>';
  const s=MINUTES.stats;
  $('statsRow').innerHTML='<span>🎤 <b>'+s.speakers.length+'</b> speakers</span><span>💬 <b>'+s.turns+'</b> turns</span><span>📝 <b>'+s.words+'</b> words</span>';
  $('warnBox').innerHTML=(j.warnings||[]).map(w=>'<p class="warn">⚠ '+esc(w)+'</p>').join('');
  $('secTldr').innerHTML=MINUTES.tldr.map(t=>'<li>'+esc(t)+'</li>').join('')||'<li>—</li>';
  $('secDec').innerHTML=MINUTES.decisions.map(d=>li(d.speaker,d.text)).join('')||'<li>—</li>';
  $('secAct').innerHTML=MINUTES.actions.map(a=>'<li><input type="checkbox" disabled> '+(a.owner?'<b>'+esc(a.owner)+'</b> — ':'')+esc(a.task)+(a.deadline?' <i>(by '+esc(a.deadline)+')</i>':'')+'</li>').join('')||'<li>—</li>';
  $('secQ').innerHTML=MINUTES.questions.map(q=>li(q.speaker,q.text)).join('')||'<li>—</li>';
  $('secQuo').innerHTML=MINUTES.quotes.map(q=>'<blockquote>'+esc(q.text)+(q.speaker?'<br>— '+esc(q.speaker):'')+'</blockquote>').join('')||'<p>—</p>';
  $('chatLog').innerHTML='';
  $('outCard').scrollIntoView({behavior:'smooth'});
}

document.querySelectorAll('.copy').forEach(b=>b.onclick=async()=>{
  const map={tldr:MINUTES.tldr,dec:MINUTES.decisions.map(d=>(d.speaker?d.speaker+': ':'')+d.text),
    act:MINUTES.actions.map(a=>'[ ] '+(a.owner?a.owner+' — ':'')+a.task+(a.deadline?' (by '+a.deadline+')':'')),
    q:MINUTES.questions.map(q=>(q.speaker?q.speaker+': ':'')+q.text),
    quo:MINUTES.quotes.map(q=>'"'+q.text+'"'+(q.speaker?' — '+q.speaker:''))};
  const txt=(map[b.dataset.sec]||[]).join('\\n');
  try{await navigator.clipboard.writeText(txt);b.textContent='Copied ✓';setTimeout(()=>b.textContent='Copy',1200);}
  catch(e){b.textContent='Copy failed';}
});

$('dlBtn').onclick=async()=>{
  const r=await fetch('/jalsa/api/download-md',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({minutes:MINUTES})});
  if(!r.ok){alert('Download mein masla aaya.');return;}
  const blob=await r.blob(),a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='jalsa-minutes.md';a.click();
};
$('printBtn').onclick=()=>window.print();

$('chatBtn').onclick=ask; $('chatQ').onkeydown=e=>{if(e.key==='Enter')ask();};
async function ask(){
  const q=$('chatQ').value.trim(); if(!q)return;
  $('chatLog').innerHTML+='<div class="msg q"><b>Tum:</b> '+esc(q)+'</div>';
  $('chatQ').value='';$('chatBtn').disabled=true;
  try{
    const r=await fetch('/jalsa/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({transcript:$('transcript').value,question:q,lang:$('lang').value})});
    const j=await r.json();
    const a=j.answer||('⚠ '+(j.error||'Jawab nahi mila.'));
    $('chatLog').innerHTML+='<div class="msg a"><b>Jalsa:</b> '+esc(a)+'</div>';
  }catch(e){$('chatLog').innerHTML+='<div class="msg a">⚠ Server se rabta nahi ho saka.</div>';}
  $('chatBtn').disabled=false;
  $('chatLog').scrollTop=$('chatLog').scrollHeight;
}

try{const last=JSON.parse(localStorage.getItem('jalsa_last')||'null');
if(last){$('title').value=last.title||'';$('transcript').value=last.t||'';}}catch(e){}
</script>
</body>
</html>
"""
