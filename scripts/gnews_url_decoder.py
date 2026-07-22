#!/usr/bin/env python3
"""
gnews_url_decoder.py — Decode Google News RSS URLs to original source URLs.

Standalone implementation (stdlib only — no requests, no selectolax deps).

Algorithm (reverse-engineered, matches SSujitX/google-news-url-decoder):
  1. Extract base64 article ID from news.google.com/rss/articles/<ID>
  2. Fetch Google News HTML page — parse out data-n-a-sg and data-n-a-ts
     attributes from a c-wiz > div[jscontroller] element.
  3. POST to Google's batchexecute endpoint with the signature + timestamp +
     base64 string. Parse the JSON response to get the real source URL.

Usage:
    from gnews_url_decoder import decode_google_news_url
    result = decode_google_news_url(google_news_url)
    if result['status']:
        real_url = result['decoded_url']

    # Or CLI:
    python3 gnews_url_decoder.py "https://news.google.com/rss/articles/CBM..."
"""
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import ssl
from typing import Optional


# NOTE: TLS verify disabled deliberately — Google News redirects sometimes go
# through GIP proxies that present certs our trust store rejects. Verifying
# source URL authenticity is not security-critical here (we only fetch public
# news pages), so accepting unverified certs is an acceptable trade-off.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def _get_base64_str(source_url: str) -> str:
    """Extract the base64 article ID from a Google News URL."""
    parsed = urllib.parse.urlparse(source_url)
    if parsed.hostname != "news.google.com":
        raise ValueError(f"Not a Google News URL: {parsed.hostname}")
    parts = parsed.path.split("/")
    if len(parts) < 2 or parts[-2] not in ("articles", "read", "rss"):
        raise ValueError(f"Unexpected path format: {parsed.path}")
    return parts[-1]


def _fetch(url: str, headers: Optional[dict] = None, data: Optional[bytes] = None,
            timeout: int = 15) -> tuple:
    """Fetch with stdlib urllib; returns (status_code, body_text)."""
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def _get_decoding_params(base64_str: str) -> dict:
    """Fetch Google News HTML and parse out signature + timestamp."""
    # Try /articles/{id} first, then /rss/articles/{id} as fallback
    for path in (f"/articles/{base64_str}", f"/rss/articles/{base64_str}"):
        url = f"https://news.google.com{path}"
        code, body = _fetch(url)
        if code != 200 or not body:
            continue

        # Parse out the c-wiz data attributes using regex (no selectolax dep)
        # Match: <c-wiz ... > ... <div jscontroller="..." data-n-a-sg="..." data-n-a-ts="...">
        sig_pats = [
            r'data-n-a-sg="([^"]+)"',
            r'data-n-a-sg=([^\s>]+)',
        ]
        ts_pats = [
            r'data-n-a-ts="([^"]+)"',
            r'data-n-a-ts=([^\s>]+)',
        ]
        sig = None
        for p in sig_pats:
            m = re.search(p, body)
            if m:
                sig = m.group(1)
                break
        ts = None
        for p in ts_pats:
            m = re.search(p, body)
            if m:
                ts = m.group(1)
                break
        if sig and ts:
            return {"status": True, "signature": sig, "timestamp": ts,
                    "base64_str": base64_str}

    return {"status": False,
            "message": "Could not find data-n-a-sg and data-n-a-ts in Google News page"}


def _decode_url(signature: str, timestamp: str, base64_str: str) -> dict:
    """POST to batchexecute to get the original source URL."""
    payload = [
        "Fbv4je",
        ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
         'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
         f'"{base64_str}",{timestamp},"{signature}"]'),
    ]
    # Wrap and URL-encode
    f_req = urllib.parse.quote(json.dumps([[payload]]))
    body = f"f.req={f_req}".encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}

    code, resp = _fetch(_BATCH_URL, headers=headers, data=body, timeout=15)
    if code != 200:
        return {"status": False, "message": f"batchexecute HTTP {code}: {resp[:200]}"}

    try:
        # Response shape:
        #   )]}'
        #
        #   [["wrb.fr","Fbv4je","[\"garturlres\",\"https://...\",1]",null,...],...]
        # Google prepends )]}' to defeat JSON hijacking. Strip it, then parse.
        body = resp
        # Remove Google's anti-hijack prefix if present
        for prefix in (")]}')", ")]}"):
            if body.startswith(prefix):
                body = body[len(prefix):]
                break
        body = body.lstrip()
        # The decoded URL is wrapped as escaped JSON inside the inner string.
        # Google escapes interior quotes as \\" — regex needs to match both
        # "garturlres","https://..." (outer) and
        # \"garturlres\",\"https://...\" (escaped inner)
        # The decoded URL itself is never escaped (just quoted), so we can
        # search for http(s):// anywhere between garturlres and the next quote.
        # Strategy: find "garturlres" (any escape), then scan forward to http(s).
        idx = resp.find("garturlres")
        if idx == -1:
            return {"status": False,
                    "message": f"Could not find garturlres. Response: {resp[:400]}"}
        tail = resp[idx:idx + 500]
        m = re.search(r'https?://[A-Za-z0-9./_\-?=&%:#+~]+', tail)
        if m:
            url = m.group(0).rstrip("\\")
            return {"status": True, "decoded_url": url}
        return {"status": False, "message": f"garturlres found but no URL after it: {resp[:400]}"}
    except (json.JSONDecodeError, IndexError, TypeError) as e:
        return {"status": False,
                "message": f"Parse error: {e}. Response sample: {resp[:400]}"}


def decode_google_news_url(source_url: str, interval: Optional[float] = None) -> dict:
    """
    Decode a Google News article URL to the original source URL.

    Returns:
        {"status": True, "decoded_url": "https://topgear.com/..."}
        or
        {"status": False, "message": "reason"}
    """
    try:
        base64 = _get_base64_str(source_url)
    except ValueError as e:
        return {"status": False, "message": str(e)}

    params = _get_decoding_params(base64)
    if not params["status"]:
        return params

    if interval:
        time.sleep(interval)

    return _decode_url(params["signature"], params["timestamp"], params["base64_str"])


# ---------- CLI ----------
def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 gnews_url_decoder.py <google_news_url> [--interval 2]")
        sys.exit(1)
    url = sys.argv[1]
    interval = None
    if "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        interval = float(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 2.0
    result = decode_google_news_url(url, interval=interval)
    if result["status"]:
        print(f"✓ {result['decoded_url']}")
    else:
        print(f"✗ FAIL: {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
