"""
AI危険人気馬BOT — CLIエントリポイント

Usage:
    python -m danger.main                    # 今日のレース
    python -m danger.main --date 20260313    # 指定日
    python -m danger.main --type jra         # JRA
"""
import argparse
import json
import os
import logging
from datetime import datetime

from .adapters.dlogic_adapter import fetch_all_horses
from .services.danger_service import find_danger_horses
from .services.article_service import (
    generate_x_post,
    generate_note_free,
    generate_note_paid,
    generate_danger_markdown,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run(date: str, race_type: str = "nar"):
    """メイン処理"""
    logger.info(f"=== 危険人気馬BOT開始: {date} ({race_type}) ===")

    # 日付表示
    try:
        dt = datetime.strptime(date, "%Y%m%d")
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        date_display = f"{dt.year}年{dt.month}月{dt.day}日({weekday_names[dt.weekday()]})"
    except ValueError:
        date_display = date

    # Step 1: 全馬データ取得
    logger.info("Step 1: 全馬データ取得")
    all_horses = fetch_all_horses(date, race_type)
    logger.info(f"  → {len(all_horses)} 頭取得")

    if not all_horses:
        logger.warning("データなし。終了。")
        return

    # Step 2: 危険人気馬判定
    logger.info("Step 2: 危険人気馬判定")
    danger_results = find_danger_horses(all_horses, top_n=3)
    logger.info(f"  → {len(danger_results)} 頭抽出")

    if not danger_results:
        logger.warning("危険人気馬なし。終了。")
        return

    for i, r in enumerate(danger_results, 1):
        h = r.horse
        logger.info(
            f"  {i}位: {h.horse_name}（{h.track_name}{h.race_number}R）"
            f" オッズ{h.odds_win} AI{round(h.ai_win_prob*100,1)}%"
            f" 市場{round(h.market_prob*100,1)}%"
            f" 歪み{round(h.distortion_diff*100,1)}pt"
            f" [{r.danger_level}]"
        )

    # Step 3: 出力生成
    logger.info("Step 3: 出力生成")
    track = danger_results[0].horse.track_name

    x_post = generate_x_post(danger_results, date_display, track)
    note_free = generate_note_free(danger_results, date_display)
    note_paid = generate_note_paid(danger_results, date_display)
    danger_md = generate_danger_markdown(danger_results, date_display)

    # JSON
    danger_json = []
    for i, r in enumerate(danger_results, 1):
        d = r.to_dict()
        d["rank"] = i
        danger_json.append(d)

    # Step 4: 保存
    logger.info("Step 4: 保存")
    output_dir = os.path.join("output", "danger", f"{date}_{race_type}")
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "danger_rank.json"), "w", encoding="utf-8") as f:
        json.dump(danger_json, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "danger_rank.md"), "w", encoding="utf-8") as f:
        f.write(danger_md)

    with open(os.path.join(output_dir, "x_post.txt"), "w", encoding="utf-8") as f:
        f.write(x_post)

    with open(os.path.join(output_dir, "note_free.md"), "w", encoding="utf-8") as f:
        f.write(note_free)

    with open(os.path.join(output_dir, "note_paid.md"), "w", encoding="utf-8") as f:
        f.write(note_paid)

    logger.info(f"  出力先: {output_dir}")
    logger.info("=== 完了 ===")
    logger.info(f"  X投稿文: {x_post[:80]}...")

    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI危険人気馬BOT")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="対象日 (YYYYMMDD)")
    parser.add_argument("--type", default="nar", choices=["jra", "nar"], help="レースタイプ")
    args = parser.parse_args()

    run(args.date, args.type)
