/**
 * store-menu.js — درج القائمة الموحّد + محمّل Firebase الكسول
 * -------------------------------------------------------------
 * 1) يحقن نفس درج القائمة في كل صفحات الموقع (الرئيسية، السلة، القانونية،
 *    أسعار اليوم، صفحات المنتج) ويعبّئ قسم «المنتجات» من قاعدة البيانات —
 *    بنفس الاسم والوصف والسعر والصورة المعروضة في الرئيسية.
 * 2) يوفّر window.StoreLive.ensure() لتحميل Firebase + طبقة المنتجات **عند
 *    الحاجة فقط** (فتح القائمة أو طلب صريح)، فتبقى الصفحات الثابتة خفيفة.
 *
 * الواجهة: window.StoreNav.open()/close()/toggle()، window.StoreLive.ensure().
 */
(function () {
  const PAGES = [
    { href: '/', label: '🏠 الرئيسية' },
    { href: '/prices', label: '💰 أسعار اليوم' },
    { href: '/cartepage.html', label: '🛒 سلة الطلبات' },
    { href: '/terms.html', label: '📜 الشروط والأحكام' },
    { href: '/privacy.html', label: '🔒 سياسة الخصوصية' },
    { href: '/returns.html', label: '↩️ سياسة الاسترجاع' }
  ];

  const AR_TRANSLIT = { 'ا':'a','أ':'a','إ':'a','آ':'a','ٱ':'a','ب':'b','ت':'t','ث':'th','ج':'j','ح':'h','خ':'kh','د':'d','ذ':'dh','ر':'r','ز':'z','س':'s','ش':'sh','ص':'s','ض':'d','ط':'t','ظ':'dh','ع':'a','غ':'gh','ف':'f','ق':'q','ك':'k','ل':'l','م':'m','ن':'n','ه':'h','و':'w','ي':'y','ى':'a','ة':'h','ء':'','ئ':'y','ؤ':'w','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9' };

  function slugify(name) {
    let t = '';
    for (const ch of (name || '')) t += (AR_TRANSLIT[ch] !== undefined ? AR_TRANSLIT[ch] : ch);
    t = t.replace(/[^A-Za-z0-9\s-]/g, '').trim().toLowerCase().replace(/[\s_]+/g, '-');
    return t || 'product';
  }

  function productUrl(p) {
    if (!p || !p._id) return null;
    return '/product/' + p._id + '/' + slugify(p.name);
  }

  function absImg(img) {
    if (!img) return '/assets/images/nfc2.png';
    if (/^(https?:|data:|\/)/.test(img)) return img;
    return '/' + img.replace(/^\.?\//, '');
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function validOnly(list) {
    return (Array.isArray(list) ? list : []).filter(p => p && p.name && p.img && p.price);
  }

  // ── محمّل Firebase الكسول ─────────────────────────────────────────
  const CDN = 'https://www.gstatic.com/firebasejs/10.12.2/';
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('تعذّر تحميل ' + src));
      document.head.appendChild(s);
    });
  }

  let livePromise = null;
  function ensureLive() {
    if (livePromise) return livePromise;
    if (window.db && typeof window.storeGetProducts === 'function') {
      livePromise = Promise.resolve();
      return livePromise;
    }
    livePromise = (async function () {
      // firebase-env.js موجود كوسم في الصفحة (يُحقن inline على serve.py، ويُولَّد
      // كملف صالح على Netlify) — لا نحمّله خارجياً لأنه مُغلّف بوسم <script>.
      if (typeof firebase === 'undefined') await loadScript(CDN + 'firebase-app-compat.js');
      if (typeof firebase.firestore !== 'function') await loadScript(CDN + 'firebase-firestore-compat.js');
      if (!window.db) await loadScript('/assets/js/firebase-init.js?v=1');
      if (typeof window.storeGetProducts !== 'function') await loadScript('/assets/js/products-store.js?v=7');
    })().catch(function (e) { console.warn('store-menu: تعذّر تحميل قاعدة البيانات:', e && e.message); });
    return livePromise;
  }

  // ── حقن CSS الدرج (مرة واحدة) ──
  const CSS = `
  .MenuOverlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 998;
    opacity: 0; pointer-events: none; transition: opacity .25s; }
  .MenuOverlay.open { opacity: 1; pointer-events: auto; }
  .MenuDrawer { position: fixed; top: 0; right: -320px; width: 300px; max-width: 85vw;
    height: 100%; background: #fff; z-index: 999; overflow-y: auto; transition: right .3s ease;
    box-shadow: -2px 0 12px rgba(0,0,0,.12); padding: 18px 0 30px; }
  .MenuDrawer.open { right: 0; }
  .MenuDrawer h3 { font-size: 15px; color: #004d7a; padding: 10px 20px 6px;
    border-bottom: 1px solid #eee; margin: 8px 0 4px; }
  .MenuDrawer .menu-close { position: absolute; top: 12px; left: 14px; border: none;
    background: #f1f3f5; border-radius: 8px; width: 32px; height: 32px; font-size: 16px;
    cursor: pointer; color: #333; }
  .MenuDrawer a.menu-link { display: flex; align-items: center; gap: 10px; padding: 11px 20px;
    font-size: 14.5px; font-weight: 600; color: #222; text-decoration: none; }
  .MenuDrawer a.menu-link:hover { background: #f4f8fb; color: #004d7a; }
  .MenuDrawer a.menu-link img { width: 34px; height: 34px; border-radius: 8px;
    object-fit: cover; background: #f1f3f5; flex-shrink: 0; }
  .MenuDrawer a.menu-link .m-price { margin-right: auto; color: #004d7a; font-size: 13px; font-weight: 800; }
  .MenuDrawer .m-empty { padding: 12px 20px; color: #888; font-size: 13.5px; }
  `;

  function injectStyle() {
    if (document.getElementById('store-menu-style')) return;
    const s = document.createElement('style');
    s.id = 'store-menu-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function injectMarkup() {
    if (document.getElementById('menuDrawer')) return;
    const wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="MenuOverlay" id="menuOverlay"></div>' +
      '<nav class="MenuDrawer" id="menuDrawer" aria-label="قائمة الموقع">' +
      '<button class="menu-close" type="button" aria-label="إغلاق">✕</button>' +
      '<h3>صفحات الموقع</h3>' +
      PAGES.map(p => '<a class="menu-link" href="' + p.href + '">' + p.label + '</a>').join('') +
      '<h3>المنتجات</h3><div id="menuProducts"></div>' +
      '</nav>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  function open(show) {
    const drawer = document.getElementById('menuDrawer');
    const overlay = document.getElementById('menuOverlay');
    if (!drawer) return;
    const state = (typeof show === 'boolean') ? show : !drawer.classList.contains('open');
    drawer.classList.toggle('open', state);
    if (overlay) overlay.classList.toggle('open', state);
    document.body.style.overflow = state ? 'hidden' : '';
    if (state) refreshLive();
  }

  function toggle(show) { open(show); }

  function renderMenuProducts(list) {
    const box = document.getElementById('menuProducts');
    if (!box) return;
    const items = validOnly(list);
    if (!items.length) {
      box.innerHTML = '<div class="m-empty">لا توجد منتجات حالياً</div>';
      return;
    }
    box.innerHTML = items.map(function (p) {
      const url = productUrl(p);
      const inner = '<img src="' + absImg(p.img) + '" alt="" loading="lazy">' +
                    '<span>' + esc(p.name) + '</span>' +
                    '<span class="m-price">' + esc(p.price) + ' د.ك</span>';
      return url ? '<a class="menu-link" href="' + url + '">' + inner + '</a>'
                 : '<span class="menu-link">' + inner + '</span>';
    }).join('');
  }

  async function fetchProducts() {
    if (typeof window.storeGetProducts === 'function') {
      try { return await window.storeGetProducts(); } catch (e) {}
    }
    if (window.db && typeof window.db.collection === 'function') {
      for (const useOrder of [true, false]) {
        try {
          const col = window.db.collection('products');
          const snap = await (useOrder ? col.orderBy('order', 'asc') : col).get();
          return snap.docs.map(d => Object.assign({ _id: d.id }, d.data()));
        } catch (e) {}
      }
    }
    return [];
  }

  let __watched = false;
  function watchProducts() {
    if (__watched) return;
    __watched = true;
    if (typeof window.storeWatchProducts === 'function') {
      window.storeWatchProducts(renderMenuProducts);
      return;
    }
    if (window.db && typeof window.db.collection === 'function') {
      const col = window.db.collection('products');
      const attach = (useOrder) => (useOrder ? col.orderBy('order', 'asc') : col)
        .onSnapshot(snap => renderMenuProducts(snap.docs.map(d => Object.assign({ _id: d.id }, d.data()))),
          err => { if (useOrder) attach(false); });
      try { attach(true); } catch (e) {}
    }
  }

  // تحميل حيّ (عند فتح القائمة أو عند توفّر Firebase مسبقاً)
  let liveDone = false;
  function refreshLive() {
    if (liveDone) return;
    liveDone = true;
    ensureLive().then(function () {
      fetchProducts().then(renderMenuProducts);
      watchProducts();
    });
  }

  function bindEvents() {
    const drawer = document.getElementById('menuDrawer');
    const overlay = document.getElementById('menuOverlay');
    const closeBtn = drawer && drawer.querySelector('.menu-close');
    if (closeBtn) closeBtn.addEventListener('click', () => open(false));
    if (overlay) overlay.addEventListener('click', () => open(false));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') open(false); });
    // ربط أي زر يحمل id="menuBtn" أو data-store-menu تلقائياً (درج موحّد).
    document.querySelectorAll('#menuBtn, [data-store-menu]').forEach(el => {
      if (el.dataset.storeMenuBound) return;
      el.dataset.storeMenuBound = '1';
      el.addEventListener('click', () => toggle());
    });
  }

  function init() {
    injectStyle();
    injectMarkup();
    bindEvents();
    if (Array.isArray(window.LOCAL_PRODUCTS) && window.LOCAL_PRODUCTS.length) {
      renderMenuProducts(window.LOCAL_PRODUCTS); // عرض فوري قبل الشبكة
    }
    // إن كانت قاعدة البيانات محمّلة مسبقاً (الرئيسية/السلة) فحدّث فوراً
    if (window.db || typeof window.storeGetProducts === 'function') refreshLive();
  }

  window.StoreNav = { open: open, close: () => open(false), toggle: toggle };
  window.StoreLive = { ensure: ensureLive };
  window.toggleMenu = toggle; // توافق مع onclick القديم

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
