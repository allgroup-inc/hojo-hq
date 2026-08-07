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

// ===== 笑顔の写真の壁(S8) =====
const CAM='<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" style="z-index:2;opacity:.85"><rect x="2.5" y="6.5" width="19" height="13" rx="2.5"/><circle cx="12" cy="13" r="4"/><path d="M8.5 6.5 L10 4 h4 l1.5 2.5"/></svg>';
const TONES={
 child:['#E8B693','#D89B72'], mama:['#DFA98A','#C98E6C'], papa:['#C9987B','#A87656'],
 oba:['#E3C2A4','#C7A183'], oji:['#D2B091','#B08D6B'], family:['#E6AC85','#BF8560']
};
const LABEL={child:'こどもの笑顔',mama:'おかあさんの笑顔',papa:'おとうさんの笑顔',oba:'おばあの笑顔',oji:'おじいの笑顔',family:'かぞくの笑顔'};
const PH=[
 [2,3,108,-5,'child'],[22,1,96,3,'oba'],[41,4,120,-2,'family'],[63,1,98,4,'oji'],[81,4,104,-4,'mama'],
 [0,24,98,4,'papa'],[18,21,112,-3,'child'],[40,26,96,2,'oba'],[60,22,104,-5,'child'],[80,25,110,3,'family'],
 [3,50,104,-3,'oji'],[24,54,96,5,'mama'],[46,51,100,-2,'child'],[68,54,108,3,'oba'],[87,50,96,-4,'child'],
 [1,74,112,3,'family'],[22,78,98,-4,'oji'],[43,75,104,2,'mama'],[65,78,110,-3,'child'],[85,74,100,4,'papa']
];
const fb=document.getElementById('faces');
fb.innerHTML=PH.map((f,i)=>{
  const [x,y,w,r,t]=f, tone=TONES[t], delay=(i%20)*0.12;
  return `<div class="photo" style="left:${x}%;top:${y}%;width:${w}px;--w:${w}px;--r:${r}deg;transition-delay:${delay}s"><div class="bob" style="animation-delay:${(i%6)*.7}s">
    <div class="ph" style="background:linear-gradient(160deg,${tone[0]},${tone[1]})">${CAM}<span class="tag2">実写がはいります</span></div>
    <div class="cap">${LABEL[t]}</div></div></div>`;
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

})();
