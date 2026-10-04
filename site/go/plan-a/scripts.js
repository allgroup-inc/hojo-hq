(() => {
    const yen = (n) => Math.round(n).toLocaleString('ja-JP');
    const num = (id) => Math.max(0, Number(document.getElementById(id).value) || 0);

    // 販売価格 =(原価 + 利益 + 送料)÷(1 - 手数料20%)
    const updateSim = () => {
        const cost = num('sim-cost');
        const profit = num('sim-profit');
        const ship = num('sim-ship');
        document.getElementById('sim-price').textContent = yen((cost + profit + ship) / 0.8);
        document.getElementById('sim-units').textContent = profit > 0 ? yen(Math.ceil(10000 / profit)) : '—';
    };
    ['sim-cost', 'sim-profit', 'sim-ship'].forEach((id) => {
        document.getElementById(id).addEventListener('input', updateSim);
    });
    updateSim();

    // 数字は最初から最終値を表示しておき、見えた時だけ0から数え上げる
    const counters = document.querySelectorAll('.count');
    if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const run = (el) => {
        const to = Number(el.dataset.to);
        const start = performance.now();
        const tick = (now) => {
            const t = Math.min(1, (now - start) / 1400);
            el.textContent = yen(to * (1 - Math.pow(1 - t, 3)));
            if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                run(entry.target);
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.6 });
    counters.forEach((el) => io.observe(el));
})();
