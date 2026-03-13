"""note記事素材・X投稿文の生成"""
from ..models.danger_result import DangerResult


def generate_x_post(results: list[DangerResult], date_display: str, track: str) -> str:
    """X投稿文を生成"""
    if not results:
        return ""

    top = results[0]
    h = top.horse
    mp = top.market_prob_pct
    ap = top.ai_win_prob_pct
    ob = round(h.overbought_ratio, 1)

    text = (
        f"【今日の危険人気馬】\n"
        f"{h.horse_name}（{h.track_name}{h.race_number}R）\n\n"
        f"単勝{h.odds_win}倍\n"
        f"市場評価{mp}%\n"
        f"AI評価{ap}%\n\n"
        f"市場は約{ob}倍買いすぎ。\n"
        f"人気の割にAI評価が追いついていない。\n\n"
        f"#競馬予想 #AI競馬 #危険人気馬"
    )
    return text


def generate_note_free(results: list[DangerResult], date_display: str) -> str:
    """note無料部分を生成"""
    if not results:
        return ""

    top = results[0]
    h = top.horse
    mp = top.market_prob_pct
    ap = top.ai_win_prob_pct
    ob = round(h.overbought_ratio, 1)

    md = f"""# 【{date_display}】今日の危険人気馬

**{h.horse_name}**（{h.track_name}{h.race_number}R）

- 市場オッズ：**{h.odds_win}倍**
- 市場勝率：**{mp}%**
- AI勝率：**{ap}%**
- → **市場は約{ob}倍買いすぎ**

市場は強く支持していますが、歪みAIはこの人気ほどの信頼性を認めていません。
人気先行の可能性があるため、過信は危険です。

---

有料部分では、

- **危険人気馬TOP3**の詳しい危険理由
- 逆に妙味がある相手候補
- 厳選レースの買い方

を公開します。

**→ 続きは有料部分で**"""
    return md


def generate_note_paid(results: list[DangerResult], date_display: str) -> str:
    """note有料部分を生成"""
    if not results:
        return ""

    sections = [f"## 危険人気馬TOP{len(results)}"]

    for i, r in enumerate(results, 1):
        h = r.horse
        mp = r.market_prob_pct
        ap = r.ai_win_prob_pct
        diff = r.distortion_diff_pct
        ob = round(h.overbought_ratio, 1)
        conf = r.confidence_pct
        fair = round(h.fair_odds, 1)

        section = f"""
### {i}位 {h.horse_name}（{h.track_name}{h.race_number}R・{h.horse_number}番）

- レース：{h.race_name}
- 単勝オッズ：**{h.odds_win}倍**
- 市場勝率：**{mp}%** → AI勝率：**{ap}%** → **差{diff}pt（市場は{ob}倍買いすぎ）**
- フェアオッズ：{fair}倍
- AI信頼度：{conf:.0f}%
- 判定：**{r.danger_level}**

**なぜ危険か**

{r.reason_summary}"""
        sections.append(section)

    # 結論
    top = results[0]
    sections.append(f"""
---

## 結論

本日もっとも危険なのは **{top.horse.horse_name}**。
市場人気の割にAI評価が明らかに追いついておらず、
期待値の観点では買いづらい人気馬です。

---

*この記事は歪みAIの分析データに基づいて作成されています。*
*投資は自己責任でお願いいたします。*""")

    return "\n".join(sections)


def generate_danger_markdown(results: list[DangerResult], date_display: str) -> str:
    """危険人気馬ランキングのMarkdown"""
    if not results:
        return "# 危険人気馬\n\n該当馬なし\n"

    lines = [
        f"# 危険人気馬ランキング｜{date_display}\n",
        "| 順位 | 馬名 | レース | 単勝 | 市場勝率 | AI勝率 | 歪み | 買われすぎ | 判定 |",
        "|------|------|--------|------|---------|--------|------|----------|------|",
    ]

    for i, r in enumerate(results, 1):
        h = r.horse
        lines.append(
            f"| {i}位 | {h.horse_name} | {h.track_name}{h.race_number}R | "
            f"{h.odds_win}倍 | {r.market_prob_pct}% | {r.ai_win_prob_pct}% | "
            f"{r.distortion_diff_pct}pt | {round(h.overbought_ratio, 1)}倍 | "
            f"{r.danger_level} |"
        )

    lines.append("")
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}位 {r.horse.horse_name}**：{r.reason_summary}\n")

    return "\n".join(lines)
