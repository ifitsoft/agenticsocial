/* The Brief — Friday, 14 August 2026
   Underlying announcements broke 13 August; this is the 14 August edition. */

meta({
  date:'2026-08-14',
  dateShort:'14 · 08 · 26',
  dateLong:'Friday, 14 August 2026',
  byline:'Ali Abdukarim',
  warmActs:[],
  pace:1.293,
});

/* ---- cold open ---- */
scene('',3.0,'',s=>{
  const h=E('h2',null,P('Google shipped its main agentic model — and halved the price.'));
  rise(h,.15);
});

scene('',3.6,'',s=>{
  const t=E('div','big-title',P('THE<br>BRIEF'));
  rise(t,.1,{stag:.09,dur:.9});
  const r=E('div','rule blue',{css:{marginTop:'46px',width:'340px'}});
  draw(r,.6);
  const d=E('div','lede',{html:META.dateLong,css:{marginTop:'40px'}});
  fade(d,.85);
  const b=E('div','body',{html:'Five stories from the last 24 hours.',css:{marginTop:'18px'}});
  fade(b,1.05);
  const by=E('div','byline',{html:'<span>'+META.byline+'</span>',css:{marginTop:'54px'}});
  fade(by,1.35,{dur:.8,dy:16});
});

/* ---- act 01 : the headline ---- */
scene('01 — The headline',3.2,'',s=>{
  E('div','kicker',P('Today’s headline'));
  const h=E('h1',null,P('Gemini 3.7 Flash is Google’s new workhorse.'));
  rise(h,.22,{stag:.045});
});

scene('01 — The headline',4.2,'blog.google',s=>{
  const b=E('div','body',{html:'A natively multimodal reasoning model tuned for <b>coding, agentic workflows and knowledge work</b>, with a one-million-token context window.'});
  fade(b,.1,{dur:.9});
  E('div','sp');
  const k=E('div','kicker',P('Live today in'));
  fade(k,.7,{dur:.5});
  const list=E('div','stack sm');
  ['Gemini API & AI Studio','Antigravity','Gemini Enterprise Agent Platform','The Spark agent'].forEach((t,i)=>{
    const it=E('div','item',{p:list,html:'<i></i><span>'+t+'</span>'});
    an(.9+i*.14,.55,EZ.quint,p=>{
      it.style.opacity=clamp(p*2);
      it.style.transform=`translateX(${(1-p)*-30}px)`;
    });
  });
});

scene('01 — The headline',4.6,'venturebeat',s=>{
  const k=E('div','kicker',P('And it costs half of what 3.6 Flash did'));
  fade(k,.05,{dur:.5});
  kpis([
    [0.75,'per 1M input tokens','',2,'$'],
    [3.75,'per 1M output tokens','',2,'$'],
    [50,'cheaper than 3.6 Flash','%',0,'']
  ],.35,'blue');
});

scene('01 — The headline',2.8,'venturebeat',s=>{
  const b=E('div','body',{html:'That is introductory pricing. It holds through 2026, then <b>doubles in 2027.</b>'});
  fade(b,.08,{dur:.8});
});

scene('01 — The headline',5.4,'deepmind',s=>{
  const b=E('div','body',{html:'The benchmark jumps over 3.6 Flash are not small.',css:{color:'var(--ink)',fontWeight:'600'}});
  fade(b,.05,{dur:.7});
  E('div','sp-s');
  const leg=E('div','legend',{html:
    '<span><i style="background:var(--blue-lo)"></i>3.6 Flash</span>'+
    '<span><i style="background:var(--blue)"></i>3.7 Flash</span>'});
  fade(leg,.28,{dur:.6,dy:12});

  const chart=E('div','chart');
  jumpChart([
    ['FrontierCode 1.1', 34.4, 43.6, '<s>34.4</s> &rarr; 43.6'],
    ['DeepSWE v1.1',     48.0, 65.3, '<s>48–49</s> &rarr; 65.3'],
    ['AutomationBench',  17.0, 30.4, '<s>17.0</s> &rarr; 30.4'],
    ['GDP.pdf',          22.0, 34.0, '<s>22.0</s> &rarr; 34.0']
  ],70,.5,chart);

  const ft=E('div','foot',{p:chart,html:'Scores as published by Google, on a common 0–70% scale. The DeepSWE v1.1 baseline is reported as a 48–49% range.'});
  an(2.9,.5,EZ.out,p=>{ft.style.opacity=p});
});

scene('01 — The headline',3.6,'reuters',s=>{
  E('div','kicker',P('Why it matters'));
  const h=E('h2',null,P('Agents just got cheaper to run.'));
  rise(h,.12,{stag:.05});
  E('div','sp-s');
  const b=E('div','body',P('Google is positioning 3.7 Flash as its main agentic model — better tool use and multi-step reliability, at half the cost of building on the last one.'));
  fade(b,.75);
});

scene('01 — The headline',3.8,'github.blog',s=>{
  const b=E('div','body',{html:'GitHub has switched it on inside <b>Copilot</b> — VS Code, Visual Studio, the CLI and the cloud agent.'});
  fade(b,.08,{dur:.85});
  E('div','sp');
  const b2=E('div','body',{html:'Enterprise admins have to enable a preview policy first.',css:{color:'var(--ink)'}});
  fade(b2,1.3);
});

/* ---- act 02 : core tech ---- */
scene('02 — Core tech',2.6,'',s=>{
  E('div','kicker',P('Model specs'));
  const h=E('h1',null,P('The spec sheet.'));
  rise(h,.18,{stag:.05});
});

scene('02 — Core tech',4.4,'deepmind',s=>{
  kpis([
    [1048576,'tokens in','',0,'','sm'],
    [65536,'tokens out','',0,'','sm']
  ],.1,'blue');
  E('div','sp-s');
  const b=E('div','body',{html:'Text, image, audio, video and <b>PDF</b> in. Text out.'});
  fade(b,1.5,{dur:.8});
});

scene('02 — Core tech',3.6,'deepmind',s=>{
  const k=E('div','kicker',P('Built in'));
  fade(k,.02,{dur:.4});
  const list=E('div','stack sm');
  ['Code execution','Computer use','URL context','Maps grounding','Function calling','Structured outputs'].forEach((t,i)=>{
    const it=E('div','item',{p:list,html:'<i></i><span>'+t+'</span>'});
    an(.2+i*.13,.55,EZ.quint,p=>{
      it.style.opacity=clamp(p*2);
      it.style.transform=`translateX(${(1-p)*-30}px)`;
    });
  });
});

scene('02 — Core tech',3.0,'aireleasetracker',s=>{
  const h=E('h2',null,P('Frontier-class releases now arrive every few days.'));
  rise(h,.1,{stag:.045});
});

/* ---- act 03 : agents ---- */
scene('03 — Agents',2.6,'',s=>{
  E('div','kicker',P('Agents & tooling'));
  const h=E('h1',null,P('The agent layer moved with it.'));
  rise(h,.18,{stag:.045});
});

scene('03 — Agents',4.0,'i-scoop',s=>{
  const h=E('h2',null,P('Gemini Spark'));
  rise(h,.08);
  const r=E('div','rule blue',{css:{marginTop:'28px',width:'240px'}});
  draw(r,.4);
  E('div','sp');
  const b=E('div','body',{html:'Google’s 24/7 personal agent — across Gmail, Calendar, Drive, Docs, Sheets, Maps and more — <b>now runs on 3.7 Flash.</b>'});
  fade(b,.6);
});

scene('03 — Agents',4.0,'aiagentslibrary',s=>{
  const k=E('div','kicker',P('Spark’s abstraction'));
  fade(k,.02,{dur:.4});
  const list=E('div','stack defs');
  [['Tasks','what to do'],['Skills','how to do it, reusably'],['Schedules','when to trigger']].forEach((t,i)=>{
    const it=E('div','item',{p:list,html:'<span>'+t[0]+'</span><span class="sub">'+t[1]+'</span>'});
    an(.2+i*.24,.6,EZ.quint,p=>{
      it.style.opacity=clamp(p*2);
      it.style.transform=`translateX(${(1-p)*-30}px)`;
    });
  });
  E('div','sp-s');
  const b=E('div','body',{html:'Repeatable workflows instead of one-off prompts.'});
  fade(b,1.15);
});

scene('03 — Agents',4.2,'github trending',s=>{
  const b=E('div','body',{html:'Two agents are climbing GitHub’s trending page.'});
  fade(b,.05,{dur:.6});
  E('div','sp-s');
  const list=E('div','stack defs');
  [['cline','an autonomous coding agent inside your IDE — every step gated behind your permission'],
   ['huggingface/ml-intern','an open-source ML engineer that reads papers, trains models and ships them']]
  .forEach((t,i)=>{
    const it=E('div','item',{p:list,html:'<span>'+t[0]+'</span><span class="sub">'+t[1]+'</span>'});
    an(.35+i*.4,.65,EZ.quint,p=>{
      it.style.opacity=clamp(p*2);
      it.style.transform=`translateX(${(1-p)*-30}px)`;
    });
  });
});

scene('03 — Agents',3.8,'github trending',s=>{
  const b=E('div','body',{html:'And the plumbing around them: <b>claude-context</b> turns whole codebases into MCP-searchable context, <b>context-mode</b> sandboxes and trims tool output.'});
  fade(b,.08,{dur:.85});
  E('div','sp');
  const b2=E('div','body',{html:'One curated list now tracks <b>1,000+ reusable agent skills.</b>',css:{color:'var(--ink)'}});
  fade(b2,1.35);
});

/* ---- act 04 : in the wild ---- */
scene('04 — In the wild',2.8,'',s=>{
  E('div','kicker',P('And finally'));
  const h=E('h1',null,P('An AI newsroom beat the reporters.'));
  rise(h,.18,{stag:.045});
});

scene('04 — In the wild',4.0,'wired',s=>{
  const h=E('h2',null,P('RuntimeWire'));
  rise(h,.08);
  const r=E('div','rule blue',{css:{marginTop:'28px',width:'240px'}});
  draw(r,.4);
  E('div','sp');
  const b=E('div','body',{html:'It crawls court databases, filings, forums and social feeds, then researches, drafts, fact-checks and publishes — with minimal human intervention.'});
  fade(b,.6);
});

scene('04 — In the wild',4.6,'wired',s=>{
  const k=E('div','kicker',P('On an OpenAI disclosure at Black Hat'));
  fade(k,.05,{dur:.5});
  kpis([
    [3,'hours ahead of the human reporters'],
    [6,'minutes from transcript to published story'],
    [2000,'stories since May','',0,'~']
  ],.35,'blue');
});

scene('04 — In the wild',4.0,'explainx',s=>{
  const b=E('div','body',{html:'Meanwhile in New Orleans, an AI agent has been quietly <b>deduplicating crash-related 911 calls since 2023</b> — and triaging non-emergency 311 calls since April.'});
  fade(b,.08,{dur:.9});
});

scene('04 — In the wild',3.8,'explainx',s=>{
  const h=E('h2',null,{html:'Nobody was told until <span class="warm-t">a viral post forced it.</span>'});
  rise(h,.1,{stag:.045});
  E('div','sp-s');
  const b=E('div','body',P('It was confirmed publicly on 6 August. The agent escalates to a human whenever the caller is involved, has new information, or it is violent crime or a medical emergency.'));
  fade(b,.8);
});

scene('04 — In the wild',3.4,'cloudsecurityalliance',s=>{
  const b=E('div','lede',P('NIST is still drafting interoperability profiles and control overlays for agentic systems.'));
  fade(b,.05,{dur:.8});
  E('div','sp-s');
  const b2=E('div','body',{html:'Deployment is outpacing governance.',css:{color:'var(--ink)'}});
  fade(b2,1.0);
});

scene('04 — In the wild',3.8,'',s=>{
  const t=E('div','big-title',P('THAT’S<br>THE BRIEF.'));
  rise(t,.08,{stag:.08,dur:.85});
  const r=E('div','rule blue',{css:{marginTop:'44px',width:'340px'}});
  draw(r,.62);
  const b=E('div','body',{html:'A cheaper agentic default. A faster Spark. And a 911 line that was already automated.',css:{marginTop:'40px'}});
  fade(b,.9);
  const b2=E('div','lede',{html:'Same time tomorrow.',css:{marginTop:'26px'}});
  fade(b2,1.6);
  const by=E('div','byline',{html:'<span>'+META.byline+'</span>',css:{marginTop:'56px'}});
  fade(by,2.1,{dur:.85,dy:18});
});
