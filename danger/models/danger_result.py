"""危険人気馬の判定結果モデル"""
from dataclasses import dataclass
from .horse import HorseData


@dataclass
class DangerResult:
    """危険人気馬の判定結果"""
    horse: HorseData
    danger_score: float
    danger_level: str  # "超危険", "強危険", "危険"
    reason_summary: str

    @property
    def market_prob_pct(self) -> float:
        return round(self.horse.market_prob * 100, 1)

    @property
    def ai_win_prob_pct(self) -> float:
        return round(self.horse.ai_win_prob * 100, 1)

    @property
    def distortion_diff_pct(self) -> float:
        return round(self.horse.distortion_diff * 100, 1)

    @property
    def confidence_pct(self) -> float:
        return round(self.horse.confidence_score * 100, 0)

    def to_dict(self) -> dict:
        h = self.horse
        return {
            "rank": 0,  # 呼び出し側でセット
            "horse_name": h.horse_name,
            "race_name": h.race_name,
            "track_name": h.track_name,
            "race_number": h.race_number,
            "horse_number": h.horse_number,
            "jockey_name": h.jockey_name,
            "odds_win": h.odds_win,
            "ai_win_prob": h.ai_win_prob,
            "ai_win_prob_pct": self.ai_win_prob_pct,
            "market_prob": round(h.market_prob, 4),
            "market_prob_pct": self.market_prob_pct,
            "distortion_diff": round(h.distortion_diff, 4),
            "distortion_diff_pct": self.distortion_diff_pct,
            "overbought_ratio": round(h.overbought_ratio, 1),
            "fair_odds": round(h.fair_odds, 1),
            "confidence_score": h.confidence_score,
            "confidence_pct": self.confidence_pct,
            "danger_score": round(self.danger_score, 2),
            "danger_level": self.danger_level,
            "reason_summary": self.reason_summary,
        }
