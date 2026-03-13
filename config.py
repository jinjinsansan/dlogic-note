"""dlogic-note 設定"""
import os
from dotenv import load_dotenv

load_dotenv()

# D-Logic VPS API
# DATA_API: レース一覧・出馬表 (Flask linebot, port 5000)
# BACKEND_API: 予想エンジン (FastAPI, port 8000)
DLOGIC_API_URL = os.getenv("DLOGIC_API_URL", "https://bot.dlogicai.in")
DLOGIC_BACKEND_URL = os.getenv("DLOGIC_BACKEND_URL", DLOGIC_API_URL)

# Claude API (記事生成用)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# 出力先
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# 対象レース設定
DEFAULT_RACE_TYPE = "jra"  # jra or nar
MIN_HORSES = 8  # 最低出走頭数（少頭数は除外）
MAX_FEATURED_RACES = 5  # 厳選レース数
