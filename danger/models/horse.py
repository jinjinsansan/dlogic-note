"""馬データモデル — 5カテゴリ100点方式対応"""
from dataclasses import dataclass, field


@dataclass
class HorseData:
    """1頭分の入力データ"""
    # 基本情報
    race_id: str
    race_name: str
    track_name: str
    race_number: int
    horse_number: int
    horse_name: str
    jockey_name: str
    odds_win: float
    popularity_rank: int

    # AI評価
    ai_win_prob: float  # 0.0〜1.0
    ai_score: float
    ai_rank: int = 99  # エンジン内部順位
    confidence_score: float = 0.0  # 0.0〜1.0
    engine_support_count: int = 0
    engine_names: list[str] = field(default_factory=list)

    # 今回の条件
    distance: str = ""
    track_condition: str = ""
    post_position: int = 0  # 枠番

    # 展開データ (race-flow API)
    running_style: str = ""  # 逃げ/先行/差し/追込
    same_style_count: int = 0  # 同型の数
    pace_scenario: str = ""  # ハイ/ミドル/スロー
    pace_advantage: list[str] = field(default_factory=list)  # 有利な脚質
    flow_score: float = 0.0  # 展開スコア (0-1)

    # 過去走データ (recent-runs API)
    recent_runs: list[dict] = field(default_factory=list)
    # 前走情報
    prev_position: int = 0  # 前走着順
    prev_distance: str = ""  # 前走距離
    prev_venue: str = ""  # 前走場所
    prev_track_condition: str = ""  # 前走馬場
    prev_field_size: int = 0  # 前走頭数

    # 騎手データ (jockey-analysis API)
    jockey_post_fukusho: float = 0.0  # 枠別複勝率
    jockey_course_fukusho: float = 0.0  # コース複勝率
    jockey_course_runs: int = 0  # コース騎乗数

    @property
    def market_prob(self) -> float:
        """市場勝率 = 1 / odds_win"""
        if self.odds_win <= 0:
            return 0.0
        return 1.0 / self.odds_win

    @property
    def distortion_diff(self) -> float:
        """歪み差 = ai_win_prob - market_prob (負=市場が過大評価)"""
        return self.ai_win_prob - self.market_prob

    @property
    def overbought_ratio(self) -> float:
        """買われすぎ倍率 = market_prob / ai_win_prob"""
        if self.ai_win_prob <= 0:
            return 99.0 if self.market_prob > 0 else 0.0
        return self.market_prob / self.ai_win_prob

    @property
    def fair_odds(self) -> float:
        """フェアオッズ = 1 / ai_win_prob"""
        if self.ai_win_prob <= 0:
            return 99.9
        return 1.0 / self.ai_win_prob

    @property
    def distance_change(self) -> str:
        """距離変化を判定"""
        if not self.distance or not self.prev_distance:
            return ""
        try:
            curr = int("".join(c for c in self.distance if c.isdigit()))
            prev = int("".join(c for c in self.prev_distance if c.isdigit()))
            diff = curr - prev
            if diff > 100:
                return "延長"
            elif diff < -100:
                return "短縮"
            return "同距離"
        except (ValueError, TypeError):
            return ""
