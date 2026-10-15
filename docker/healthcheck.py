"""Healthy = the server answers. With auth on, an unauthenticated request must get 401."""
import sys
import urllib.error
import urllib.request

try:
    urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3)
except urllib.error.HTTPError as exc:
    sys.exit(0 if exc.code in (401, 404, 406) else 1)
except Exception:
    sys.exit(1)
sys.exit(0)
