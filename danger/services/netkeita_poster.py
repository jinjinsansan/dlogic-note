"""netkeita API への記事自動投稿サービス (わい予想家).

送信する記事は `content_type="prediction"` 固定 — 予想家ページ
(`/tipsters/{id}`) は prediction しか拾わないため、article 扱いで
投げると tipster 一覧に出ない。

環境変数:
    NETKEITA_API_URL     netkeita API のベース URL (既定: https://bot.dlogicai.in/nk)
    NETKEITA_API_KEY     POST /api/articles 用の X-Internal-Key
    NETKEITA_TIPSTER_ID  わい (管理者) の line_user_id
"""
import logging
import os
import re
import unicodedata

import requests

logger = logging.getLogger(__name__)

NETKEITA_API_URL = os.getenv("NETKEITA_API_URL", "https://bot.dlogicai.in/nk")
NETKEITA_API_KEY = os.getenv("NETKEITA_API_KEY", "")
NETKEITA_TIPSTER_ID = os.getenv("NETKEITA_TIPSTER_ID", "")


def _make_slug(title: str, date: str) -> str:
    """記事タイトルと日付から slug を生成 (半角英数のみ残す)"""
    short = unicodedata.normalize("NFKC", title)
    short = re.sub(r"[^\w\s-]", "", short, flags=re.UNICODE)
    short = re.sub(r"[\s_]+", "-", short).strip("-").lower()
    # 日本語を除去した後は殆ど空になりがちなので "wai-danger-{date}" を base に
    short = short[:30] if short else ""
    return f"wai-danger-{date}-{short}".rstrip("-")


def post_to_netkeita(
    title: str,
    body: str,
    date: str,
    description: str = "",
    is_premium: bool = False,
    preview_body: str = "",
    race_id: str = "",
) -> dict:
    """netkeita に予想記事を投稿する。

    Args:
        title:         記事タイトル
        body:          Markdown 本文
        date:          YYYYMMDD (slug 生成に使用)
        description:   記事概要 (一覧カード用)
        is_premium:    有料記事フラグ (わいは基本 False)
        preview_body:  無料プレビュー本文 (OGP・プレミア記事の teaser)
        race_id:       関連レース ID (例: "20260417-川崎-10")。
                       複数レースをまとめた記事なら代表的な 1 レースを指定。

    Returns:
        {"status": "ok", "slug": "..."} | {"status": "error", "message": "..."}
    """
    if not NETKEITA_API_KEY:
        return {"status": "error", "message": "NETKEITA_API_KEY が未設定です"}
    if not NETKEITA_TIPSTER_ID:
        return {"status": "error", "message": "NETKEITA_TIPSTER_ID が未設定です"}

    slug = _make_slug(title, date)

    payload = {
        "title": title,
        "body": body,
        "description": description or title,
        "status": "published",
        # 予想家ページ (/tipsters/{id}) は content_type=="prediction" のみ拾う
        "content_type": "prediction",
        "tipster_id": NETKEITA_TIPSTER_ID,
        "race_id": race_id,
        "bet_method": "",
        "ticket_count": 0,
        "preview_body": preview_body,
        "is_premium": is_premium,
        "slug": slug,
    }

    headers = {
        "X-Internal-Key": NETKEITA_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{NETKEITA_API_URL}/api/articles",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            # netkeita API は admin_view() の戻り値 (フラット dict) を返す
            data = resp.json()
            article_slug = data.get("slug", slug)
            logger.info(f"netkeita投稿成功: /articles/{article_slug}")
            return {"status": "ok", "slug": article_slug}
        else:
            msg = f"HTTP {resp.status_code}: {resp.text[:300]}"
            logger.warning(f"netkeita投稿失敗: {msg}")
            return {"status": "error", "message": msg}
    except Exception as e:
        logger.error(f"netkeita投稿例外: {e}")
        return {"status": "error", "message": str(e)}
