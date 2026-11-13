#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_firestore.py — نقل منتجات المشروع (products-snapshot.json) إلى Firestore.

يقرأ اللقطة المحلية (التي تحمل الأسعار المعدّلة والصور) ويكتب كل منتج كوثيقة
في مجموعة `products` بمشروع Firebase، مع حقل `order` متسلسلاً. ثم يرفع الصور
المحلية إلى Cloudinary ويستبدل المسار المحلي برابط Cloudinary الدائم.

يُستخدم مرة واحدة للترحيل الأولي، ويمكن تشغيله لاحقاً بأمان (upsert بالمعرّف).

الاستخدام:
    python3 seed_firestore.py --dry-run     # عرض ما سيُكتب دون تنفيذ
    python3 seed_firestore.py               # تنفيذ فعلي (رفع الصور + كتابة الوثائق)
    python3 seed_firestore.py --no-images   # كتابة الوثائق بمسارات محلية فقط
"""
import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import firebase_config  # noqa: E402

SNAPSHOT = os.path.join(ROOT, 'products-snapshot.json')


def sign_upload(params, secret):
    """توقيع Cloudinary: sha1 لترتيب المعطيات أبجدياً + السرّ."""
    to_sign = '&'.join('%s=%s' % (k, params[k]) for k in sorted(params))
    return hashlib.sha1((to_sign + secret).encode('utf-8')).hexdigest()


def upload_image(path, cloud, key, secret, folder):
    """يرفع صورة موقّعاً ويعيد secure_url. None عند الفشل."""
    ts = int(time.time())
    params = {'timestamp': ts, 'folder': folder}
    params['signature'] = sign_upload(params, secret)
    params['api_key'] = key
    boundary = '----oh%s' % hashlib.md5(str(ts).encode()).hexdigest()
    with open(path, 'rb') as f:
        raw = f.read()
    ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    parts = []
    for k, v in params.items():
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: %s\r\n\r\n'
                  % (boundary, os.path.basename(path), ctype)).encode() + raw + b'\r\n')
    parts.append(('--%s--\r\n' % boundary).encode())
    body = b''.join(parts)
    req = urllib.request.Request(
        'https://api.cloudinary.com/v1_1/%s/image/upload' % cloud, data=body, method='POST',
        headers={'Content-Type': 'multipart/form-data; boundary=%s' % boundary})
    try:
        res = json.loads(urllib.request.urlopen(req, timeout=120).read())
        return res.get('secure_url')
    except urllib.error.HTTPError as ex:
        print('   ⚠️ فشل رفع %s: %s' % (os.path.basename(path), ex.read().decode('utf-8', 'ignore')[:150]))
        return None


def firestore_token(env):
    payload = json.dumps({'email': env['panelEmail'], 'password': env['panelPassword'],
                          'returnSecureToken': True}).encode()
    req = urllib.request.Request(
        'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=%s' % env['apiKey'],
        data=payload, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())['idToken']


def fs_commit(project, token, writes):
    """ينفّذ batch write في Firestore REST (حد 500 عملية)."""
    base = ('https://firestore.googleapis.com/v1/projects/%s/databases/(default)/documents' % project)
    for i in range(0, len(writes), 400):
        chunk = writes[i:i + 400]
        body = json.dumps({'writes': chunk}).encode()
        req = urllib.request.Request(base + ':commit', data=body, method='POST',
                                     headers={'Content-Type': 'application/json',
                                              'Authorization': 'Bearer ' + token})
        urllib.request.urlopen(req, timeout=60).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-images', action='store_true', help='لا ترفع الصور، اكتب المسارات المحلية')
    args = ap.parse_args()

    items = json.load(open(SNAPSHOT, encoding='utf-8'))
    env = firebase_config.firebase_env()
    cloud = firebase_config.cloudinary_env()['cloudName']
    ckey = os.environ.get('CLOUDINARY_API_KEY', '')
    csecret = os.environ.get('CLOUDINARY_API_SECRET', '')
    folder = 'myah-products'

    print('منتجات في اللقطة: %d | مشروع: %s | سحابة: %s' % (len(items), env['projectId'], cloud))
    if not args.no_images and not (ckey and csecret):
        print('❌ CLOUDINARY_API_KEY/SECRET مفقودان في البيئة.'); return 1
    if args.dry_run:
        for i, p in enumerate(items):
            print('  %2d | %-48s | %s | %s' % (i, p['name'][:46], p['price'], p['img'][:60]))
        print('(dry-run: لا كتابة)')
        return 0

    token = firestore_token(env)
    project = env['projectId']
    api = 'https://firestore.googleapis.com/v1'
    # اسم الوثيقة في commit بلا بادئة المضيف
    docbase = 'projects/%s/databases/(default)/documents' % project
    writes = []
    uploaded = {}  # مسار محلي → رابط Cloudinary (تجنّب رفع نفس الصورة مرتين)
    for i, p in enumerate(items):
        img = p['img']
        if not args.no_images and not img.startswith('http'):
            if img in uploaded:
                img = uploaded[img]
            else:
                local = os.path.join(ROOT, img)
                if os.path.exists(local):
                    url = upload_image(local, cloud, ckey, csecret, folder)
                    if url:
                        img = uploaded[img] = url
        fields = {
            'name': {'stringValue': p['name']},
            'desc': {'stringValue': p.get('desc', '')},
            'price': {'stringValue': str(p['price'])},
            'img': {'stringValue': img},
            'order': {'integerValue': str(i)},
        }
        writes.append({'update': {
            'name': '%s/products/%s' % (docbase, p['_id']),
            'fields': fields}})
        print('  %2d ✓ %s' % (i, p['name'][:50]))
    fs_commit(project, token, writes)
    print('✅ كُتب %d منتجاً في Firestore.' % len(writes))
    return 0


if __name__ == '__main__':
    sys.exit(main())
