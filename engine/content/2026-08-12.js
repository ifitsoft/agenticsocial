/* The Brief — Wednesday, 12 August 2026 */

meta({
  date:'2026-08-12',
  dateShort:'12 · 08 · 26',
  dateLong:'Wednesday, 12 August 2026',
  byline:'Ali Abdukarim',
  warmActs:['03 — Agents'],
  pace:1.435,
});

/* ---- cold open ---- */
scene('',3.0,'',s=>{
  const h=E('h2',null,P('Today, AI-generated text began signing itself.'));
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
  const h=E('h1',null,P('Claude will start signing everything it writes.'));
  rise(h,.22,{stag:.045});
});

scene('01 — The headline',4.6,'gizmodo',s=>{
  const b=E('div','body',{html:'Anthropic is embedding <b>invisible, machine-readable watermarks</b> into the text Claude generates — a transparency rule written for the EU AI Act that they are extending worldwide.'});
  fade(b,.1,{dur:.9});
  E('div','sp');
  const para=E('div','para',P('The pattern is woven through the generated text itself. It is not a header, not a footer, not a tag you can delete. It rides along inside the words, invisible to you, legible to a detector that knows what to look for.'));
  fade(para,.55,{dur:.7,dy:16});
  const words=para.textContent.split(' ');
  para.innerHTML='';
  const spans=[];
  words.forEach((w,i)=>{
    const sp=document.createElement('span');sp.className='w';sp.textContent=w+' ';
    para.appendChild(sp);
    // deterministic scatter, but only on substantial words — lighting up "a"
    // and "is" reads as a typo rather than a hidden pattern
    if((i%5===2||i%11===7)&&w.replace(/\W/g,'').length>=4)spans.push(sp);
  });
  const scan=E('div','scan',{p:para});
  const H=para.offsetHeight;
  an(1.25,2.1,EZ.io,p=>{
    scan.style.top=(p*H)+'px';
    scan.style.opacity=p<=0||p>=1?0:.9;
  });
  spans.forEach(sp=>{
    const y=sp.offsetTop+10;
    const hit=1.25+(y/H)*2.1;
    an(hit,.45,EZ.out,p=>{
      // colour + glow only — a font-weight change would reflow the paragraph mid-sweep
      sp.style.color=p>0?`rgba(46,107,255,${lerp(.55,1,p)})`:'';
      sp.style.textShadow=p>0?`0 0 ${20*p}px rgba(46,107,255,${.45*p})`:'none';
    });
  });
});

scene('01 — The headline',3.0,'',s=>{
  const h=E('h2',null,P('Copy it. Paste it. The mark travels with it.'));
  rise(h,.12,{stag:.05});
});

scene('01 — The headline',3.6,'gizmodo',s=>{
  const b=E('div','body',{html:'And supported image formats — <b>PNG, JPG</b> — get signed provenance metadata following the C2PA standard.'});
  fade(b,.08);
  E('div','sp');
  const tile=E('div','tile');
  E('div','ridge',{p:tile});E('div','ridge two',{p:tile});E('div','sun',{p:tile});
  fade(tile,.3,{dur:.7,dy:20});
  const seal=E('div','seal',{p:tile,html:'<svg viewBox="0 0 24 24" fill="none" stroke="#2E6BFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 L9.5 18 L20 6.5"/></svg><span>C2PA SIGNED</span>'});
  const path=seal.querySelector('path');
  path.style.strokeDasharray='30';
  an(1.0,.55,EZ.back,p=>{
    seal.style.opacity=clamp(p*3);
    seal.style.transform=`scale(${lerp(.72,1,p)})`;
  });
  an(1.45,.5,EZ.out,p=>{path.style.strokeDashoffset=String(30*(1-p))});
});

scene('01 — The headline',3.6,'',s=>{
  E('div','kicker',P('Why it matters'));
  const h=E('h2',null,P('The default is flipping.'));
  rise(h,.12,{stag:.05});
  E('div','sp-s');
  const b=E('div','body',P('For two years watermarking was a debate. It is now a setting — AI text arrives labelled unless someone strips the label off.'));
  fade(b,.75);
});

scene('01 — The headline',3.8,'globalnews',s=>{
  const h=E('h2',null,P('The limits are real.'));
  rise(h,.1,{stag:.05});
  E('div','sp-s');
  const b=E('div','body',{html:'Marks survive light edits. Heavy rewriting or a format change can wash them out — and Anthropic says <b>false positives and false negatives</b> are both possible.'});
  fade(b,.7);
});

/* ---- act 02 : models ---- */
scene('02 — Models',2.8,'',s=>{
  E('div','kicker',P('Core tech'));
  const h=E('h1',null,P('Two model releases landed.'));
  rise(h,.18,{stag:.045});
});

scene('02 — Models',4.2,'x.ai',s=>{
  const h=E('h2',null,P('Grok 4.6'));
  rise(h,.1);
  const r=E('div','rule blue',{css:{marginTop:'28px',width:'220px'}});
  draw(r,.42);
  E('div','sp');
  const b=E('div','body',{html:'xAI is not selling this one on benchmarks. The pitch is <b>long-running agents</b> and more ambitious interactive and visual work.'});
  fade(b,.62);
  E('div','sp-s');
  const b2=E('div','body',{html:'In practice: <b>state that survives a long task.</b>',css:{color:'var(--ink)'}});
  fade(b2,1.5);
});

scene('02 — Models',2.8,'artificialintelligence-news',s=>{
  const h=E('h2',null,P('Google ran AMIE as a live video consultation.'));
  rise(h,.12,{stag:.045});
});

scene('02 — Models',5.6,'artificialintelligence-news',s=>{
  const b=E('div','body',{html:'Evaluators rated it <b>on par with primary care physicians.</b>',css:{color:'var(--ink)',fontWeight:'600'}});
  fade(b,.05,{dur:.7});
  E('div','sp-s');

  const leg=E('div','legend',{html:
    '<span><i style="background:var(--blue)"></i>AMIE (video)</span>'+
    '<span><i style="background:var(--cyan)"></i>Primary care physician</span>'+
    '<span><i class="split"></i>both</span>'});
  fade(leg,.3,{dur:.6,dy:12});

  const chart=E('div','chart');
  const ROWS=[
    ['History-taking',        .72,.72,'on par',false],
    ['Diagnostic accuracy',   .72,.72,'on par',false],
    ['Management',            .72,.72,'on par',false],
    ['Communication quality', .72,.72,'on par',false]
  ];
  const EXTRA=['Eliciting physical signs',.82,.58,'rated higher',true];

  function row(spec,d0,parent){
    const [lab,a,b2,note,up]=spec;
    const r=E('div','crow',{p:parent});
    const L=E('div','lab',{p:r,text:lab});
    const N=E('div','note'+(up?' up':''),{p:r,text:note});
    const tr=E('div','track',{p:r});
    fade(L,d0,{dur:.5,dy:10,blur:5});
    draw(tr,d0+.05,.6);

    if(up){
      // a real gap: AMIE separates out from the physician marker
      const dB=E('div','dot b',{p:r});
      const dA=E('div','dot a',{p:r});
      dB.style.left=b2*100+'%';
      an(d0+.28,.9,EZ.quint,p=>{
        dB.style.opacity=clamp(p*3);dB.style.transform=`scale(${lerp(.4,1,p)})`;
        dA.style.left=lerp(b2*100,a*100,p)+'%';
        dA.style.opacity=clamp(p*3);dA.style.transform=`scale(${lerp(.4,1,p)})`;
      });
    }else{
      // no gap: one two-tone marker rather than two dots stacked invisibly
      const d=E('div','dot merged',{p:r});
      d.style.left=a*100+'%';
      an(d0+.28,.7,EZ.back,p=>{
        d.style.opacity=clamp(p*3);
        d.style.transform=`scale(${lerp(.25,1,p)})`;
      });
    }
    an(d0+1.0,.4,EZ.out,p=>{N.style.opacity=p});
  }

  ROWS.forEach((sp,i)=>row(sp,.55+i*.22,chart));
  const dv=E('div','div-line',{p:chart});
  draw(dv,1.62,.5);
  row(EXTRA,1.8,chart);

  const ax=E('div','axis',{p:chart,html:'<span>lower rating</span><span>higher rating &rarr;</span>'});
  an(2.5,.5,EZ.out,p=>{ax.style.opacity=p*.9});
  const ft=E('div','foot',{p:chart,html:'Direction only — the source reports evaluator ratings, not published scores.'});
  an(2.7,.5,EZ.out,p=>{ft.style.opacity=p});
});

scene('02 — Models',2.6,'artificialintelligence-news',s=>{
  const h=E('h2',null,P('Patient actors preferred the video interface to chat.'));
  rise(h,.1,{stag:.042});
});

scene('02 — Models',2.6,'',s=>{
  const b=E('div','body',{html:'Also moving: <b>Dyna-2</b> teaches robots straight from human video, and <b>MiniMax H3</b> runs multimodal inference locally on a Mac.'});
  fade(b,.08,{dur:.8});
});

/* ---- act 03 : agents ---- */
scene('03 — Agents',2.8,'',s=>{
  E('div','kicker',P('Agents & tooling'));
  const h=E('h1',null,P('Agents got a real job — and a real wound.'));
  rise(h,.18,{stag:.045});
});

scene('03 — Agents',4.4,'nordiclifescience',s=>{
  const h=E('h2',null,P('Novo Nordisk × AWS'));
  rise(h,.08);
  const r=E('div','rule blue',{css:{marginTop:'28px',width:'260px'}});
  draw(r,.4);
  E('div','sp');
  const b=E('div','body',{html:'A London co-innovation hub where AWS engineers sit with Novo Nordisk scientists, running agents across <b>genomic, imaging and clinical data.</b>'});
  fade(b,.6);
  E('div','sp-s');
  const b2=E('div','body',{html:'The target: compress the path from <b>drug target to first human dose.</b>',css:{color:'var(--ink)'}});
  fade(b2,1.5);
});

scene('03 — Agents',2.2,'',s=>{
  const h=E('h2',null,{html:'And then <span class="warm-t">the warning.</span>'});
  rise(h,.08,{stag:.045});
});

scene('03 — Agents',5.4,'devops.com',s=>{
  const k=E('div','kicker',{html:'The LiteLLM supply-chain attack',css:{color:'var(--warm)'}});
  fade(k,.05,{dur:.5});
  kpis([[2500,'organisations exposed'],[434000,'CI/CD pipelines'],[40,'minutes on PyPI']],.35,'warm');
});

scene('03 — Agents',4.4,'devops.com',s=>{
  const b=E('div','body',{html:'LiteLLM was never the target. Attackers hijacked <b>Trivy</b> — a security scanner — and one unrevoked credential turned an open-source security tool into an AI infrastructure breach.'});
  fade(b,.08,{dur:.85});
  E('div','sp');
  const b2=E('div','body',{html:'Forty minutes of poisoned releases. That was all it took.',css:{color:'var(--ink)',fontWeight:'600'}});
  fade(b2,1.5);
});

scene('03 — Agents',2.8,'',s=>{
  const k=E('div','kicker',P('The new attack surface'));
  fade(k,.02,{dur:.4});
  const list=E('div','stack warm');
  ['AI gateways','Agent runtimes','MCP servers','Vector stores'].forEach((t,i)=>{
    const it=E('div','item',{p:list,html:'<i></i><span>'+t+'</span>'});
    an(.22+i*.16,.6,EZ.quint,p=>{
      it.style.opacity=clamp(p*2);
      it.style.transform=`translateX(${(1-p)*-34}px)`;
    });
  });
});

/* ---- act 04 : the human one ---- */
scene('04 — The human one',2.8,'',s=>{
  E('div','kicker',P('And finally'));
  const h=E('h1',null,P('ChatTJB.'));
  rise(h,.15,{stag:.06});
  E('div','sp-s');
  const b=E('div','body',P('Marketed like an AI chatbot.'));
  fade(b,.75);
});

scene('04 — The human one',3.4,'fortune',s=>{
  const h=E('h2',null,{html:'It is one 32-year-old and <em>10,000 volunteers</em>, answering by hand.'});
  rise(h,.1,{stag:.045});
});

scene('04 — The human one',2.6,'',s=>{
  const b=E('div','lede',P('A whole company simulating the one thing everybody else is automating.'));
  fade(b,.05,{dur:.8});
  E('div','sp-s');
  const b2=E('div','body',{html:'The inversion is the point.',css:{color:'var(--ink)'}});
  fade(b2,.95);
});

scene('04 — The human one',3.8,'',s=>{
  const t=E('div','big-title',P('THAT’S<br>THE BRIEF.'));
  rise(t,.08,{stag:.08,dur:.85});
  const r=E('div','rule blue',{css:{marginTop:'44px',width:'340px'}});
  draw(r,.62);
  const b=E('div','body',{html:'Watermarks by default. Agents that outlast a session. A supply chain nobody is watching.',css:{marginTop:'40px'}});
  fade(b,.9);
  const b2=E('div','lede',{html:'Same time tomorrow.',css:{marginTop:'26px'}});
  fade(b2,1.6);
  const by=E('div','byline',{html:'<span>'+META.byline+'</span>',css:{marginTop:'56px'}});
  fade(by,2.1,{dur:.85,dy:18});
});
