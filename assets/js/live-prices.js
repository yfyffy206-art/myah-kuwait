/**
 * live-prices.js — تحديث صفحة «أسعار اليوم» من قاعدة البيانات مباشرة
 * -------------------------------------------------------------------
 * ملف prices.html ثابت (يُولَّد عند البناء لأغراض SEO)، لكن الأسعار قد تتغيّر من
 * لوحة التحكم بعد التوليد. هذا السكربت يعيد بناء شبكة المنتجات من Firestore
 * بنفس الاسم والوصف والسعر والصورة المعروضة في الرئيسية، فتتطابق كل الصفحات.
 *
 * الاستخدام: ضع في prices.html عنصراً بالمعرّف prices-grid، ووسم بيانات
 * <script id="prices-i18n" type="application/json">{"free":"...","unavailable":"..."}</script>
 */
(function () {
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
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function i18n() {
    const el = document.getElementById('prices-i18n');
    if (!el) return { free: 'شامل التوصيل المجاني ✅', unavailable: 'لا توجد منتجات حالياً' };
    try { return JSON.parse(el.textContent); } catch (e) { return {}; }
  }

  function validOnly(list) {
    return (Array.isArray(list) ? list : []).filter(p => p && p.name && p.img && p.price);
  }

  let __sig = null;
  function signature(list) {
    return list.map(p => [p._id || '', p.name || '', p.price || '', p.desc || '', p.img || ''].join('|')).join('\n');
  }

  function render(list) {
    const grid = document.getElementById('prices-grid');
    if (!grid) return;
    const items = validOnly(list);
    if (!items.length) return; // لا تمسح العرض الحالي (المولّد) بمصدر فارغ
    const sig = signature(items);
    if (sig === __sig) return; // نفس القائمة → لا إعادة رسم (بلا وميض)
    __sig = sig;
    const t = i18n();
    grid.innerHTML = items.map(function (p) {
      const url = productUrl(p);
      const img = '<img src="' + absImg(p.img) + '" alt="' + esc('سعر ' + p.name + ' اليوم في الكويت') + '" loading="lazy">';
      const imgHtml = url ? '<a href="' + url + '">' + img + '</a>' : img;
      const nameHtml = url ? '<a href="' + url + '">' + esc(p.name) + '</a>' : esc(p.name);
      return '<div class="pcard">' + imgHtml +
        '<div class="pbody"><div class="pname">' + nameHtml + '</div>' +
        '<div class="pdesc">' + esc(p.desc || '') + '</div>' +
        '<div class="pprice">' + esc(p.price) + ' د.ك<small>' + esc(t.free || '') + '</small></div>' +
        '</div></div>';
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

  function init() {
    if (Array.isArray(window.LOCAL_PRODUCTS) && window.LOCAL_PRODUCTS.length) {
      render(window.LOCAL_PRODUCTS); // عرض فوري من اللقطة المحلية
    }
    const ensure = (window.StoreLive && window.StoreLive.ensure)
      ? window.StoreLive.ensure()
      : Promise.resolve();
    ensure.then(function () {
      fetchProducts().then(render);
      if (typeof window.storeWatchProducts === 'function') {
        window.storeWatchProducts(render);
      } else if (window.db && typeof window.db.collection === 'function') {
        const col = window.db.collection('products');
        const attach = (useOrder) => (useOrder ? col.orderBy('order', 'asc') : col)
          .onSnapshot(snap => render(snap.docs.map(d => Object.assign({ _id: d.id }, d.data()))),
            err => { if (useOrder) attach(false); });
        try { attach(true); } catch (e) {}
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
