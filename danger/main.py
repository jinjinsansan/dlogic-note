"""
AI危険人気馬BOT — CLIエントリポイント

Usage:
    python -m danger.main                    # 今日のレース
    python -m danger.main --date 20260313    # 指定日
    python -m danger.main --type jra         # JRA
"""
from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import os
import logging
import hashlib
from datetime import datetime

from .adapters.dlogic_adapter import fetch_all_horses
from .services.danger_service import find_danger_horses
from .services.article_service import (
    generate_x_post,
    generate_note_free,
    generate_note_paid,
    generate_danger_markdown,
)
from .services.x_poster import post_to_x
from .services.note_poster import post_to_note
from .services.netkeita_poster import post_to_netkeita

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _state_path(output_dir: str) -> str:
    return os.path.join(output_dir, "post_state.json")


def _load_post_state(output_dir: str) -> dict:
    path = _state_path(output_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_post_state(output_dir: str, state: dict) -> None:
    path = _state_path(output_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(date: str, race_type: str = "nar", force_post: bool = False):
    """メイン処理"""
    logger.info(f"=== 危険人気馬BOT開始: {date} ({race_type}) ===")

    # 日付表示
    try:
        dt = datetime.strptime(date, "%Y%m%d")
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        date_display = f"{dt.year}年{dt.month}月{dt.day}日({weekday_names[dt.weekday()]})"
    except ValueError:
        date_display = date

    # Step 1: 全馬データ取得
    logger.info("Step 1: 全馬データ取得")
    all_horses = fetch_all_horses(date, race_type)
    logger.info(f"  → {len(all_horses)} 頭取得")

    if not all_horses:
        logger.warning("データなし。終了。")
        return

    # Step 2: 危険人気馬判定
    logger.info("Step 2: 危険人気馬判定")
    danger_results = find_danger_horses(all_horses, top_n=3)
    logger.info(f"  → {len(danger_results)} 頭抽出")

    if not danger_results:
        logger.warning("危険人気馬なし。終了。")
        return

    for i, r in enumerate(danger_results, 1):
        h = r.horse
        logger.info(
            f"  {i}位: {h.horse_name}（{h.track_name}{h.race_number}R）"
            f" オッズ{h.odds_win} AI{round(h.ai_win_prob*100,1)}%"
            f" 市場{round(h.market_prob*100,1)}%"
            f" 歪み{round(h.distortion_diff*100,1)}pt"
            f" [{r.danger_level}]"
        )

    # Step 3: 出力生成
    logger.info("Step 3: 出力生成")
    track = danger_results[0].horse.track_name

    x_post = generate_x_post(danger_results, date_display, track)
    note_free = generate_note_free(danger_results, date_display)
    note_paid = generate_note_paid(danger_results, date_display)
    danger_md = generate_danger_markdown(danger_results, date_display)

    # JSON
    danger_json = []
    for i, r in enumerate(danger_results, 1):
        d = r.to_dict()
        d["rank"] = i
        danger_json.append(d)

    # Step 4: 保存
    logger.info("Step 4: 保存")
    output_dir = os.path.join("output", "danger", f"{date}_{race_type}")
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "danger_rank.json"), "w", encoding="utf-8") as f:
        json.dump(danger_json, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "danger_rank.md"), "w", encoding="utf-8") as f:
        f.write(danger_md)

    with open(os.path.join(output_dir, "x_post.txt"), "w", encoding="utf-8") as f:
        f.write(x_post)

    with open(os.path.join(output_dir, "note_free.md"), "w", encoding="utf-8") as f:
        f.write(note_free)

    with open(os.path.join(output_dir, "note_paid.md"), "w", encoding="utf-8") as f:
        f.write(note_paid)

    logger.info(f"  出力先: {output_dir}")

    # Step 5: X自動投稿
    logger.info("Step 5: X自動投稿")
    state = _load_post_state(output_dir)
    x_hash = _hash_text(x_post) if x_post else ""
    if x_post and (not force_post and state.get("x_posted") and state.get("x_hash") == x_hash):
        logger.info("  ↳ X投稿は既に実施済みのためスキップ")
    elif x_post:
        x_result = post_to_x(x_post)
        if x_result["status"] == "ok":
            tweet_id = x_result.get("tweet_id", "")
            state.update({
                "x_posted": True,
                "x_hash": x_hash,
                "x_tweet_id": tweet_id,
                "x_posted_at": datetime.now().isoformat(),
            })
            logger.info(f"  ✓ X投稿成功: https://x.com/i/status/{tweet_id}")
        else:
            logger.warning(f"  ✗ X投稿失敗: {x_result['message']}")
    else:
        logger.warning("  ✗ X投稿文が空のためスキップ")

    # Step 6: note無料記事投稿
    logger.info("Step 6: note無料記事投稿")
    note_title = f"【{date_display}】買ってはいけない人気馬{len(danger_results)}頭｜独自AIが過剰人気を検知"
    note_hash = _hash_text(note_title + note_free + note_paid)
    if not force_post and state.get("note_posted") and state.get("note_hash") == note_hash:
        logger.info("  ↳ note投稿は既に実施済みのためスキップ")
    else:
        note_result = post_to_note(
            title=note_title,
            body_md=note_free + "\n\n" + note_paid,
            price=0,
        )
        if note_result["status"] == "ok":
            state.update({
                "note_posted": True,
                "note_hash": note_hash,
                "note_url": note_result.get("url", ""),
                "note_posted_at": datetime.now().isoformat(),
            })
            logger.info(f"  ✓ note投稿成功: {note_result.get('url', '')}")
        else:
            logger.warning(f"  ✗ note投稿失敗: {note_result['message']}")

    # Step 7: netkeita 自動投稿
    logger.info("Step 7: netkeita投稿")
    nk_hash = _hash_text(note_title + note_free + note_paid)
    if not force_post and state.get("netkeita_posted") and state.get("netkeita_hash") == nk_hash:
        logger.info("  ↳ netkeita投稿は既に実施済みのためスキップ")
    else:
        # プレビュー本文: note_free の最初の200文字
        preview = (note_free[:200].rstrip() + "…") if len(note_free) > 200 else note_free
        # 代表レース ID: 最上位 (危険度が最も高い) の危険人気馬が出走するレース
        representative_race_id = danger_results[0].horse.race_id if danger_results else ""
        nk_result = post_to_netkeita(
            title=note_title,
            body=note_free + "\n\n" + note_paid,
            date=date,
            description=f"AI独自分析による危険人気馬予想 — {date_display}",
            is_premium=False,
            preview_body=preview,
            race_id=representative_race_id,
        )
        if nk_result["status"] == "ok":
            state.update({
                "netkeita_posted": True,
                "netkeita_hash": nk_hash,
                "netkeita_slug": nk_result.get("slug", ""),
                "netkeita_posted_at": datetime.now().isoformat(),
            })
            logger.info(f"  ✓ netkeita投稿成功: /articles/{nk_result.get('slug', '')}")
        else:
            logger.warning(f"  ✗ netkeita投稿失敗: {nk_result['message']}")

    _save_post_state(output_dir, state)

    logger.info("=== 完了 ===")

    return output_dir


def auto_race_type(date_str: str) -> str:
    """曜日から自動判定: 土日=JRA、平日=NAR"""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return "jra" if dt.weekday() >= 5 else "nar"  # 5=土, 6=日
    except ValueError:
        return "nar"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI危険人気馬BOT")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="対象日 (YYYYMMDD)")
    parser.add_argument("--type", default=None, choices=["jra", "nar"], help="レースタイプ (省略時: 土日=jra, 平日=nar)")
    parser.add_argument("--force-post", action="store_true", help="既投稿でも再投稿する")
    args = parser.parse_args()

    race_type = args.type or auto_race_type(args.date)
    run(args.date, race_type, force_post=args.force_post)
