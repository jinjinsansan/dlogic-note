"""
記事生成パイプライン — Claude APIでnote記事を生成
「市場歪み」を軸にした売れる記事構成
"""
import json
import os
from datetime import datetime
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, OUTPUT_DIR


client = Anthropic(api_key=ANTHROPIC_API_KEY)


ARTICLE_SYSTEM_PROMPT = """あなたは競馬予想の有料note記事を書くプロライターです。
歪みAIの分析データを元に、読者が「買ってよかった」と思える記事を書いてください。

## コンセプト
この記事の最大の売りは「市場歪みAI」です。
AIが算出した勝率と、市場オッズから逆算した勝率のズレ（歪み）を見せることで、
「この馬は買いすぎ」「この馬は見逃されている」を明確にします。
記事は「読み物」ではなく「武器」。短く、数字で殴る。

## 文体ルール
- 「です/ます」調、データに基づく冷静な分析
- 短い文で読みやすく。1段落は2行まで。長い説明は不要
- 数字を最大限強調する。例：「AI勝率14.3% → 市場評価1.8% → **歪み+12.5%**（市場は8倍も過小評価）」
- 歪みは%だけでなく「市場はX倍過小評価」「市場はX倍買いすぎ」のような倍率表現も併用する
- 展開予想は2行以内。簡潔に
- 各馬の説明も2-3行で十分

## 禁止事項
- 「絶対」「確実」「必勝」などの断定表現
- 「確度」という表現（代わりに「信頼度」を使用）
- 射幸心を煽る表現
- 的中を保証する表現
- 的中率・回収率などの実績数値を捏造すること（データにない数字は書かない）
- AIスコア0の馬を「分析対象外」と表現すること（代わりに「AI未評価」と表現）
- レースを5つ以上取り上げること（2-3レースに厳選）
- 「D-Logic」「dLogic」「iLogic」「I-Logic」「MetaLogic」「ViewLogic」などのエンジン名を出すこと（これらは内部名称であり、読者に見せてはならない）
- 代わりに「歪みAI」「AI」「複数エンジン」「複数の分析モデル」などの一般的な表現を使う
- 三連複で同じ馬番を2回使うこと（三連複は異なる3頭の組み合わせ）
- 「本来の実力はX倍が妥当」のような根拠のない断定。代わりに「AI勝率○○%から見たフェアオッズは約○○倍」と数式準拠で書く
- フェアオッズは 1 ÷ AI勝率 で計算する（例：AI勝率12.3% → フェアオッズ約8.1倍）

## 歪み表現の統一ルール
歪みは常に以下の2つをセットで書く：
- **差（pt）**: AI勝率 − 市場勝率（例：+13.3pt）
- **倍率**: AI勝率 ÷ 市場勝率（例：市場は14.3倍見落とし）
この2つ以外の表現は使わない。「歪み+2.2倍」のような混在表現は禁止。
"""


def generate_note_article(
    date: str,
    race_analyses: list[dict],
    featured_races: list[dict],
    danger_horses: list[dict],
    value_horses: list[dict],
    race_type: str = "jra",
    distortion_ranking: list[dict] = None,
    danger_ranking: list[dict] = None,
) -> dict:
    """
    note記事を生成（市場歪み中心の構成）

    Returns:
        {
            "markdown": str,  # 記事本文（Markdown）
            "free_section": str,  # 無料部分
            "paid_section": str,  # 有料部分
            "x_post": str,  # X告知文
        }
    """
    type_label = "中央競馬(JRA)" if race_type == "jra" else "地方競馬"

    # 日付フォーマット: "20260313" → "2026年3月13日(金)"
    try:
        dt = datetime.strptime(date, "%Y%m%d")
        date_display = f"{dt.year}年{dt.month}月{dt.day}日"
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        date_display += f"({weekday_names[dt.weekday()]})"
    except ValueError:
        date_display = date

    # 開催会場一覧を抽出
    venues = sorted(set(r.get("venue", "") for r in race_analyses if r.get("venue")))
    venues_label = "・".join(venues) if venues else type_label

    # 歪みデータを整形
    distortion_ranking = distortion_ranking or []
    danger_ranking = danger_ranking or []

    # 本命期待値馬（市場オッズ10倍以下で歪みが+の馬）を抽出
    honmei_candidates = [
        d for d in (distortion_ranking or [])
        if d.get("market_odds", 999) <= 10 and d.get("distortion", 0) > 0
    ]

    # データをClaude用にまとめる
    data_summary = {
        "date": date_display,
        "race_type": type_label,
        "venues": venues,
        "total_races_analyzed": len(race_analyses),
        "featured_races": featured_races,
        "distortion_ranking_top5": distortion_ranking,
        "honmei_value_horses": honmei_candidates[:3],
        "danger_ranking_top3": danger_ranking,
        "danger_horses": danger_horses,
        "value_horses": value_horses[:5],
    }

    data_json = json.dumps(data_summary, ensure_ascii=False, indent=2)
    # エンジン名を内部名称からジェネリック名に置換（記事に漏れないように）
    for engine_name in ["D-Logic", "dLogic", "d-Logic", "I-Logic", "iLogic", "MetaLogic", "ViewLogic"]:
        data_json = data_json.replace(engine_name, "AI分析")

    # タイトル生成用の情報
    top_danger_name = danger_ranking[0]["name"] if danger_ranking else "?"
    num_featured = len(featured_races)

    # AI一点の馬を事前決定（歪みランキング1位。歪み馬と同じなら2位）
    top_distortion = distortion_ranking[0] if distortion_ranking else None
    if len(distortion_ranking) >= 2:
        ai_itten_horse = distortion_ranking[1]  # 歪み馬(1位)と被らないよう2位
    elif top_distortion:
        ai_itten_horse = top_distortion
    else:
        ai_itten_horse = None

    ai_itten_info = ""
    if ai_itten_horse:
        ai_itten_info = (
            f"馬名: {ai_itten_horse['name']}, "
            f"レース: {ai_itten_horse.get('race_name', '')}, "
            f"馬番: {ai_itten_horse.get('horse_number', '')}, "
            f"AI勝率: {ai_itten_horse.get('ai_prob', 0)}%, "
            f"市場勝率: {ai_itten_horse.get('market_prob', 0)}%, "
            f"歪み: {ai_itten_horse.get('distortion', 0)}pt, "
            f"市場オッズ: {ai_itten_horse.get('market_odds', 0)}倍, "
            f"フェアオッズ: {ai_itten_horse.get('fair_odds', 0)}倍"
        )

    # Step 1: 無料部分を生成
    free_prompt = f"""以下のデータを元に、note記事の**無料部分**をMarkdownで書いてください。

## データ
```json
{data_json}
```

## 記事タイトル（H1）
尖ったタイトルを付けてください。例：
- 「【歪みAI】市場が完全に見落とした馬2頭｜{date_display}」
- 「【AI競馬】市場が買いすぎた危険人気馬{len(danger_ranking)}頭｜{venues_label}」
データの内容に合った刺さるタイトルを考えてください。

## 無料部分の構成（この順序で。全体で短く）

1. **今日の歪みAI注目馬**（最初に1頭ドンと出す）
   - distortion_ranking_top5の1位の馬を具体的に出す
   - こう書く：
     馬名
     AI勝率 ○○%
     市場評価 ○○%
     → **歪み+○○%**（市場はX倍も過小評価）
   - 1-2行で「なぜこの馬が見逃されているか」

2. **今日のAI一点**（無料で見せる！購入フックになる）
   - **この馬を使うこと（変更禁止）**: {ai_itten_info}
   - 馬名、レース名、AI勝率、歪みだけ。短く
   - 「この馬の詳細分析と買い目は有料部分で」と誘導

3. **今日の危険人気馬**（1頭だけチラ見せ）
   - danger_ranking_top3の1位を出す
   - 馬名、市場オッズ、AI勝率だけ。短く

4. **有料部分の予告**（箇条書き3-4行）
   - 歪みAI指数ランキングTOP5
   - 危険人気馬TOP3の徹底分析
   - 厳選{num_featured}レースの買い目

5. 「**続きは有料部分で →**」

## 重要な指示
- 日付は「{date_display}」
- 的中率・回収率は絶対に書かない
- 無料部分は短く。出しすぎない
- 歪みは「+○○%」に加えて「市場はX倍過小評価」の倍率表現を必ず入れる
- 全体で500字程度に収める

Markdownのみ出力してください。"""

    free_resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=2048,
        system=ARTICLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": free_prompt}],
    )
    free_section = free_resp.content[0].text.strip()

    # Step 2: 有料部分を生成
    paid_prompt = f"""以下のデータを元に、note記事の**有料部分**をMarkdownで書いてください。

## データ
```json
{data_json}
```

## 有料部分の構成（この順序で。全体で簡潔に）
※H1タイトルは不要（無料部分に既にあるため）。H2から始めること。

### 1. 歪みAI指数ランキングTOP5
表形式で一目瞭然に：

| 順位 | 馬名 | レース | AI勝率 | 市場勝率 | 歪み | 倍率 | 判定 |
（distortion_ranking_top5のデータを使用）
- 歪みが+なら「過小評価🟢」、-なら「過大評価🔴」
- 「倍率」列にはAI勝率÷市場勝率の倍率を書く（例：「12倍過小評価」「3倍買われすぎ」）
- 本命（市場オッズ10倍以下）と穴（10倍超）が混在するように意識する

表の後に1行だけコメント。長い説明不要。

### 2. 危険人気馬TOP3
各馬2-3行で簡潔に：
- 馬名、レース、市場オッズ → AI勝率 → 歪み
- **なぜ危険か**を1行で（「エンジン未評価」「歪み-21%」など数字で）
- 長い解説は不要。数字が語る

### 3. 歪みレース詳細（{num_featured}レースのみ）
各レース：
- **展開予想**（2行以内。簡潔に）
- AI期待値馬ランキング表（上位3-4頭）
- 注目馬のコメント（各馬1-2行。数字中心）
- **推奨買い目**（単勝・ワイド・3連複、金額目安付き。三連複は必ず異なる3頭で構成すること）

### 4. 今日のAI一点（詳細版）
**この馬を使うこと（変更禁止）**: {ai_itten_info}
  **[馬名]（[レース名]・[馬番]番）**
  AI勝率 ○○% → 市場勝率 ○○% → **差+○○pt（市場はX倍見落とし）**
  フェアオッズ：約○○倍（= 1÷AI勝率）vs 市場オッズ○○倍
  なぜこの馬が一点なのか（2-3行で。エンジン評価の一致度、信頼度など）
  この馬を含む推奨買い目

## 重要な指示
- 日付は「{date_display}」
- 「AI勝率 vs 市場勝率 = 歪み」の対比を常に見せる
- 歪みは%に加えて「市場はX倍過小評価」の倍率表現を必ず入れる
- 的中率・回収率は絶対に書かない
- 「確度」禁止。「信頼度」を使う
- レースは{num_featured}つだけ
- 文章は短く。1段落2行まで。数字で殴る
- 各馬の説明は2-3行で十分。冗長な解説は削る

Markdownのみ出力してください。"""

    paid_resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=8192,
        system=ARTICLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": paid_prompt}],
    )
    paid_section = paid_resp.content[0].text.strip()

    # Step 3: X告知文を生成
    # トップ歪み馬の情報
    top_distortion_name = distortion_ranking[0]["name"] if distortion_ranking else "?"
    top_distortion_pct = distortion_ranking[0].get("distortion", 0) if distortion_ranking else 0

    x_prompt = f"""以下のデータを元に、X（Twitter）告知文を1つ書いてください。140字以内。

{date_display} {type_label}（{venues_label}）

使える素材:
- 歪みAI指数で{top_distortion_name}が+{top_distortion_pct}%の過小評価
- 危険人気馬{top_danger_name}（オッズと実力の乖離）
- 厳選{num_featured}レース分析

「歪みAI指数」「市場が見落とした」「買われすぎ」などのフックを使う。
テキストのみ出力。ハッシュタグ2-3個付き。"""

    x_resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=256,
        system="競馬予想noteの告知ツイートを書くコピーライター。「市場の歪み」「危険人気馬」をフックに使う。簡潔で引きのある文を書く。",
        messages=[{"role": "user", "content": x_prompt}],
    )
    x_post = x_resp.content[0].text.strip()

    result = {
        "free_section": free_section,
        "paid_section": paid_section,
        "x_post": x_post,
    }

    # 完全なMarkdownを組み立て
    markdown = f"""{result.get('free_section', '')}

---
**▼ ここから有料部分 ▼**
---

{result.get('paid_section', '')}

---
*この記事は歪みAIの分析データに基づいて作成されています。*
*投資は自己責任でお願いいたします。*
"""

    result["markdown"] = markdown
    return result


def save_output(date: str, article: dict, race_data: list[dict], race_type: str = "jra"):
    """出力ファイルを保存"""
    date_dir = os.path.join(OUTPUT_DIR, f"note_drafts/{date}_{race_type}")
    os.makedirs(date_dir, exist_ok=True)

    # Markdown記事
    with open(os.path.join(date_dir, "main_note.md"), "w", encoding="utf-8") as f:
        f.write(article["markdown"])

    # 無料部分のみ
    with open(os.path.join(date_dir, "free_section.md"), "w", encoding="utf-8") as f:
        f.write(article.get("free_section", ""))

    # 有料部分のみ
    with open(os.path.join(date_dir, "paid_section.md"), "w", encoding="utf-8") as f:
        f.write(article.get("paid_section", ""))

    # X告知文
    with open(os.path.join(date_dir, "x_post.txt"), "w", encoding="utf-8") as f:
        f.write(article.get("x_post", ""))

    # 分析データJSON
    with open(os.path.join(date_dir, "race_data.json"), "w", encoding="utf-8") as f:
        json.dump(race_data, f, ensure_ascii=False, indent=2)

    # サマリー
    summary = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "total_races": len(race_data),
        "files": ["main_note.md", "free_section.md", "paid_section.md", "x_post.txt", "race_data.json"],
    }
    with open(os.path.join(date_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return date_dir
