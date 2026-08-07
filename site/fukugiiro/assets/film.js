(function(){

// ===== 星空(S1) =====
const starbox = document.getElementById('stars');
const SEED = [7,23,41,3,59,17,83,29,67,11,47,71,5,37,89,53,13,79,31,61,19,43,73,97,2,63,27,91,49,33,81,9,57,21,77,39,87,15,69,51];
let html = '';
for (let i=0;i<SEED.length;i++){
  const a=SEED[i], b=SEED[(i+7)%SEED.length];
  const x=(a*97+b*13)%100, y=((b*53+a*29)%50);
  const s=1.4+(a%3)*0.8, d=(a%17)/5, dur=2.6+(b%14)/6;
  html += `<div class="hoshi" style="left:${x}%;top:${y}%;width:${s}px;height:${s}px;animation-delay:${d}s;animation-duration:${dur}s"></div>`;
}
starbox.innerHTML = html;

// ===== 集落の灯り(S1) =====
const vb = document.getElementById('vlights');
const VP=[[8,81],[13,79],[18,82],[24,80],[31,78],[37,81],[44,79],[52,80],[58,78],[64,81],[71,79],[78,82],[85,80],[91,81],[27,83],[48,83],[68,83],[88,84],[15,84],[55,84]];
vb.innerHTML = VP.map((v,i)=>`<div class="vlight" style="left:${v[0]}%;top:${v[1]}%;animation-delay:${(i%9)*.5}s"></div>`).join('');

// ===== 笑顔の壁(S8): 自作イラストポートレート(実写が届き次第差し替え) =====
function PORTRAIT(t,i){
  const SKIN=['#F8D8BC','#F3CBA8','#EFC29B'][i%3];
  const BG=['#FCE8D9','#E8F1EC','#FDF2D9','#F3E3EF','#E4EEF5'][i%5];
  const HAIR={child:'#54402F',mama:'#7A523C',papa:'#403022',oba:'#D9D2C6',oji:'#CFC8BB',family:'#6B4A38'}[t];
  const SHIRT={child:'#6FAEA4',mama:'#D2694A',papa:'#3E5B57',oba:'#B9737F',oji:'#8A7A5C',family:'#F2C14E'}[t];
  const kari = (t==='papa'||t==='oji') ? '<g fill="#fff" opacity=".4"><circle cx="26" cy="78" r="1.8"/><circle cx="40" cy="84" r="1.8"/><circle cx="54" cy="78" r="1.8"/><circle cx="33" cy="88" r="1.8"/><circle cx="48" cy="88" r="1.8"/></g>':'';
  let hair='';
  if(t==='child') hair=`<path d="M40 17 C29 17 21 24 19 33 C26 26 54 26 61 33 C59 24 51 17 40 17 Z" fill="${HAIR}"/><path d="M40 18 C38 12 43 9 46 12 C44 14 42 16 42 18 Z" fill="${HAIR}"/>`;
  else if(t==='mama') hair=`<path d="M40 15 C26 15 17 25 17 38 C17 44 18 48 21 51 C18 40 24 24 40 23 C56 24 62 40 59 51 C62 48 63 44 63 38 C63 25 54 15 40 15 Z" fill="${HAIR}"/>`;
  else if(t==='papa') hair=`<path d="M40 16 C29 16 21 23 19 32 C27 25 53 25 61 32 C59 23 51 16 40 16 Z" fill="${HAIR}"/>`;
  else if(t==='oba') hair=`<path d="M40 16 C29 16 21 23 19 32 C27 25 53 25 61 32 C59 23 51 16 40 16 Z" fill="${HAIR}"/><circle cx="40" cy="13" r="7" fill="${HAIR}"/><g transform="translate(57 24) scale(.55)" fill="#D2694A"><ellipse cx="0" cy="-7" rx="4.5" ry="7"/><ellipse cx="6.5" cy="-2" rx="4.5" ry="7" transform="rotate(72)"/><ellipse cx="4" cy="6" rx="4.5" ry="7" transform="rotate(144)"/><ellipse cx="-4" cy="6" rx="4.5" ry="7" transform="rotate(216)"/><ellipse cx="-6.5" cy="-2" rx="4.5" ry="7" transform="rotate(288)"/><circle r="2.4" fill="#F2C14E"/></g>`;
  else if(t==='oji') hair=`<path d="M19 34 C18 27 21 21 26 18 C23 24 22 30 23 35 Z" fill="${HAIR}"/><path d="M61 34 C62 27 59 21 54 18 C57 24 58 30 57 35 Z" fill="${HAIR}"/>`;
  else hair=`<path d="M40 16 C29 16 21 23 19 32 C27 25 53 25 61 32 C59 23 51 16 40 16 Z" fill="${HAIR}"/>`;
  const must = t==='oji' ? '<path d="M31 47.5 q9 5 18 0" stroke="#CFC8BB" stroke-width="3" fill="none" stroke-linecap="round"/>' : '';
  const mouthY = t==='oji' ? 52 : 47;
  return `<svg viewBox="0 0 80 92" style="display:block;width:100%;height:100%">
  <rect width="80" height="92" fill="${BG}"/>
  <path d="M14 92 C14 74 24 66 40 66 C56 66 66 74 66 92 Z" fill="${SHIRT}"/>${kari}
  <rect x="34" y="54" width="12" height="14" rx="5" fill="${SKIN}"/>
  <circle cx="20" cy="40" r="4" fill="${SKIN}"/><circle cx="60" cy="40" r="4" fill="${SKIN}"/>
  <circle cx="40" cy="38" r="20" fill="${SKIN}"/>
  ${hair}
  <path d="M30 39 q3.5 4 7 0 M43 39 q3.5 4 7 0" stroke="#5C4634" stroke-width="2.4" fill="none" stroke-linecap="round"/>
  <circle cx="25" cy="45.5" r="3.4" fill="#F3B5A0" opacity=".55"/><circle cx="55" cy="45.5" r="3.4" fill="#F3B5A0" opacity=".55"/>
  ${must}<path d="M33 ${mouthY} q7 6 14 0" stroke="#B9502F" stroke-width="2.6" fill="none" stroke-linecap="round"/>
</svg>`;
}
const LABEL={child:'こどもの笑顔',mama:'おかあさんの笑顔',papa:'おとうさんの笑顔',oba:'おばあの笑顔',oji:'おじいの笑顔',family:'かぞくの笑顔'};
const PH=[
 [2,3,108,-5,'child'],[22,1,96,3,'oba'],[41,4,120,-2,'family'],[63,1,98,4,'oji'],[81,4,104,-4,'mama'],
 [0,24,98,4,'papa'],[18,21,112,-3,'child'],[40,26,96,2,'oba'],[60,22,104,-5,'child'],[80,25,110,3,'family'],
 [3,50,104,-3,'oji'],[24,54,96,5,'mama'],[46,51,100,-2,'child'],[68,54,108,3,'oba'],[87,50,96,-4,'child'],
 [1,74,112,3,'family'],[22,78,98,-4,'oji'],[43,75,104,2,'mama'],[65,78,110,-3,'child'],[85,74,100,4,'papa']
];
const REALS={2:'assets/film/egao/e1.jpg',4:'assets/film/egao/e2.jpg',0:'assets/film/egao/e3.jpg',3:'assets/film/egao/e4.jpg'};
const CAPS={2:'姉妹の笑顔',4:'おばあたちの笑顔',3:'おじいとおばあの笑顔'};
const fb=document.getElementById('faces');
fb.innerHTML=PH.map((f,i)=>{
  const [x,y,w,r,t]=f, delay=(i%20)*0.12;
  return `<div class="photo" style="left:${x}%;top:${y}%;width:${w}px;--w:${w}px;--r:${r}deg;transition-delay:${delay}s"><div class="bob" style="animation-delay:${(i%6)*.7}s">
    <div class="ph">${REALS[i]?`<img src="${REALS[i]}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">`:PORTRAIT(t,i)}</div>
    <div class="cap">${CAPS[i]||LABEL[t]}</div></div></div>`;
}).join('');

// ===== シーン出現 =====
const io = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) e.target.classList.add('in'); });
}, {threshold: .35});
document.querySelectorAll('.scene').forEach(s => io.observe(s));

// ビジョン: 一文字ずつ
const v = document.getElementById('visiontext');
v.innerHTML = [...v.textContent].map((c,i)=>`<span style="transition-delay:${.15+i*.09}s">${c}</span>`).join('');

// ヘッダー反転(明るいシーン)
const th = document.getElementById('thead');
const light = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) th.classList.toggle('on-light', ['s6','s7','s8'].includes(e.target.id)); });
}, {threshold: .55});
['s1','s2','s3','s4','s6','s7','s8'].forEach(id => { const el=document.getElementById(id); if(el) light.observe(el); });


// 実用レイヤーもフィルムと同じ呼吸で(内容不変・クラス付与のみ)
const pio = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); pio.unobserve(e.target); } });
}, {threshold: .18});
document.querySelectorAll('main > section:not(.scene) .wrap').forEach(w => {
  [...w.children].forEach((el,i) => {
    el.classList.add('prise');
    el.style.transitionDelay = Math.min(i*0.12, 0.6)+'s';
    pio.observe(el);
  });
});

})();
