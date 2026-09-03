/* もらいわすれ堂 山梨版 冒頭フィルム(沖縄版 assets/film.js の山梨向け実装)
   - 写真(assets/film/*.jpg)が未配置でも影絵+光の演出で成立し、置けば実写が主役になる
   - 要素が無ければ各ブロックは静かにスキップ(null安全)
   - 計測イベントは ymn_ 接頭辞で沖縄版と分離 */
(function(){

// ===== 星空(S1: 甲府盆地の夜) =====
var starbox = document.getElementById('stars');
if (starbox) {
  var SEED = [7,23,41,3,59,17,83,29,67,11,47,71,5,37,89,53,13,79,31,61,19,43,73,97,2,63,27,91,49,33,81,9,57,21,77,39,87,15,69,51];
  var html = '';
  for (var i=0;i<SEED.length;i++){
    var a=SEED[i], b=SEED[(i+7)%SEED.length];
    var x=(a*97+b*13)%100, y=((b*53+a*29)%50);
    var s=1.4+(a%3)*0.8, d=(a%17)/5, dur=2.6+(b%14)/6;
    html += '<div class="hoshi" style="left:'+x+'%;top:'+y+'%;width:'+s+'px;height:'+s+'px;animation-delay:'+d+'s;animation-duration:'+dur+'s"></div>';
  }
  starbox.innerHTML = html;
}

// ===== 盆地の灯り(S1) =====
var vb = document.getElementById('vlights');
if (vb) {
  var VP=[[8,81],[13,79],[18,82],[24,80],[31,78],[37,81],[44,79],[52,80],[58,78],[64,81],[71,79],[78,82],[85,80],[91,81],[27,83],[48,83],[68,83],[88,84],[15,84],[55,84]];
  vb.innerHTML = VP.map(function(v,i){return '<div class="vlight" style="left:'+v[0]+'%;top:'+v[1]+'%;animation-delay:'+((i%9)*.5)+'s"></div>';}).join('');
}

// ===== 写真: 未配置なら静かに消して影絵を主役に(置けばそのまま実写が出る) =====
document.querySelectorAll('.film .photoback img').forEach(function(img){
  function mark(){
    img.style.display='none';
    var pb = img.closest('.photoback');
    if (pb) pb.classList.add('nophoto');
  }
  img.addEventListener('error', mark);
  // deferで動くため、すでに読み込み失敗が確定している画像もここで拾う
  if (img.complete && img.naturalWidth === 0) mark();
});

// ===== シーン出現 =====
var fgSeen = {};
var io = new IntersectionObserver(function(es){
  es.forEach(function(e){
    if (e.isIntersecting) {
      e.target.classList.add('in');
      var id = e.target.id;
      if (id && !fgSeen[id] && window.fgTrack) { fgSeen[id]=1; fgTrack('ymn_film_scene_'+id); }
    }
  });
}, {threshold: .35});
document.querySelectorAll('.scene').forEach(function(s){ io.observe(s); });

// ビジョン: 一文字ずつ
var v = document.getElementById('visiontext');
if (v) v.innerHTML = Array.prototype.map.call(v.textContent, function(c,i){
  return '<span style="transition-delay:'+(.15+i*.09)+'s">'+c+'</span>';
}).join('');

// ヘッダー反転(明るいシーン)
var th = document.getElementById('thead');
if (th) {
  var light = new IntersectionObserver(function(es){
    es.forEach(function(e){ if (e.isIntersecting) th.classList.toggle('on-light', ['s6','s7','s8'].indexOf(e.target.id)>=0); });
  }, {threshold: .55});
  ['s1','s2','s3b','s4','s6','s7','s8'].forEach(function(id){ var el=document.getElementById(id); if(el) light.observe(el); });
}

// 実用レイヤーもフィルムと同じ呼吸で(内容不変・クラス付与のみ)
var pio = new IntersectionObserver(function(es){
  es.forEach(function(e){ if (e.isIntersecting) { e.target.classList.add('in'); pio.unobserve(e.target); } });
}, {threshold: .18});
document.querySelectorAll('main > section:not(.scene) .wrap').forEach(function(w){
  Array.prototype.forEach.call(w.children, function(el,i){
    el.classList.add('prise');
    el.style.transitionDelay = Math.min(i*0.12, 0.6)+'s';
    pio.observe(el);
  });
});

// 計測: フィルム内の導線クリック
document.querySelectorAll('.s8 .cta').forEach(function(a){ a.addEventListener('click', function(){ if(window.fgTrack) fgTrack('ymn_film_cta_shindan'); }); });
document.querySelectorAll('.s8 a[href*="area"]').forEach(function(a){ a.addEventListener('click', function(){ if(window.fgTrack) fgTrack('ymn_film_link_area'); }); });
document.querySelectorAll('.tinyhead .skip').forEach(function(a){ a.addEventListener('click', function(){ if(window.fgTrack) fgTrack('ymn_film_skip'); }); });

})();
