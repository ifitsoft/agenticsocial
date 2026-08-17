/* ============================================================
   The Brief — render engine.
   Deterministic: seek(t) positions every element from t alone.
   No CSS keyframes, no Date.now(), no randomness.

   Content lives in content/<YYYY-MM-DD>.js, which sets META and
   then calls scene(...) once per beat. This file never changes
   between episodes.
   ============================================================ */

const clamp=(v,a=0,b=1)=>v<a?a:v>b?b:v;
const lerp=(a,b,p)=>a+(b-a)*p;
const EZ={
  lin:p=>p,
  out:p=>1-Math.pow(1-p,3),
  quint:p=>1-Math.pow(1-p,5),
  expo:p=>p>=1?1:1-Math.pow(2,-11*p),
  io:p=>p<.5?2*p*p:1-Math.pow(-2*p+2,2)/2,
  back:p=>{const c=1.6;return 1+(c+1)*Math.pow(p-1,3)+c*Math.pow(p-1,2)}
};

const SCENES=[];
let META={}, ANIMS=[], CUR=-1, SC=null, TOTAL=0, STARTS=[], ACT_START={}, PACE=1;
let stageScenes,actEl,tagEl,byEl,progEl;

const P=(t)=>({html:t});

/* content entry points ---------------------------------------------------- */
function meta(m){META=m;}
/* base duration; the PACE multiplier is applied at init */
function scene(act,dur,tag,build){SCENES.push({act,base:dur,tag,build});}

/* register an animation: fn receives eased progress */
function an(d0,dur,ez,fn){ANIMS.push({d0,dur,ez,fn});fn(0);}

function E(tag,cls,opts){
  opts=opts||{};
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(opts.html!=null)e.innerHTML=opts.html;
  if(opts.text!=null)e.textContent=opts.text;
  if(opts.css)Object.assign(e.style,opts.css);
  (opts.p||SC).appendChild(e);
  return e;
}

/* masked word-by-word rise. Walks the DOM so inline tags (<em>, <br>) survive. */
function rise(el,d0,o){
  o=o||{};
  const stag=o.stag||.052, dur=o.dur||.78;
  const reg=[];
  (function walk(node){
    for(const c of [...node.childNodes]){
      if(c.nodeType===3){
        const frag=document.createDocumentFragment();
        for(const w of c.textContent.split(/(\s+)/)){
          if(!w)continue;
          if(/^\s+$/.test(w)){frag.appendChild(document.createTextNode(' '));continue;}
          const m=document.createElement('span');m.className='wm';
          const inner=document.createElement('span');inner.className='wi';
          inner.textContent=w;
          m.appendChild(inner);frag.appendChild(m);
          reg.push(inner);
        }
        node.replaceChild(frag,c);
      }else if(c.nodeType===1){walk(c);}
    }
  })(el);
  reg.forEach((inner,k)=>{
    an(d0+k*stag,dur,EZ.quint,p=>{
      inner.style.transform=`translateY(${(1-p)*115}%)`;
      inner.style.opacity=clamp(p*2.2);
    });
  });
  return d0+reg.length*stag+dur;
}

/* blur-to-sharp fade up */
function fade(el,d0,o){
  o=o||{};const dur=o.dur||.85,dy=o.dy==null?26:o.dy,bl=o.blur==null?9:o.blur;
  an(d0,dur,EZ.out,p=>{
    el.style.opacity=p;
    el.style.transform=`translateY(${(1-p)*dy}px)`;
    el.style.filter=p>=1?'none':`blur(${(1-p)*bl}px)`;
  });
  return d0+dur;
}

/* rule draws left→right */
function draw(el,d0,dur){
  dur=dur||.7;
  an(d0,dur,EZ.expo,p=>{el.style.transform=`scaleX(${p})`});
  return d0+dur;
}

/* eased count-up */
function count(el,d0,dur,to,suffix,decimals,prefix){
  an(d0,dur,EZ.quint,p=>{
    const v=to*p;
    el.textContent=(prefix||'')+(decimals?v.toFixed(decimals):Math.round(v).toLocaleString('en-US'))+(suffix||'');
  });
  return d0+dur;
}

/* KPI stack — a column of headline figures. `tone` is 'blue' or 'warm'.
   item = [value, unit, suffix, decimals, prefix, sizeClass] */
function kpis(items,d0,tone){
  items.forEach((it,i)=>{
    const row=E('div','kpi '+(tone||'blue')+(it[5]?' '+it[5]:''));
    const n=E('div','n',{p:row,text:'0'});
    const u=E('div','u',{p:row,text:it[1]});
    const rule=E('div','kpi-rule '+(tone||'blue'));
    const t0=d0+i*.62;
    an(t0,.5,EZ.out,p=>{row.style.opacity=p;row.style.transform=`translateY(${(1-p)*20}px)`});
    if(typeof it[0]==='number')count(n,t0,1.35,it[0],it[2],it[3],it[4]);
    else an(t0,.5,EZ.out,p=>{n.textContent=p>0?it[0]:''});
    an(t0+.1,.7,EZ.expo,p=>{rule.style.transform=`scaleX(${p})`});
  });
}

/* Before→after dumbbell. rows: [label, from, to, formatted] · max sets the scale. */
function jumpChart(rows,max,d0,parent){
  rows.forEach((r,i)=>{
    const [lab,from,to,shown]=r;
    const row=E('div','jrow',{p:parent});
    const head=E('div','jhead',{p:row});
    E('div','jlab',{p:head,text:lab});
    const val=E('div','jval',{p:head,html:shown});
    const tr=E('div','jtrack',{p:row});
    const gain=E('div','jgain',{p:row});
    const dA=E('div','dot from',{p:row});
    const dB=E('div','dot to',{p:row});
    const t0=d0+i*.34;
    fade(head,t0,{dur:.5,dy:12,blur:5});
    draw(tr,t0+.05,.55);
    dA.style.left=(from/max*100)+'%';
    an(t0+.3,.45,EZ.back,p=>{dA.style.opacity=clamp(p*3);dA.style.transform=`scale(${lerp(.3,1,p)})`});
    // the blue segment grows from the old score to the new one — the gain IS the story
    gain.style.left=(from/max*100)+'%';
    an(t0+.5,.8,EZ.quint,p=>{
      gain.style.width=((to-from)/max*100*p)+'%';
      gain.style.opacity=clamp(p*4);
      dB.style.left=(from/max*100+(to-from)/max*100*p)+'%';
      dB.style.opacity=clamp(p*4);
      dB.style.transform=`scale(${lerp(.5,1,p)})`;
    });
  });
}

/* ============================ seek ============================ */
function seek(t){
  t=clamp(t,0,TOTAL-.0001);

  /* background — continuous, never resets across cuts */
  document.getElementById('b1').style.transform=
    `translate(${120+Math.sin(t*.21)*180}px,${180+Math.cos(t*.17)*220}px)`;
  document.getElementById('b2').style.transform=
    `translate(${520+Math.cos(t*.15)*200}px,${1180+Math.sin(t*.19)*240}px)`;
  document.getElementById('grid').style.transform=
    `translate(${-(t*4)%90}px,${-(t*9)%90}px)`;
  progEl.style.transform=`scaleX(${t/TOTAL})`;

  /* active scene */
  let i=SCENES.length-1;
  for(let k=0;k<SCENES.length;k++){if(t<STARTS[k]+SCENES[k].dur){i=k;break;}}
  const S=SCENES[i], lt=t-STARTS[i];

  if(i!==CUR){
    CUR=i;ANIMS=[];stageScenes.innerHTML='';
    SC=document.createElement('div');SC.className='sc';
    stageScenes.appendChild(SC);
    S.build(SC);
  }

  for(const a of ANIMS){a.fn(a.ez(clamp((lt-a.d0)/a.dur)));}

  /* scene exit — blur out on the tail so cuts feel authored, not abrupt */
  const tail=.34;
  if(lt>S.dur-tail){
    const p=EZ.io((lt-(S.dur-tail))/tail);
    SC.style.opacity=String(1-p);
    SC.style.transform=`translateY(${-30*p}px)`;
    SC.style.filter=`blur(${8*p}px)`;
  }else{
    SC.style.opacity='1';SC.style.transform='none';SC.style.filter='none';
  }

  /* act label */
  if(S.act){
    actEl.textContent=S.act;
    actEl.className=(META.warmActs||[]).includes(S.act)?'warm':'';
    const ap=clamp((t-ACT_START[S.act])/.5);
    actEl.style.opacity=String(EZ.out(ap));
    actEl.style.transform=`translateY(${(1-EZ.out(ap))*14}px)`;
  }else{actEl.style.opacity='0';}

  /* persistent byline — suppressed on any card that draws its own full-size one */
  const ownByline=!!SC.querySelector('.byline');
  byEl.style.opacity=ownByline?'0':String(EZ.out(clamp((t-.6)/.8)));

  /* source tag */
  if(S.tag){
    tagEl.textContent=S.tag;
    const tp=clamp((lt-.55)/.5)*(lt>S.dur-tail?1-EZ.io((lt-(S.dur-tail))/tail):1);
    tagEl.style.opacity=String(EZ.out(tp));
  }else{tagEl.style.opacity='0';}
}

/* ============================ init ============================ */
function init(){
  stageScenes=document.getElementById('scenes');
  actEl=document.getElementById('act');
  tagEl=document.getElementById('tag');
  byEl=document.getElementById('by');
  progEl=document.querySelector('#prog i');

  /* Read-time knob. Entrance animations keep their speed — PACE only extends how
     long each beat HOLDS after its text has landed. URL wins, then the episode's
     own value, then 1.0. */
  PACE=Number(new URLSearchParams(location.search).get('pace'))||META.pace||1;
  SCENES.forEach(s=>{s.dur=s.base*PACE;});

  document.getElementById('date').textContent=META.dateShort||'';
  document.getElementById('by').textContent=META.byline||'';

  TOTAL=SCENES.reduce((a,s)=>a+s.dur,0);
  STARTS=[];{let a=0;for(const s of SCENES){STARTS.push(a);a+=s.dur;}}
  ACT_START={};SCENES.forEach((s,i)=>{if(s.act&&!(s.act in ACT_START))ACT_START[s.act]=STARTS[i];});

  window.__seek=seek;
  window.__total=TOTAL;
  window.__meta=META;
  window.__scenes=SCENES.map(s=>({act:s.act,dur:s.dur,tag:s.tag}));

  const sl=document.getElementById('sl');
  sl.addEventListener('input',()=>seek(sl.value/1000*TOTAL));
  seek(0);
  console.log('TOTAL',TOTAL.toFixed(2),'s ·',SCENES.length,'scenes · pace',PACE);
}
