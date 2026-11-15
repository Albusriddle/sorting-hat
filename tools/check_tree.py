from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["hw", "fw", "host", "docs", "fixtures", "release", "tools"]
missing = [d for d in REQUIRED if not (ROOT / d).is_dir()]
extra = [p.name for p in ROOT.iterdir() if p.is_dir() and p.name not in REQUIRED
         and not p.name.startswith(".") and p.name != "__pycache__"]
print("missing:", missing or "none")
print("extra:", extra or "none")
sys.exit(1 if missing else 0)
