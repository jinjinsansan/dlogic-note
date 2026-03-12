# dlogic-note

D-Logic AI × note 自動記事生成システム

VPS上のD-Logic予想エンジンAPIを活用し、毎日の競馬予想をnote有料記事として半自動生成する。

## アーキテクチャ
```
cron (毎朝)
  → fetch_races.py      レースデータ取得
  → analyze_races.py    D-Logic AI解析 + 市場歪み計算
  → generate_article.py Claude APIで記事生成
  → output/YYYYMMDD/    Markdown + HTML + X告知文
```

## API依存先
- VPS `https://bot.dlogicai.in/api/v2/predictions/newspaper` — 4エンジン予想
- VPS `https://bot.dlogicai.in/api/v2/predictions/imlogic` — IMLogic予想
- VPS `https://bot.dlogicai.in/api/v2/analysis/*` — 展開/騎手/血統/近走分析
