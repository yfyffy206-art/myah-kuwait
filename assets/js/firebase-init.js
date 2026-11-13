/**
 * firebase-init.js — تهيئة Firebase خفيفة للصفحات الثابتة (القراءة فقط)
 * ---------------------------------------------------------------------
 * الغرض: تمكين الصفحات الثابتة (الصفحات القانونية، أسعار اليوم، تفاصيل المنتج)
 * من قراءة المنتجات مباشرة من Firestore بنفس بيانات الموقع الرئيسي — فيرى
 * العميل نفس الاسم والوصف والسعر والصورة في كل صفحة.
 *
 * لا تسجّل الدخول ولا ترسل بيانات: القراءة العامة في مجموعة products مسموحة
 * بلا مصادقة (قواعد الأمان)، لذا نكتفي بالقراءة. الصفحات التي تحتاج الكتابة
 * (الموقع/السلة) تستخدم firebase-client.js بدلاً منها.
 *
 * تعتمد على: firebase-env.js (يوفّر window.__FIREBASE_ENV__) + firebase-app-compat
 * و firebase-firestore-compat (يُحمَّلان في الصفحة قبلها).
 */
(function () {
  const ENV = window.__FIREBASE_ENV__ || {};
  if (!ENV.apiKey) {
    console.warn('firebase-init.js: window.__FIREBASE_ENV__ مفقود — لن تُقرأ المنتجات من قاعدة البيانات.');
    return;
  }
  if (typeof firebase === 'undefined') {
    console.warn('firebase-init.js: مكتبة firebase غير محمّلة.');
    return;
  }
  if (!firebase.apps.length) {
    firebase.initializeApp({
      apiKey: ENV.apiKey,
      authDomain: ENV.authDomain,
      databaseURL: ENV.databaseURL,
      projectId: ENV.projectId,
      storageBucket: ENV.storageBucket,
      messagingSenderId: ENV.messagingSenderId,
      appId: ENV.appId,
      measurementId: ENV.measurementId
    });
  }
  window.db = firebase.firestore();
  // قاعدة الزمن الحقيقي اختيارية — لا تُهيّأ إلا إن كانت وحدة database محمّلة
  // (الصفحات الثابتة تحمّل Firestore فقط لتخفيف الحجم).
  window.rtd = (typeof firebase.database === 'function') ? firebase.database() : null;
})();
