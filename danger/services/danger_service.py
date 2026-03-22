"""危険人気馬の判定ロジック — 5カテゴリ100点方式

スコア構造:
  A. 人気先行度:    0〜25点
  B. 条件ズレ度:    0〜20点
  C. 展開不利度:    0〜20点
  D. 再現性不安度:  0〜20点
  E. 期待値悪化度:  0〜15点
  合計: 0〜100点

判定:
  80〜100: 危険度A (過剰人気の可能性が高い)
  65〜79:  危険度B (人気ほどの信頼は置きにくい)
  50〜64:  危険度C (妙味が薄い)
  0〜49:   危険指定なし
"""
from ..models.horse import HorseData
from ..models.danger_result import DangerResult, ScoreBreakdown


# ---------------------------------------------------------------------------
# A. 人気先行度 (0-25)
# ---------------------------------------------------------------------------
def _score_popularity_bias(h: HorseData) -> tuple[int, list[str]]:
    """人気の理由が実力ではなく「わかりやすい材料」で売れていないか"""
    score = 0
    reasons = []

    # A1: 前走着順で売れすぎ (0-8)
    if h.prev_position == 1 and h.ai_rank >= 4:
        score += 8
        reasons.append("前走1着だがAI評価は低い")
    elif h.prev_position == 1 and h.ai_rank >= 3:
        score += 5
        reasons.append("前走1着の割にAI評価が追いついていない")
    elif h.prev_position <= 3 and h.ai_rank >= 5:
        score += 6
        reasons.append("近走着順で売れている可能性")

    # A2: 騎手人気先行 (0-5)
    if h.jockey_course_runs > 0 and h.jockey_course_fukusho < 20:
        score += 4
        reasons.append("騎手のコース実績が低い")
    elif h.jockey_course_runs == 0:
        score += 2  # データ不足

    # A3: AI評価との乖離 (0-8)
    # 人気上位なのにAIが全く評価していない
    if h.popularity_rank <= 3 and h.engine_support_count == 0:
        score += 8
        reasons.append("AIエンジンが全く支持していない人気馬")
    elif h.popularity_rank <= 3 and h.engine_support_count <= 1:
        score += 5
        reasons.append("AI支持が薄い割に人気")
    elif h.popularity_rank <= 2 and h.ai_rank >= 5:
        score += 6
        reasons.append("人気と内部評価の差が大きい")

    # A4: オッズが実力以上に低い (0-4)
    if h.overbought_ratio >= 3.0:
        score += 4
        reasons.append(f"市場は約{h.overbought_ratio:.1f}倍買いすぎ")
    elif h.overbought_ratio >= 2.0:
        score += 2

    return min(score, 25), reasons


# ---------------------------------------------------------------------------
# B. 条件ズレ度 (0-20)
# ---------------------------------------------------------------------------
def _score_condition_mismatch(h: HorseData) -> tuple[int, list[str]]:
    """前走と比べて今回の条件がズレていないか"""
    score = 0
    reasons = []

    # B1: 距離変化 (0-6)
    dc = h.distance_change
    if dc == "延長":
        score += 5
        reasons.append("距離延長で未知の距離に挑む")
    elif dc == "短縮":
        score += 3
        reasons.append("距離短縮で忙しい競馬になる可能性")

    # B2: 会場変更 (0-4)
    if h.prev_venue and h.track_name and h.prev_venue != h.track_name:
        score += 3
        reasons.append(f"前走{h.prev_venue}→今回{h.track_name}のコース替わり")

    # B3: 馬場変化 (0-4)
    if h.prev_track_condition and h.track_condition:
        prev_good = h.prev_track_condition in ("良", "")
        curr_bad = h.track_condition in ("重", "不良", "稍重")
        if prev_good and curr_bad:
            score += 4
            reasons.append(f"良馬場好走→{h.track_condition}馬場で不安")

    # B4: 枠順不利 (0-3)
    # 外枠の先行馬は不利
    if h.post_position >= 7 and h.running_style in ("逃げ", "先行"):
        score += 3
        reasons.append("外枠で先行は展開的にロスが大きい")

    # B5: 昇級初戦（前走が下級条件で好走） (0-3)
    # 簡易判定: 前走少頭数で好走 = 相手が弱かった可能性
    if h.prev_position <= 2 and h.prev_field_size > 0 and h.prev_field_size <= 8:
        score += 3
        reasons.append("前走は少頭数戦で好走、相手強化の可能性")

    return min(score, 20), reasons


# ---------------------------------------------------------------------------
# C. 展開不利度 (0-20)
# ---------------------------------------------------------------------------
def _score_pace_risk(h: HorseData) -> tuple[int, list[str]]:
    """展開が向きにくいか"""
    score = 0
    reasons = []

    # C1: 同型多数 (0-6)
    if h.running_style in ("逃げ", "先行") and h.same_style_count >= 3:
        score += 6
        reasons.append(f"同型{h.same_style_count}頭で先行争い激化")
    elif h.running_style in ("逃げ", "先行") and h.same_style_count >= 2:
        score += 3
        reasons.append("先行勢が多くペースが厳しくなる可能性")

    # C2: ペースと脚質の不一致 (0-6)
    if h.pace_scenario == "スローペース" and h.running_style in ("差し", "追込"):
        score += 6
        reasons.append("スロー想定で差し届かない懸念")
    elif h.pace_scenario == "ハイペース" and h.running_style in ("逃げ", "先行"):
        score += 5
        reasons.append("ハイペース想定で先行馬に厳しい")

    # C3: 展開スコアが低い (0-5)
    if h.flow_score > 0 and h.flow_score < 0.4:
        score += 5
        reasons.append("展開シミュレーションで不利判定")
    elif h.flow_score > 0 and h.flow_score < 0.5:
        score += 3

    # C4: 有利脚質ではない (0-3)
    if h.pace_advantage and h.running_style and h.running_style not in h.pace_advantage:
        score += 3
        reasons.append(f"想定ペースでは{'/'.join(h.pace_advantage)}が有利")

    return min(score, 20), reasons


# ---------------------------------------------------------------------------
# D. 再現性不安度 (0-20)
# ---------------------------------------------------------------------------
def _score_repeatability_risk(h: HorseData) -> tuple[int, list[str]]:
    """前走の好走が今回も再現可能か"""
    score = 0
    reasons = []

    runs = h.recent_runs
    if not runs:
        # データなし = 未知数 = やや加点
        score += 5
        reasons.append("過去走データ不足で裏付けが取れない")
        return min(score, 20), reasons

    # D1: 前走好走だが今回条件悪化 (0-6)
    if h.prev_position <= 2:
        mismatch = 0
        if h.distance_change in ("延長", "短縮"):
            mismatch += 1
        if h.prev_venue and h.track_name and h.prev_venue != h.track_name:
            mismatch += 1
        if h.prev_track_condition != h.track_condition and h.track_condition:
            mismatch += 1
        if mismatch >= 2:
            score += 6
            reasons.append("前走好走も今回は条件が大きく変わる")
        elif mismatch == 1:
            score += 3
            reasons.append("前走好走だが条件替わりに注意")

    # D2: 近走成績の安定性 (0-5)
    # 直近3走で着順が大きくバラつく = 再現性低い
    positions = []
    for r in runs[:3]:
        pos = r.get("position")
        if pos and isinstance(pos, (int, float)) and pos > 0:
            positions.append(int(pos))
    if len(positions) >= 2:
        avg = sum(positions) / len(positions)
        variance = sum((p - avg) ** 2 for p in positions) / len(positions)
        if variance > 10:
            score += 5
            reasons.append("近走着順にバラつきがあり安定感に欠ける")
        elif variance > 5:
            score += 3

    # D3: 前走少頭数・弱メン (0-5)
    if h.prev_position <= 2 and h.prev_field_size > 0 and h.prev_field_size <= 9:
        score += 4
        reasons.append("前走は少頭数で相手に恵まれた可能性")

    # D4: 連勝中の過信 (0-4)
    consecutive_wins = 0
    for r in runs[:3]:
        if r.get("position") == 1:
            consecutive_wins += 1
        else:
            break
    if consecutive_wins >= 2 and h.popularity_rank <= 2:
        score += 4
        reasons.append("連勝中で人気集中、反動リスク")

    return min(score, 20), reasons


# ---------------------------------------------------------------------------
# E. 期待値悪化度 (0-15)
# ---------------------------------------------------------------------------
def _score_value_risk(h: HorseData) -> tuple[int, list[str]]:
    """市場人気と内部評価の乖離からオッズ妙味を判定"""
    score = 0
    reasons = []

    # E1: 順位差方式 (0-8)
    rank_gap = h.popularity_rank - h.ai_rank  # 負 = AIより人気がある
    if h.ai_rank >= 6 and h.popularity_rank <= 2:
        score += 8
        reasons.append(f"人気{h.popularity_rank}位だがAI評価は{h.ai_rank}位")
    elif h.ai_rank >= 4 and h.popularity_rank <= 2:
        score += 5
        reasons.append(f"人気に対してAI評価が{h.ai_rank}位と低い")
    elif h.ai_rank >= 5 and h.popularity_rank <= 3:
        score += 4

    # E2: 率差方式 (0-7)
    if h.market_prob > 0 and h.ai_win_prob >= 0:
        prob_gap = h.market_prob - h.ai_win_prob
        if prob_gap > 0.20:
            score += 7
            reasons.append("市場評価とAI評価の乖離が非常に大きい")
        elif prob_gap > 0.15:
            score += 5
            reasons.append("市場がAIより大幅に高く評価")
        elif prob_gap > 0.10:
            score += 3
            reasons.append("オッズに対して妙味が薄い")

    return min(score, 15), reasons


# ---------------------------------------------------------------------------
# 補正ルール
# ---------------------------------------------------------------------------
def _apply_corrections(h: HorseData, breakdown: ScoreBreakdown) -> int:
    """補正を適用して最終スコアを返す"""
    total = breakdown.total

    # 多重不安補正: 3カテゴリ以上で高スコア(各カテゴリの50%以上)なら+5
    high_count = sum([
        breakdown.popularity_bias >= 13,
        breakdown.condition_mismatch >= 10,
        breakdown.pace_risk >= 10,
        breakdown.repeatability_risk >= 10,
        breakdown.value_risk >= 8,
    ])
    if high_count >= 3:
        total += 5

    # 低人気除外: 6番人気以下は対象外
    if h.popularity_rank > 5:
        total = 0

    return min(total, 100)


# ---------------------------------------------------------------------------
# 危険度判定
# ---------------------------------------------------------------------------
def _classify_danger(score: int) -> str:
    if score >= 80:
        return "A"
    elif score >= 65:
        return "B"
    elif score >= 50:
        return "C"
    return ""


def _classify_danger_type(h: HorseData, breakdown: ScoreBreakdown) -> str:
    """危険パターン分類"""
    top = breakdown.top_reasons[0][0] if breakdown.top_reasons else ""
    if top == "人気先行":
        if h.prev_position == 1:
            return "Type1:前走着順先行型"
        return "Type2:人気先行型"
    elif top == "条件ズレ":
        return "Type5:条件替わり軽視型"
    elif top == "展開不利":
        return "Type6:展開逆風見落とし型"
    elif top == "再現性不安":
        return "Type4:昇級過信型"
    elif top == "期待値悪化":
        return "Type3:過剰評価型"
    return ""


def _generate_betting_note(level: str) -> str:
    """馬券での扱い方"""
    if level == "A":
        return "軸には不向き。消しも視野に入れたい。"
    elif level == "B":
        return "軸には不向き。押さえまでが無難。"
    elif level == "C":
        return "過信は禁物。相手までが妥当。"
    return ""


def _generate_story(h: HorseData, breakdown: ScoreBreakdown) -> str:
    """各馬固有の具体的なストーリーを生成

    ルール:
    - 展開・条件・再現性を具体的に書く（抽象禁止）
    - 各馬に"キャラ"をつける（展開型/オッズ型/前走過信型）
    - オッズ視点を必ず入れる
    - 「期待値」は使わず「オッズに見合わない」「リスクに対してリターン」で表現
    """
    parts = []

    # --- 展開面のストーリー ---
    if breakdown.pace_risk >= 10:
        if h.running_style in ("逃げ", "先行") and h.same_style_count >= 3:
            parts.append(
                f"今回は同型の先行馬が{h.same_style_count}頭おり、"
                "ペースが上がる可能性が高い。\n"
                "前走のような「楽な形」になりにくい。"
            )
        elif h.running_style in ("逃げ", "先行") and h.same_style_count >= 2:
            parts.append(
                "この馬は「自分の形で運べてこそ」のタイプ。\n"
                "今回は同型の存在でポジションが不安定になりやすい。"
            )
        elif h.running_style in ("差し", "追込") and h.pace_scenario == "スローペース":
            parts.append(
                "スローペースが想定され、前が止まらない展開になりやすい。\n"
                "差し脚質のこの馬には厳しい流れ。"
            )
        elif h.pace_scenario == "ハイペース" and h.running_style in ("逃げ", "先行"):
            parts.append(
                "ハイペースが想定される中での先行は消耗が大きい。\n"
                "最後まで脚が持つかが不安。"
            )
        else:
            parts.append(
                "展開面で不利を受けやすい状況。\n"
                "能力があっても今回は噛み合わない可能性がある。"
            )

    # --- 条件面のストーリー ---
    if breakdown.condition_mismatch >= 5:
        dc = h.distance_change
        if dc == "延長":
            parts.append(
                "さらに今回は距離延長。\n"
                "最後まで同じパフォーマンスを維持できるかは不透明。"
            )
        elif dc == "短縮":
            parts.append(
                "距離短縮で忙しい競馬になる可能性があり、\n"
                "前走のリズムとは異なるレースになりそう。"
            )

        if h.prev_venue and h.track_name and h.prev_venue != h.track_name:
            parts.append(
                f"コースも前走{h.prev_venue}から{h.track_name}に替わり、適性面は未知数。"
            )

        if h.track_condition in ("重", "不良", "稍重") and h.prev_track_condition in ("良", ""):
            parts.append(
                f"馬場も{h.track_condition}に悪化。\n"
                "良馬場での好走がそのまま通用するかは疑問。"
            )

    # --- 再現性のストーリー ---
    if breakdown.repeatability_risk >= 6:
        if h.prev_position <= 2 and h.prev_field_size > 0 and h.prev_field_size <= 9:
            parts.append(
                "前走は好走しているが、相手関係も今回より楽だった。\n"
                "展開の恩恵もあった可能性があり、再現性はやや疑問。"
            )
        elif h.prev_position <= 2:
            parts.append(
                "前走は好走しているが、展開がハマった面もある。\n"
                "今回は前走と同じ評価を与えるのは危険。"
            )
        else:
            parts.append(
                "近走の成績にバラつきがあり、安定感に欠ける。\n"
                "人気ほどの信頼を置くには材料不足。"
            )

    # --- 人気先行のストーリー（展開/条件が弱い場合のフォールバック） ---
    if not parts and breakdown.popularity_bias >= 15:
        if h.prev_position == 1:
            parts.append(
                "前走の勝利で人気を集めているが、\n"
                "中身を見ると条件に恵まれた部分もある。\n"
                "今回の条件で同じ競馬ができるかは不透明。"
            )
        else:
            parts.append(
                "人気の理由は近走のインパクト。\n"
                "ただし中身を見ると、人気ほどの裏付けは感じにくい。"
            )

    # フォールバック
    if not parts:
        parts.append(
            "独自分析では、この人気で買うにはリスクが高い。\n"
            "能力は否定しないが、今回は買い時ではない。"
        )

    # --- オッズ視点（必ず入れる） ---
    if h.odds_win <= 2.0:
        parts.append(
            f"この条件で単勝{h.odds_win}倍はリスクに対してリターンが合わない。\n"
            "軸にしてしまうと馬券全体を落とす可能性がある。"
        )
    elif h.odds_win <= 5.0:
        parts.append(
            f"単勝{h.odds_win}倍という人気だが、\n"
            "このリスクを背負ってまで買う妙味は薄い。"
        )
    else:
        parts.append(
            f"単勝{h.odds_win}倍のオッズに見合う信頼度があるかは疑問。"
        )

    return "\n\n".join(parts)


def _generate_reason_summary(h: HorseData, story: str, level: str) -> str:
    """記事外（JSON/Markdown）向けの短い理由サマリー"""
    # ストーリーの最初の2文を使う
    sentences = [s.strip() for s in story.replace("\n", "。").split("。") if s.strip()]
    summary = "。".join(sentences[:2]) + "。"

    if level == "A":
        summary += " 人気ほどの信頼は置きにくく、回避推奨。"
    elif level == "B":
        summary += " 人気ほどの信頼は置きにくい。"

    return summary


# ---------------------------------------------------------------------------
# メイン判定関数
# ---------------------------------------------------------------------------
def find_danger_horses(horses: list[HorseData], top_n: int = 5) -> list[DangerResult]:
    """
    危険人気馬を5カテゴリ100点方式で抽出

    対象条件:
    - popularity_rank <= 5 (想定5番人気以内)
    - odds_win > 0
    - odds_win <= 10.0 (人気馬のみ)
    """
    candidates = []

    for h in horses:
        # 除外条件
        if h.odds_win <= 0:
            continue
        if h.popularity_rank > 5:
            continue
        if h.odds_win > 10.0:
            continue

        # 5カテゴリ採点
        all_reasons = []

        a_score, a_reasons = _score_popularity_bias(h)
        all_reasons.extend(a_reasons)

        b_score, b_reasons = _score_condition_mismatch(h)
        all_reasons.extend(b_reasons)

        c_score, c_reasons = _score_pace_risk(h)
        all_reasons.extend(c_reasons)

        d_score, d_reasons = _score_repeatability_risk(h)
        all_reasons.extend(d_reasons)

        e_score, e_reasons = _score_value_risk(h)
        all_reasons.extend(e_reasons)

        breakdown = ScoreBreakdown(
            popularity_bias=a_score,
            condition_mismatch=b_score,
            pace_risk=c_score,
            repeatability_risk=d_score,
            value_risk=e_score,
        )

        total = _apply_corrections(h, breakdown)
        level = _classify_danger(total)

        danger_type = _classify_danger_type(h, breakdown)
        betting_note = _generate_betting_note(level) if level else "過信は禁物。相手までが妥当。"
        story = _generate_story(h, breakdown)
        # Assign minimum level C for top-N fallback (will be set below)
        if not level:
            level = "C"
        reason_summary = _generate_reason_summary(h, story, level)

        candidates.append(DangerResult(
            horse=h,
            danger_score=total,
            danger_level=level,
            reason_summary=reason_summary,
            score_breakdown=breakdown,
            main_reasons=all_reasons[:5],
            betting_note=betting_note,
            danger_type=danger_type,
            story=story,
        ))

    candidates.sort(key=lambda x: x.danger_score, reverse=True)

    # Ensure top_n results: if fewer than top_n scored 50+, include lower-scored
    # horses but cap at minimum score 20 to avoid noise
    result = [c for c in candidates if c.danger_score >= 50][:top_n]
    if len(result) < top_n:
        remaining = [c for c in candidates if c.danger_score < 50 and c.danger_score >= 20]
        result.extend(remaining[:top_n - len(result)])

    if not result and candidates:
        result = candidates[:top_n]

    if not candidates and horses:
        with_odds = [h for h in horses if h.odds_win > 0]
        source = with_odds if with_odds else horses

        def _fallback_key(h: HorseData) -> tuple:
            if h.odds_win > 0:
                return (0, h.odds_win)
            if h.ai_rank and h.ai_rank < 99:
                return (1, h.ai_rank)
            return (2, h.horse_number)

        fallback_horses = sorted(source, key=_fallback_key)[:top_n]
        fallback_results = []
        for h in fallback_horses:
            breakdown = ScoreBreakdown()
            level = "C"
            betting_note = _generate_betting_note(level)
            story = _generate_story(h, breakdown)
            reason_summary = _generate_reason_summary(h, story, level)
            fallback_results.append(DangerResult(
                horse=h,
                danger_score=breakdown.total,
                danger_level=level,
                reason_summary=reason_summary,
                score_breakdown=breakdown,
                main_reasons=[],
                betting_note=betting_note,
                danger_type="",
                story=story,
            ))
        return fallback_results

    return result
