import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings as _settings  # noqa: E402

_settings.tts_pace_ms = 0       # 测试里不按实时节拍，避免 7s+ 的等待
