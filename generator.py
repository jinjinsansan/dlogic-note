"""
記事生成パイプライン — Claude APIでnote記事を生成
"""
import json
import os
from datetime import datetime
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, OUTPUT_DIR


client = Anthropic(api_key=ANTHROPIC_API_KEY)


ARTICLE_SYSTEM_PROMPT = """あなたは競馬予想の有料note記事を書くプロライターです。
D-Logic AIの分析データを元に、読者が「買ってよかった」と思える記事を書いてください。

## 記事構成ルール
1. 無料部分: 今日の開催概要、厳選レース紹介（レース名のみ）、的中実績
2. 有料部分: 各レースの詳細分析、AI期待値ランキング、危険人気馬、推奨買い目
3. 文体: 「です/ます」調、データに基づく冷静な分析、しかし読みやすく
4. 数字は具体的に（「AIスコア82.4」「勝率23%」など）
5. 各レースに「ひとこと展開予想」を必ず入れる
6. 危険人気馬には理由を明記する

## 禁止事項
- 「絶対」「確実」「必勝」などの断定表現
- 射幸心を煽る表現
- 的中を保証する表現
"""


def generate_note_article(
    date: str,
    race_analyses: list[dict],
    featured_races: list[dict],
    danger_horses: list[dict],
    value_horses: list[dict],
    race_type: str = "jra",
) -> dict:
    """
    note記事を生成

    Returns:
        {
            "markdown": str,  # 記事本文（Markdown）
            "free_section": str,  # 無料部分
            "paid_section": str,  # 有料部分
            "x_post": str,  # X告知文
        }
    """
    type_label = "中央競馬(JRA)" if race_type == "jra" else "地方競馬"

    # データをClaude用にまとめる
    data_summary = {
        "date": date,
        "race_type": type_label,
        "total_races": len(race_analyses),
        "featured_races": featured_races,
        "danger_horses": danger_horses,
        "value_horses": value_horses,
    }

    data_json = json.dumps(data_summary, ensure_ascii=False, indent=2)

    # Step 1: 無料部分を生成
    free_prompt = f"""以下のデータを元に、note記事の**無料部分**をMarkdownで書いてください。

## データ
```json
{data_json}
```

## 無料部分に含めるもの
- 本日の開催概要（{type_label}、レース数）
- 厳選レース名の紹介（詳細分析は有料部分で）
- D-Logic AIエンジンの簡単な紹介
- 注目ポイント（具体的な馬名は1-2頭だけチラ見せ）
- 最後に「続きは有料部分で →」で締める

Markdownのみ出力してください。JSON不要。"""

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

## 有料部分に含めるもの
- 厳選レースごとの詳細分析（AIスコア、勝率、適正オッズ）
- 各レースの「ひとこと展開予想」
- AI期待値馬ランキング（上位5頭、スコアとオッズ付き）
- 危険人気馬（AIスコアが低いのに人気の馬、理由付き）
- 各レースの推奨買い目（3連複・ワイド・単勝など）

Markdownのみ出力してください。JSON不要。"""

    paid_resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=8192,
        system=ARTICLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": paid_prompt}],
    )
    paid_section = paid_resp.content[0].text.strip()

    # Step 3: X告知文を生成
    x_prompt = f"""以下のデータを元に、X（Twitter）告知文を1つ書いてください。140字以内。

{type_label} {date}
厳選{len(featured_races)}レース、AI期待値馬{len(value_horses)}頭を公開中。

テキストのみ出力。ハッシュタグ2-3個付き。"""

    x_resp = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=256,
        system="競馬予想noteの告知ツイートを書くコピーライター。簡潔で引きのある文を書く。",
        messages=[{"role": "user", "content": x_prompt}],
    )
    x_post = x_resp.content[0].text.strip()

    result = {
        "free_section": free_section,
        "paid_section": paid_section,
        "x_post": x_post,
    }

    # 完全なMarkdownを組み立て
    markdown = f"""# 【D-Logic AI】{date} {type_label}予想

{result.get('free_section', '')}

---
**▼ ここから有料部分 ▼**
---

{result.get('paid_section', '')}

---
*この記事はD-Logic AIの分析データに基づいて作成されています。*
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
