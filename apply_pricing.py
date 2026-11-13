#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_pricing.py — تعديل أسعار المنتجات في ملفات المشروع وفق شرائح محدّدة.

الشرائح (كما طلب العميل):
    السعر > 10 د.ك          → يُخصم 2.000
    5 < السعر <= 10         → يُخصم 1.000
    1 < السعر <= 5          → يُخصم 0.500
    السعر <= 1              → يُخصم 20%

يعدّل:
  - products-snapshot.json
  - assets/js/products-local.js
ثم يعيد توليد الصفحات الثابتة (build_static) ويرفع ?v= في index.html.

الاستخدام:
    python3 apply_pricing.py --dry-run     # عرض الجدول دون كتابة
    python3 apply_pricing.py               # تطبيق فعلي
"""
import argparse
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.abspath(__file__))
LOCAL_JS = os.path.join(ROOT, 'assets', 'js', 'products-local.js')
SNAPSHOT_FILE = os.path.join(ROOT, 'products-snapshot.json')
INDEX_FILE = os.path.join(ROOT, 'index.html')

CENTS = Decimal('0.001')


def new_price(value):
    """يطبّق شرائح التسعير ويعيد السعر الجديد مقرّباً لثلاث خانات."""
    p = Decimal(str(value))
    if p >= Decimal('10'):
        n = p - Decimal('2')
    elif p > Decimal('5'):
        n = p - Decimal('1')
    elif p > Decimal('1'):
        n = p - Decimal('0.5')
    else:
        n = p * Decimal('0.8')
    if n < 0:
        n = Decimal('0')
    return n.quantize(CENTS, rounding=ROUND_HALF_UP)


def load_items():
    with open(SNAPSHOT_FILE, encoding='utf-8') as f:
        return json.load(f)


def write_outputs(items, dry_run=False):
    payload = json.dumps(items, ensure_ascii=False, separators=(',', ':'))
    content = (
        '/* مولّد تلقائياً — لا تعدّله يدوياً. */\n'
        'window.LOCAL_PRODUCTS = ' + payload + ';\n'
    )
    version = hashlib.sha1(content.encode('utf-8')).hexdigest()[:10]
    if dry_run:
        return version
    with open(LOCAL_JS, 'w', encoding='utf-8') as f:
        f.write(content)
    with open(SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    try:
        html = open(INDEX_FILE, encoding='utf-8').read()
        new_html, n = re.subn(r'(assets/js/products-local\.js)(\?v=[0-9a-zA-Z]+)?',
                              lambda m: m.group(1) + '?v=' + version, html, count=1)
        if n and new_html != html:
            open(INDEX_FILE, 'w', encoding='utf-8').write(new_html)
    except Exception as exc:
        print('تنبيه: تعذّر تحديث index.html: %r' % exc)
    return version


def main():
    ap = argparse.ArgumentParser(description='تعديل أسعار المنتجات وفق الشرائح')
    ap.add_argument('--dry-run', action='store_true', help='عرض الجدول دون كتابة ملفات')
    args = ap.parse_args()

    items = load_items()
    changed = 0
    print('%-52s %-10s %-10s %s' % ('المنتج', 'القديم', 'الجديد', 'الفرق'))
    print('-' * 86)
    for it in items:
        old = Decimal(str(it.get('price') or '0'))
        nw = new_price(old)
        if nw != old:
            changed += 1
        it['price'] = '%.3f' % nw
        print('%-52s %-10s %-10s %s' % (
            (it.get('name') or '')[:50], '%.3f' % old, '%.3f' % nw, '%.3f' % (old - nw)))
    print('-' * 86)
    print('إجمالي: %d | معدّل: %d' % (len(items), changed))

    version = write_outputs(items, args.dry_run)
    if not args.dry_run:
        try:
            import build_static
            build_static.build(items)
            print('تم توليد الصفحات الثابتة.')
        except Exception as exc:
            print('تنبيه: تعذّر توليد الصفحات الثابتة: %r' % exc)
        print('تم التحديث (products-local.js v=%s).' % version)
    else:
        print('(dry-run: لم تُكتب أي ملفات)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
