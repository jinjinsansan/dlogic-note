"""
dlogic-note メインパイプライン
毎日の実行エントリポイント

Usage:
    python main.py                  # 今日のレース
    python main.py --date 20260315  # 指定日
    python main.py --type nar       # 地方競馬
"""
import argparse
import logging
from datetime import datetime

from config import DEFAULT_RACE_TYPE, MIN_HORSES, MAX_FEATURED_RACES
from adapter import (
    fetch_races,
    fetch_entries,
    fetch_predictions,
    fetch_odds,
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
    logger.info("Step 1: レース一覧取得")
    races = fetch_races(date, race_type)
    logger.info(f"  → {len(races)} レース取得")

    if not races:
        logger.warning("レースが見つかりません。終了します。")
        return

    # Step 2: 各レースの出馬表 + 予想取得
    logger.info("Step 2: 出馬表・予想取得")
    race_analyses = []

    for race in races:
        race_id = race["race_id"]
        headcount = race.get("headcount", 0)

        if headcount < MIN_HORSES:
            logger.info(f"  Skip {race_id} ({headcount}頭 < {MIN_HORSES})")
            continue

        try:
            # 出馬表取得
            entries_data = fetch_entries(race_id, race_type)
            if "error" in entries_data:
                logger.warning(f"  {race_id}: {entries_data['error']}")
                continue

            entries = entries_data.get("entries", [])
            horses = [e["horse_name"] for e in entries]
            horse_numbers = [e["horse_number"] for e in entries]
            jockeys = [e.get("jockey", "") for e in entries]
            posts = [e.get("post", 0) for e in entries]

            # オッズ取得（出馬表に含まれている場合）
            odds = {}
            for e in entries:
                if e.get("odds"):
                    odds[e["horse_number"]] = e["odds"]

            # 予想取得
            predictions = fetch_predictions(
                race_id=race_id,
                horses=horses,
                horse_numbers=horse_numbers,
                jockeys=jockeys,
                posts=posts,
                venue=entries_data.get("venue", race.get("venue", "")),
                distance=entries_data.get("distance", race.get("distance", "")),
                track_condition=entries_data.get("track_condition", "良"),
            )

            # 統一JSON変換
            race_info = {
                "horses": horses,
                "horse_numbers": horse_numbers,
                "jockeys": jockeys,
                "venue": entries_data.get("venue", ""),
                "race_number": entries_data.get("race_number", 0),
                "race_name": entries_data.get("race_name", ""),
                "distance": entries_data.get("distance", ""),
                "track_condition": entries_data.get("track_condition", "良"),
            }

            unified = build_unified_race_json(race_id, race_info, predictions, odds or None)
            race_analyses.append(unified)
            logger.info(f"  ✓ {race_id} {unified['race_name']} ({len(horses)}頭)")

        except Exception as e:
            logger.error(f"  ✗ {race_id}: {e}")
            continue

    logger.info(f"  → {len(race_analyses)} レース分析完了")

    if not race_analyses:
        logger.warning("分析可能なレースがありません。終了します。")
        return

    # Step 3: 厳選レース選定 + 危険人気馬 + 期待値馬
    logger.info("Step 3: 厳選レース・注目馬抽出")

    # 厳選レース: value_gapの分散が大きいレース（AIと市場の乖離が大きい＝妙味あり）
    featured = select_featured_races(race_analyses)
    logger.info(f"  厳選レース: {len(featured)} レース")

    all_danger = []
    all_value = []
    for analysis in race_analyses:
        all_danger.extend(extract_danger_horses(analysis))
        all_value.extend(extract_value_horses(analysis))

    # 全体でソートして上位を取得
    all_danger.sort(key=lambda x: x.get("value_gap", 0), reverse=True)
    all_value.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
    top_danger = all_danger[:5]
    top_value = all_value[:10]

    logger.info(f"  危険人気馬: {len(top_danger)} 頭")
    logger.info(f"  期待値馬: {len(top_value)} 頭")

    # Step 4: 記事生成
    logger.info("Step 4: 記事生成")
    article = generate_note_article(
        date=date,
        race_analyses=race_analyses,
        featured_races=featured,
        danger_horses=top_danger,
        value_horses=top_value,
        race_type=race_type,
    )

    # Step 5: 保存
    logger.info("Step 5: 出力保存")
    output_dir = save_output(date, article, race_analyses, race_type)
    logger.info(f"  出力先: {output_dir}")

    # サマリー表示
    logger.info("=== 完了 ===")
    logger.info(f"  記事: {output_dir}/main_note.md")
    logger.info(f"  X告知: {output_dir}/x_post.txt")
    if article.get("x_post"):
        logger.info(f"  X告知文: {article['x_post'][:100]}...")

    return output_dir


def select_featured_races(race_analyses: list[dict]) -> list[dict]:
    """
    厳選レースを選定
    基準: AIスコアの上位馬と下位馬の差が大きい（＝AIが明確な優劣をつけているレース）
    """
    scored = []
    for analysis in race_analyses:
        horses = analysis.get("horses", [])
        if len(horses) < 2:
            continue
        scores = [h.get("ai_score", 0) for h in horses]
        score_spread = max(scores) - min(scores)
        scored.append((score_spread, analysis))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [analysis for _, analysis in scored[:MAX_FEATURED_RACES]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dlogic-note 記事生成")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="対象日 (YYYYMMDD)")
    parser.add_argument("--type", default=DEFAULT_RACE_TYPE, choices=["jra", "nar"], help="レースタイプ")
    args = parser.parse_args()

    run(args.date, args.type)
