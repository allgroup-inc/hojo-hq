/* Plan A LP — 計測とふるまい(個人情報は一切送らない)
   GA4: サイト本体(site/index.html)と同じ測定ID。イベントは plan_a_view と plan_a_cta_click のみ。
   /go/plan-a-line/ 側で plan_a_line_redirect(channel=plan-a-line)が別に記録される(導線クリックと転送を別名で数える)。 */
(function () {
  var GA_ID = 'G-TW6M6WFB9T';
  var variant = document.body.getAttribute('data-variant') || 'a';
  var bot = navigator.webdriver === true;

  function loadGA() {
    if (bot) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', GA_ID, { send_page_view: true, anonymize_ip: true });
    window.gtag('event', 'plan_a_view', { variant: variant });
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
  }

  function onCta(e) {
    var a = e.currentTarget;
    var pos = a.getAttribute('data-pos') || 'unknown';
    if (window.gtag && !bot) {
      window.gtag('event', 'plan_a_cta_click', { variant: variant, position: pos, transport_type: 'beacon' });
    }
    /* 転送は止めない(計測より導線優先)。/go/plan-a-line/ 側で転送イベントが記録される */
  }

  var ctas = document.querySelectorAll('.js-cta');
  for (var i = 0; i < ctas.length; i++) ctas[i].addEventListener('click', onCta);

  /* 未確定箇所の見える化(開発中のみ)。公開前に 0 件にする */
  var todos = document.querySelectorAll('.todo');
  if (todos.length && /github\.io|localhost|127\.0\.0\.1/.test(location.hostname) === false) {
    console.warn('[Plan A] 未確定箇所(.todo)が ' + todos.length + ' 件あります。公開前に 0 件にしてください');
  }

  loadGA();
})();
