#!/usr/bin/env python3
"""R2(S3 호환) 업로드 — 표준 라이브러리만 사용 (AWS SigV4 직접 서명).

  /usr/bin/python3 r2_upload.py <파일> [원격키]        업로드 → 공개 URL 출력
  /usr/bin/python3 r2_upload.py --delete <원격키>      삭제

boto3/wrangler 같은 외부 의존성을 두지 않는다.
파이썬 3.14(python.org 빌드)는 인증서 문제가 있으므로 /usr/bin/python3 로 실행한다.
자격증명은 ~/.config/bulkfarmer/r2.env. 키 값을 출력에 찍지 않는다.
"""
import hashlib, hmac, sys, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

CFG = Path("~/.config/bulkfarmer/r2.env").expanduser()
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".mp4": "video/mp4"}


def cfg():
    env = {}
    for line in CFG.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def sign_key(secret, date, region, service):
    k = ("AWS4" + secret).encode()
    for part in (date, region, service, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    return k


def request(method, key, body=b"", content_type=None):
    e = cfg()
    acct, bucket = e["R2_ACCOUNT_ID"], e["R2_BUCKET"]
    host = f"{acct}.r2.cloudflarestorage.com"
    region, service = "auto", "s3"

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    # 경로는 반드시 퍼센트 인코딩한다. 한글 키를 그대로 쓰면 HTTP 요청 라인이
    # ASCII 인코딩에 실패하고, SigV4 서명도 실제 요청과 어긋난다.
    path = f"/{bucket}/{urllib.parse.quote(key, safe='/')}"

    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    if content_type:
        headers["content-type"] = content_type

    signed = ";".join(sorted(headers))
    canon_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canon = f"{method}\n{path}\n\n{canon_headers}\n{signed}\n{payload_hash}"

    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{hashlib.sha256(canon.encode()).hexdigest()}"
    sig = hmac.new(sign_key(e["R2_SECRET_ACCESS_KEY"], date, region, service),
                   to_sign.encode(), hashlib.sha256).hexdigest()

    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={e['R2_ACCESS_KEY_ID']}/{scope}, "
        f"SignedHeaders={signed}, Signature={sig}")

    req = urllib.request.Request(f"https://{host}{path}", data=body or None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, ""
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()[:400]


def public_url(key):
    base = cfg().get("R2_PUBLIC_URL", "").rstrip("/")
    enc = urllib.parse.quote(key, safe="/")
    return f"{base}/{enc}" if base else f"(R2_PUBLIC_URL 미설정)/{enc}"


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    if args[0] == "--delete":
        for key in args[1:]:
            code, err = request("DELETE", key)
            print(f"{'삭제' if code in (200, 204) else '실패 '+str(code)}  {key}  {err}")
        return

    path = Path(args[0])
    key = args[1] if len(args) > 1 else path.name
    body = path.read_bytes()
    code, err = request("PUT", key, body, MIME.get(path.suffix.lower(), "application/octet-stream"))
    if code == 200:
        print(public_url(key))
    else:
        sys.exit(f"업로드 실패 {code}: {err}")


if __name__ == "__main__":
    main()
