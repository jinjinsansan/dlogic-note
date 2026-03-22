"""
D-Logic APIからデータを取得し、HorseDataに変換するアダプタ
5カテゴリ100点方式に必要な全データを取得する
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapter import fetch_races, fetch_entries, fetch_predictions, fetch_analysis
from config import MIN_HORSES, DLOGIC_BACKEND_URL
from ..models.horse import HorseData

logger = logging.getLogger(__name__)


def _fetch_race_flow(race_id: str, params: dict) -> dict:
    """展開予想を取得"""
    try:
        return fetch_analysis(race_id, "race-flow", params)
    except Exception as e:
        logger.warning(f"  race-flow取得失敗 {race_id}: {e}")
        return {}


def _fetch_recent_runs(race_id: str, params: dict) -> dict:
    """直近走データを取得"""
    try:
        return fetch_analysis(race_id, "recent-runs", params)
    except Exception as e:
        logger.warning(f"  recent-runs取得失敗 {race_id}: {e}")
        return {}


def _fetch_jockey_analysis(race_id: str, params: dict) -> dict:
    """騎手分析を取得"""
    try:
        return fetch_analysis(race_id, "jockey-analysis", params)
    except Exception as e:
        logger.warning(f"  jockey-analysis取得失敗 {race_id}: {e}")
        return {}


def _parse_running_style(flow_data: dict, horse_name: str) -> tuple[str, int, list[str]]:
    """展開データから脚質・同型数・有利脚質を解析"""
    style = ""
    same_count = 0
    advantage = []

    # style_summary から脚質を特定
    style_summary = flow_data.get("style_summary", {})
    for style_type, horses in style_summary.items():
        if horse_name in horses:
            # "逃げ(状況逃げ)" → "逃げ"
            base = style_type.split("(")[0] if "(" in style_type else style_type
            style = base
            break

    # style_groups から同型数を算出
    style_groups = flow_data.get("style_groups", {})
    if style and style in style_groups:
        same_count = len(style_groups[style])

    # scenarios から有利脚質
    scenarios = flow_data.get("scenarios", [])
    for sc in scenarios:
        if sc.get("probability", 0) >= 40:
            advantage = sc.get("advantage", [])
            break
    if not advantage and scenarios:
        advantage = scenarios[0].get("advantage", [])

    return style, same_count, advantage


def _parse_flow_score(flow_data: dict, horse_name: str) -> tuple[float, str]:
    """展開スコアとペースシナリオを取得"""
    flow_score = 0.0
    pace = flow_data.get("main_pace", "")

    # 本線シナリオのflow_scoresから取得
    scenarios = flow_data.get("scenarios", [])
    for sc in scenarios:
        if sc.get("probability", 0) >= 40:
            scores = sc.get("flow_scores", {})
            if horse_name in scores:
                flow_score = scores[horse_name]
            pace = sc.get("pace", pace)
            break

    if flow_score == 0 and scenarios:
        scores = scenarios[0].get("flow_scores", {})
        if horse_name in scores:
            flow_score = scores[horse_name]

    return flow_score, pace


def _parse_recent_runs(runs_data: dict, horse_name: str) -> tuple[list[dict], dict]:
    """直近走データと前走情報を解析"""
    runs = []
    prev = {}

    for h in runs_data.get("horses", []):
        if h.get("horse_name") == horse_name:
            runs = h.get("runs", [])
            if runs:
                prev = runs[0]  # 最新走 = 前走
            break

    return runs, prev


def fetch_all_horses(date: str, race_type: str = "nar") -> list[HorseData]:
    """
    指定日の全レースから全馬のHorseDataを取得
    5カテゴリ100点方式に必要な全データを含む
    """
    all_horses = []

    races = fetch_races(date, race_type)
    logger.info(f"  {len(races)} レース取得")

    for race in races:
        race_id = race["race_id"]
        headcount = race.get("headcount", 0)

        if headcount < MIN_HORSES:
            continue

        try:
            # 1. 出馬表取得
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
            distance = entries_data.get("distance", race.get("distance", ""))
            track_condition = entries_data.get("track_condition", "良")

            # オッズ取得
            odds_map = {}
            for e in entries:
                if e.get("odds"):
                    odds_map[e["horse_number"]] = e["odds"]

            # Fallback: オッズが全て0の場合、Data API経由でリアルタイムオッズ取得
            if not odds_map:
                try:
                    import requests as _req
                    _api_base = os.getenv("DLOGIC_API_URL", "http://localhost:5000")
                    _resp = _req.get(
                        f"{_api_base}/api/data/odds/{race_id}",
                        params={"type": race_type},
                        timeout=30,
                    )
                    if _resp.ok:
                        _odds_data = _resp.json().get("odds", {})
                        for _num_str, _val in _odds_data.items():
                            try:
                                odds_map[int(_num_str)] = float(_val)
                            except (ValueError, TypeError):
                                pass
                    if odds_map:
                        logger.info(f"  Odds fallback: {len(odds_map)} horses via API")
                except Exception as _e:
                    logger.warning(f"  Odds fallback failed: {_e}")

            # 共通パラメータ
            analysis_params = {
                "race_id": race_id,
                "horses": horses,
                "horse_numbers": horse_numbers,
                "jockeys": jockeys,
                "posts": posts,
                "venue": venue,
                "distance": distance,
                "track_condition": track_condition,
            }

            # 2. 予想取得
            predictions = fetch_predictions(**analysis_params)

            # 3. 展開予想取得
            flow_data = _fetch_race_flow(race_id, analysis_params)

            # 4. 直近走データ取得
            runs_data = _fetch_recent_runs(race_id, analysis_params)

            # 5. 騎手分析取得
            jockey_data = _fetch_jockey_analysis(race_id, analysis_params)

            # AI評価の計算
            engine_results = predictions.get("engines", {})
            all_scores = {}
            engine_support = {}
            ai_ranks = {}

            for i, (name, num) in enumerate(zip(horses, horse_numbers)):
                ai_score = 0
                engines = []
                for eng_name, eng_data in engine_results.items():
                    rankings = eng_data.get("rankings", [])
                    for r in rankings:
                        if r.get("horse_number") == num or r.get("horse_name") == name:
                            rank = r.get("rank", 99)
                            if rank <= 5:
                                score_add = {1: 100, 2: 80, 3: 60, 4: 40, 5: 20}.get(rank, 10)
                                ai_score += score_add
                                engines.append(eng_name)
                            break
                all_scores[num] = ai_score
                engine_support[num] = engines

            # MetaLogicの順位をai_rankに
            metalogic = engine_results.get("MetaLogic", engine_results.get("metalogic", {}))
            for r in metalogic.get("rankings", []):
                num = r.get("horse_number")
                if num:
                    ai_ranks[num] = r.get("rank", 99)

            # スコア正規化
            score_sum = sum(s for s in all_scores.values() if s > 0)

            # 騎手データの展開
            jockey_post_stats = jockey_data.get("jockey_post_stats", {})
            jockey_course_stats = jockey_data.get("jockey_course_stats", {})

            for i, (name, num) in enumerate(zip(horses, horse_numbers)):
                ai_score = all_scores.get(num, 0)
                engines = engine_support.get(num, [])
                odds = odds_map.get(num, 0)
                jockey = jockeys[i] if i < len(jockeys) else ""
                post = posts[i] if i < len(posts) else 0

                # AI勝率 (スコアベース正規化)
                if ai_score > 0 and score_sum > 0:
                    ai_win_prob = ai_score / score_sum
                else:
                    ai_win_prob = 0.0

                # 信頼度
                total_engines = max(len(engine_results), 1)
                confidence = len(engines) / total_engines

                # 展開データ解析
                running_style, same_style_count, pace_advantage = _parse_running_style(flow_data, name)
                flow_score, pace_scenario = _parse_flow_score(flow_data, name)

                # 直近走データ
                recent_runs, prev_run = _parse_recent_runs(runs_data, name)

                # 騎手データ
                jps = jockey_post_stats.get(jockey, {})
                jcs = jockey_course_stats.get(jockey, {})

                horse_data = HorseData(
                    race_id=race_id,
                    race_name=race_name,
                    track_name=venue,
                    race_number=race_number,
                    horse_number=num,
                    horse_name=name,
                    jockey_name=jockey,
                    odds_win=odds,
                    popularity_rank=99,
                    ai_win_prob=round(ai_win_prob, 4),
                    ai_score=ai_score,
                    ai_rank=ai_ranks.get(num, 99),
                    confidence_score=round(confidence, 2),
                    engine_support_count=len(engines),
                    engine_names=engines,
                    distance=distance,
                    track_condition=track_condition,
                    post_position=post,
                    running_style=running_style,
                    same_style_count=same_style_count,
                    pace_scenario=pace_scenario,
                    pace_advantage=pace_advantage,
                    flow_score=flow_score,
                    recent_runs=recent_runs,
                    prev_position=prev_run.get("position", 0) or 0,
                    prev_distance=prev_run.get("distance", ""),
                    prev_venue=prev_run.get("venue", ""),
                    prev_track_condition=prev_run.get("track_condition", ""),
                    prev_field_size=prev_run.get("field_size", 0) or 0,
                    jockey_post_fukusho=jps.get("fukusho_rate", 0),
                    jockey_course_fukusho=jcs.get("fukusho_rate", 0),
                    jockey_course_runs=jcs.get("total_runs", 0),
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

    horses_sorted = sorted(horses, key=lambda h: h.race_id)
    for race_id, group in groupby(horses_sorted, key=lambda h: h.race_id):
        race_horses = list(group)
        ranked = sorted(
            [h for h in race_horses if h.odds_win > 0],
            key=lambda h: h.odds_win,
        )
        for rank, h in enumerate(ranked, 1):
            h.popularity_rank = rank
