#!/usr/bin/env python3
"""내 네이버 블로그 카테고리 번호 조회.

  /usr/bin/python3 list_category.py

publish_post.py --category 에 넣을 번호를 여기서 확인한다.
"""
import json, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import naver_auth

API = "https://openapi.naver.com/blog/listCategory.json"

req = urllib.request.Request(API, headers={"Authorization": f"Bearer {naver_auth.ensure_token()}"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    sys.exit(f"조회 실패 HTTP {e.code}: {e.read().decode()[:400]}")

msg = res.get("message", {})
if msg.get("status") != "success":
    sys.exit(json.dumps(res, ensure_ascii=False, indent=2))

for c in msg.get("result", []):
    print(f"{c.get('categoryNo','?'):>4}  {c.get('categoryName','')}")
