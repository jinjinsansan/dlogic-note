"""
dlogic-note メインパイプライン
毎日の実行エントリポイント

Usage:
    python main.py                  # 今日のレース
    python main.py --date 20260315  # 指定日
"""
import argparse
import logging
from datetime import datetime

from config import DEFAULT_RACE_TYPE
from adapter import (
    fetch_predictions,
    fetch_analysis,
    build_unified_race_json,
    extract_danger_horses,
    extract_value_horses,
)
from generator import generate_note_article, save_output

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run(date: str, race_type: str = DEFAULT_RACE_TYPE):
    """メインパイプライン"""
    logger.info(f"=== dlogic-note 記事生成開始: {date} ({race_type}) ===")

    # Step 1: レースデータ取得
    # TODO Phase 1: VPSにレース一覧APIを追加 or スクレイパー共有
    logger.info("Step 1: レースデータ取得")
    # races = fetch_races(date, race_type)
    # entries = [fetch_entries(r["race_id"], race_type) for r in races]

    # Step 2: 各レースをD-Logic AIで解析
    logger.info("Step 2: D-Logic AI解析")
    # race_analyses = []
    # for entry in entries:
    #     predictions = fetch_predictions(...)
    #     unified = build_unified_race_json(entry["race_id"], entry, predictions, odds)
    #     race_analyses.append(unified)

    # Step 3: 厳選レース・危険人気馬・期待値馬を抽出
    logger.info("Step 3: 分析データ抽出")
    # featured = select_featured_races(race_analyses)
    # danger = []
    # value = []
    # for analysis in race_analyses:
    #     danger.extend(extract_danger_horses(analysis))
    #     value.extend(extract_value_horses(analysis))

    # Step 4: 記事生成
    logger.info("Step 4: 記事生成")
    # article = generate_note_article(date, race_analyses, featured, danger, value)

    # Step 5: 保存
    logger.info("Step 5: 出力保存")
    # output_dir = save_output(date, article, race_analyses)
    # logger.info(f"出力先: {output_dir}")

    logger.info("=== 完了（Phase 1 実装後に動作します） ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dlogic-note 記事生成")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="対象日 (YYYYMMDD)")
    parser.add_argument("--type", default=DEFAULT_RACE_TYPE, choices=["jra", "nar"], help="レースタイプ")
    args = parser.parse_args()

    run(args.date, args.type)
