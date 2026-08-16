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

// ===== 笑顔の壁(S8): 実写9枚。PC=円(縁)を描く配置 / スマホ=上5・下4 =====
const RING=[
 [50,9,130,-2,'assets/film/egao/e4.jpg','おじいとおばあの笑顔'],
 [76.4,17.9,120,4,'assets/film/egao/e8.jpg','琉装のこどもたち'],
 [90.4,40.4,120,-3,'assets/film/egao/e2.jpg','おばあたちの笑顔'],
 [85.5,66,120,3,'assets/film/egao/e5.jpg','ともだちの笑顔'],
 [64,82.7,124,-3,'assets/film/egao/e7.jpg','おかあさんの笑顔'],
 [36,82.7,124,3,'assets/film/egao/e6.jpg','きょうだいの笑顔'],
 [14.5,66,120,-4,'assets/film/egao/e9.jpg','ふたりの門出'],
 [9.6,40.4,120,3,'assets/film/egao/e1.jpg','姉妹の笑顔'],
 [23.6,17.9,120,-4,'assets/film/egao/e3.jpg','こどもの笑顔']
];
const ROWS=[
 [10,12,120,-4,'assets/film/egao/e3.jpg','こどもの笑顔'],
 [30,10,120,3,'assets/film/egao/e1.jpg','姉妹の笑顔'],
 [50,13,120,-2,'assets/film/egao/e4.jpg','おじいとおばあの笑顔'],
 [70,10,120,4,'assets/film/egao/e8.jpg','琉装のこどもたち'],
 [90,13,120,-3,'assets/film/egao/e2.jpg','おばあたちの笑顔'],
 [12.5,88,132,3,'assets/film/egao/e9.jpg','ふたりの門出'],
 [37.5,85,132,-3,'assets/film/egao/e6.jpg','きょうだいの笑顔'],
 [62.5,88,132,2,'assets/film/egao/e7.jpg','おかあさんの笑顔'],
 [87.5,85,132,-4,'assets/film/egao/e5.jpg','ともだちの笑顔']
];
const PH = window.innerWidth>=900 ? RING : ROWS;
const fb=document.getElementById('faces');
fb.innerHTML=PH.map((f,i)=>{
  const [x,y,w,r,src,cap]=f, delay=(i%9)*0.15;
  return `<div class="photo" style="left:${x}%;top:${y}%;width:${w}px;--w:${w}px;--r:${r}deg;transition-delay:${delay}s"><div class="bob" style="animation-delay:${(i%6)*.7}s">
    <div class="ph"><img src="${src}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></div>
    <div class="cap">${cap}</div></div></div>`;
}).join('');

// ===== シーン出現 =====
const fgSeen = new Set();
const io = new IntersectionObserver(es => {
  es.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('in');
      const id = e.target.id;
      if (id && !fgSeen.has(id) && window.fgTrack) { fgSeen.add(id); fgTrack('film_scene_'+id); }
    }
  });
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


// 計測: フィルム内の導線クリック
document.querySelectorAll('.s8 .cta').forEach(a=>a.addEventListener('click',()=>{ if(window.fgTrack) fgTrack('film_cta_shindan'); }));
document.querySelectorAll('.s8 a[href*="area"]').forEach(a=>a.addEventListener('click',()=>{ if(window.fgTrack) fgTrack('film_link_area'); }));
document.querySelectorAll('.tinyhead .skip').forEach(a=>a.addEventListener('click',()=>{ if(window.fgTrack) fgTrack('film_skip'); }));

})();
