"""危険人気馬の判定結果モデル — 5カテゴリ100点方式"""
from dataclasses import dataclass, field
from .horse import HorseData


@dataclass
class ScoreBreakdown:
    """5カテゴリのスコア内訳"""
    popularity_bias: int = 0    # A. 人気先行度 (0-25)
    condition_mismatch: int = 0  # B. 条件ズレ度 (0-20)
    pace_risk: int = 0          # C. 展開不利度 (0-20)
    repeatability_risk: int = 0  # D. 再現性不安度 (0-20)
    value_risk: int = 0         # E. 期待値悪化度 (0-15)

    @property
    def total(self) -> int:
        return (self.popularity_bias + self.condition_mismatch +
                self.pace_risk + self.repeatability_risk + self.value_risk)

    def to_dict(self) -> dict:
        return {
            "popularity_bias": self.popularity_bias,
            "condition_mismatch": self.condition_mismatch,
            "pace_risk": self.pace_risk,
            "repeatability_risk": self.repeatability_risk,
            "value_risk": self.value_risk,
            "total": self.total,
        }

    @property
    def top_reasons(self) -> list[tuple[str, int]]:
        """スコア上位3カテゴリを返す"""
        items = [
            ("人気先行", self.popularity_bias),
            ("条件ズレ", self.condition_mismatch),
            ("展開不利", self.pace_risk),
            ("再現性不安", self.repeatability_risk),
            ("期待値悪化", self.value_risk),
        ]
        return sorted(items, key=lambda x: x[1], reverse=True)[:3]


@dataclass
class DangerResult:
    """危険人気馬の判定結果"""
    horse: HorseData
    danger_score: int
    danger_level: str  # "A", "B", "C"
    reason_summary: str
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    main_reasons: list[str] = field(default_factory=list)
    betting_note: str = ""
    danger_type: str = ""  # Type1-6の分類
    story: str = ""  # 具体的な危険ストーリー（note記事用）

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
            "rank": 0,
            "horse_name": h.horse_name,
            "race_name": h.race_name,
            "track_name": h.track_name,
            "race_number": h.race_number,
            "horse_number": h.horse_number,
            "jockey_name": h.jockey_name,
            "odds_win": h.odds_win,
            "popularity_rank": h.popularity_rank,
            "ai_win_prob": h.ai_win_prob,
            "ai_win_prob_pct": self.ai_win_prob_pct,
            "ai_rank": h.ai_rank,
            "market_prob": round(h.market_prob, 4),
            "market_prob_pct": self.market_prob_pct,
            "overbought_ratio": round(h.overbought_ratio, 1),
            "fair_odds": round(h.fair_odds, 1),
            "danger_score": self.danger_score,
            "danger_level": self.danger_level,
            "danger_type": self.danger_type,
            "score_breakdown": self.score_breakdown.to_dict(),
            "main_reasons": self.main_reasons,
            "betting_note": self.betting_note,
            "reason_summary": self.reason_summary,
        }
