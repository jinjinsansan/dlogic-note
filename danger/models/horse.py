"""馬データモデル"""
from dataclasses import dataclass, field


@dataclass
class HorseData:
    """1頭分の入力データ"""
    race_id: str
    race_name: str
    track_name: str
    race_number: int
    horse_number: int
    horse_name: str
    jockey_name: str
    odds_win: float
    popularity_rank: int
    ai_win_prob: float  # 0.0〜1.0
    ai_score: float
    confidence_score: float  # 0.0〜1.0
    engine_support_count: int
    engine_names: list[str] = field(default_factory=list)

    @property
    def market_prob(self) -> float:
        """市場勝率 = 1 / odds_win"""
        if self.odds_win <= 0:
            return 0.0
        return 1.0 / self.odds_win

    @property
    def distortion_diff(self) -> float:
        """歪み差 = ai_win_prob - market_prob"""
        return self.ai_win_prob - self.market_prob

    @property
    def overbought_ratio(self) -> float:
        """買われすぎ倍率 = market_prob / ai_win_prob"""
        if self.ai_win_prob <= 0:
            return 0.0
        return self.market_prob / self.ai_win_prob

    @property
    def fair_odds(self) -> float:
        """フェアオッズ = 1 / ai_win_prob"""
        if self.ai_win_prob <= 0:
            return 0.0
        return 1.0 / self.ai_win_prob
