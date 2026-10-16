// LPの「文字のはみ出し」検査。背景や枠のある箱ごとに、中の文字が箱の外に出ていないかを調べる。
// 使い方: 検査したいHTMLの </head> の直前に <script src="(このファイル)"></script> を入れ、
//   headless_shell --window-size=1280,900 --virtual-time-budget=5000 --dump-dom file://.../page.html
// を実行して <title>RESULT:[...]</title> を読む。[] なら合格。PC(1280)とスマホ(390・360)の両方で流す。
// 注意: 本番と同じWebフォント(しっぽり明朝・BIZ UDPゴシック等)を ~/.fonts に入れてから検査する。
//   フォントが違うと文字の幅が変わり、はみ出しを見逃す(2026-10-05 GLOW世界へ推進LPのロゴで実際に見逃した)。
window.addEventListener('load', () => setTimeout(() => {
  const bad = [];
  const boxes = [...document.querySelectorAll('body *')].filter(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const hasBg = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.backgroundImage !== 'none';
    const hasBorder = parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.outlineWidth) > 0;
    return hasBg || hasBorder;
  });
  boxes.forEach(box => {
    const b = box.getBoundingClientRect();
    if (b.width === 0) return;
    const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const pe = n.parentElement;
      if (getComputedStyle(pe).display === 'none' || pe.closest('[aria-hidden]')) continue;
      // 箱の中に別の箱がある場合は内側の箱で判定
      let owner = pe; while (owner && owner !== box && !boxes.includes(owner)) owner = owner.parentElement;
      if (owner !== box) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const rr of r.getClientRects()) {
        if (rr.width === 0) continue;
        if (rr.left < b.left - 1 || rr.right > b.right + 1 || rr.top < b.top - 1 || rr.bottom > b.bottom + 1) {
          bad.push((box.className || box.tagName) + ' | ' + n.textContent.trim().slice(0, 25) + ' | text ' + Math.round(rr.left) + '-' + Math.round(rr.right) + ' box ' + Math.round(b.left) + '-' + Math.round(b.right));
          break;
        }
      }
    }
  });
  if (document.documentElement.scrollWidth > window.innerWidth) bad.push('PAGE-HSCROLL ' + document.documentElement.scrollWidth);
  document.title = 'RESULT:' + JSON.stringify([...new Set(bad)]);
}, 1500));
