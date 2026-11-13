#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_abraaj.py — استيراد منتجات متجر "مياه أبراج" (order.abraajwater.com)
إلى ملفات المشروع المحلية.

ماذا يفعل:
  1) يجلب فئات المتجر ثم صفحات تفاصيل كل منتج (بيانات Next.js المضمّنة).
  2) يفكّك كل منتج متعدّد الخيارات (variants) إلى **منتج منفصل لكل حجم/خيار**،
     مع تسمية تجمع اسم المنتج + اسم الخيار.
  3) ينزّل صور المنتجات إلى assets/images/products/ (عبر مُحسّن صور الموقع
     لأن static.zyda.com يحجب الطلبات المباشرة بـ 403).
  4) يكتب assets/js/products-local.js و products-snapshot.json بنفس صيغة المشروع
     (name, desc, price, img, _id) دون لمس الشكل أو الترتيب.
  5) يولّد الصفحات الثابتة (build_static) إن أمكن.

الاستخدام:
    python3 import_abraaj.py --dry-run     # عرض النتيجة دون كتابة
    python3 import_abraaj.py               # كتابة الملفات وتنزيل الصور
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, 'assets', 'images', 'products')
LOCAL_JS = os.path.join(ROOT, 'assets', 'js', 'products-local.js')
SNAPSHOT_FILE = os.path.join(ROOT, 'products-snapshot.json')
INDEX_FILE = os.path.join(ROOT, 'index.html')

BASE = 'https://order.abraajwater.com'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# الفئات المعروضة في المتجر بترتيبها (الفئات الفارغة تُتخطّى تلقائياً)
CATEGORIES = [
    '604a752f-a585-4489-847b-14ff3201727f',  # عرض خاص ولفترة محدودة
    'da76f76b-3bd3-49be-ac13-c14704012f25',  # عبوات
    '1640607e-b9cc-4690-867d-beceb9045955',  # جالونات
    '01873daf-54b7-4d5f-bf0e-78bc3a5b9316',  # المياه المستوردة
    'dc69e57f-e74b-4605-8097-f48ccaf9681e',  # أبطالنا الصغار
    '80d725e0-88a6-458c-91ac-0738e3848c14',  # الثلج والأكواب
]

OPT_WIDTHS = (720, 300, 1200)  # العروض المسموحة في مُحسّن صور الموقع


def log(msg):
    print(msg, flush=True)


def fetch(url, referer=None, retries=3):
    headers = {'User-Agent': UA, 'Accept-Language': 'ar,en;q=0.9'}
    if referer:
        headers['Referer'] = referer
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception as exc:
            last = exc
            time.sleep(1.5)
    raise last


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def fetch_category_products(cat_uuid):
    html = fetch('%s/ar/categories/%s' % (BASE, cat_uuid)).decode('utf-8', 'ignore')
    data = next_data(html)
    if not data:
        return []
    for e in data['props']['pageProps'].get('ssrCacheEntries') or []:
        d = e.get('data')
        if isinstance(d, dict) and 'products' in d:
            return d['products']
    return []


def fetch_product_detail(uuid):
    html = fetch('%s/ar/products/%s' % (BASE, uuid)).decode('utf-8', 'ignore')
    data = next_data(html)
    if not data:
        return None
    for e in data['props']['pageProps'].get('ssrCacheEntries') or []:
        k = e.get('key')
        key = k[0] if isinstance(k, list) else k
        if key == '#q:productDetails':
            return e['data']
    return None


def clean_base(title):
    """ينظّف اسم المنتج الأساسي: يزيل بادئة «حجم |» ويضمن ذكر العلامة مرة واحدة."""
    t = (title or '').strip()
    t = re.sub(r'^\s*(ال)?حجم\s*\|\s*', '', t).strip()
    if t and 'أبراج' not in t and 'ابراج' not in t:
        t = 'مياه أبراج ' + t
    return t or 'مياه أبراج'


def variant_label(v):
    t = (v.get('titleAr') or v.get('titleEn') or '').strip()
    return re.sub(r'\s+', ' ', t)


def effective_price(v):
    """السعر الفعلي المعروض: السعر المخفّض إن وُجد، وإلا السعر."""
    if v.get('discountEnabled') and v.get('discountedPrice'):
        return float(v['discountedPrice'])
    return float(v.get('price') or 0)


def fmt_price(amount):
    return '%.3f' % amount


def download_image(remote_url, dry_run=False):
    """ينزّل صورة المنتج عبر مُحسّن الصور ويعيد المسار النسبي المحلي."""
    if not remote_url:
        return ''
    enc = urllib.parse.quote(remote_url, safe='')
    for w in OPT_WIDTHS:
        url = '%s/_next/image?url=%s&w=%d&q=75' % (BASE, enc, w)
        try:
            raw = fetch(url, referer=BASE + '/')
        except Exception:
            continue
        if not raw or len(raw) < 1000:
            continue
        digest = hashlib.sha1(raw).hexdigest()[:16]
        name = digest + '.jpg'
        rel = 'assets/images/products/' + name
        if not dry_run:
            os.makedirs(IMG_DIR, exist_ok=True)
            path = os.path.join(IMG_DIR, name)
            if not (os.path.exists(path) and os.path.getsize(path) == len(raw)):
                with open(path, 'wb') as f:
                    f.write(raw)
        return rel
    log('  تنبيه: تعذّر تنزيل صورة: %s' % remote_url)
    return ''


def variant_image(v, product):
    imgs = v.get('images') or []
    for im in imgs:
        if im.get('photoUrl'):
            return im['photoUrl']
    return product.get('photoUrl') or ''


def build_products(dry_run=False):
    seen = set()
    out = []
    for cat_uuid in CATEGORIES:
        try:
            products = fetch_category_products(cat_uuid)
        except Exception as exc:
            log('تعذّر جلب الفئة %s: %r' % (cat_uuid, exc))
            continue
        for prod in products:
            uuid = prod.get('uuid')
            if uuid in seen:
                continue
            seen.add(uuid)
            try:
                detail = fetch_product_detail(uuid) or prod
            except Exception:
                detail = prod
            variants = detail.get('variants') or []
            base = clean_base(detail.get('titleAr') or prod.get('titleAr'))
            desc_raw = (detail.get('descriptionAr') or prod.get('descriptionAr') or '').strip()
            title_en = (detail.get('titleEn') or prod.get('titleEn') or '').strip()
            for idx, v in enumerate(variants):
                label = variant_label(v)
                if len(variants) > 1 and label:
                    name = '%s - %s' % (base, label)
                else:
                    name = base
                vid = str(v.get('id') or idx)
                item = {
                    '_id': 'ab-%s-%s' % (uuid.split('-')[0], vid),
                    'name': name,
                    'desc': desc_raw or title_en,
                    'price': fmt_price(effective_price(v)),
                    'img': download_image(variant_image(v, detail), dry_run),
                }
                out.append(item)
                log('  + %s | %s د.ك | %s' % (name, item['price'], item['img'] or '(بلا صورة)'))
    return out


def write_outputs(items, dry_run=False):
    payload = json.dumps(items, ensure_ascii=False, separators=(',', ':'))
    content = (
        '/* مولّد تلقائياً بواسطة import_abraaj.py — لا تعدّله يدوياً.\n'
        '   الغرض: عرض المنتجات فوراً عند فتح الموقع قبل مزامنة قاعدة البيانات. */\n'
        'window.LOCAL_PRODUCTS = ' + payload + ';\n'
    )
    version = hashlib.sha1(content.encode('utf-8')).hexdigest()[:10]
    if dry_run:
        return version
    with open(LOCAL_JS, 'w', encoding='utf-8') as f:
        f.write(content)
    with open(SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    # ارفع ?v= في index.html لتجاوز كاش المتصفح
    try:
        html = open(INDEX_FILE, encoding='utf-8').read()
        new_html, n = re.subn(r'(assets/js/products-local\.js)(\?v=[0-9a-zA-Z]+)?',
                              lambda m: m.group(1) + '?v=' + version, html, count=1)
        if n and new_html != html:
            open(INDEX_FILE, 'w', encoding='utf-8').write(new_html)
            log('تم تحديث إصدار products-local.js في index.html إلى v=%s' % version)
    except Exception as exc:
        log('تنبيه: تعذّر تحديث index.html: %r' % exc)
    return version


def main():
    ap = argparse.ArgumentParser(description='استيراد منتجات مياه أبراج إلى ملفات المشروع')
    ap.add_argument('--dry-run', action='store_true', help='عرض النتيجة دون كتابة ملفات')
    args = ap.parse_args()

    log('جلب المنتجات من %s ...' % BASE)
    items = build_products(args.dry_run)
    if not items:
        log('فشل: لم يتم استيراد أي منتج.')
        return 1

    log('')
    log('إجمالي المنتجات: %d' % len(items))
    version = write_outputs(items, args.dry_run)
    if not args.dry_run:
        try:
            import build_static
            build_static.build(items)
            log('تم توليد الصفحات الثابتة (product/, prices, feed, sitemap).')
        except Exception as exc:
            log('تنبيه: تعذّر توليد الصفحات الثابتة: %r' % exc)
        log('')
        log('كُتب: %s' % os.path.relpath(LOCAL_JS, ROOT))
        log('كُتب: %s' % os.path.relpath(SNAPSHOT_FILE, ROOT))
    else:
        log('(dry-run: لم تُكتب أي ملفات)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
