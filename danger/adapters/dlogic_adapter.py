"""
D-Logic APIからデータを取得し、HorseDataに変換するアダプタ
既存のadapter.pyを経由してデータを取得する
"""
import sys
import os
import logging

# 親ディレクトリをパスに追加（dlogic-noteのadapter.pyを使うため）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapter import fetch_races, fetch_entries, fetch_predictions, fetch_odds
from config import MIN_HORSES
from ..models.horse import HorseData

logger = logging.getLogger(__name__)


def fetch_all_horses(date: str, race_type: str = "nar") -> list[HorseData]:
    """
    指定日の全レースから全馬のHorseDataを取得

    Returns:
        list[HorseData]: 全馬データ
    """
    all_horses = []

    # レース一覧取得
    races = fetch_races(date, race_type)
    logger.info(f"  {len(races)} レース取得")

    for race in races:
        race_id = race["race_id"]
        headcount = race.get("headcount", 0)

        if headcount < MIN_HORSES:
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

            venue = entries_data.get("venue", race.get("venue", ""))
            race_number = entries_data.get("race_number", 0)
            race_name = entries_data.get("race_name", "")

            # オッズ取得
            odds_map = {}
            for e in entries:
                if e.get("odds"):
                    odds_map[e["horse_number"]] = e["odds"]

            # 予想取得
            predictions = fetch_predictions(
                race_id=race_id,
                horses=horses,
                horse_numbers=horse_numbers,
                jockeys=jockeys,
                posts=posts,
                venue=venue,
                distance=entries_data.get("distance", race.get("distance", "")),
                track_condition=entries_data.get("track_condition", "良"),
            )

            # 全馬のai_scoreを計算
            engine_results = predictions.get("engines", {})
            all_scores = {}
            engine_support = {}  # horse_number -> [engine_names]

            for i, (name, num) in enumerate(zip(horses, horse_numbers)):
                ai_score = 0
                engines = []
                for eng_name, eng_data in engine_results.items():
                    rankings = eng_data.get("rankings", [])
                    for r in rankings:
                        if r.get("horse_number") == num or r.get("horse_name") == name:
                            rank = r.get("rank", 99)
                            if rank <= 3:
                                score_add = {1: 100, 2: 75, 3: 50}.get(rank, 25)
                                ai_score += score_add
                                engines.append(eng_name)
                            break
                all_scores[num] = ai_score
                engine_support[num] = engines

            # ai_scoreを正規化してai_win_probを計算
            score_sum = sum(s for s in all_scores.values() if s > 0)

            for i, (name, num) in enumerate(zip(horses, horse_numbers)):
                ai_score = all_scores.get(num, 0)
                engines = engine_support.get(num, [])
                odds = odds_map.get(num, 0)

                # AI勝率
                if ai_score > 0 and score_sum > 0:
                    ai_win_prob = ai_score / score_sum
                else:
                    ai_win_prob = 0.0

                # 信頼度（エンジン支持数 / 全エンジン数）
                total_engines = max(len(engine_results), 1)
                confidence = len(engines) / total_engines

                # 人気順（オッズから推定）
                popularity_rank = 99

                horse_data = HorseData(
                    race_id=race_id,
                    race_name=race_name,
                    track_name=venue,
                    race_number=race_number,
                    horse_number=num,
                    horse_name=name,
                    jockey_name=jockeys[i] if i < len(jockeys) else "",
                    odds_win=odds,
                    popularity_rank=popularity_rank,
                    ai_win_prob=round(ai_win_prob, 4),
                    ai_score=ai_score,
                    confidence_score=round(confidence, 2),
                    engine_support_count=len(engines),
                    engine_names=engines,
                )
                all_horses.append(horse_data)

            logger.info(f"  ✓ {race_id} {race_name} ({len(horses)}頭)")

        except Exception as e:
            logger.error(f"  ✗ {race_id}: {e}")
            continue

    # オッズで人気順をセット
    _assign_popularity_ranks(all_horses)

    return all_horses


def _assign_popularity_ranks(horses: list[HorseData]):
    """レースごとにオッズから人気順を割り当て"""
    from itertools import groupby

    # レースIDでグループ化
    horses_sorted = sorted(horses, key=lambda h: h.race_id)
    for race_id, group in groupby(horses_sorted, key=lambda h: h.race_id):
        race_horses = list(group)
        # オッズ昇順（低いほど人気）
        ranked = sorted(
            [h for h in race_horses if h.odds_win > 0],
            key=lambda h: h.odds_win,
        )
        for rank, h in enumerate(ranked, 1):
            h.popularity_rank = rank
