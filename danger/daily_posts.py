"""
危険人気馬 X投稿スケジューラー

投稿スケジュール:
  10:00 — ① 今日の危険人気馬 (main.py で実行)
  12:00 — ② 昨日の振り返り
  15:00 — ③ 教育コンテンツ（ローテーション）
  毎週月曜 11:00 — ④ 週次実績レポート

Usage:
  python -m danger.daily_posts review     # ② 昨日の振り返り
  python -m danger.daily_posts education  # ③ 教育コンテンツ
  python -m danger.daily_posts stats      # ④ 実績レポート
"""
import argparse
import logging
from datetime import datetime, timedelta

from .services.result_checker import check_danger_results, load_accumulated_stats
from .services.article_service import (
    generate_x_review_post,
    generate_x_education_post,
    generate_x_stats_post,
)
from .services.x_poster import post_to_x

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _yesterday() -> tuple[str, str]:
    """昨日の日付とレースタイプを返す"""
    dt = datetime.now() - timedelta(days=1)
    date_str = dt.strftime("%Y%m%d")
    race_type = "jra" if dt.weekday() >= 5 else "nar"
    return date_str, race_type


def _date_display(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        return f"{dt.month}/{dt.day}({weekday_names[dt.weekday()]})"
    except ValueError:
        return date_str


def post_review():
    """② 昨日の危険人気馬の結果振り返りを投稿"""
    date_str, race_type = _yesterday()
    logger.info(f"=== 振り返り投稿: {date_str} ({race_type}) ===")

    results = check_danger_results(date_str, race_type)
    if not results:
        logger.warning("昨日の危険人気馬データなし。スキップ。")
        return

    display = _date_display(date_str)
    text = generate_x_review_post(results, display)
    logger.info(f"投稿文:\n{text}")

    result = post_to_x(text)
    if result["status"] == "ok":
        logger.info(f"✓ 振り返り投稿成功: {result['tweet_id']}")
    else:
        logger.warning(f"✗ 投稿失敗: {result['message']}")


def post_education(slot: str = "afternoon"):
    """③ 教育/誘導コンテンツ投稿

    slot:
        morning  — 朝投稿（①王道フック or ③気づき系）
        afternoon — 昼投稿（④限定感 or ⑤実用系）
        evening  — 直前投稿（②恐怖訴求 or ⑩クロージング）
    """
    day_index = (datetime.now() - datetime(2026, 1, 1)).days

    # スロットに応じたテンプレートインデックス
    slot_indices = {
        "morning": [0, 2],      # ①王道フック, ③気づき系
        "afternoon": [3, 4],    # ④限定感, ⑤実用系
        "evening": [1, 9],      # ②恐怖訴求, ⑩クロージング
    }
    indices = slot_indices.get(slot, [3, 4])
    idx = indices[day_index % len(indices)]

    logger.info(f"=== 教育投稿: slot={slot} index={idx} ===")

    text = generate_x_education_post(idx)
    logger.info(f"投稿文:\n{text}")

    result = post_to_x(text)
    if result["status"] == "ok":
        logger.info(f"✓ 教育投稿成功: {result['tweet_id']}")
    else:
        logger.warning(f"✗ 投稿失敗: {result['message']}")


def post_stats():
    """④ 累積実績レポートを投稿"""
    logger.info("=== 実績投稿 ===")

    stats = load_accumulated_stats()
    text = generate_x_stats_post(stats)
    logger.info(f"投稿文:\n{text}")

    result = post_to_x(text)
    if result["status"] == "ok":
        logger.info(f"✓ 実績投稿成功: {result['tweet_id']}")
    else:
        logger.warning(f"✗ 投稿失敗: {result['message']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="危険人気馬 X投稿スケジューラー")
    parser.add_argument("action", choices=["review", "education", "stats"],
                        help="review=振り返り, education=教育, stats=実績")
    parser.add_argument("--slot", default="afternoon", choices=["morning", "afternoon", "evening"],
                        help="教育投稿のスロット (morning/afternoon/evening)")
    args = parser.parse_args()

    if args.action == "review":
        post_review()
    elif args.action == "education":
        post_education(args.slot)
    elif args.action == "stats":
        post_stats()
