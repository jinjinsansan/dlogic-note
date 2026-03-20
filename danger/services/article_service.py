"""X投稿文・note記事の生成 — chatGPT仕様書準拠

絶対ルール:
- サイト名・外部サービス名を出さない
- 常に「独自AI分析」「独自ロジック」「独自指数」で統一
- 断定しすぎない
- 初心者にもわかる表現
- 売り込みすぎない
"""
from ..models.danger_result import DangerResult


# ---------------------------------------------------------------------------
# 表現辞書
# ---------------------------------------------------------------------------
_LEVEL_DESC = {
    "A": "過剰人気の可能性が高く、馬券ではかなり慎重に見たい",
    "B": "人気ほどの信頼は置きにくく、押さえまでが無難",
    "C": "能力は認めても人気とのバランス面で妙味が薄い",
}

_BETTING_NOTE = {
    "A": "消しも視野。少なくとも軸にはしにくい。",
    "B": "軸としての信頼度は下げたい。押さえまでが無難。",
    "C": "相手までの評価。妙味面では慎重に見たい。",
}

_REASON_REWRITE = {
    "近走着順で売れている可能性": "前走着順で評価されすぎている可能性",
    "AIエンジンが全く支持していない人気馬": "独自AI分析では人気ほどの裏付けが取れない",
    "AI支持が薄い割に人気": "独自指数では支持が薄いのに市場で買われている",
    "人気と内部評価の差が大きい": "独自分析と市場評価のズレが大きい",
    "市場評価とAI評価の乖離が非常に大きい": "独自分析と市場の見方が大きく異なる",
    "市場がAIより大幅に高く評価": "市場の評価が独自分析を大幅に上回っている",
    "展開シミュレーションで不利判定": "独自シミュレーションで展開面が不利と判定",
}


def _clean_reason(reason: str) -> str:
    """理由文からDlogic関連ワードを除去し、仕様準拠の表現に変換"""
    for old, new in _REASON_REWRITE.items():
        if old in reason:
            return new
    # 残りの汎用クリーニング
    return (reason
            .replace("AIエンジン", "独自AI")
            .replace("AI評価", "独自指数")
            .replace("AI", "独自AI")
            .replace("エンジン", "独自ロジック"))


def _clean_reasons(reasons: list[str]) -> list[str]:
    return [_clean_reason(r) for r in reasons]


def _overbought_text(ratio: float) -> str:
    """買われすぎ倍率を自然な表現に変換"""
    if ratio >= 10:
        return "独自分析では人気ほどの裏付けがなく、過剰人気の可能性"
    elif ratio >= 3:
        return f"独自指数では市場の約{ratio:.0f}倍の評価差がある"
    elif ratio >= 2:
        return "市場の期待に対して独自分析の評価が追いついていない"
    return ""


# ---------------------------------------------------------------------------
# ① X投稿: 今日の危険人気馬
# ---------------------------------------------------------------------------
def generate_x_post(results: list[DangerResult], date_display: str, track: str) -> str:
    """X無料投稿文を生成（1頭だけ公開、280文字以内）"""
    if not results:
        return ""

    top = results[0]
    h = top.horse
    level = top.danger_level
    reasons = _clean_reasons(top.main_reasons[:2])
    reason = reasons[0] if reasons else "人気ほどの信頼は置きにくい"

    text = (
        f"【今日の危険人気馬】\n"
        f"{h.horse_name}（{h.track_name}{h.race_number}R）\n"
        f"{h.popularity_rank}番人気 単勝{h.odds_win}倍\n"
        f"危険度{level}\n\n"
        f"{reason}\n\n"
        f"#競馬予想 #危険人気馬"
    )
    return text


# ---------------------------------------------------------------------------
# ② X投稿: 振り返り
# ---------------------------------------------------------------------------
def generate_x_review_post(checked_results: list[dict], date_display: str) -> str:
    """X振り返り投稿 — 昨日の危険人気馬の結果"""
    if not checked_results:
        return ""

    lines = [f"【{date_display}の危険人気馬 結果】\n"]
    hit_count = 0
    for r in checked_results:
        pos = r.get("position", 0)
        level = r["danger_level"]
        if pos == 0:
            result_str = "結果未確定"
        elif pos >= 4:
            result_str = f"{pos}着（馬券外）"
            hit_count += 1
        else:
            result_str = f"{pos}着"

        lines.append(f"{r['horse_name']}（{r['race']}）")
        lines.append(f"危険度{level} → {result_str}\n")

    total = len([r for r in checked_results if r.get("position", 0) > 0])
    if total > 0:
        rate = hit_count / total * 100
        lines.append(f"馬券外率: {hit_count}/{total}（{rate:.0f}%）")

    lines.append("\n#危険人気馬 #AI競馬")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ③ X投稿: 教育コンテンツ（ローテーション）
# ---------------------------------------------------------------------------
_EDUCATION_TEMPLATES = [
    # ① 王道フック
    (
        "今日の1番人気、普通に危ないです。\n\n"
        "理由はシンプルで\n"
        "「前走がハマりすぎ」\n\n"
        "今回同じ形になる可能性は低い。\n\n"
        "人気ほどの信頼は置きにくいので、\n"
        "軸にする人は一度見直した方がいいです。\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ② 恐怖訴求
    (
        "これ、普通に買うとやられます。\n\n"
        "今日の危険人気馬は\n"
        "「能力はあるけど買い時じゃないタイプ」\n\n"
        "こういう馬が一番回収率を壊す。\n\n"
        "当てるより\n"
        "「避ける」が重要な日です\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ③ 気づき系（教育）
    (
        "競馬で負ける人の共通点\n\n"
        "前走1着をそのまま信じる\n\n"
        "でも実際は\n"
        "・展開がハマっただけ\n"
        "・相手が弱かっただけ\n"
        "・馬場が向いただけ\n\n"
        "このズレがあると普通に飛びます\n\n"
        "#競馬予想 #AI競馬"
    ),
    # ④ 限定感
    (
        "今日は3頭だけです。\n\n"
        "その中でも1番危ないのは\n"
        "人気的にも\"買いたくなる位置\"ですが\n"
        "条件と展開がズレてます。\n\n"
        "こういう日は\n"
        "「軸を外すだけ」で結果変わる\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ⑤ 実用系（馬券直結）
    (
        "今日の使い方これです\n\n"
        "軸にする → NG\n"
        "相手まで → OK\n"
        "消し → レース次第\n\n"
        "危険人気馬は\n"
        "「買うかどうか」じゃなくて\n"
        "「どこまで評価を落とすか」\n\n"
        "これで回収率変わります\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ⑥ 比較型（納得させる）
    (
        "この馬、強いのは間違いないです。\n\n"
        "ただ\n"
        "今回は\"強さを出せる条件じゃない\"\n\n"
        "ここを見ないと負けます。\n\n"
        "人気＝正解ではないので\n"
        "条件ズレはちゃんと見た方がいいです\n\n"
        "#競馬予想 #AI競馬"
    ),
    # ⑦ シンプル強フック
    (
        "この人気、ちょっと危険です。\n\n"
        "理由は3つ\n\n"
        "・展開が向きにくい\n"
        "・前走の再現が難しい\n"
        "・オッズ妙味がない\n\n"
        "買うなら一段下げたい\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ⑧ 実績匂わせ
    (
        "最近これでかなり助かってます\n\n"
        "「危険人気馬だけ避ける」\n\n"
        "これやるだけで\n"
        "無駄な負けが減る\n\n"
        "今日は分かりやすい日なので\n"
        "特に注意した方がいいです\n\n"
        "#競馬予想 #危険人気馬"
    ),
    # ⑨ 逆張り訴求
    (
        "みんなが買う馬ほど危ない\n\n"
        "これ競馬あるあるです\n\n"
        "特に\n"
        "前走圧勝 → 次も人気\n\n"
        "この流れは要注意\n\n"
        "今回も1頭います\n"
        "普通に買うと危ないタイプ\n\n"
        "#競馬予想 #AI競馬"
    ),
    # ⑩ クロージング（購入誘導強）
    (
        "今日の危険人気馬まとめました。\n\n"
        "・買いたくなる位置の人気\n"
        "・でも中身はズレてる\n"
        "・だからオッズに見合わない\n\n"
        "このパターンが一番危ないです\n\n"
        "「当てる」より「外す」判断\n"
        "やるだけで変わります\n\n"
        "#競馬予想 #危険人気馬"
    ),
]


def generate_x_education_post(day_index: int = 0) -> str:
    """③ X教育投稿 — テンプレートをローテーション"""
    idx = day_index % len(_EDUCATION_TEMPLATES)
    return _EDUCATION_TEMPLATES[idx]


# ---------------------------------------------------------------------------
# ④ X投稿: 実績レポート
# ---------------------------------------------------------------------------
def generate_x_stats_post(stats: dict) -> str:
    """④ X実績投稿 — 累積成績"""
    total = stats.get("total", 0)
    hit = stats.get("hit", 0)

    if total == 0:
        return (
            "【危険人気馬 独自AI分析 実績】\n\n"
            "データ集計中です\n"
            "今後の実績を随時公開していきます\n\n"
            "#危険人気馬 #AI競馬"
        )

    hit_rate = hit / total * 100

    lines = ["【危険人気馬 独自AI分析 実績】\n"]
    lines.append(f"判定数: {total}頭")
    lines.append(f"馬券外: {hit}頭（{hit_rate:.0f}%）\n")

    by_level = stats.get("by_level", {})
    for level in ["A", "B", "C"]:
        lv = by_level.get(level, {})
        lv_total = lv.get("total", 0)
        lv_hit = lv.get("hit", 0)
        if lv_total > 0:
            lv_rate = lv_hit / lv_total * 100
            lines.append(f"危険度{level}: {lv_hit}/{lv_total}（{lv_rate:.0f}%）")

    lines.append("\n#危険人気馬 #AI競馬")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# note記事: 無料部分（冒頭）
# ---------------------------------------------------------------------------
def generate_note_free(results: list[DangerResult], date_display: str) -> str:
    """note無料部分 — chatGPTリライト版準拠"""
    if not results:
        return ""

    top = results[0]
    h = top.horse
    count = len(results)

    # 今日の傾向を自動判定
    trend = "「前走評価だけで売れすぎているタイプ」が目立つ日"
    types = set(r.danger_type for r in results)
    if all("展開" in t for t in types if t):
        trend = "「展開が向かないのに人気が落ちない」タイプが多い日"
    elif all("条件" in t for t in types if t):
        trend = "「条件替わりを市場が軽視している」タイプが多い日"

    md = f"""# 【{date_display}】買ってはいけない人気馬{count}頭

独自AIが"過剰人気"を検知

## 今日の結論（先に重要な話）

今日の人気馬、普通に買うと危ないかもしれません。

{trend}。

特に注意したいのは、展開が変わるのに人気が落ちない馬。

このタイプは、能力があっても「買い時ではない」ケースが多いです。

今日はその中から、明確に"過剰人気の可能性がある{count}頭"を抽出しています。

今日の中で1頭、「普通に買われるけど構造的に危ない馬」がいます。

---

有料部分では、

- **危険人気馬 全{count}頭**の展開・条件・再現性を具体的に分析
- 各馬の馬券での扱い方（消し/軸NG/相手まで）
- **本日の最重要危険人気馬**——なぜこの馬を軸にしてはいけないのか

を公開しています。

**→ 続きは有料部分で**"""
    return md


# ---------------------------------------------------------------------------
# note記事: 有料部分（本文）
# ---------------------------------------------------------------------------
def generate_note_paid(results: list[DangerResult], date_display: str) -> str:
    """note有料部分 — chatGPTリライト版完全準拠"""
    if not results:
        return ""

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    sections = []

    # 危険人気馬一覧
    sections.append("## 本日の危険人気馬\n")

    # 各馬の解説（ストーリー形式）
    for i, r in enumerate(results):
        h = r.horse
        bd = r.score_breakdown
        medal = medals[i] if i < len(medals) else f"{i+1}位"

        sections.append(f"""{medal}{h.horse_name}（{h.track_name}{h.race_number}R）

想定{h.popularity_rank}番人気 / 単勝{h.odds_win}倍 / 危険度{r.danger_level}（{r.danger_score}点）

**なぜ危険か**

{r.story}

**馬券での扱い方**

{r.betting_note}

{_LEVEL_DESC.get(r.danger_level, "")}。
期待値面では一段評価を下げたい1頭です。
""")

    # 最重要危険人気馬（"殺し"を強く）
    top = results[0]
    sections.append(f"""---

## 🔴本日の最重要危険人気馬

**{top.horse.horse_name}**（{top.horse.track_name}{top.horse.race_number}R）

今回の中で最も"人気で買うリスクが高い1頭"。

能力ではなく「条件」で負ける可能性が高い馬。

前走 → ハマった
今回 → 再現しにくい

このギャップがある状態で{top.horse.popularity_rank}番人気・単勝{top.horse.odds_win}倍。
軸にしてしまうと、馬券全体の回収率を落とす可能性が高い。

この馬を「信じるか、疑うか」で今日の収支が変わります。
""")

    # まとめ
    sections.append(f"""---

## まとめ

今日の危険人気馬に共通しているのは、

「前走評価がそのまま反映されている」こと。

競馬で一番危ないのは、「前走の結果をそのまま信じること」です。

今日はまさにその典型日。

今日は「当てる日」ではなく「外す判断で勝つ日」です。

**今日の使い方**

- 本命にする前に一度疑う
- 軸から外す検討をする
- 相手までに落とす
- 馬券構成を変える

---

毎日、人気の裏にある"市場の歪み"だけを抽出しています。

*本記事は独自AI分析に基づく情報提供です。*
*最終判断はご自身でお願いいたします。*""")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Markdown（内部記録用）
# ---------------------------------------------------------------------------
def generate_danger_markdown(results: list[DangerResult], date_display: str) -> str:
    """危険人気馬ランキングのMarkdown"""
    if not results:
        return "# 危険人気馬\n\n該当馬なし\n"

    lines = [
        f"# 危険人気馬ランキング｜{date_display}\n",
        "| 順位 | 馬名 | レース | 人気 | 単勝 | 危険度 | スコア |",
        "|------|------|--------|------|------|--------|--------|",
    ]

    for i, r in enumerate(results, 1):
        h = r.horse
        lines.append(
            f"| {i}位 | {h.horse_name} | {h.track_name}{h.race_number}R | "
            f"{h.popularity_rank}人気 | {h.odds_win}倍 | {r.danger_level} | "
            f"{r.danger_score}点 |"
        )

    lines.append("")
    for i, r in enumerate(results, 1):
        h = r.horse
        reasons = _clean_reasons(r.main_reasons[:3])
        lines.append(f"**{i}位 {h.horse_name}**（{r.danger_level}・{r.danger_score}点）")
        for reason in reasons:
            lines.append(f"  - {reason}")
        lines.append(f"  → {_BETTING_NOTE.get(r.danger_level, '')}\n")

    return "\n".join(lines)
