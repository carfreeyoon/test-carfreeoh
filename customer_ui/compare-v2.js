(() => {
  const opening = document.getElementById('comparisonOpening');
  if (opening) {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.body.classList.add('opening-active');
    if (reduced) {
      opening.remove();
      document.body.classList.remove('opening-active');
    } else {
      window.setTimeout(() => {
        document.getElementById('openingMessage').textContent = '두 방식의 비용을 비교하고 있어요';
        document.getElementById('openingDetail').textContent = '만기 때 반납하거나 인수하는 경우까지';
      }, 760);
      window.setTimeout(() => {
        opening.classList.add('opening-complete');
        document.body.classList.remove('opening-active');
        window.setTimeout(() => opening.remove(), 420);
      }, 1900);
    }
  }
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.documentElement.classList.add('motion-ready');
  const sectionObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    });
  }, { threshold: .05, rootMargin: '0px 0px -25px 0px' });
  document.querySelectorAll('.section').forEach(el => sectionObserver.observe(el));
  const moneyObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const card = entry.target;
      card.classList.add('is-visible');
      card.querySelectorAll('.amounts b,.difference strong').forEach(el => {
        const value = Number(el.textContent.replace(/[^0-9]/g, ''));
        if (!value) return;
        const from = performance.now(), duration = 760;
        function frame(now) {
          const t = Math.min(1, (now - from) / duration);
          const progress = 1 - Math.pow(1 - t, 3);
          el.textContent = Math.round(value * progress).toLocaleString('ko-KR') + '원';
          if (t < 1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
      observer.unobserve(card);
    });
  }, { threshold: .35 });
  document.querySelectorAll('.reveal-result').forEach(el => moneyObserver.observe(el));
})();
