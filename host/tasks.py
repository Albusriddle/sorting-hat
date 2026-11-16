"""Windows-friendly task runner: python tasks.py test|up|preheat|ready|smoke|replay"""
import json
import os
import subprocess
import sys
import urllib.request

TOKEN = os.getenv("ADMIN_TOKEN", "dev-token")
BASE = "http://127.0.0.1:8080"


def _req(path, data=None):
    req = urllib.request.Request(BASE + path, method="POST" if data is not None else "GET")
    req.add_header("X-Admin-Token", TOKEN)
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=180) as r:
        return json.loads(r.read().decode() or "{}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "test":
        return subprocess.call([sys.executable, "-m", "pytest", "-q"])
    if cmd == "up":
        return subprocess.call([sys.executable, "-m", "app.run"])
    if cmd == "preheat":
        print(_req("/v1/preheat", {}))
    elif cmd == "ready":
        print(_req("/readyz"))
    elif cmd == "replay":
        print(_req("/v1/replay", {"text": "我想赢，我要第一"}))
    elif cmd == "smoke":
        return subprocess.call([sys.executable, "tools/smoke_ws.py"])
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
