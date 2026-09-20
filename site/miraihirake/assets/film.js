/* みらいひらけ堂 世界観フィルム(堂シリーズ: fukugiiro/assets/film.js と同じ文法。計測なし) */
(function(){

// 星空(S1)
var starbox = document.getElementById("mstars");
if (starbox){
  var SEED = [7,23,41,3,59,17,83,29,67,11,47,71,5,37,89,53,13,79,31,61,19,43,73,97,2,63,27,91,49,33,81,9,57,21,77,39,87,15,69,51];
  var html = "";
  for (var i=0;i<SEED.length;i++){
    var a=SEED[i], b=SEED[(i+7)%SEED.length];
    var x=(a*97+b*13)%100, y=((b*53+a*29)%50);
    var s=1.4+(a%3)*0.8, d=(a%17)/5, dur=2.6+(b%14)/6;
    html += '<div class="hoshi" style="left:'+x+'%;top:'+y+'%;width:'+s+'px;height:'+s+'px;animation-delay:'+d+'s;animation-duration:'+dur+'s"></div>';
  }
  starbox.innerHTML = html;
}

// 集落の灯り(S1)
var vb = document.getElementById("mvlights");
if (vb){
  var VP=[[8,81],[13,79],[18,82],[24,80],[31,78],[37,81],[44,79],[52,80],[58,78],[64,81],[71,79],[78,82],[85,80],[91,81],[27,83],[48,83],[68,83],[88,84]];
  vb.innerHTML = VP.map(function(v,i){ return '<div class="vlight" style="left:'+v[0]+'%;top:'+v[1]+'%;animation-delay:'+(i%9)*0.5+'s"></div>'; }).join("");
}

// シーン出現
var io = new IntersectionObserver(function(es){
  es.forEach(function(e){ if (e.isIntersecting) e.target.classList.add("in"); });
}, {threshold: .35});
document.querySelectorAll(".mfilm .scene").forEach(function(s){ io.observe(s); });

// ビジョン: 一文字ずつ
var v = document.getElementById("mvision");
if (v){
  v.innerHTML = Array.from(v.textContent).map(function(c,i){
    return '<span style="transition-delay:'+(0.15+i*0.09)+'s">'+c+"</span>";
  }).join("");
}

// ヘッダー反転(明るいシーン)
var th = document.getElementById("mhead");
if (th){
  var light = new IntersectionObserver(function(es){
    es.forEach(function(e){ if (e.isIntersecting) th.classList.toggle("on-light", ["ms4","ms5"].indexOf(e.target.id) >= 0); });
  }, {threshold: .55});
  ["ms1","ms2","ms3","ms4","ms5"].forEach(function(id){ var el=document.getElementById(id); if(el) light.observe(el); });
}

})();
