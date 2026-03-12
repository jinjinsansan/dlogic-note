"""
DLogicAdapter — VPS APIの出力を統一JSONに変換する
仕様書の統一フォーマットに合わせる
"""
import requests
import logging
from typing import Optional

from config import DLOGIC_API_URL

logger = logging.getLogger(__name__)


def fetch_races(date: str, race_type: str = "jra") -> list[dict]:
    """レース一覧を取得（dlogic-agentのスクレイパーと同等）"""
    resp = requests.post(
        f"{DLOGIC_API_URL}/api/chat",
        json={"message": f"今日の{'JRA' if race_type == 'jra' else '地方競馬'}"},
        timeout=30,
    )
    # 注: これはチャットAPI経由。直接スクレイピングの方が効率的なので
    # 将来的にはdlogic-agentのスクレイパーを共有モジュール化する
    raise NotImplementedError("Phase 1で実装: VPS APIに直接レース一覧エンドポイント追加")


def fetch_entries(race_id: str, race_type: str = "jra") -> dict:
    """出馬表を取得"""
    raise NotImplementedError("Phase 1で実装")


def fetch_predictions(
    race_id: str,
    horses: list[str],
    horse_numbers: list[int],
    jockeys: list[str],
    posts: list[int],
    venue: str = "",
    distance: str = "",
    track_condition: str = "良",
) -> dict:
    """4エンジン予想を取得"""
    payload = {
        "race_id": race_id,
        "horses": horses,
        "horse_numbers": horse_numbers,
        "jockeys": jockeys,
        "posts": posts,
        "venue": venue,
        "distance": distance,
        "track_condition": track_condition,
    }
    resp = requests.post(
        f"{DLOGIC_API_URL}/api/v2/predictions/newspaper",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_odds(race_id: str, race_type: str = "jra") -> dict:
    """リアルタイムオッズを取得"""
    raise NotImplementedError("Phase 1で実装: オッズスクレイパー連携")


def fetch_analysis(race_id: str, endpoint: str, params: dict) -> dict:
    """分析API汎用呼び出し（展開/騎手/血統/近走）"""
    resp = requests.post(
        f"{DLOGIC_API_URL}/api/v2/analysis/{endpoint}",
        json=params,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def build_unified_race_json(
    race_id: str,
    race_info: dict,
    predictions: dict,
    odds: Optional[dict] = None,
) -> dict:
    """
    仕様書の統一JSONフォーマットに変換

    Returns:
        {
            "race_id": "20260313_TOKYO_11R",
            "horses": [
                {
                    "horse_id": "...",
                    "name": "サンプルホース",
                    "ai_score": 82.4,
                    "win_prob": 0.23,
                    "place_prob": 0.51,
                    "fair_odds": 4.35,
                    "ai_rank": 1,
                    "confidence_score": 0.78,
                    "logic_name": "MetaLogic",
                    "market_odds": 3.5,
                    "popularity": 1,
                    "value_gap": 0.85  # fair_odds / market_odds
                }
            ]
        }
    """
    horses = race_info.get("horses", [])
    horse_numbers = race_info.get("horse_numbers", [])
    jockeys = race_info.get("jockeys", [])

    # 4エンジンの順位から統合スコアを算出
    engine_ranks = {}  # horse_number -> {engine: rank}
    for engine_name in ["dlogic", "ilogic", "viewlogic", "metalogic"]:
        ranked_numbers = predictions.get(engine_name, [])
        for rank_idx, num in enumerate(ranked_numbers):
            if num not in engine_ranks:
                engine_ranks[num] = {}
            engine_ranks[num][engine_name] = rank_idx + 1

    total_horses = len(horses)
    result_horses = []

    for i, (name, num) in enumerate(zip(horses, horse_numbers)):
        ranks = engine_ranks.get(num, {})

        # AI総合スコア: 各エンジン順位の逆数加重平均 (1位=100, 最下位=0)
        if ranks:
            scores = []
            for eng in ["dlogic", "ilogic", "viewlogic", "metalogic"]:
                r = ranks.get(eng)
                if r is not None:
                    scores.append(max(0, 100 - (r - 1) * (100 / total_horses)))
            ai_score = round(sum(scores) / len(scores), 1) if scores else 0
        else:
            ai_score = 0

        # MetaLogicの順位をai_rankとする
        meta_rank = ranks.get("metalogic", total_horses)

        # 勝率・複勝率の簡易推定（オッズから）
        market_odds = None
        win_prob = None
        place_prob = None
        fair_odds = None
        value_gap = None

        if odds and num in odds:
            market_odds = odds[num]
            # オッズから勝率推定 (控除率20%考慮)
            win_prob = round(0.8 / market_odds, 3) if market_odds > 0 else 0
            place_prob = round(min(1.0, win_prob * 2.5), 3)

        # AI fair_odds: AIスコアから逆算
        if ai_score > 0:
            implied_prob = ai_score / 100
            fair_odds = round(0.8 / implied_prob, 2) if implied_prob > 0 else 99.9

        # バリューギャップ（fair_odds / market_odds）
        # > 1.0 = 市場が過大評価（危険人気）、< 1.0 = 市場が過小評価（妙味あり）
        if fair_odds and market_odds and market_odds > 0:
            value_gap = round(fair_odds / market_odds, 2)

        # confidence: データ充足度（4エンジン中何個にランクインしているか）
        confidence = round(len(ranks) / 4, 2)

        result_horses.append({
            "horse_number": num,
            "name": name,
            "jockey": jockeys[i] if i < len(jockeys) else "",
            "ai_score": ai_score,
            "ai_rank": meta_rank,
            "win_prob": win_prob,
            "place_prob": place_prob,
            "fair_odds": fair_odds,
            "market_odds": market_odds,
            "value_gap": value_gap,
            "confidence_score": confidence,
            "logic_name": "MetaLogic",
            "engine_ranks": ranks,
        })

    # ai_rankでソート
    result_horses.sort(key=lambda x: x["ai_rank"])

    return {
        "race_id": race_id,
        "venue": race_info.get("venue", ""),
        "race_number": race_info.get("race_number", 0),
        "race_name": race_info.get("race_name", ""),
        "distance": race_info.get("distance", ""),
        "track_condition": race_info.get("track_condition", "良"),
        "horses_count": total_horses,
        "horses": result_horses,
    }


def extract_danger_horses(unified_json: dict, top_n: int = 3) -> list[dict]:
    """
    危険人気馬を抽出
    条件: 人気上位（オッズ低い）なのにAIスコアが低い馬
    value_gap > 1.5 = AI的には過大評価されている
    """
    horses = unified_json.get("horses", [])
    danger = [
        h for h in horses
        if h.get("value_gap") and h["value_gap"] > 1.5
        and h.get("market_odds") and h["market_odds"] < 10.0  # 人気馬のみ
    ]
    danger.sort(key=lambda x: x["value_gap"], reverse=True)
    return danger[:top_n]


def extract_value_horses(unified_json: dict, top_n: int = 5) -> list[dict]:
    """
    AI期待値馬ランキング
    条件: AIスコアが高く、市場オッズとの乖離がある（妙味あり）
    """
    horses = unified_json.get("horses", [])
    # ai_scoreでソート
    ranked = sorted(horses, key=lambda x: x.get("ai_score", 0), reverse=True)
    return ranked[:top_n]
