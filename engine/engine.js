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

/* ---------------------- the declared context (spec 9) ----------------------
   A format is a declared CONTEXT, not a stylesheet fork. Every per-format
   difference is one of these values, and the beat builders below never read
   any of them: they draw the same elements, and scene.html's rules apply
   according to what the stage declares.

   The default IS the vertical stage, so content/<date>.js — which carries no
   format at all — draws exactly what it always drew. */
let FMT={name:'vertical',w:1080,h:1920,safe_top:400,safe_bottom:1580,measure:'narrow',scale:1};

/* `type_scale` was copied into plan.json and read by nobody (D-116) — a knob an
   operator would reasonably believe controls the typography, that controlled
   nothing, while the approval bound it. It is the multiplier ON the format's
   scale: the type is set smaller or larger and the measure moves with it, so
   `compact` fits more copy per card rather than merely shrinking the words.
   Its neighbour in `[design]` — the font stack — was retired instead of wired
   (D-077): whether a family resolves is a property of the machine rather than
   of the string, so it could only ever fail silently. Nothing in this directory
   names it, which is the state a grep can check. */
const TYPE_SCALES={default:1,compact:.88,large:1.12};
let TYPE_SCALE=1;

function applyFormat(){
  const st=document.getElementById('stage');
  if(!st)return;
  st.style.setProperty('--stage-w',FMT.w+'px');
  st.style.setProperty('--stage-h',FMT.h+'px');
  st.style.setProperty('--safe-top',FMT.safe_top+'px');
  st.style.setProperty('--safe-bottom',FMT.safe_bottom+'px');
  const s=FMT.scale*TYPE_SCALE;
  st.style.setProperty('--fmt-scale',String(s));
  st.dataset.measure=FMT.measure;
  /* data-scaled, not "scale it always": transform:scale(1) promotes the scene
     to its own compositing layer and changes how blurred glyphs rasterise,
     which is the invariant this engine sells. */
  if(s===1)delete st.dataset.scaled; else st.dataset.scaled='';
}

const P=(t)=>({html:t});

/* content entry points ---------------------------------------------------- */
function meta(m){META=m;}
/* the format the plan declares. Refused rather than defaulted where it is
   malformed: a stage silently 1080 wide when the plan said 1920 is M7. */
function format(f){
  if(!f)return;
  for(const k of ['w','h','safe_top','safe_bottom','scale']){
    if(typeof f[k]!=='number'||!isFinite(f[k])){
      throw new Error('plan.format.'+k+' is '+JSON.stringify(f[k])+
        ' — the stage is the format the plan declares, and a format that cannot '+
        'say how big it is would silently render at the default size');
    }
  }
  FMT=Object.assign({},FMT,f);
  applyFormat();
}
function typeScale(name){
  if(name==null||name==='')return;
  if(!Object.prototype.hasOwnProperty.call(TYPE_SCALES,name)){
    throw new Error('unknown type_scale '+JSON.stringify(name)+' — the scales are '+
      Object.keys(TYPE_SCALES).join(', ')+'. Refused rather than defaulted to 1: '+
      'a knob that reads as set and is not is exactly what D-116 found');
  }
  TYPE_SCALE=TYPE_SCALES[name];
  applyFormat();
}
/* base duration; the PACE multiplier is applied at init. `kind` is the beat
   type, carried so a refusal can say what it was looking at — the hand-written
   episodes pass four arguments and are unaffected. */
function scene(act,dur,tag,build,kind){SCENES.push({act,base:dur,tag,build,kind});}

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

/* Value-animation timing, named rather than inlined.
   A count-up that cannot finish inside its beat's hold leaves the LAST rendered
   frame showing a mid-count figure, and a mid-count figure at the end of a beat
   is not "on its way" to anything — it IS what the video says. planbuild.js
   refuses such a beat, and it has to compute the hold it needs from the same
   numbers the animation uses; a second copy of `.62` there would drift from
   this one silently. Renamed, retimed or restaggered here, the requirement
   moves with it. */
const KPI_STAGGER=.62, KPI_COUNT_DUR=1.35;
const JUMP_STAGGER=.34, JUMP_GROW_D0=.5, JUMP_GROW_DUR=.8;

/* KPI stack — a column of headline figures. `tone` is 'blue' or 'warm'.
   item = [value, unit, suffix, decimals, prefix, sizeClass] */
function kpis(items,d0,tone){
  /* One container, one cell per figure. Both exist for the WIDE context, where
     9 sets this stack as a single row: a figure and the rule under it have to
     travel together, or a row layout interleaves four figures and four rules.
     In the narrow context they are plain blocks in a column, which is what the
     two committed episodes already drew — verified frame-identical. */
  const box=E('div','kpis');
  items.forEach((it,i)=>{
    const cell=E('div','kpi-cell',{p:box});
    const row=E('div','kpi '+(tone||'blue')+(it[5]?' '+it[5]:''),{p:cell});
    const n=E('div','n',{p:row,text:'0'});
    const u=E('div','u',{p:row,text:it[1]});
    const rule=E('div','kpi-rule '+(tone||'blue'),{p:cell});
    const t0=d0+i*KPI_STAGGER;
    an(t0,.5,EZ.out,p=>{row.style.opacity=p;row.style.transform=`translateY(${(1-p)*20}px)`});
    if(typeof it[0]==='number')count(n,t0,KPI_COUNT_DUR,it[0],it[2],it[3],it[4]);
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
    const t0=d0+i*JUMP_STAGGER;
    fade(head,t0,{dur:.5,dy:12,blur:5});
    draw(tr,t0+.05,.55);
    dA.style.left=(from/max*100)+'%';
    an(t0+.3,.45,EZ.back,p=>{dA.style.opacity=clamp(p*3);dA.style.transform=`scale(${lerp(.3,1,p)})`});
    // the blue segment grows from the old score to the new one — the gain IS the story
    gain.style.left=(from/max*100)+'%';
    an(t0+JUMP_GROW_D0,JUMP_GROW_DUR,EZ.quint,p=>{
      gain.style.width=((to-from)/max*100*p)+'%';
      gain.style.opacity=clamp(p*4);
      dB.style.left=(from/max*100+(to-from)/max*100*p)+'%';
      dB.style.opacity=clamp(p*4);
      dB.style.transform=`scale(${lerp(.5,1,p)})`;
    });
  });
}

/* Dumbbell — two entities on one UNLABELLED track.
   rows: [label, a, b, note] · positions are fractions of the track (0..1).

   Extracted from content/2026-08-12.js, which built the AMIE chart inline and
   is the only dumbbell that has ever rendered. Two things about it are the
   reason the type exists, and neither is decoration:

   1. There is no numeric axis and no scale argument. Spec §7.2: this is the
      correct type when a source publishes RATINGS rather than scores, so a
      value is a position, not a figure, and nothing here prints one. The
      footnote is where "direction only" gets said out loud.
   2. Where the two values coincide, ONE two-tone marker — the episode's own
      comment: "no gap: one two-tone marker rather than two dots stacked
      invisibly". Two dots at the same left stack, the second hides the first,
      and the chart shows one series while claiming to compare two. The absent
      gap IS the finding, so it has to be drawn as something.

   `gap` is derived from the values, never declared: a flag can disagree with
   the numbers it describes, and the disagreement is invisible on screen. */
const DUMB_STAGGER=.22, DUMB_MOVE_D0=.28, DUMB_MOVE_DUR=.9;
function dumbbell(rows,d0,parent){
  rows.forEach((r,i)=>{
    const [lab,a,b,note]=r;
    const gap=a!==b;
    const row=E('div','crow',{p:parent});
    const L=E('div','lab',{p:row,text:lab});
    /* `.note.up` is the accent colour — it marks the row that separated, which
       is the row the chart is about. */
    const N=E('div','note'+(gap?' up':''),{p:row,text:note||''});
    const tr=E('div','track',{p:row});
    const t0=d0+i*DUMB_STAGGER;
    fade(L,t0,{dur:.5,dy:10,blur:5});
    draw(tr,t0+.05,.6);
    if(gap){
      // a real gap: the first series separates out from the second's marker
      const dB=E('div','dot b',{p:row});
      const dA=E('div','dot a',{p:row});
      dB.style.left=b*100+'%';
      an(t0+DUMB_MOVE_D0,DUMB_MOVE_DUR,EZ.quint,p=>{
        dB.style.opacity=clamp(p*3);dB.style.transform=`scale(${lerp(.4,1,p)})`;
        dA.style.left=lerp(b*100,a*100,p)+'%';
        dA.style.opacity=clamp(p*3);dA.style.transform=`scale(${lerp(.4,1,p)})`;
      });
    }else{
      // no gap: one two-tone marker rather than two dots stacked invisibly
      const d=E('div','dot merged',{p:row});
      d.style.left=a*100+'%';
      an(t0+DUMB_MOVE_D0,.7,EZ.back,p=>{
        d.style.opacity=clamp(p*3);
        d.style.transform=`scale(${lerp(.25,1,p)})`;
      });
    }
    an(t0+1,.4,EZ.out,p=>{N.style.opacity=p});
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
  }else{
    /* Clear, don't just hide. A scene with no act must not inherit the previous
       scene's label: opacity:0 leaves the stale text and transform in the DOM,
       so __seek(t) would depend on where you seeked from. Invisible today only
       because the opacity is exactly 0 — it becomes a wrong-label bug the moment
       the chip fades instead of snapping, or anything reads the text. */
    actEl.textContent='';actEl.className='';
    actEl.style.opacity='0';actEl.style.transform='none';
  }

  /* persistent byline — suppressed on any card that draws its own full-size one */
  const ownByline=!!SC.querySelector('.byline');
  byEl.style.opacity=ownByline?'0':String(EZ.out(clamp((t-.6)/.8)));

  /* source tag */
  if(S.tag){
    tagEl.textContent=S.tag;
    const tp=clamp((lt-.55)/.5)*(lt>S.dur-tail?1-EZ.io((lt-(S.dur-tail))/tail):1);
    tagEl.style.opacity=String(EZ.out(tp));
  }else{tagEl.textContent='';tagEl.style.opacity='0';}

  /* Re-insert the scene node so it is rasterised from scratch every seek.
     Chromium composites `filter: blur()` differently on a layer that already has
     a warm raster (scrubbed into the tail within one scene) than on a layer built
     fresh (jumped in from another scene) — up to 9/255 on blurred glyphs. That
     made seek(t) depend on where you seeked from, which is exactly the invariant
     this engine sells. appendChild() of an existing child is a remove+insert, so
     it throws away the paint layer WITHOUT rebuilding the DOM or re-running
     rise()'s walk: the scene is still built once per scene, not once per frame. */
  stageScenes.appendChild(SC);
}

/* ============================ does it fit? ============================
 *
 * The check nothing else in this project can make.
 *
 * Verification compares the words on the card to their source. Drift compares
 * what the operator authored to what they approved. Determinism compares a
 * frame to itself. **None of them can see a beat whose text leaves its box.**
 * Nothing clips, nothing throws, no status is wrong — the video is simply bad,
 * and the first person to find out is a viewer.
 *
 * MEASURED, never predicted. How tall a paragraph sets is a property of the
 * font this machine resolved and of Chromium's line breaking, which is exactly
 * the half D-116 says no approval covers. Python could estimate it, and an
 * estimate is a second answer to a question the page already answers — D-007's
 * rule pointed at layout instead of timing. So the refusal happens as early as
 * a real measurement can happen, which is here.
 *
 * At the SETTLED state — every animation at p=1 — because that is the card a
 * viewer reads. At p=0 every risen word sits 115% below its line and every beat
 * in the series "overflows".
 *
 * ONCE, at init, over every beat, rather than lazily as seek() reaches them:
 * render.mjs inspects page errors immediately after load, so this costs the
 * operator a second instead of the fourteen minutes it takes to discover beat
 * 14 at frame 900.
 */
const FIT_TOL=2; /* px. A sub-pixel line box is not an overflowing card (D-040:
                    a check that cries wolf is a check people turn off). */

function fitOf(i){
  ANIMS=[];stageScenes.innerHTML='';
  SC=document.createElement('div');SC.className='sc';
  stageScenes.appendChild(SC);
  SCENES[i].build(SC);
  for(const a of ANIMS)a.fn(1);
  const box=SC.getBoundingClientRect();
  let top=null,bottom=null;
  for(const el of SC.children){
    const r=el.getBoundingClientRect();
    if(!r.width&&!r.height)continue; /* a spacer or an empty rule is not content */
    if(top===null||r.top<top)top=r.top;
    if(bottom===null||r.bottom>bottom)bottom=r.bottom;
  }
  /* Vertically: the union of the children, because `.sc` centres its column and
     an overflowing card spills off BOTH ends — scrollHeight only ever sees the
     bottom one. Horizontally: scrollWidth, because a block's own rect stays the
     width of its container however far the glyphs run past it. */
  const parts=[];
  const above=top===null?0:Math.round(box.top-top);
  const below=bottom===null?0:Math.round(bottom-box.bottom);
  const side=Math.round(SC.scrollWidth-SC.clientWidth);
  if(above>FIT_TOL)parts.push(above+'px above');
  if(below>FIT_TOL)parts.push(below+'px below');
  if(side>FIT_TOL)parts.push(side+'px past the measure');
  return parts.length?parts.join(' and '):null;
}

function checkFit(){
  const bad=[];
  for(let i=0;i<SCENES.length;i++){
    const over=fitOf(i);
    if(over)bad.push('beat '+i+' ('+(SCENES[i].kind||'scene')+') by '+over);
  }
  /* Put the stage back the way a seek expects to find it, whatever the verdict:
     CUR=-1 makes the next seek rebuild from scratch, so nothing measured here
     can survive into a frame. */
  CUR=-1;ANIMS=[];stageScenes.innerHTML='';SC=null;
  if(!bad.length)return;
  const msg='overflow — '+bad.join('; ')+'. The '+FMT.name+' safe area is '+
    (FMT.safe_bottom-FMT.safe_top)+'px tall on a '+FMT.w+'x'+FMT.h+' stage, and '+
    'nothing clips this: the words simply leave the card while every other check '+
    'stays green. Shorten the beat, split it, or give the format more room';
  /* Two audiences, the same way the CSP refusal has two: the operator scrubbing
     the slider reads #fit (inside #ui, which the render hides, so it can never
     reach a frame), and the renderer gets an uncaught error — the `pageerror`
     path render.mjs already prints and exits on. */
  const el=document.getElementById('fit');
  if(el){el.hidden=false;el.textContent=msg;}
  throw new Error(msg);
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
  console.log('TOTAL',TOTAL.toFixed(2),'s ·',SCENES.length,'scenes · pace',PACE,
    '·',FMT.name,FMT.w+'x'+FMT.h);
  /* Last, so everything above is already exposed: an operator whose episode
     overflows can still scrub the slider and SEE it. Throws if it does not fit,
     which is the whole point — a bad frame nobody looks at is the failure this
     exists to prevent. */
  checkFit();
  seek(0); /* checkFit cleared the stage; leave the page on a real frame */
}
