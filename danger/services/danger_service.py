"""危険人気馬の判定ロジック"""
from ..models.horse import HorseData
from ..models.danger_result import DangerResult


def calculate_danger_score(horse: HorseData) -> float:
    """危険度スコアを計算"""
    market_prob = horse.market_prob
    ai_prob = horse.ai_win_prob
    overbought = horse.overbought_ratio
    confidence = horse.confidence_score

    score = (
        (market_prob - ai_prob) * 100
        + max(0, overbought - 1.0) * 10
        + (1.0 - confidence) * 5
    )
    return score


def classify_danger_level(horse: HorseData) -> str:
    """危険レベルを判定"""
    diff = horse.distortion_diff
    overbought = horse.overbought_ratio
    confidence = horse.confidence_score
    pop = horse.popularity_rank

    # 超危険
    if diff <= -0.20 or overbought >= 3.0 or (confidence <= 0.30 and pop <= 3):
        return "超危険"
    # 強危険
    if diff <= -0.15 or overbought >= 2.5:
        return "強危険"
    return "危険"


def generate_reason(horse: HorseData, danger_level: str) -> str:
    """理由文を自動生成"""
    mp = round(horse.market_prob * 100, 1)
    ap = round(horse.ai_win_prob * 100, 1)
    ob = round(horse.overbought_ratio, 1)
    conf = round(horse.confidence_score * 100, 0)

    parts = []
    parts.append(f"市場は{mp}%を織り込む一方、AIは{ap}%と判定。市場は約{ob}倍買いすぎ。")

    if horse.confidence_score <= 0.30:
        parts.append(f"AI信頼度{conf:.0f}%と低く、人気先行の可能性。")
    elif horse.engine_support_count <= 1:
        parts.append(f"AI評価エンジン{horse.engine_support_count}本のみ。裏付けが薄い。")

    if danger_level == "超危険":
        parts.append(f"単勝{horse.odds_win}倍は過大評価。回避推奨。")
    elif danger_level == "強危険":
        parts.append(f"単勝{horse.odds_win}倍は割高。注意が必要。")

    return " ".join(parts)


def find_danger_horses(horses: list[HorseData], top_n: int = 3) -> list[DangerResult]:
    """
    危険人気馬を抽出してランキング

    基本条件:
    - popularity_rank <= 5
    - odds_win <= 5.0
    - ai_win_prob > 0
    - market_prob > ai_win_prob
    """
    candidates = []

    for horse in horses:
        # 除外条件
        if horse.ai_win_prob <= 0:
            continue
        if horse.odds_win <= 0:
            continue
        if horse.popularity_rank > 5:
            continue
        if horse.odds_win > 5.0:
            continue
        # 市場が過大評価している馬のみ
        if horse.market_prob <= horse.ai_win_prob:
            continue

        danger_score = calculate_danger_score(horse)
        danger_level = classify_danger_level(horse)
        reason = generate_reason(horse, danger_level)

        candidates.append(DangerResult(
            horse=horse,
            danger_score=danger_score,
            danger_level=danger_level,
            reason_summary=reason,
        ))

    # スコア降順でソート
    candidates.sort(key=lambda x: x.danger_score, reverse=True)
    return candidates[:top_n]
